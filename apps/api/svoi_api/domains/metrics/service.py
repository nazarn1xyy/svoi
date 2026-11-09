"""Product metrics for /metrics (S10b)."""

from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import ColumnElement, Date, and_, cast, func, or_, select
from svoi_contracts.api.admin import MetricsOut
from svoi_contracts.enums import (
    LikeStatus,
    OnboardingStep,
    Pool,
    ReportStatus,
    UserStatus,
    ViewAction,
)

from svoi_api.core import time as clock
from svoi_api.db.models import Like, Match, Profile, Report, User, UserActivityDay, View
from svoi_api.deps import Ctx


def _rate(part: float, whole: float) -> float:
    return 0.0 if not whole else part / whole


def _start(day: date) -> datetime:
    return datetime.combine(day, time(0, 0), clock.KYIV)


async def _retention(ctx: Ctx, first: date, last: date, offset: int) -> float:
    """Share of new users of the cohort active `offset` days after sign-up."""
    today = clock.kyiv_today()
    signup = cast(func.timezone("Europe/Kyiv", User.created_at), Date)
    cohort = (
        select(User.id, signup.label("day"))
        .where(signup.between(first, min(last, today - timedelta(days=offset))))
        .subquery()
    )
    size = await ctx.session.scalar(select(func.count()).select_from(cohort))
    back = await ctx.session.scalar(
        select(func.count(func.distinct(cohort.c.id)))
        .select_from(cohort)
        .join(
            UserActivityDay,
            and_(
                UserActivityDay.user_id == cohort.c.id,
                UserActivityDay.day == cohort.c.day + offset,
            ),
        )
    )
    return _rate(back or 0, size or 0)


async def metrics(ctx: Ctx, days: int) -> MetricsOut:
    """Funnel and quality for the last `days` Kyiv days."""
    last = clock.kyiv_today()
    first = last - timedelta(days=days - 1)
    since, until = _start(first), _start(last + timedelta(days=1))
    in_period = and_(User.created_at >= since, User.created_at < until)
    starts = await ctx.session.scalar(select(func.count()).where(in_period)) or 0
    completed = (
        await ctx.session.scalar(
            select(func.count()).where(in_period, User.onboarding_step == OnboardingStep.done)
        )
        or 0
    )
    like_period = and_(Like.created_at >= since, Like.created_at < until)
    likes = await ctx.session.scalar(select(func.count()).where(like_period)) or 0
    mutual = (
        await ctx.session.scalar(
            select(func.count()).where(like_period, Like.status == LikeStatus.matched)
        )
        or 0
    )
    matches = (
        await ctx.session.scalar(
            select(func.count()).where(Match.created_at >= since, Match.created_at < until)
        )
        or 0
    )
    views = (
        await ctx.session.scalar(
            select(func.count()).where(View.shown_at >= since, View.shown_at < until)
        )
        or 0
    )
    report_period = and_(Report.created_at >= since, Report.created_at < until)
    reports = (
        await ctx.session.scalar(
            select(func.count()).where(report_period, Report.reporter_id.is_not(None))
        )
        or 0
    )
    accepted = (
        await ctx.session.scalar(
            select(func.count()).where(report_period, Report.status == ReportStatus.accepted)
        )
        or 0
    )
    rejected = (
        await ctx.session.scalar(
            select(func.count()).where(report_period, Report.status == ReportStatus.rejected)
        )
        or 0
    )
    totals = await _totals(ctx, since, until)
    return MetricsOut(
        period_from=first,
        period_to=last,
        starts=starts,
        onboarding_completed=completed,
        onboarding_rate=_rate(completed, starts),
        likes_total=likes,
        matches_total=matches,
        mutual_rate=_rate(mutual, likes),
        d1_retention=await _retention(ctx, first, last, 1),
        d7_retention=await _retention(ctx, first, last, 7),
        reports_per_1000_views=_rate(reports * 1000, views),
        confirmed_reports_rate=_rate(accepted, accepted + rejected),
        reports_total=reports,
        views_total=views,
        **totals,
    )


async def _count(ctx: Ctx, *where: ColumnElement[bool]) -> int:
    return int(await ctx.session.scalar(select(func.count()).where(*where)) or 0)


async def _totals(ctx: Ctx, since: datetime, until: datetime) -> dict[str, Any]:
    """Counts right now and per-period counts added in core v5."""
    by_status = {s: 0 for s in UserStatus}
    for status, n in await ctx.session.execute(
        select(User.status, func.count()).group_by(User.status)
    ):
        by_status[status] = n
    by_pool = {p: 0 for p in Pool}
    for pool, n in await ctx.session.execute(
        select(Profile.pool, func.count()).where(Profile.pool.is_not(None)).group_by(Profile.pool)
    ):
        if pool is not None:
            by_pool[pool] = n
    today = clock.kyiv_today()

    async def active(days: int) -> int:
        return int(
            await ctx.session.scalar(
                select(func.count(func.distinct(UserActivityDay.user_id))).where(
                    UserActivityDay.day > today - timedelta(days=days)
                )
            )
            or 0
        )

    acted = and_(View.acted_at >= since, View.acted_at < until)
    return {
        "users_total": sum(by_status.values()),
        "users_by_status": by_status,
        "users_by_pool": by_pool,
        "verified_total": await _count(ctx, User.verified.is_(True)),
        "shadow_banned_total": await _count(ctx, User.shadow_banned.is_(True)),
        "bot_blocked_total": await _count(ctx, User.bot_blocked.is_(True)),
        "active_today": await active(1),
        "active_7d": await active(7),
        "active_30d": await active(30),
        "skips_total": await _count(ctx, acted, View.action == ViewAction.skip),
        "likes_with_message": await _count(
            ctx,
            Like.created_at >= since,
            Like.created_at < until,
            or_(Like.message.is_not(None), Like.media_kind.is_not(None)),
        ),
        "likes_all_time": await _count(ctx, Like.id.is_not(None)),
        "matches_all_time": await _count(ctx, Match.id.is_not(None)),
        "likes_pending": await _count(ctx, Like.status == LikeStatus.pending),
    }
