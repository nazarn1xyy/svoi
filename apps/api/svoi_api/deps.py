"""Request dependencies: auth, current user, admin, DB session, Redis, queue (B0.1)."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, Header, Request
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from svoi_contracts.enums import UserStatus
from svoi_contracts.errors import ErrorCode

from svoi_api.clients import Clients
from svoi_api.config import Settings
from svoi_api.core import time
from svoi_api.core.errors import DomainError, Unauthorized
from svoi_api.core.queue import Queue
from svoi_api.db.models import User, UserActivityDay

ACTIVE_TOUCH = timedelta(minutes=1)


@dataclass
class Ctx:
    """Everything a service needs for one request."""

    session: AsyncSession
    redis: Redis
    queue: Queue
    settings: Settings
    clients: Clients


async def _session(request: Request) -> AsyncIterator[AsyncSession]:
    maker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with maker() as session:
        yield session


async def get_ctx(request: Request, session: Annotated[AsyncSession, Depends(_session)]) -> Ctx:
    """Shared request context."""
    state = request.app.state
    return Ctx(session, state.redis, state.queue, state.settings, state.clients)


CtxDep = Annotated[Ctx, Depends(get_ctx)]


def check_token(request: Request, authorization: Annotated[str | None, Header()] = None) -> None:
    """Authorization: Bearer <INTERNAL_API_TOKEN>, else 401."""
    settings: Settings = request.app.state.settings
    if authorization != f"Bearer {settings.internal_api_token}":
        raise Unauthorized


def tg_id_header(
    x_tg_user_id: Annotated[int | None, Header(alias="X-Tg-User-Id")] = None,
) -> int:
    """The acting user's Telegram id."""
    if x_tg_user_id is None:
        raise DomainError(ErrorCode.validation_error, message="X-Tg-User-Id is required")
    return x_tg_user_id


TgId = Annotated[int, Depends(tg_id_header)]


async def _touch(ctx: Ctx, user: User) -> None:
    """last_active_at at most once a minute, plus the Kyiv activity day (S10b)."""
    now = time.now()
    if now - user.last_active_at < ACTIVE_TOUCH:
        return
    user.last_active_at = now
    await ctx.session.execute(
        insert(UserActivityDay)
        .values(user_id=user.id, day=time.kyiv_today())
        .on_conflict_do_nothing()
    )
    await ctx.session.commit()


async def _lift_expired_ban(ctx: Ctx, user: User) -> None:
    if user.status is not UserStatus.banned or user.banned_until is None:
        return
    if user.banned_until > time.now():
        return
    from svoi_api.domains.notifications import service as notifications  # noqa: PLC0415 - cycle

    user.status, user.banned_until = UserStatus.active, None
    await notifications.moderation_result(ctx, user, "unbanned", key=f"unban:{user.id}")
    await ctx.session.commit()


async def load_user(ctx: Ctx, tg_id: int, *, allow_banned: bool) -> User:
    """User by tg_id with the common checks of docs/tech.md 7.1."""
    user = await ctx.session.scalar(select(User).where(User.tg_id == tg_id))
    if user is None:
        raise DomainError(ErrorCode.not_found, message="unknown tg_id")
    await _lift_expired_ban(ctx, user)
    if user.status is UserStatus.banned and not allow_banned:
        until = None if user.banned_until is None else user.banned_until.isoformat()
        raise DomainError(ErrorCode.banned, {"until": until})
    await _touch(ctx, user)
    return user


async def current_user(ctx: CtxDep, tg_id: TgId) -> User:
    """Known, not banned user from X-Tg-User-Id."""
    return await load_user(ctx, tg_id, allow_banned=False)


async def current_user_any(ctx: CtxDep, tg_id: TgId) -> User:
    """Same, banned users included (GET /users/me only)."""
    return await load_user(ctx, tg_id, allow_banned=True)


async def admin_user(ctx: CtxDep, user: Annotated[User, Depends(current_user)]) -> User:
    """Admins from ADMIN_TG_IDS, else 403 forbidden."""
    if user.tg_id not in ctx.settings.admin_tg_ids:
        raise DomainError(ErrorCode.forbidden)
    return user


CurrentUser = Annotated[User, Depends(current_user)]
AnyUser = Annotated[User, Depends(current_user_any)]
AdminUser = Annotated[User, Depends(admin_user)]
