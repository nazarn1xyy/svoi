"""Incoming likes, responses, matches, contacts, icebreaker, expiry (S9)."""

import base64
from datetime import datetime, timedelta

from sqlalchemy import Select, and_, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import aliased
from svoi_contracts.api.likes import (
    ContactOut,
    IncomingLike,
    IncomingResponse,
    NoIncoming,
    RespondOut,
)
from svoi_contracts.api.reactions import MessageMedia
from svoi_contracts.cards import Icebreaker, MatchResult, Page, ProfileCardShort
from svoi_contracts.constants import LIKE_EXPIRE_DAYS
from svoi_contracts.enums import (
    IcebreakerTemplate,
    LikeDecision,
    LikeStatus,
    UserStatus,
)
from svoi_contracts.errors import ErrorCode

from svoi_api.core import time
from svoi_api.core.errors import DomainError
from svoi_api.core.i18n import local
from svoi_api.db.models import (
    Block,
    City,
    Institution,
    Interest,
    Like,
    Match,
    Profile,
    ProfileGoal,
    ProfileInterest,
    User,
)
from svoi_api.deps import Ctx


def _visible_incoming(user_id: int) -> Select[Like]:
    author = aliased(User, name="author")
    ap = aliased(Profile, name="ap")
    me = aliased(Profile, name="me")
    return (
        select(Like)
        .join(author, author.id == Like.from_id)
        .join(ap, ap.user_id == Like.from_id)
        .join(me, me.user_id == Like.to_id)
        .where(
            Like.to_id == user_id,
            Like.status == LikeStatus.pending,
            author.status == UserStatus.active,
            author.shadow_banned.is_(False),
            ap.pool == me.pool,
            ~exists().where(
                or_(
                    and_(Block.user_id == user_id, Block.blocked_id == Like.from_id),
                    and_(Block.user_id == Like.from_id, Block.blocked_id == user_id),
                )
            ),
        )
    )


async def incoming_count(ctx: Ctx, user_id: int) -> int:
    """Pending likes from visible authors of the same pool."""
    q = _visible_incoming(user_id).subquery()
    return int(await ctx.session.scalar(select(func.count()).select_from(q)) or 0)


async def incoming_next(ctx: Ctx, user: User) -> IncomingResponse:
    """Oldest incoming like with the author's card."""
    from svoi_api.domains.profiles import card  # noqa: PLC0415 - cycle

    like = await ctx.session.scalar(
        _visible_incoming(user.id).order_by(Like.created_at, Like.id).limit(1)
    )
    if like is None:
        return NoIncoming()
    media = None
    if like.media_kind is not None and like.media_file_id is not None:
        # the likes table keeps no duration; the bot only replays the file
        media = MessageMedia(kind=like.media_kind, file_id=like.media_file_id, duration_s=0)
    return IncomingLike(
        like_id=like.id,
        card=await card.build(ctx, user, like.from_id, "incoming"),
        message=like.message,
        media=media,
    )


async def create_match(ctx: Ctx, a: int, b: int) -> Match:
    """One match per pair even under races (unique pair + ON CONFLICT)."""
    low, high = min(a, b), max(a, b)
    await ctx.session.execute(
        insert(Match).values(user_a_id=low, user_b_id=high).on_conflict_do_nothing()
    )
    match = await ctx.session.scalar(
        select(Match).where(Match.user_a_id == low, Match.user_b_id == high)
    )
    if match is None:
        raise RuntimeError("match is missing")
    if match.removed_by_id is not None:
        match.removed_by_id = None
    return match


async def _icebreaker(ctx: Ctx, viewer: User, partner_id: int) -> Icebreaker | None:
    mine = select(ProfileInterest.interest_id).where(ProfileInterest.user_id == viewer.id)
    best = await ctx.session.scalar(
        select(Interest)
        .join(ProfileInterest, ProfileInterest.interest_id == Interest.id)
        .where(ProfileInterest.user_id == partner_id, Interest.id.in_(mine))
        .order_by(Interest.idf.desc(), Interest.id)
        .limit(1)
    )
    if best is not None:
        return Icebreaker(
            template=IcebreakerTemplate.common_interest,
            interest_title=local(best, "title", viewer.lang),
        )
    vp = await ctx.session.get(Profile, viewer.id)
    pp = await ctx.session.get(Profile, partner_id)
    if vp and pp and vp.institution_id is not None and vp.institution_id == pp.institution_id:
        inst = await ctx.session.get(Institution, vp.institution_id)
        if inst is not None:
            return Icebreaker(
                template=IcebreakerTemplate.same_institution,
                institution_name=inst.short_name or inst.name,
            )
    goal = await ctx.session.scalar(
        select(ProfileGoal.goal)
        .where(
            ProfileGoal.user_id == partner_id,
            ProfileGoal.goal.in_(select(ProfileGoal.goal).where(ProfileGoal.user_id == viewer.id)),
        )
        .order_by(ProfileGoal.goal)
        .limit(1)
    )
    if goal is not None:
        return Icebreaker(template=IcebreakerTemplate.common_goal, goal=goal)
    return None


