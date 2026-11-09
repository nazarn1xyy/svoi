"""Round-video verification (S12)."""

import secrets

from sqlalchemy import select
from svoi_contracts.api.verification import GestureOut, VerificationOut
from svoi_contracts.enums import GestureCode, MediaKind, ModerationStatus
from svoi_contracts.errors import ErrorCode

from svoi_api.core.errors import DomainError
from svoi_api.db.models import Media, User, Verification
from svoi_api.deps import Ctx


async def _latest(ctx: Ctx, user_id: int) -> Verification | None:
    return await ctx.session.scalar(
        select(Verification)
        .where(Verification.user_id == user_id)
        .order_by(Verification.created_at.desc(), Verification.id.desc())
        .limit(1)
    )


async def start(ctx: Ctx, user: User) -> GestureOut:
    """Random gesture; conflicts: already_verified, pending, no_photo."""
    if user.verified:
        raise DomainError(ErrorCode.conflict, {"reason": "already_verified"})
    last = await _latest(ctx, user.id)
    if last and last.status is ModerationStatus.pending and last.video_note_file_id:
        raise DomainError(ErrorCode.conflict, {"reason": "pending"})
    photo = await ctx.session.scalar(
        select(Media.id).where(
            Media.user_id == user.id,
            Media.kind == MediaKind.photo,
            Media.moderation_status == ModerationStatus.approved,
        )
    )
    if photo is None:
        raise DomainError(ErrorCode.conflict, {"reason": "no_photo"})
    gesture = secrets.choice(list(GestureCode))
    v = Verification(user_id=user.id, gesture=gesture, status=ModerationStatus.pending)
    ctx.session.add(v)
    await ctx.session.commit()
    return GestureOut(verification_id=v.id, gesture=gesture)


async def submit(ctx: Ctx, user: User, verification_id: int, file_id: str) -> VerificationOut:
    """Attach the round video; goes to the verifications queue."""
    v = await ctx.session.get(Verification, verification_id)
    if v is None or v.user_id != user.id:
        raise DomainError(ErrorCode.not_found)
    if v.video_note_file_id is not None or v.status is not ModerationStatus.pending:
        raise DomainError(ErrorCode.conflict, message="already submitted")
    v.video_note_file_id = file_id
    await ctx.session.commit()
    return VerificationOut(status=ModerationStatus.pending)


async def status(ctx: Ctx, user: User) -> VerificationOut:
    """None when never submitted."""
    if user.verified:
        return VerificationOut(status=ModerationStatus.approved)
    last = await _latest(ctx, user.id)
    if last is None or last.video_note_file_id is None:
        return VerificationOut(status=None)
    return VerificationOut(status=last.status)
