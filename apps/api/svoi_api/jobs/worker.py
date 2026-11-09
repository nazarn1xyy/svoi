"""arq worker of the `api` queue: arq svoi_api.jobs.worker.WorkerSettings (B0.2)."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, ClassVar, cast

import structlog
from arq import cron
from arq.connections import ArqRedis, RedisSettings
from arq.typing import WorkerCoroutine
from arq.worker import Function, func
from pydantic import ValidationError
from svoi_contracts.jobs import DemoPing, JobBase, ModeratePhoto, RebuildFeed

from svoi_api.clients import make_clients
from svoi_api.config import Settings
from svoi_api.core.queue import ArqQueue
from svoi_api.core.time import KYIV
from svoi_api.db.session import make_engine, make_sessionmaker
from svoi_api.deps import Ctx
from svoi_api.domains.likes import service as likes
from svoi_api.domains.matching import service as matching
from svoi_api.domains.moderation import jobs as moderation_jobs
from svoi_api.domains.notifications import service as notifications

log = structlog.get_logger()
QUEUE = "api"
MAX_TRIES = 5


@asynccontextmanager
async def job_ctx(ctx: dict[str, Any]) -> AsyncIterator[Ctx]:
    """A fresh DB session per job, shared Redis, queue and clients."""
    async with ctx["sessionmaker"]() as session:
        yield Ctx(session, ctx["redis"], ctx["queue"], ctx["settings"], ctx["clients"])


def _parse[J: JobBase](kind: type[J], payload: dict[str, Any]) -> J | None:
    try:
        return kind.model_validate(payload)
    except ValidationError:
        log.error("invalid payload", topic=kind.topic)  # no retry for garbage
        return None


async def moderate_photo(ctx: dict[str, Any], payload: dict[str, Any]) -> str:
    """api.moderate_photo."""
    job = _parse(ModeratePhoto, payload)
    if job is None:
        return "invalid"
    async with job_ctx(ctx) as c:
        return await moderation_jobs.moderate_photo(c, job, ctx.get("job_try", 1))


async def rebuild_feed(ctx: dict[str, Any], payload: dict[str, Any]) -> str:
    """api.rebuild_feed."""
    job = _parse(RebuildFeed, payload)
    if job is None:
        return "invalid"
    async with job_ctx(ctx) as c:
        await matching.rebuild_job(c, job.user_id)
    return "ok"


async def demo(ctx: dict[str, Any], payload: dict[str, Any]) -> str:
    """Skeleton check: forward the ping to the bot queue (local and test only)."""
    job = _parse(DemoPing, payload)
    if job is None:
        return "invalid"
    await ctx["queue"].enqueue(job, "bot")
    return "forwarded"


def _cron(fn: Callable[[Ctx], Awaitable[Any]]) -> WorkerCoroutine:
    async def run(ctx: dict[str, Any]) -> Any:
        async with job_ctx(ctx) as c:
            return await fn(c)

    run.__qualname__ = run.__name__ = fn.__name__
    return cast(WorkerCoroutine, run)


async def _age_tick(c: Ctx) -> int:
    from svoi_api.domains.profiles import jobs as profile_jobs  # noqa: PLC0415

    return await profile_jobs.age_tick(c)


async def _recalc_idf(c: Ctx) -> int:
    from svoi_api.domains.catalog import jobs as catalog_jobs  # noqa: PLC0415

    return await catalog_jobs.recalc_idf(c)


async def startup(ctx: dict[str, Any]) -> None:
    """Engine, Redis, queue and clients once per process."""
    settings: Settings = ctx.get("settings") or Settings()
    ctx["settings"] = settings
    ctx["engine"] = make_engine(settings.database_url)
    ctx["sessionmaker"] = make_sessionmaker(ctx["engine"])
    arq_redis: ArqRedis = ctx["redis"]  # a redis.asyncio.Redis: domains use it directly
    ctx["queue"] = ArqQueue(arq_redis)
    ctx["clients"] = make_clients(settings)


async def shutdown(ctx: dict[str, Any]) -> None:
    """Close the DB pool (arq closes Redis)."""
    await ctx["engine"].dispose()


_settings = Settings()
_functions: list[Function] = [
    func(moderate_photo, name=ModeratePhoto.topic, max_tries=MAX_TRIES),
    func(rebuild_feed, name=RebuildFeed.topic, max_tries=MAX_TRIES),
]
if _settings.env in ("local", "test"):
    _functions.append(func(demo, name="api.demo", max_tries=1))


class WorkerSettings:
    """arq settings; crons from docs/tech.md section 8 (Europe/Kyiv)."""

    queue_name = QUEUE
    functions: ClassVar[list[Function]] = _functions
    cron_jobs: ClassVar[list[Any]] = [
        cron(
            _cron(notifications.notify_schedule),
            name="api.notify_schedule",
            minute=set(range(0, 60, 5)),
        ),
        cron(_cron(likes.expire_likes), name="api.likes_expire", hour={3}, minute={0}),
        cron(_cron(_recalc_idf), name="api.tags_recalc_idf", hour={4}, minute={0}),
        cron(_cron(_age_tick), name="api.age_tick", hour={0}, minute={10}),
        cron(_cron(notifications.reminders_scan), name="api.reminders_scan", minute={0}),
        cron(
            _cron(notifications.new_people_scan), name="api.new_people_scan", hour={18}, minute={0}
        ),
    ]
    timezone = KYIV
    on_startup = startup
    on_shutdown = shutdown
    max_tries = MAX_TRIES
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
