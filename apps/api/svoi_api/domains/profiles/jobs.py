"""api.age_tick: +1 year on the anniversary of age_set_at (S5)."""

from sqlalchemy import extract, or_, select, update
from svoi_contracts.constants import AGE_MAX
from svoi_contracts.enums import Pool

from svoi_api.core import time
from svoi_api.db.models import Filters, Profile
from svoi_api.deps import Ctx
from svoi_api.domains.profiles.rules import POOL_BOUNDS, pool_for


async def age_tick(ctx: Ctx) -> int:
    """Idempotent: age_incremented_on = today blocks a second run."""
    today = time.kyiv_today()
    rows = list(
        await ctx.session.scalars(
            select(Profile).where(
                Profile.age.is_not(None),
                Profile.age < AGE_MAX,
                Profile.age_set_at.is_not(None),
                extract("month", Profile.age_set_at) == today.month,
                extract("day", Profile.age_set_at) == today.day,
                Profile.age_set_at < today,
                or_(Profile.age_incremented_on.is_(None), Profile.age_incremented_on != today),
            )
        )
    )
    for p in rows:
        if p.age is None:
            raise RuntimeError("p.age is missing")
        was = p.pool
        p.age += 1
        p.pool = pool_for(p.age)
        p.age_incremented_on = today
        if was is Pool.minor and p.pool is Pool.adult:
            low, high = POOL_BOUNDS[Pool.adult]
            await ctx.session.execute(
                update(Filters)
                .where(Filters.user_id == p.user_id)
                .values(age_min=low, age_max=min(high, p.age + 3))
            )
            await ctx.redis.delete(f"feed:batch:{p.user_id}", f"feed:seen:{p.user_id}")
    await ctx.session.commit()
    return len(rows)
