"""Reactions: like, like with a message, skip, undo, daily limits (S8)."""

from sqlalchemy import func, select
from svoi_contracts.api.feed import FeedItem
from svoi_contracts.api.reactions import ReactionIn, ReactionOut
from svoi_contracts.cards import Limits
from svoi_contracts.constants import MESSAGES_PER_DAY, REACTIONS_PER_DAY, UNDO_WINDOW_SECONDS
from svoi_contracts.enums import LikeStatus, Pool, ReactionType, ViewAction
from svoi_contracts.errors import ErrorCode

from svoi_api.core import time
from svoi_api.core.errors import DomainError
from svoi_api.db.models import Like, Profile, ReactionBonus, User, View
from svoi_api.deps import Ctx

TWO_DAYS = 48 * 3600


def _keys(user_id: int) -> tuple[str, str]:
    day = f"{time.kyiv_today():%Y%m%d}"
    return f"lim:react:{user_id}:{day}", f"lim:msg:{user_id}:{day}"


async def limits(ctx: Ctx, user: User) -> Limits:
    """What is left today (bonuses included); resets at Kyiv midnight."""
    react_key, msg_key = _keys(user.id)
    used_react, used_msg = await ctx.redis.mget([react_key, msg_key])
    bonus = await ctx.session.scalar(
        select(func.coalesce(func.sum(ReactionBonus.amount), 0)).where(
            ReactionBonus.user_id == user.id, ReactionBonus.on_date == time.kyiv_today()
        )
    )
    return Limits(
        reactions_left=max(0, REACTIONS_PER_DAY + int(bonus or 0) - int(used_react or 0)),
        messages_left=max(0, MESSAGES_PER_DAY - int(used_msg or 0)),
        resets_at=time.next_kyiv_midnight(),
    )


async def _count(ctx: Ctx, user: User, *, message: bool) -> None:
    react_key, msg_key = _keys(user.id)
    for key in (react_key, msg_key) if message else (react_key,):
        await ctx.redis.incr(key)
        await ctx.redis.expire(key, TWO_DAYS)


async def react(ctx: Ctx, user: User, body: ReactionIn) -> ReactionOut:  # noqa: PLR0912
    """Rules of BACKEND S8; a like back to someone who liked you is an instant match."""
    from svoi_api.domains import likes, notifications, safety  # noqa: PLC0415 - cycle

    view = await ctx.session.get(View, (user.id, body.target_id))
    if view is None or view.action not in (ViewAction.shown, ViewAction.undo) or view.acted_at:
        raise DomainError(ErrorCode.conflict, message="card was not shown or already answered")
    if await safety.service.captcha_required(ctx, user):
        raise DomainError(ErrorCode.captcha_required)
    await safety.service.check_rhythm(ctx, user)
    left = await limits(ctx, user)
    if left.reactions_left <= 0:
        raise DomainError(ErrorCode.limit_reached, left.model_dump(mode="json"))
    is_msg = body.type is ReactionType.like_msg
    if is_msg:
        if left.messages_left <= 0:
            raise DomainError(ErrorCode.limit_reached, left.model_dump(mode="json"))
        pool = await ctx.session.scalar(select(Profile.pool).where(Profile.user_id == user.id))
        if body.media is not None and pool is Pool.minor:
            raise DomainError(ErrorCode.media_forbidden)
        if body.message:
            await safety.service.check_like_message(ctx, user, body.message)
            await safety.service.register_message(ctx, user, body.target_id, body.message)

    view.action = ViewAction(body.type.value)
    view.acted_at = time.now()
    await _count(ctx, user, message=is_msg)
    if body.type is ReactionType.skip:
        await ctx.session.commit()
        await ctx.redis.set(f"feed:undo:{user.id}", body.target_id, ex=UNDO_WINDOW_SECONDS)
        return ReactionOut(match=None, limits=await limits(ctx, user))

    await ctx.redis.delete(f"feed:undo:{user.id}")
    target = await ctx.session.get(User, body.target_id)
    if target is None:
        raise RuntimeError("target is missing")
    back = await ctx.session.scalar(
        select(Like).where(
            Like.from_id == body.target_id, Like.to_id == user.id, Like.status == LikeStatus.pending
        )
    )
    like = Like(
        from_id=user.id,
        to_id=body.target_id,
        message=body.message,
        media_kind=None if body.media is None else body.media.kind,
        media_file_id=None if body.media is None else body.media.file_id,
        status=LikeStatus.pending,
    )
    ctx.session.add(like)
    match = None
    if back is not None and not user.shadow_banned:
        back.status = like.status = LikeStatus.matched
        back.responded_at = like.responded_at = time.now()
        match = await likes.service.create_match(ctx, user.id, target.id)
    await ctx.session.commit()
    if user.shadow_banned:
        pass  # recorded, never delivered
    elif match is not None:
        await notifications.service.match(ctx, target, match.id)
    else:
        await notifications.service.likes(ctx, target)
    result = None if match is None else await likes.service.match_result(ctx, user, match)
    return ReactionOut(match=result, limits=await limits(ctx, user))


async def undo(ctx: Ctx, user: User) -> FeedItem:
    """Bring back the last skip within UNDO_WINDOW_SECONDS; the spent reaction stays spent."""
    from svoi_api.domains.matching import service as matching  # noqa: PLC0415 - cycle

    key = f"feed:undo:{user.id}"
    raw = await ctx.redis.get(key)
    if raw is None:
        raise DomainError(ErrorCode.undo_unavailable)
    await ctx.redis.delete(key)
    target = int(raw)
    view = await ctx.session.get(View, (user.id, target))
    if view is None:
        raise DomainError(ErrorCode.undo_unavailable)
    view.action, view.acted_at = ViewAction.undo, None
    await ctx.session.commit()
    return await matching.item_for(ctx, user, target)
