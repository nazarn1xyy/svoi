"""HTTP: /internal/* for bot-worker (S13)."""

from fastapi import APIRouter, Response

from svoi_api.deps import CtxDep
from svoi_api.domains.notifications import service

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/users/{tg_id}/bot-blocked", status_code=204)
async def bot_blocked(tg_id: int, ctx: CtxDep) -> Response:
    """The user blocked the bot."""
    await service.bot_blocked(ctx, tg_id)
    return Response(status_code=204)


@router.post("/notifications/{dedupe_key}/sent", status_code=204)
async def sent(dedupe_key: str, ctx: CtxDep) -> Response:
    """Notification delivered."""
    await service.mark_sent(ctx, dedupe_key)
    return Response(status_code=204)
