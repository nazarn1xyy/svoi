"""HTTP: /referral (S14)."""

from fastapi import APIRouter
from svoi_contracts.api.referral import ReferralOut

from svoi_api.deps import CtxDep, CurrentUser
from svoi_api.domains.referrals import service

router = APIRouter(tags=["referrals"])


@router.get("/referral")
async def referral(ctx: CtxDep, user: CurrentUser) -> ReferralOut:
    """Invite link data."""
    return await service.info(ctx, user)