async def match_result(ctx: Ctx, viewer: User, match: Match) -> MatchResult:
    """Partner card, current username and an icebreaker for the viewer."""
    from svoi_api.domains.profiles import card  # noqa: PLC0415 - cycle

    partner_id = match.user_b_id if match.user_a_id == viewer.id else match.user_a_id
    partner = await ctx.session.get(User, partner_id)
    if partner is None:
        raise DomainError(ErrorCode.not_found)
    return MatchResult(
        match_id=match.id,
        partner=await card.build(ctx, viewer, partner_id, "match"),
        partner_username=partner.tg_username,
        partner_tg_id=partner.tg_id,
        icebreaker=await _icebreaker(ctx, viewer, partner_id),
    )


async def respond(ctx: Ctx, user: User, like_id: int, decision: LikeDecision) -> RespondOut:
    """accept -> match and a notification to the author; decline -> quietly closed."""
    from svoi_api.domains.notifications import service as notifications  # noqa: PLC0415

    like = await ctx.session.get(Like, like_id)
    if like is None or like.to_id != user.id:
        raise DomainError(ErrorCode.not_found)
    if like.status is not LikeStatus.pending:
        raise DomainError(ErrorCode.conflict, message="already answered")
    like.responded_at = time.now()
    if decision is LikeDecision.decline:
        like.status = LikeStatus.declined
        await ctx.session.commit()
        return RespondOut(match=None)
    like.status = LikeStatus.matched
    match = await create_match(ctx, user.id, like.from_id)
    await ctx.session.commit()
    author = await ctx.session.get(User, like.from_id)
    if author is not None:
        await notifications.match(ctx, author, match.id)
    return RespondOut(match=await match_result(ctx, user, match))


async def get_match(ctx: Ctx, user: User, match_id: int) -> MatchResult:
    """Only for participants."""
    match = await ctx.session.get(Match, match_id)
    if match is None or user.id not in (match.user_a_id, match.user_b_id):
        raise DomainError(ErrorCode.not_found)
    return await match_result(ctx, user, match)


def _cursor(at: datetime, match_id: int) -> str:
    return base64.urlsafe_b64encode(f"{at.isoformat()}|{match_id}".encode()).decode()


def _parse_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        at, mid = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        return datetime.fromisoformat(at), int(mid)
    except ValueError as exc:
        raise DomainError(ErrorCode.validation_error, message="bad cursor") from exc


async def contacts(ctx: Ctx, user: User, cursor: str | None, limit: int) -> Page[ContactOut]:
    """Live matches, newest first."""
    q = (
        select(Match)
        .where(
            or_(Match.user_a_id == user.id, Match.user_b_id == user.id),
            Match.removed_by_id.is_(None),
        )
        .order_by(Match.created_at.desc(), Match.id.desc())
        .limit(limit + 1)
    )
    if cursor:
        at, mid = _parse_cursor(cursor)
        q = q.where(or_(Match.created_at < at, and_(Match.created_at == at, Match.id < mid)))
    rows = list(await ctx.session.scalars(q))
    items = []
    for m in rows[:limit]:
        pid = m.user_b_id if m.user_a_id == user.id else m.user_a_id
        partner = await ctx.session.get(User, pid)
        profile = await ctx.session.get(Profile, pid)
        if partner is None or profile is None or profile.age is None or profile.name is None:
            continue
        city = await ctx.session.get(City, profile.city_id) if profile.city_id else None
        items.append(
            ContactOut(
                match_id=m.id,
                partner=ProfileCardShort(
                    user_id=pid,
                    name=profile.name,
                    age=profile.age,
                    city_name=local(city, "name", user.lang) if city else "",
                ),
                partner_username=partner.tg_username,
                partner_tg_id=partner.tg_id,
                matched_at=m.created_at,
            )
        )
    more = len(rows) > limit
    last = rows[limit - 1] if more else None
    return Page[ContactOut](
        items=items, next_cursor=_cursor(last.created_at, last.id) if last else None
    )


async def delete_contact(ctx: Ctx, user: User, match_id: int) -> None:
    """Gone for both sides."""
    match = await ctx.session.get(Match, match_id)
    if match is None or user.id not in (match.user_a_id, match.user_b_id):
        raise DomainError(ErrorCode.not_found)
    if match.removed_by_id is None:
        match.removed_by_id = user.id
    await ctx.session.commit()


async def expire_likes(ctx: Ctx) -> int:
    """api.likes_expire: pending older than LIKE_EXPIRE_DAYS -> expired."""
    cutoff = time.now() - timedelta(days=LIKE_EXPIRE_DAYS)
    result = await ctx.session.execute(
        update(Like)
        .where(Like.status == LikeStatus.pending, Like.created_at < cutoff)
        .values(status=LikeStatus.expired)
    )
    await ctx.session.commit()
    return int(result.rowcount or 0)  # type: ignore[attr-defined]  # CursorResult
