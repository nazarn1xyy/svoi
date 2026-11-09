"""Reports, blocks, admin queues and actions (S10, S12 review)."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Select, and_, case, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from svoi_contracts.api.admin import AdminActionIn, AdminQueueItem, AdminUserOut, ReportBrief
from svoi_contracts.api.moderation import ReportIn
from svoi_contracts.constants import AGE_MIN, REPORTS_AUTOHIDE
from svoi_contracts.enums import (
    AdminAction,
    AdminQueueKind,
    ContentField,
    LikeStatus,
    MediaKind,
    ModerationResultKind,
    ModerationStatus,
    Pool,
    ReportContext,
    ReportReason,
    ReportStatus,
    UserStatus,
    ViewAction,
)
from svoi_contracts.errors import ErrorCode

from svoi_api.core import time
from svoi_api.core.errors import DomainError
from svoi_api.db.models import (
    Block,
    Filters,
    Interest,
    Like,
    Match,
    Media,
    ModAction,
    Profile,
    ProfilePrompt,
    Report,
    User,
    Verification,
    View,
)
from svoi_api.deps import Ctx

CONTACT_WEIGHT = 1.5
WEIGHT_DECAY = 0.9
WEIGHT_FLOOR = 0.3
BAN_7D = timedelta(days=7)
MINOR_AGE = AGE_MIN + 1  # moved to the 16-17 pool as 17


# ---- user side --------------------------------------------------------------------------


async def _mark_view(ctx: Ctx, viewer_id: int, target_id: int, action: ViewAction) -> None:
    await ctx.session.execute(
        insert(View)
        .values(viewer_id=viewer_id, target_id=target_id, action=action, acted_at=time.now())
        .on_conflict_do_update(
            index_elements=["viewer_id", "target_id"],
            set_={"action": action, "acted_at": time.now()},
        )
    )


async def _autohide(ctx: Ctx, target_id: int) -> None:
    rows = await ctx.session.execute(
        select(Report, User.report_weight)
        .outerjoin(User, User.id == Report.reporter_id)
        .where(Report.target_id == target_id, Report.status == ReportStatus.open)
    )
    total = 0.0
    underage = False
    for report, weight in rows:
        underage |= report.reason is ReportReason.underage
        if report.reporter_id is not None:
            factor = CONTACT_WEIGHT if report.context is ReportContext.contact else 1.0
            total += (weight or 1.0) * factor
    if underage or total >= REPORTS_AUTOHIDE:
        await ctx.session.execute(
            update(Profile).where(Profile.user_id == target_id).values(hidden_by_moderation=True)
        )


async def report(ctx: Ctx, user: User, body: ReportIn) -> None:
    """One report per pair; may hide the target right away."""
    from svoi_api.domains.safety import service as safety  # noqa: PLC0415 - cycle

    if body.target_id == user.id or await ctx.session.get(User, body.target_id) is None:
        raise DomainError(ErrorCode.not_found)
    if body.text:
        await safety.check_field(ctx, user, body.text, ContentField.report_text)
    done = await ctx.session.scalar(
        select(Report.id).where(Report.reporter_id == user.id, Report.target_id == body.target_id)
    )
    if done is not None:
        raise DomainError(ErrorCode.conflict, message="already reported")
    ctx.session.add(
        Report(
            reporter_id=user.id,
            target_id=body.target_id,
            reason=body.reason,
            text=body.text,
            context=body.context,
        )
    )
    await _mark_view(ctx, user.id, body.target_id, ViewAction.report)
    await ctx.session.flush()
    await _autohide(ctx, body.target_id)
    await ctx.session.commit()


async def _unmatch(ctx: Ctx, a: int, b: int, by: int) -> None:
    await ctx.session.execute(
        update(Match)
        .where(
            Match.user_a_id == min(a, b),
            Match.user_b_id == max(a, b),
            Match.removed_by_id.is_(None),
        )
        .values(removed_by_id=by)
    )


async def block(ctx: Ctx, user: User, target_id: int) -> None:
    """Never see each other again; their match ends."""
    if target_id == user.id or await ctx.session.get(User, target_id) is None:
        raise DomainError(ErrorCode.not_found)
    await ctx.session.execute(
        insert(Block).values(user_id=user.id, blocked_id=target_id).on_conflict_do_nothing()
    )
    await _unmatch(ctx, user.id, target_id, user.id)
    await _mark_view(ctx, user.id, target_id, ViewAction.block)
    await ctx.session.commit()


async def unblock(ctx: Ctx, user: User, target_id: int) -> None:
    """Remove the block; the match does not come back."""
    result = await ctx.session.execute(
        delete(Block).where(Block.user_id == user.id, Block.blocked_id == target_id)
    )
    if not result.rowcount:  # type: ignore[attr-defined]  # CursorResult
        raise DomainError(ErrorCode.not_found)
    await ctx.session.commit()


# ---- admin queues -----------------------------------------------------------------------


def _photos_queue() -> Select[*tuple[Any, ...]]:
    """Pending media the NSFW check could not decide (or videos, or duplicates)."""
    return select(Media).where(
        Media.moderation_status == ModerationStatus.pending,
        or_(Media.kind == MediaKind.video, Media.nsfw_score.is_not(None)),
    )


def _queue_query(kind: AdminQueueKind) -> Select[*tuple[Any, ...]]:
    if kind is AdminQueueKind.reports:
        has_underage = func.bool_or(Report.reason == ReportReason.underage)
        return (
            select(Report.target_id, func.max(Report.id).label("item_id"))
            .where(Report.status == ReportStatus.open)
            .group_by(Report.target_id)
            .order_by(
                case((has_underage, 0), else_=1), func.count().desc(), func.min(Report.created_at)
            )
        )
    if kind is AdminQueueKind.photos:
        return _photos_queue().order_by(Media.created_at, Media.id)
    if kind is AdminQueueKind.verifications:
        return (
            select(Verification)
            .where(
                Verification.status == ModerationStatus.pending,
                Verification.video_note_file_id.is_not(None),
            )
            .order_by(Verification.created_at)
        )
    if kind is AdminQueueKind.custom_tags:
        return (
            select(Interest)
            .where(Interest.is_custom, Interest.moderation_status == ModerationStatus.pending)
            .order_by(Interest.id)
        )
    return (
        select(ProfilePrompt)
        .where(ProfilePrompt.moderation_status == ModerationStatus.pending)
        .order_by(ProfilePrompt.user_id, ProfilePrompt.prompt_id)
    )


async def stats(ctx: Ctx) -> dict[AdminQueueKind, int]:
    """Size of every queue."""
    out = {}
    for kind in AdminQueueKind:
        sub = _queue_query(kind).order_by(None).subquery()
        out[kind] = int(await ctx.session.scalar(select(func.count()).select_from(sub)) or 0)
    return out


async def _reports_of(ctx: Ctx, target_id: int) -> list[ReportBrief]:
    rows = await ctx.session.scalars(
        select(Report)
        .where(Report.target_id == target_id, Report.status == ReportStatus.open)
        .order_by(Report.created_at)
    )
    return [ReportBrief(reason=r.reason, text=r.text, created_at=r.created_at) for r in rows]


def _prompt_item_id(user_id: int, prompt_id: int) -> int:
    """profile_prompts has a composite key; pack it into one id for AdminCb."""
    return user_id * 1000 + prompt_id


def _unpack_prompt(item_id: int) -> tuple[int, int]:
    return divmod(item_id, 1000)


async def next_item(ctx: Ctx, admin: User, kind: AdminQueueKind) -> AdminQueueItem | None:
    """Oldest item of the queue with the full target card."""
    from svoi_api.domains.profiles import card  # noqa: PLC0415
    from svoi_api.domains.profiles import service as profiles  # noqa: PLC0415

    row = (await ctx.session.execute(_queue_query(kind).limit(1))).first()
    if row is None:
        return None
    media_ref = None
    verification_file = verification_gesture = custom = flagged = None
    if kind is AdminQueueKind.reports:
        target_id, item_id = row[0], row[1]
        created = (await ctx.session.get(Report, item_id)).created_at  # type: ignore[union-attr]
    elif kind is AdminQueueKind.photos:
        media: Media = row[0]
        target_id, item_id, created = media.user_id, media.id, media.created_at
        media_ref = profiles.media_ref(media)
    elif kind is AdminQueueKind.verifications:
        v: Verification = row[0]
        target_id, item_id, created = v.user_id, v.id, v.created_at
        verification_file, verification_gesture = v.video_note_file_id, v.gesture
    elif kind is AdminQueueKind.custom_tags:
        tag: Interest = row[0]
        if tag.created_by_id is None:
            raise RuntimeError("tag.created_by_id is missing")
        target_id, item_id, created = tag.created_by_id, tag.id, time.now()
        custom = tag.title_uk
    else:
        pp: ProfilePrompt = row[0]
        target_id, item_id = pp.user_id, _prompt_item_id(pp.user_id, pp.prompt_id)
        created, flagged = time.now(), pp.text
    target = await ctx.session.get(User, target_id)
    if target is None:
        raise RuntimeError("target is missing")
    return AdminQueueItem(
        item_id=item_id,
        kind=kind,
        target_user_id=target.id,
        target_tg_id=target.tg_id,
        target_card=await card.build(ctx, admin, target.id, "admin"),
        reports=await _reports_of(ctx, target.id),
        media=media_ref,
        verification_file_id=verification_file,
        verification_gesture=verification_gesture,
        custom_interest_title=custom,
        flagged_text=flagged,
        created_at=created,
    )


# ---- admin actions ----------------------------------------------------------------------


async def _close_reports(ctx: Ctx, target_id: int, status: ReportStatus, admin: User) -> None:
    await ctx.session.execute(
        update(Report)
        .where(Report.target_id == target_id, Report.status == ReportStatus.open)
        .values(status=status, moderator_tg_id=admin.tg_id, resolved_at=time.now())
    )


async def _ban(ctx: Ctx, target: User, until: datetime | None, admin: User) -> None:
    target.status, target.banned_until = UserStatus.banned, until
    await _close_reports(ctx, target.id, ReportStatus.accepted, admin)
    await ctx.session.execute(
        update(Like)
        .where(Like.from_id == target.id, Like.status == LikeStatus.pending)
        .values(status=LikeStatus.expired)
    )


async def _to_minor(ctx: Ctx, target: User, admin: User) -> None:
    from svoi_api.domains.profiles.rules import POOL_BOUNDS  # noqa: PLC0415

    p = await ctx.session.get(Profile, target.id)
    if p is None:
        raise RuntimeError("p is missing")
    p.age, p.pool, p.age_edits = MINOR_AGE, Pool.minor, 1
    low, high = POOL_BOUNDS[Pool.minor]
    await ctx.session.execute(
        update(Filters).where(Filters.user_id == target.id).values(age_min=low, age_max=high)
    )
    adults = select(Profile.user_id).where(Profile.pool == Pool.adult)
    await ctx.session.execute(
        update(Match)
        .where(
            Match.removed_by_id.is_(None),
            or_(
                and_(Match.user_a_id == target.id, Match.user_b_id.in_(adults)),
                and_(Match.user_b_id == target.id, Match.user_a_id.in_(adults)),
            ),
        )
        .values(removed_by_id=target.id)
    )
    await ctx.session.execute(
        update(Like)
        .where(
            Like.status == LikeStatus.pending,
            or_(
                and_(Like.from_id == target.id, Like.to_id.in_(adults)),
                and_(Like.to_id == target.id, Like.from_id.in_(adults)),
            ),
        )
        .values(status=LikeStatus.expired)
    )
    await _close_reports(ctx, target.id, ReportStatus.accepted, admin)
    await ctx.redis.delete(f"feed:batch:{target.id}")


async def _target_of(ctx: Ctx, body: AdminActionIn) -> tuple[int, bool]:
    """(target user id, item still open)."""
    kind, item = body.kind, body.item_id
    if kind is AdminQueueKind.reports:
        r = await ctx.session.get(Report, item)
        if r is None:
            raise DomainError(ErrorCode.not_found)
        return r.target_id, r.status is ReportStatus.open
    if kind is AdminQueueKind.photos:
        m = await ctx.session.get(Media, item)
        if m is None:
            raise DomainError(ErrorCode.conflict, message="media is gone")
        return m.user_id, m.moderation_status is ModerationStatus.pending
    if kind is AdminQueueKind.verifications:
        v = await ctx.session.get(Verification, item)
        if v is None:
            raise DomainError(ErrorCode.not_found)
        return v.user_id, v.status is ModerationStatus.pending
    if kind is AdminQueueKind.custom_tags:
        tag = await ctx.session.get(Interest, item)
        if tag is None or tag.created_by_id is None:
            raise DomainError(ErrorCode.not_found)
        return tag.created_by_id, tag.moderation_status is ModerationStatus.pending
    user_id, prompt_id = _unpack_prompt(item)
    pp = await ctx.session.get(ProfilePrompt, (user_id, prompt_id))
    if pp is None:
        raise DomainError(ErrorCode.not_found)
    return user_id, pp.moderation_status is ModerationStatus.pending


_ALLOWED: dict[AdminQueueKind, frozenset[AdminAction]] = {
    AdminQueueKind.reports: frozenset(
        {AdminAction.ok, AdminAction.delete_media, AdminAction.delete_text, AdminAction.ban_7d,
         AdminAction.ban_forever, AdminAction.move_to_minor_pool}
    ),
    AdminQueueKind.photos: frozenset(
        {AdminAction.approve, AdminAction.reject, AdminAction.delete_media, AdminAction.ban_7d,
         AdminAction.ban_forever}
    ),
    AdminQueueKind.verifications: frozenset({AdminAction.approve, AdminAction.reject}),
    AdminQueueKind.custom_tags: frozenset({AdminAction.approve, AdminAction.reject}),
    AdminQueueKind.texts: frozenset(
        {AdminAction.ok, AdminAction.approve, AdminAction.reject, AdminAction.delete_text,
         AdminAction.ban_7d, AdminAction.ban_forever, AdminAction.move_to_minor_pool}
    ),
}  # fmt: skip


async def act(ctx: Ctx, admin: User, body: AdminActionIn) -> None:  # noqa: PLR0912, PLR0915
    """Apply a moderator decision; every action is logged and notified."""
    from svoi_api.domains.notifications import service as notify  # noqa: PLC0415
    from svoi_api.domains.profiles import service as profiles  # noqa: PLC0415

    if body.action not in _ALLOWED[body.kind]:
        raise DomainError(ErrorCode.validation_error, message="action does not fit the queue")
    target_id, still_open = await _target_of(ctx, body)
    if not still_open:
        raise DomainError(ErrorCode.conflict, message="already handled")
    target = await ctx.session.get(User, target_id)
    if target is None:
        raise RuntimeError("target is missing")
    kind, action, item = body.kind, body.action, body.item_id
    result: ModerationResultKind | None = None
    until = None

    if action is AdminAction.ok:
        await ctx.session.execute(
            update(User)
            .where(
                User.id.in_(
                    select(Report.reporter_id).where(
                        Report.target_id == target_id, Report.status == ReportStatus.open
                    )
                )
            )
            .values(report_weight=func.greatest(WEIGHT_FLOOR, User.report_weight * WEIGHT_DECAY))
        )
        await _close_reports(ctx, target_id, ReportStatus.rejected, admin)
        await ctx.session.execute(
            update(ProfilePrompt)
            .where(ProfilePrompt.user_id == target_id)
            .values(moderation_status=ModerationStatus.approved)
        )
        await ctx.session.execute(
            update(Profile).where(Profile.user_id == target_id).values(hidden_by_moderation=False)
        )
    elif action is AdminAction.delete_media:
        await profiles.drop_media(ctx, target_id, item if kind is AdminQueueKind.photos else None)
        if kind is AdminQueueKind.reports:
            await _close_reports(ctx, target_id, ReportStatus.accepted, admin)
        result = ModerationResultKind.media_rejected
    elif action is AdminAction.delete_text:
        await ctx.session.execute(delete(ProfilePrompt).where(ProfilePrompt.user_id == target_id))
        await _close_reports(ctx, target_id, ReportStatus.accepted, admin)
        await ctx.session.execute(
            update(Profile).where(Profile.user_id == target_id).values(hidden_by_moderation=False)
        )
        result = ModerationResultKind.text_removed
    elif action in (AdminAction.ban_7d, AdminAction.ban_forever):
        until = time.now() + BAN_7D if action is AdminAction.ban_7d else None
        await _ban(ctx, target, until, admin)
        result = ModerationResultKind.banned
    elif action is AdminAction.move_to_minor_pool:
        await _to_minor(ctx, target, admin)
    elif kind is AdminQueueKind.photos:
        media = await ctx.session.get(Media, item)
        if media is None:
            raise RuntimeError("media is missing")
        if action is AdminAction.approve:
            media.moderation_status = ModerationStatus.approved
        else:
            await profiles.drop_media(ctx, target_id, item)
            result = ModerationResultKind.media_rejected
    elif kind is AdminQueueKind.verifications:
        v = await ctx.session.get(Verification, item)
        if v is None:
            raise RuntimeError("v is missing")
        v.reviewed_at = time.now()
        if action is AdminAction.approve:
            v.status, target.verified = ModerationStatus.approved, True
            result = ModerationResultKind.verified
        else:
            v.status = ModerationStatus.rejected
            result = ModerationResultKind.verification_rejected
    elif kind is AdminQueueKind.custom_tags:
        tag = await ctx.session.get(Interest, item)
        if tag is None:
            raise RuntimeError("tag is missing")
        if action is AdminAction.approve:
            tag.moderation_status = ModerationStatus.approved
            await profiles.add_interest(ctx, target_id, tag.id)
            result = ModerationResultKind.tag_approved
        else:
            tag.moderation_status = ModerationStatus.rejected
            result = ModerationResultKind.tag_rejected
    else:  # texts approve / reject
        user_id, prompt_id = _unpack_prompt(item)
        pp = await ctx.session.get(ProfilePrompt, (user_id, prompt_id))
        if pp is None:
            raise RuntimeError("pp is missing")
        if action is AdminAction.approve:
            pp.moderation_status = ModerationStatus.approved
        else:
            await ctx.session.delete(pp)
            result = ModerationResultKind.text_removed
        pending_left = await ctx.session.scalar(
            select(func.count()).where(
                ProfilePrompt.user_id == user_id,
                ProfilePrompt.moderation_status == ModerationStatus.pending,
                ProfilePrompt.prompt_id != prompt_id,
            )
        )
        if not pending_left:
            await ctx.session.execute(
                update(Profile).where(Profile.user_id == user_id).values(hidden_by_moderation=False)
            )

    ctx.session.add(
        ModAction(
            moderator_tg_id=admin.tg_id,
            target_user_id=target_id,
            queue_kind=kind,
            item_id=item,
            action=action,
            reason=body.reason,
        )
    )
    await ctx.session.commit()
    await profiles.profile_changed(ctx, target_id, rebuild=False)
    if result is not None:
        key = f"mod:{kind.value}:{item}:{action.value}"
        await notify.moderation_result(ctx, target, result, key=key, until=until)


async def user_info(ctx: Ctx, admin: User, tg_id: int) -> AdminUserOut:
    """/user <tg_id>."""
    from svoi_api.domains.profiles import card  # noqa: PLC0415

    target = await ctx.session.scalar(select(User).where(User.tg_id == tg_id))
    if target is None:
        raise DomainError(ErrorCode.not_found)
    try:
        target_card = await card.build(ctx, admin, target.id, "admin")
    except DomainError:
        target_card = None
    reports_total = await ctx.session.scalar(
        select(func.count()).select_from(Report).where(Report.target_id == target.id)
    )
    actions = await ctx.session.scalars(
        select(ModAction)
        .where(ModAction.target_user_id == target.id)
        .order_by(ModAction.created_at.desc())
        .limit(20)
    )
    return AdminUserOut(
        user_id=target.id,
        tg_id=target.tg_id,
        status=target.status,
        shadow_banned=target.shadow_banned,
        banned_until=target.banned_until,
        risk_score=target.risk_score,
        card=target_card,
        reports_total=int(reports_total or 0),
        mod_actions=[
            f"{a.created_at:%Y-%m-%d %H:%M} {a.queue_kind.value}/{a.action.value}"
            + (f": {a.reason}" if a.reason else "")
            for a in actions
        ],
    )
