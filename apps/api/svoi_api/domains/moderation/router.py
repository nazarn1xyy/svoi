"""HTTP: /reports, /blocks, /admin/* (S10)."""

from fastapi import APIRouter, Response
from svoi_contracts.api.admin import AdminActionIn, AdminQueueItem, AdminUserOut
from svoi_contracts.api.moderation import BlockIn, ReportIn
from svoi_contracts.enums import AdminQueueKind

from svoi_api.deps import AdminUser, CtxDep, CurrentUser
from svoi_api.domains.moderation import service

router = APIRouter(tags=["moderation"])


@router.post("/reports", status_code=204)
async def report(body: ReportIn, ctx: CtxDep, user: CurrentUser) -> Response:
    """Report a user."""
    await service.report(ctx, user, body)
    return Response(status_code=204)


@router.post("/blocks", status_code=204)
async def block(body: BlockIn, ctx: CtxDep, user: CurrentUser) -> Response:
    """Block a user."""
    await service.block(ctx, user, body.target_id)
    return Response(status_code=204)


@router.delete("/blocks/{target_id}", status_code=204)
async def unblock(target_id: int, ctx: CtxDep, user: CurrentUser) -> Response:
    """Unblock."""
    await service.unblock(ctx, user, target_id)
    return Response(status_code=204)


@router.get("/admin/queue")
async def queue(kind: AdminQueueKind, ctx: CtxDep, admin: AdminUser) -> AdminQueueItem | None:
    """Next item of a moderation queue."""
    return await service.next_item(ctx, admin, kind)


@router.get("/admin/queue/stats")
async def queue_stats(ctx: CtxDep, admin: AdminUser) -> dict[AdminQueueKind, int]:
    """Queue sizes."""
    return await service.stats(ctx)


@router.post("/admin/actions", status_code=204)
async def action(body: AdminActionIn, ctx: CtxDep, admin: AdminUser) -> Response:
    """Moderator decision."""
    await service.act(ctx, admin, body)
    return Response(status_code=204)


@router.get("/admin/users/{tg_id}")
async def user_info(tg_id: int, ctx: CtxDep, admin: AdminUser) -> AdminUserOut:
    """User lookup."""
    return await service.user_info(ctx, admin, tg_id)
