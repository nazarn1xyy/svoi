"""HTTP: /reactions, /limits (S8)."""

from fastapi import APIRouter
from svoi_contracts.api.feed import FeedItem
from svoi_contracts.api.reactions import ReactionIn, ReactionOut
from svoi_contracts.cards import Limits

from svoi_api.deps import CtxDep, CurrentUser
from svoi_api.domains.reactions import service

router = APIRouter(tags=["reactions"])


@router.post("/reactions")
async def react(body: ReactionIn, ctx: CtxDep, user: CurrentUser) -> ReactionOut:
    """Like, like with a message, skip."""
    return await service.react(ctx, user, body)


@router.post("/reactions/undo")
async def undo(ctx: CtxDep, user: CurrentUser) -> FeedItem:
    """Bring the last skip back."""
    return await service.undo(ctx, user)


@router.get("/limits")
async def limits(ctx: CtxDep, user: CurrentUser) -> Limits:
    """Reactions and messages left today."""
    return await service.limits(ctx, user)
