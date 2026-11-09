"""api.moderate_photo: NSFW score and duplicate check of a new photo (S4)."""

from arq import Retry
from sqlalchemy import select
from svoi_contracts.constants import NSFW_REJECT, NSFW_REVIEW, PHASH_DUP_DISTANCE
from svoi_contracts.enums import ModerationResultKind, ModerationStatus
from svoi_contracts.jobs import ModeratePhoto

from svoi_api.clients._faults import ClientError
from svoi_api.clients.hasher import distance
from svoi_api.db.models import Media, User
from svoi_api.deps import Ctx

RETRY_STEP_S = 10


async def _duplicate(ctx: Ctx, media: Media, phash: str) -> bool:
    others = await ctx.session.scalars(
        select(Media.phash).where(Media.user_id != media.user_id, Media.phash.is_not(None))
    )
    return any(distance(phash, h) <= PHASH_DUP_DISTANCE for h in others if h)


async def moderate_photo(ctx: Ctx, job: ModeratePhoto, attempt: int = 1) -> str:
    """Idempotent: a scored or decided photo is skipped."""
    from svoi_api.domains.notifications import service as notify  # noqa: PLC0415
    from svoi_api.domains.profiles import service as profiles  # noqa: PLC0415
    from svoi_api.domains.safety import service as safety  # noqa: PLC0415

    media = await ctx.session.get(Media, job.media_id)
    if media is None or media.moderation_status is not ModerationStatus.pending:
        return "skipped"
    if media.nsfw_score is not None:
        return "skipped"
    try:
        image = await ctx.clients.files.download(media.file_id)
        score = await ctx.clients.nsfw.score(image)
    except ClientError as exc:
        raise Retry(defer=RETRY_STEP_S * attempt) from exc
    phash = ctx.clients.hasher.phash(image)
    duplicate = await _duplicate(ctx, media, phash)
    media.phash, media.nsfw_score = phash, score
    user = await ctx.session.get(User, media.user_id)
    if user is None:
        raise RuntimeError("user is missing")
    outcome = "review"
    if score >= NSFW_REJECT:
        media.moderation_status = ModerationStatus.rejected
        outcome = "rejected"
    elif score < NSFW_REVIEW and not duplicate:
        media.moderation_status = ModerationStatus.approved
        outcome = "approved"
    if duplicate:
        await safety.add_risk(ctx, user, safety.RISK_PHASH_DUP)
    await ctx.session.commit()
    if outcome == "rejected":
        await notify.moderation_result(
            ctx, user, ModerationResultKind.media_rejected, key=f"mod:photos:{media.id}:reject"
        )
    await profiles.profile_changed(ctx, user.id, rebuild=outcome == "approved")
    return outcome
