"""HTTP: /verification/* (S12)."""

from fastapi import APIRouter
from svoi_contracts.api.verification import GestureOut, VerificationIn, VerificationOut

from svoi_api.deps import CtxDep, CurrentUser
from svoi_api.domains.verification import service

router = APIRouter(prefix="/verification", tags=["verification"])


@router.post("/start")
async def start(ctx: CtxDep, user: CurrentUser) -> GestureOut:
    """Get a gesture."""
    return await service.start(ctx, user)


@router.post("/submit")
async def submit(body: VerificationIn, ctx: CtxDep, user: CurrentUser) -> VerificationOut:
    """Send the round video."""
    return await service.submit(ctx, user, body.verification_id, body.video_note_file_id)


@router.get("/status")
async def status(ctx: CtxDep, user: CurrentUser) -> VerificationOut:
    """Verification status."""
    return await service.status(ctx, user)
