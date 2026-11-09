"""HTTP: /likes/*, /matches/*, /contacts (S9)."""

from typing import Annotated

from fastapi import APIRouter, Query, Response
from svoi_contracts.api.likes import (
    ContactOut,
    CountOut,
    IncomingResponse,
    RespondIn,
    RespondOut,
)
from svoi_contracts.cards import MatchResult, Page

from svoi_api.deps import CtxDep, CurrentUser
from svoi_api.domains.likes import service

router = APIRouter(tags=["likes"])


@router.get("/likes/incoming/count")
async def incoming_count(ctx: CtxDep, user: CurrentUser) -> CountOut:
    """How many people liked me."""
    return CountOut(count=await service.incoming_count(ctx, user.id))


@router.get("/likes/incoming/next", response_model=IncomingResponse)
async def incoming_next(ctx: CtxDep, user: CurrentUser) -> IncomingResponse:
    """Next incoming like."""
    return await service.incoming_next(ctx, user)


@router.post("/likes/{like_id}/respond")
async def respond(like_id: int, body: RespondIn, ctx: CtxDep, user: CurrentUser) -> RespondOut:
    """Accept or decline."""
    return await service.respond(ctx, user, like_id, body.decision)


@router.get("/matches/{match_id}")
async def get_match(match_id: int, ctx: CtxDep, user: CurrentUser) -> MatchResult:
    """Match details."""
    return await service.get_match(ctx, user, match_id)


@router.get("/contacts")
async def contacts(
    ctx: CtxDep,
    user: CurrentUser,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> Page[ContactOut]:
    """Mutual likes."""
    return await service.contacts(ctx, user, cursor, limit)


@router.delete("/contacts/{match_id}", status_code=204)
async def delete_contact(match_id: int, ctx: CtxDep, user: CurrentUser) -> Response:
    """Remove a contact."""
    await service.delete_contact(ctx, user, match_id)
    return Response(status_code=204)
