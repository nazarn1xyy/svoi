"""HTTP: /catalog/* (S2-S4)."""

from typing import Annotated

from fastapi import APIRouter, Query
from svoi_contracts.api.catalog import (
    CategoryOut,
    CityOut,
    CustomInterestIn,
    CustomInterestOut,
    GoalOut,
    InstitutionOut,
    InterestOut,
    PromptOut,
)

from svoi_api.deps import CtxDep, CurrentUser
from svoi_api.domains.catalog import service

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/cities/search")
async def search_cities(
    q: str, ctx: CtxDep, user: CurrentUser, limit: Annotated[int, Query(ge=1, le=20)] = 5
) -> list[CityOut]:
    """City by text."""
    return await service.search_cities(ctx, user, q, limit)


@router.get("/cities/by-location")
async def city_by_location(lat: float, lon: float, ctx: CtxDep, user: CurrentUser) -> CityOut:
    """City by coordinates."""
    return await service.city_by_location(ctx, user, lat, lon)


@router.get("/goals")
async def goals(user: CurrentUser) -> list[GoalOut]:
    """Goals."""
    return service.goals(user)


@router.get("/interest-categories")
async def categories(ctx: CtxDep, user: CurrentUser) -> list[CategoryOut]:
    """Interest categories."""
    return await service.categories(ctx, user)


@router.get("/interests")
async def interests(category_id: int, ctx: CtxDep, user: CurrentUser) -> list[InterestOut]:
    """Tags of a category."""
    return await service.interests(ctx, user, category_id)


@router.post("/interests/custom")
async def custom_interest(
    body: CustomInterestIn, ctx: CtxDep, user: CurrentUser
) -> CustomInterestOut:
    """Own tag."""
    return await service.custom_interest(ctx, user, body.title)


@router.get("/institutions/search")
async def search_institutions(
    city_id: int,
    ctx: CtxDep,
    user: CurrentUser,
    q: str = "",
    limit: Annotated[int, Query(ge=1, le=20)] = 8,
) -> list[InstitutionOut]:
    """Institutions of a city."""
    return await service.search_institutions(ctx, city_id, q, limit)


@router.get("/prompts")
async def prompts(ctx: CtxDep, user: CurrentUser) -> list[PromptOut]:
    """Prompts."""
    return await service.prompts(ctx, user)
