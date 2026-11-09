"""Outbox: create, batch likes, enqueue for bot-worker, crons, delivery receipts (S9, S13)."""

from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import and_, func, select, update
from sqlalchemy.dialects.postgresql import insert
from svoi_contracts.constants import (
    NEW_PEOPLE_MIN,
    OUTBOX_MAX_ATTEMPTS,
    OUTBOX_REENQUEUE_MINUTES,
    REMINDER_DAYS,
)
from svoi_contracts.enums import (
    ModerationResultKind,
    NotificationKind,
    OutboxStatus,
    ReminderKind,
    UserStatus,
)
from svoi_contracts.errors import ErrorCode
from svoi_contracts.jobs import (
    JobBase,
    NotifyLikes,
    NotifyMatch,
    NotifyModeration,
    NotifyNewPeople,
    NotifyReminder,
)

from svoi_api.core import time
from svoi_api.core.errors import DomainError
from svoi_api.core.i18n import local
from svoi_api.db.models import (
    Interest,
    NotificationOutbox,
    Profile,
    ProfileInterest,
    Settings,
    User,
)
from svoi_api.deps import Ctx
from svoi_api.domains.notifications import rules

_TOPICS: dict[str, type[JobBase]] = {
    j.topic: j
    for j in (NotifyLikes, NotifyMatch, NotifyModeration, NotifyNewPeople, NotifyReminder)
}
_KIND_TOPIC: dict[NotificationKind, type[JobBase]] = {
    NotificationKind.likes: NotifyLikes,
    NotificationKind.match: NotifyMatch,
    NotificationKind.moderation: NotifyModeration,
    NotificationKind.reminder: NotifyReminder,
    NotificationKind.new_people: NotifyNewPeople,
}


async def _when(ctx: Ctx, user_id: int, kind: NotificationKind) -> datetime:
    settings = await ctx.session.get(Settings, user_id)
    if settings is None:
        return time.now()
    return rules.next_delivery(
        time.now(),
        kind=kind,
        frequency=settings.notify_frequency,
        quiet_from=settings.quiet_from,
        quiet_to=settings.quiet_to,
        tz=settings.tz,
    )


async def _enqueue_row(ctx: Ctx, row: NotificationOutbox) -> None:
    job = _KIND_TOPIC[row.kind].model_validate(row.payload)
    await ctx.queue.enqueue(job, "bot")
    row.status, row.enqueued_at = OutboxStatus.enqueued, time.now()
    row.attempts += 1


async def add(ctx: Ctx, user: User, kind: NotificationKind, job: JobBase, when: datetime) -> None:
    """New outbox row; due now -> straight to the bot queue (commits)."""
    if user.bot_blocked:
        return
    stmt = (
        insert(NotificationOutbox)
        .values(
            user_id=user.id,
            kind=kind,
            payload=job.model_dump(mode="json"),
            dedupe_key=job.dedupe_key,
            scheduled_for=when,
            status=OutboxStatus.pending,
            attempts=0,
        )
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
        .returning(NotificationOutbox.id)
    )
    new_id = await ctx.session.scalar(stmt)
    await ctx.session.commit()
    if new_id is not None and when <= time.now():
        row = await ctx.session.get(NotificationOutbox, new_id)
        if row is None:
            raise RuntimeError("row is missing")
        try:
            await _enqueue_row(ctx, row)
        except Exception:
            await ctx.session.rollback()
            return
        await ctx.session.commit()


async def likes(ctx: Ctx, recipient: User) -> None:
    """One outbox per delivery window; a new like in the window updates the count."""
    from svoi_api.domains.likes import service as likes_service  # noqa: PLC0415 - cycle

    when = await _when(ctx, recipient.id, NotificationKind.likes)
    window = when.replace(second=0, microsecond=0)
    key = f"likes:{recipient.id}:{window.isoformat()}"
    count = await likes_service.incoming_count(ctx, recipient.id)
    if count == 0:
        return
    job = NotifyLikes(
        dedupe_key=key,
        user_id=recipient.id,
        tg_id=recipient.tg_id,
        lang=recipient.lang,
        count=count,
    )
    existing = await ctx.session.scalar(
        select(NotificationOutbox).where(NotificationOutbox.dedupe_key == key)
    )
    if existing is not None:
        if existing.status is OutboxStatus.pending:
            existing.payload = job.model_dump(mode="json")
            await ctx.session.commit()
        return
    await add(ctx, recipient, NotificationKind.likes, job, window)


async def match(ctx: Ctx, recipient: User, match_id: int) -> None:
    """Mutual like: always immediate (quiet hours still apply)."""
    job = NotifyMatch(
        dedupe_key=f"match:{match_id}:{recipient.id}",
        match_id=match_id,
        recipient_user_id=recipient.id,
        tg_id=recipient.tg_id,
        lang=recipient.lang,
    )
    await add(
        ctx,
        recipient,
        NotificationKind.match,
        job,
        await _when(ctx, recipient.id, NotificationKind.match),
    )


async def moderation_result(
    ctx: Ctx,
    user: User,
    result: ModerationResultKind | Literal["unbanned"],
    *,
    key: str,
    until: datetime | None = None,
) -> None:
    """Moderation outcome for the user (key: mod:{queue_kind}:{item_id}:{action})."""
    job = NotifyModeration(
        dedupe_key=key,
        user_id=user.id,
        tg_id=user.tg_id,
        lang=user.lang,
        result=ModerationResultKind(result),
        until=until,
    )
    await add(
        ctx,
        user,
        NotificationKind.moderation,
        job,
        await _when(ctx, user.id, NotificationKind.moderation),
    )


