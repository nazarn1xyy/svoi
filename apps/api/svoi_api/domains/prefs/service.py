"""Filters and settings (S6)."""

from datetime import time

from sqlalchemy import select
from svoi_contracts.api.prefs import FiltersIn, FiltersOut, SettingsIn, SettingsOut
from svoi_contracts.constants import QUIET_HOURS_DEFAULT
from svoi_contracts.enums import GenderFilter, NotifyFrequency, Pool, RadiusMode, RebuildReason
from svoi_contracts.errors import ErrorCode
from svoi_contracts.jobs import RebuildFeed

from svoi_api.core import time as clock
from svoi_api.core.errors import DomainError
from svoi_api.db.models import Filters, Profile, Settings, User
from svoi_api.deps import Ctx
from svoi_api.domains.profiles.rules import POOL_BOUNDS, default_age_range

KM_RADII = frozenset({RadiusMode.km25, RadiusMode.km50, RadiusMode.km100})


async def ensure_defaults(ctx: Ctx, user_id: int) -> None:
    """Default filters (age ±3 within the pool) and settings, once (no commit)."""
    profile = await ctx.session.get(Profile, user_id)
    if await ctx.session.get(Filters, user_id) is None and profile and profile.age:
        low, high = default_age_range(profile.age)
        ctx.session.add(
            Filters(
                user_id=user_id,
                age_min=low,
                age_max=high,
                gender=GenderFilter.all,
                radius=RadiusMode.city,
                verified_only=False,
            )
        )
    if await ctx.session.get(Settings, user_id) is None:
        ctx.session.add(
            Settings(
                user_id=user_id,
                notify_frequency=NotifyFrequency.instant,
                quiet_from=time.fromisoformat(QUIET_HOURS_DEFAULT[0]),
                quiet_to=time.fromisoformat(QUIET_HOURS_DEFAULT[1]),
                tz="Europe/Kyiv",
                show_distance=True,
                show_institution=True,
            )
        )
    await ctx.session.flush()


async def _pool(ctx: Ctx, user_id: int) -> Pool:
    pool = await ctx.session.scalar(select(Profile.pool).where(Profile.user_id == user_id))
    if pool is None:
        raise DomainError(ErrorCode.profile_incomplete, {"missing": ["age"]})
    return pool


async def _filters(ctx: Ctx, user: User) -> Filters:
    await ensure_defaults(ctx, user.id)
    row = await ctx.session.get(Filters, user.id)
    if row is None:
        raise DomainError(ErrorCode.profile_incomplete, {"missing": ["age"]})
    return row


def filters_out(row: Filters, pool: Pool) -> FiltersOut:
    """Contract view with the pool's age bounds."""
    return FiltersOut(
        age_min=row.age_min,
        age_max=row.age_max,
        age_bounds=POOL_BOUNDS[pool],
        gender=row.gender,
        radius=row.radius,
        verified_only=row.verified_only,
    )


async def get_filters(ctx: Ctx, user: User) -> FiltersOut:
    """Current feed filters."""
    row = await _filters(ctx, user)
    await ctx.session.commit()
    return filters_out(row, await _pool(ctx, user.id))


async def rebuild(ctx: Ctx, user_id: int, reason: RebuildReason) -> None:
    """Queue a feed rebuild (dedupe per minute)."""
    stamp = clock.now().strftime("%Y%m%d%H%M")
    job = RebuildFeed(
        dedupe_key=f"feed:{user_id}:{reason.value}:{stamp}", user_id=user_id, reason=reason
    )
    await ctx.queue.enqueue(job, "api")


async def set_radius(ctx: Ctx, user: User, radius: RadiusMode) -> None:
    """Change only the radius (feed expand); km radii need a location."""
    row = await _filters(ctx, user)
    if radius in KM_RADII:
        geo = await ctx.session.scalar(select(Profile.geo).where(Profile.user_id == user.id))
        if geo is None:
            raise DomainError(ErrorCode.validation_error, {"reason": "no_geo"})
    row.radius = radius
    await ctx.session.commit()


async def set_filters(ctx: Ctx, user: User, body: FiltersIn) -> FiltersOut:
    """Age within the pool, min <= max; km radius needs geo."""
    pool = await _pool(ctx, user.id)
    low, high = POOL_BOUNDS[pool]
    if not low <= body.age_min <= body.age_max <= high:
        raise DomainError(ErrorCode.validation_error, message="age range outside the pool")
    row = await _filters(ctx, user)
    if body.radius in KM_RADII:
        geo = await ctx.session.scalar(select(Profile.geo).where(Profile.user_id == user.id))
        if geo is None:
            raise DomainError(ErrorCode.validation_error, {"reason": "no_geo"})
    row.age_min, row.age_max = body.age_min, body.age_max
    row.gender, row.radius, row.verified_only = body.gender, body.radius, body.verified_only
    await ctx.session.commit()
    await rebuild(ctx, user.id, RebuildReason.filters_changed)
    return filters_out(row, pool)


async def settings_row(ctx: Ctx, user_id: int) -> Settings:
    """Settings, created with defaults if missing."""
    await ensure_defaults(ctx, user_id)
    row = await ctx.session.get(Settings, user_id)
    if row is None:
        raise RuntimeError("row is missing")
    return row


def settings_out(row: Settings) -> SettingsOut:
    """Contract view."""
    return SettingsOut(
        notify_frequency=row.notify_frequency,
        quiet_from=row.quiet_from,
        quiet_to=row.quiet_to,
        show_distance=row.show_distance,
        show_institution=row.show_institution,
    )


async def get_settings(ctx: Ctx, user: User) -> SettingsOut:
    """Notifications and privacy."""
    row = await settings_row(ctx, user.id)
    await ctx.session.commit()
    return settings_out(row)


async def set_settings(ctx: Ctx, user: User, body: SettingsIn) -> SettingsOut:
    """Save; quiet_from == quiet_to means no quiet hours."""
    row = await settings_row(ctx, user.id)
    row.notify_frequency = body.notify_frequency
    row.quiet_from, row.quiet_to = body.quiet_from, body.quiet_to
    row.show_distance, row.show_institution = body.show_distance, body.show_institution
    await ctx.session.commit()
    return settings_out(row)
