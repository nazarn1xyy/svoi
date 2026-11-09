"""FastAPI app factory: uvicorn svoi_api.main:create_app --factory (B0.1)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import sentry_sdk
import structlog
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from svoi_api.clients import Clients, make_clients
from svoi_api.config import Settings
from svoi_api.core import errors
from svoi_api.core.queue import ArqQueue, Queue
from svoi_api.db.session import make_engine, make_sessionmaker
from svoi_api.deps import check_token
from svoi_api.domains.catalog.router import router as catalog
from svoi_api.domains.likes.router import router as likes
from svoi_api.domains.matching.router import router as matching
from svoi_api.domains.metrics.router import router as metrics
from svoi_api.domains.moderation.router import router as moderation
from svoi_api.domains.notifications.router import router as internal
from svoi_api.domains.prefs.router import router as prefs
from svoi_api.domains.profiles.router import router as profiles
from svoi_api.domains.reactions.router import router as reactions
from svoi_api.domains.referrals.router import router as referrals
from svoi_api.domains.safety.router import router as safety
from svoi_api.domains.users.router import router as users
from svoi_api.domains.verification.router import router as verification

log = structlog.get_logger()
ROUTERS: tuple[APIRouter, ...] = (
    users,
    profiles,
    catalog,
    prefs,
    matching,
    reactions,
    likes,
    moderation,
    metrics,
    safety,
    verification,
    internal,
    referrals,
)


def create_app(
    settings: Settings | None = None,
    *,
    sessionmaker: async_sessionmaker[AsyncSession] | None = None,
    redis: Redis | None = None,
    queue: Queue | None = None,
    clients: Clients | None = None,
) -> FastAPI:
    """The API; tests pass their own session factory, Redis, queue and fakes."""
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owned: list[object] = []
        if settings.sentry_dsn:
            sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.env)
        if sessionmaker is None:
            engine = make_engine(settings.database_url)
            owned.append(engine)
            app.state.sessionmaker = make_sessionmaker(engine)
        if redis is None:
            app.state.redis = Redis.from_url(settings.redis_url)
            owned.append(app.state.redis)
        if queue is None:
            pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
            owned.append(pool)
            app.state.queue = ArqQueue(pool)
        yield
        for resource in owned:
            if hasattr(resource, "dispose"):
                await resource.dispose()
            elif hasattr(resource, "aclose"):
                await resource.aclose()

    app = FastAPI(title="Svoi API", version="1", lifespan=lifespan)
    app.state.settings = settings
    app.state.sessionmaker = sessionmaker
    app.state.redis = redis
    app.state.queue = queue
    app.state.clients = clients or make_clients(settings)
    errors.install(app)
    for router in ROUTERS:
        app.include_router(router, prefix="/v1", dependencies=[Depends(check_token)])

    @app.get("/health")
    async def health(request: Request) -> JSONResponse:
        """Database and Redis answer."""
        state = request.app.state
        try:
            async with state.sessionmaker() as session:
                await session.execute(text("SELECT 1"))
            await state.redis.ping()
        except Exception as exc:
            log.warning("health", error=str(exc))
            return JSONResponse({"status": "down"}, status_code=503)
        return JSONResponse({"status": "ok"})

    return app
