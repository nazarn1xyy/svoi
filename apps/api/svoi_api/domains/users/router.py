"""HTTP: /users/*, /onboarding/* (S1, S4 complete, S5 delete)."""

from fastapi import APIRouter, Response
from svoi_contracts.api.profile import SkipIn
from svoi_contracts.api.users import LangIn, StartIn
from svoi_contracts.cards import UserState

from svoi_api.deps import AnyUser, CtxDep, CurrentUser, TgId
from svoi_api.domains.users import service

router = APIRouter(tags=["users"])


@router.post("/users/start")
async def start(body: StartIn, ctx: CtxDep, tg_id: TgId) -> UserState:
    """Register or come back."""
    return await service.start(ctx, tg_id, body)


@router.get("/users/me")
async def me(ctx: CtxDep, user: AnyUser) -> UserState:
    """Current state; banned users get it too."""
    return await service.state(ctx, user)


@router.put("/users/me/lang")
async def set_lang(body: LangIn, ctx: CtxDep, user: CurrentUser) -> UserState:
    """Language."""
    return await service.set_lang(ctx, user, body.lang)


@router.post("/users/me/consent")
async def consent(ctx: CtxDep, user: CurrentUser) -> UserState:
    """Accept the rules."""
    return await service.consent(ctx, user)


@router.post("/onboarding/skip")
async def skip(body: SkipIn, ctx: CtxDep, user: CurrentUser) -> UserState:
    """Skip an optional step."""
    return await service.skip(ctx, user, body.step)


@router.post("/onboarding/complete")
async def complete(ctx: CtxDep, user: CurrentUser) -> UserState:
    """Finish onboarding."""
    return await service.complete(ctx, user)


@router.delete("/users/me", status_code=204)
async def delete_me(ctx: CtxDep, user: CurrentUser) -> Response:
    """Delete all user data."""
    await service.delete_me(ctx, user)
    return Response(status_code=204)
