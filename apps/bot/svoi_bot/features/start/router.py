"""/start router."""

from aiogram import Router
from aiogram.filters import Command, CommandStart

from svoi_bot.features.onboarding import context
from svoi_bot.features.start import handlers


def make_router() -> Router:
    """/start with or without a deep-link payload."""
    router = Router(name="start")
    context.attach(router)
    router.message.register(handlers.on_start, CommandStart())
    router.message.register(handlers.on_help, Command("help"))
    return router
