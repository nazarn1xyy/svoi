"""HTTP: /admin/metrics (S10b)."""

from typing import Annotated

from fastapi import APIRouter, Query
from svoi_contracts.api.admin import MetricsOut

from svoi_api.deps import AdminUser, CtxDep
from svoi_api.domains.metrics import service

router = APIRouter(tags=["metrics"])


@router.get("/admin/metrics")
async def metrics(
    ctx: CtxDep, admin: AdminUser, days: Annotated[int, Query(ge=1, le=90)] = 7
) -> MetricsOut:
    """Product metrics."""
    return await service.metrics(ctx, days)
