"""arq worker of the `bot` queue: arq worker svoi_bot.workers.main.WorkerSettings."""

from collections.abc import Callable, Coroutine
from typing import Any, ClassVar

from aiogram import Bot
from arq.connections import RedisSettings
from arq.worker import Function, func
from svoi_contracts.jobs import DemoPing

from svoi_bot.config import Settings
from svoi_bot.main import init_sentry, make_api, make_bot
from svoi_bot.workers import demo
from svoi_bot.workers.delivery import MAX_TRIES

QUEUE = "bot"
JobFn = Callable[..., Coroutine[Any, Any, Any]]


def functions(settings: Settings) -> list[Function]:
    """Topic name = arq function name; slices add their notify_* handlers here."""
    registry: dict[str, JobFn] = {}
    if settings.dev_routes:
        registry[DemoPing.topic] = demo.demo
    return [func(fn, name=topic, max_tries=MAX_TRIES) for topic, fn in registry.items()]


async def startup(ctx: dict[str, Any]) -> None:
    """One Bot and one ApiClient per worker process."""
    settings: Settings = ctx.get("settings") or Settings()
    ctx["settings"] = settings
    init_sentry(settings)
    ctx["bot"] = make_bot(settings)
    ctx["api"] = make_api(settings)


async def shutdown(ctx: dict[str, Any]) -> None:
    """Close network sessions."""
    bot: Bot = ctx["bot"]
    await bot.session.close()
    await ctx["api"].aclose()


_settings = Settings()


class WorkerSettings:
    """arq settings; retries come from deliver_once via arq.Retry."""

    queue_name = QUEUE
    functions: ClassVar[list[Function]] = functions(_settings)
    on_startup = startup
    on_shutdown = shutdown
    max_tries = MAX_TRIES
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
