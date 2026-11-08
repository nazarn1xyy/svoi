"""Verification router."""

from aiogram import F, Router
from aiogram.filters import Command

from svoi_bot.features.onboarding import context
from svoi_bot.features.verification import handlers
from svoi_bot.ui.callbacks import NavCb


def make_router() -> Router:
    """/verify, the profile button, and anything sent while waiting for the video."""
    router = Router(name="verification")
    context.attach(router)
    router.message.register(handlers.on_command, Command("verify"))
    router.callback_query.register(
        handlers.on_button, NavCb.filter((F.screen == "me") & (F.arg == "verify"))
    )
    router.message.register(handlers.on_video_note, handlers.VerifySG.video)
    return router
