"""HTTP: /profile/* (S1-S5)."""

from fastapi import APIRouter
from svoi_contracts.api.profile import (
    AgeIn,
    CityIn,
    ClarificationOut,
    GenderIn,
    GoalsIn,
    HeightIn,
    InstitutionIn,
    InterestsIn,
    MediaIn,
    MediaOrderIn,
    NameIn,
    NoteIn,
    PromptsIn,
)
from svoi_contracts.cards import MediaRef, ProfileCard, UserState

from svoi_api.deps import CtxDep, CurrentUser
from svoi_api.domains.profiles import service

router = APIRouter(prefix="/profile", tags=["profiles"])


@router.put("/age")
async def set_age(body: AgeIn, ctx: CtxDep, user: CurrentUser) -> UserState:
    """Age."""
    return await service.set_age(ctx, user, body.age)


@router.put("/name")
async def set_name(body: NameIn, ctx: CtxDep, user: CurrentUser) -> UserState:
    """Name."""
    return await service.set_name(ctx, user, body.name)


@router.put("/gender")
async def set_gender(body: GenderIn, ctx: CtxDep, user: CurrentUser) -> UserState:
    """Gender."""
    return await service.set_gender(ctx, user, body.gender)


@router.put("/city")
async def set_city(body: CityIn, ctx: CtxDep, user: CurrentUser) -> UserState:
    """City and optional location."""
    return await service.set_city(ctx, user, body)


@router.put("/goals")
async def set_goals(body: GoalsIn, ctx: CtxDep, user: CurrentUser) -> UserState:
    """Goals."""
    return await service.set_goals(ctx, user, body.codes)


@router.put("/interests")
async def set_interests(body: InterestsIn, ctx: CtxDep, user: CurrentUser) -> UserState:
    """Interests."""
    return await service.set_interests(ctx, user, body.interest_ids)


@router.get("/clarifications")
async def clarifications(ctx: CtxDep, user: CurrentUser) -> list[ClarificationOut]:
    """Open clarification questions."""
    return await service.clarifications(ctx, user)


@router.put("/interests/{interest_id}/note")
async def set_note(interest_id: int, body: NoteIn, ctx: CtxDep, user: CurrentUser) -> UserState:
    """Clarification answer."""
    return await service.set_note(ctx, user, interest_id, body.option_key)


@router.put("/institution")
async def set_institution(body: InstitutionIn, ctx: CtxDep, user: CurrentUser) -> UserState:
    """Institution."""
    return await service.set_institution(ctx, user, body.institution_id)


@router.put("/height")
async def set_height(body: HeightIn, ctx: CtxDep, user: CurrentUser) -> UserState:
    """Height."""
    return await service.set_height(ctx, user, body.height_cm)


@router.put("/prompts")
async def set_prompts(body: PromptsIn, ctx: CtxDep, user: CurrentUser) -> UserState:
    """Prompt answers."""
    return await service.set_prompts(ctx, user, body)


@router.post("/media")
async def add_media(body: MediaIn, ctx: CtxDep, user: CurrentUser) -> MediaRef:
    """Add a photo or video."""
    return await service.add_media(ctx, user, body)


@router.put("/media/order")
async def reorder_media(body: MediaOrderIn, ctx: CtxDep, user: CurrentUser) -> list[MediaRef]:
    """Reorder media."""
    return await service.reorder_media(ctx, user, body.ids)


@router.delete("/media/{media_id}")
async def delete_media(media_id: int, ctx: CtxDep, user: CurrentUser) -> UserState:
    """Delete media."""
    return await service.delete_media(ctx, user, media_id)


@router.get("/me/card")
async def my_card(ctx: CtxDep, user: CurrentUser) -> ProfileCard:
    """Own card."""
    return await service.my_card(ctx, user)


@router.post("/reset")
async def reset(ctx: CtxDep, user: CurrentUser) -> UserState:
    """Fill in again."""
    return await service.reset(ctx, user)


@router.post("/hide")
async def hide(ctx: CtxDep, user: CurrentUser) -> UserState:
    """Hide from the feed."""
    return await service.hide(ctx, user)


@router.post("/unhide")
async def unhide(ctx: CtxDep, user: CurrentUser) -> UserState:
    """Back to the feed."""
    return await service.unhide(ctx, user)