# ---- crons ------------------------------------------------------------------------------


async def notify_schedule(ctx: Ctx) -> int:
    """Due pending rows -> bot queue; stale enqueued rows retried, then failed."""
    now = time.now()
    stale = now - timedelta(minutes=OUTBOX_REENQUEUE_MINUTES)
    rows = list(
        await ctx.session.scalars(
            select(NotificationOutbox)
            .where(
                (
                    (NotificationOutbox.status == OutboxStatus.pending)
                    & (NotificationOutbox.scheduled_for <= now)
                )
                | (
                    (NotificationOutbox.status == OutboxStatus.enqueued)
                    & (NotificationOutbox.enqueued_at < stale)
                )
            )
            .order_by(NotificationOutbox.id)
            .with_for_update(skip_locked=True)
        )
    )
    sent = 0
    for row in rows:
        if row.attempts >= OUTBOX_MAX_ATTEMPTS:
            row.status = OutboxStatus.failed
            continue
        await _enqueue_row(ctx, row)
        sent += 1
    await ctx.session.commit()
    return sent


async def reminders_scan(ctx: Ctx) -> int:
    """day3 / day7 reminder once per inactivity period."""
    now = time.now()
    made = 0
    for days, kind in zip(REMINDER_DAYS, (ReminderKind.day3, ReminderKind.day7), strict=True):
        users = await ctx.session.scalars(
            select(User).where(
                User.status == UserStatus.active,
                User.bot_blocked.is_(False),
                User.last_active_at <= now - timedelta(days=days),
                User.last_active_at > now - timedelta(days=days + 1),
            )
        )
        for user in list(users):
            key = f"reminder:{user.id}:{kind.value}:{user.last_active_at.date().isoformat()}"
            job = NotifyReminder(
                dedupe_key=key, user_id=user.id, tg_id=user.tg_id, lang=user.lang, kind=kind
            )
            await add(
                ctx,
                user,
                NotificationKind.reminder,
                job,
                await _when(ctx, user.id, NotificationKind.reminder),
            )
            made += 1
    return made


async def new_people_scan(ctx: Ctx) -> int:
    """Daily digest: >= NEW_PEOPLE_MIN new people in the same city and pool share an interest."""
    now = time.now()
    since = now - timedelta(hours=24)
    viewer = Profile.__table__.alias("vp")
    newcomer = Profile.__table__.alias("np")
    vi = ProfileInterest.__table__.alias("vi")
    ni = ProfileInterest.__table__.alias("ni")
    nu = User.__table__.alias("nu")
    counts = (
        select(viewer.c.user_id, vi.c.interest_id, func.count().label("n"))
        .select_from(viewer)
        .join(vi, vi.c.user_id == viewer.c.user_id)
        .join(ni, ni.c.interest_id == vi.c.interest_id)
        .join(
            newcomer,
            and_(
                newcomer.c.user_id == ni.c.user_id,
                newcomer.c.city_id == viewer.c.city_id,
                newcomer.c.pool == viewer.c.pool,
            ),
        )
        .join(
            nu,
            and_(
                nu.c.id == newcomer.c.user_id,
                nu.c.status == UserStatus.active,
                nu.c.created_at >= since,
            ),
        )
        .where(newcomer.c.user_id != viewer.c.user_id)
        .group_by(viewer.c.user_id, vi.c.interest_id)
        .subquery()
    )
    best = (
        select(counts.c.user_id, counts.c.interest_id, counts.c.n)
        .distinct(counts.c.user_id)
        .where(counts.c.n >= NEW_PEOPLE_MIN)
        .order_by(counts.c.user_id, counts.c.n.desc(), counts.c.interest_id)
    )
    made = 0
    for user_id, interest_id, n in (await ctx.session.execute(best)).tuples():
        user = await ctx.session.get(User, user_id)
        interest = await ctx.session.get(Interest, interest_id)
        if user is None or interest is None or user.status is not UserStatus.active:
            continue
        key = f"newpeople:{user.id}:{time.kyiv_today():%Y%m%d}"
        job = NotifyNewPeople(
            dedupe_key=key,
            user_id=user.id,
            tg_id=user.tg_id,
            lang=user.lang,
            interest_title=local(interest, "title", user.lang),
            count=n,
        )
        await add(
            ctx,
            user,
            NotificationKind.new_people,
            job,
            await _when(ctx, user.id, NotificationKind.new_people),
        )
        made += 1
    return made


# ---- internal endpoints -----------------------------------------------------------------


async def bot_blocked(ctx: Ctx, tg_id: int) -> None:
    """Telegram 403: stop notifying, cancel what is waiting."""
    user = await ctx.session.scalar(select(User).where(User.tg_id == tg_id))
    if user is None:
        raise DomainError(ErrorCode.not_found)
    user.bot_blocked = True
    await ctx.session.execute(
        update(NotificationOutbox)
        .where(
            NotificationOutbox.user_id == user.id, NotificationOutbox.status == OutboxStatus.pending
        )
        .values(status=OutboxStatus.cancelled)
    )
    await ctx.session.commit()


async def mark_sent(ctx: Ctx, dedupe_key: str) -> None:
    """bot-worker delivered the notification."""
    row = await ctx.session.scalar(
        select(NotificationOutbox).where(NotificationOutbox.dedupe_key == dedupe_key)
    )
    if row is None:
        raise DomainError(ErrorCode.not_found)
    row.status = OutboxStatus.sent
    await ctx.session.commit()
