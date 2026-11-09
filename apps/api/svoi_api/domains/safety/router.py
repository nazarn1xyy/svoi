"""HTTP: /users/me/captcha (S11b)."""

from fastapi import APIRouter
from svoi_contracts.api.safety import CaptchaAnswerIn, CaptchaChallenge
from svoi_contracts.cards import UserState

from svoi_api.deps import CtxDep, CurrentUser
from svoi_api.domains.safety import service

router = APIRouter(prefix="/users/me/captcha", tags=["safety"])


@router.post("")
async def new_captcha(ctx: CtxDep, user: CurrentUser) -> CaptchaChallenge:
    """Issue a captcha."""
    return await service.new_captcha(ctx, user)


@router.post("/verify")
async def verify(body: CaptchaAnswerIn, ctx: CtxDep, user: CurrentUser) -> UserState:
    """Check the answer."""
    return await service.verify_captcha(ctx, user, body.challenge_id, body.answer)
