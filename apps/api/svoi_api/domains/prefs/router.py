"""HTTP: /filters, /settings (S6)."""

from fastapi import APIRouter
from svoi_contracts.api.prefs import FiltersIn, FiltersOut, SettingsIn, SettingsOut

from svoi_api.deps import CtxDep, CurrentUser
from svoi_api.domains.prefs import service

router = APIRouter(tags=["prefs"])


@router.get("/filters")
async def get_filters(ctx: CtxDep, user: CurrentUser) -> FiltersOut:
    """Feed filters."""
    return await service.get_filters(ctx, user)


@router.put("/filters")
async def set_filters(body: FiltersIn, ctx: CtxDep, user: CurrentUser) -> FiltersOut:
    """Save feed filters."""
    return await service.set_filters(ctx, user, body)


@router.get("/settings")
async def get_settings(ctx: CtxDep, user: CurrentUser) -> SettingsOut:
    """Notification and privacy settings."""
    return await service.get_settings(ctx, user)


@router.put("/settings")
async def set_settings(body: SettingsIn, ctx: CtxDep, user: CurrentUser) -> SettingsOut:
    """Save settings."""
    return await service.set_settings(ctx, user, body)
