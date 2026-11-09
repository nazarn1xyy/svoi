"""HTTP: /feed/* (S7)."""

from fastapi import APIRouter
from svoi_contracts.api.feed import ExpandIn, FeedResponse

from svoi_api.deps import CtxDep, CurrentUser
from svoi_api.domains.matching import service

router = APIRouter(prefix="/feed", tags=["matching"])


@router.get("/next", response_model=FeedResponse)
async def feed_next(ctx: CtxDep, user: CurrentUser) -> FeedResponse:
    """Next card."""
    return await service.feed_next(ctx, user)


@router.post("/expand", response_model=FeedResponse)
async def expand(body: ExpandIn, ctx: CtxDep, user: CurrentUser) -> FeedResponse:
    """Wider search."""
    return await service.expand(ctx, user, body.radius)
