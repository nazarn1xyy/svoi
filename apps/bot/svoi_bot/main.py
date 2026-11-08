"""Entry point of the bot: python -m svoi_bot.main (polling locally, webhook on the VPS)."""

import asyncio
import logging
import time
from collections.abc import Callable

import structlog
from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from svoi_bot import errors, features
from svoi_bot.admin import router as admin
from svoi_bot.api_client import ApiClient, FakeApiClient, HttpApiClient
from svoi_bot.commands import set_commands
from svoi_bot.config import Settings
from svoi_bot.middlewares import I18nMiddleware, ThrottleMiddleware, UserContextMiddleware
from svoi_bot.ui import kitchen_sink

log = structlog.get_logger()


def make_api(settings: Settings) -> ApiClient:
    """FakeApiClient when BOT_USE_FAKE_API=true, otherwise the HTTP client."""
    if settings.bot_use_fake_api:
        return FakeApiClient(admin_ids=set(settings.admin_tg_ids))
    return HttpApiClient(settings.api_base_url, settings.internal_api_token)


def build_dispatcher(
    api: ApiClient,
    storage: BaseStorage,
    settings: Settings,
    extra_routers: list[Router] | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> Dispatcher:
    """Dispatcher with middlewares and routers; tests pass fakes and a virtual clock."""
    dp = Dispatcher(storage=storage, api=api, settings=settings)
    throttle = ThrottleMiddleware(clock)
    user_context = UserContextMiddleware(api, clock)
    for observer in (dp.message, dp.callback_query):
        observer.outer_middleware(throttle)
        observer.outer_middleware(I18nMiddleware())
        observer.outer_middleware(user_context)
    dp.include_router(errors.make_router())
    # admin first: moderators reach queues even with an unfinished profile (ADR 0001)
    dp.include_router(admin.make_router())
    for router in [*(extra_routers or []), *features.routers()]:
        dp.include_router(router)
    if settings.dev_routes:
        dp.include_router(kitchen_sink.make_router())
    return dp


def make_bot(settings: Settings) -> Bot:
    """Bot with HTML parse mode by default."""
    return Bot(settings.bot_token, default=DefaultBotProperties(parse_mode="HTML"))


async def run(settings: Settings) -> None:
    """Start polling or the webhook server."""
    api = make_api(settings)
    bot = make_bot(settings)
    dp = build_dispatcher(api, RedisStorage.from_url(settings.redis_url), settings)
    await set_commands(bot)
    try:
        if settings.bot_mode == "polling":
            await bot.delete_webhook(drop_pending_updates=False)
            await dp.start_polling(bot)
            return
        await bot.set_webhook(
            settings.webhook_base_url.rstrip("/") + settings.webhook_path,
            secret_token=settings.webhook_secret,
        )
        app = web.Application()
        SimpleRequestHandler(dp, bot, secret_token=settings.webhook_secret).register(
            app, path=settings.webhook_path
        )
        setup_application(app, dp, bot=bot)
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", settings.webhook_port).start()  # noqa: S104 - inside the Docker network only
        log.info("webhook_started", port=settings.webhook_port)
        await asyncio.Event().wait()
    finally:
        await api.aclose()
        await bot.session.close()


def main() -> None:
    """CLI entry."""
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(Settings()))


if __name__ == "__main__":
    main()
