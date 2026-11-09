"""api.tags_recalc_idf: rarer interests weigh more in scoring (S7)."""

import math

from sqlalchemy import func, select, update

from svoi_api.db.models import Interest, ProfileInterest, User
from svoi_api.deps import Ctx


async def recalc_idf(ctx: Ctx) -> int:
    """idf = ln((N + 1) / (n + 1)) + 1; same result on every run."""
    total = int(await ctx.session.scalar(select(func.count()).select_from(User)) or 0)
    counts = dict(
        (
            await ctx.session.execute(
                select(ProfileInterest.interest_id, func.count()).group_by(
                    ProfileInterest.interest_id
                )
            )
        ).tuples()
    )
    ids = list(await ctx.session.scalars(select(Interest.id)))
    for iid in ids:
        idf = math.log((total + 1) / (counts.get(iid, 0) + 1)) + 1
        await ctx.session.execute(update(Interest).where(Interest.id == iid).values(idf=idf))
    await ctx.session.commit()
    return len(ids)
