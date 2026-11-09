"""Product metrics for /metrics (S10b)."""

from datetime import date, datetime, time, timedelta

from sqlalchemy import Date, and_, cast, func, select
from svoi_contracts.api.admin import MetricsOut
from svoi_contracts.enums import LikeStatus, OnboardingStep, ReportStatus

from svoi_api.core import time as clock
from svoi_api.db.models import Like, Match, Report, User, UserActivityDay, View
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
    )
