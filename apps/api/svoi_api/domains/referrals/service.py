"""Referral codes and bonuses (S14)."""

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from svoi_contracts.api.referral import ReferralOut
from svoi_contracts.constants import REFERRAL_BONUS_REACTIONS
from svoi_contracts.enums import BonusSource, UserStatus

from svoi_api.core import time
from svoi_api.db.models import ReactionBonus, User
from svoi_api.deps import Ctx


async def info(ctx: Ctx, user: User) -> ReferralOut:
    """Code and how many invited people finished onboarding."""
    invited = await ctx.session.scalar(
        select(func.count()).where(User.referred_by_id == user.id, User.status == UserStatus.active)
    )
    return ReferralOut(
        code=user.referral_code,
        invited_count=int(invited or 0),
        bonus_per_invite=REFERRAL_BONUS_REACTIONS,
    )


async def reward(ctx: Ctx, invited: User) -> None:
    """Both sides get the bonus once; the unique index stops repeats (no commit)."""
    if invited.referred_by_id is None or invited.referred_by_id == invited.id:
        return
    today = time.kyiv_today()
    for user_id in (invited.id, invited.referred_by_id):
        await ctx.session.execute(
            insert(ReactionBonus)
            .values(
                user_id=user_id,
                on_date=today,
                amount=REFERRAL_BONUS_REACTIONS,
                source=BonusSource.referral,
                source_ref=str(invited.id),
            )
            .on_conflict_do_nothing()
        )
