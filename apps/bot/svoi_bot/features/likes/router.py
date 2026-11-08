"""Incoming likes router."""

from aiogram import F, Router
from aiogram.filters import Command

from svoi_bot.features.likes import handlers, views
from svoi_bot.features.onboarding import context
from svoi_bot.ui.callbacks import LikeCb, NavCb
from svoi_bot.ui.i18n import all_translations


def make_router() -> Router:
    """Menu button (with or without the counter), /likes, answers."""
    router = Router(name="likes")
    context.attach(router)
    likes_buttons = all_translations("ui.menu.likes")
    router.message.register(handlers.on_open, Command("likes"))
    router.message.register(
        handlers.on_open,
        F.text.func(lambda t: any(t.startswith(b) for b in likes_buttons)),
    )
    router.callback_query.register(handlers.on_answer, LikeCb.filter())
    router.callback_query.register(handlers.on_nav, NavCb.filter(F.screen == views.LIKES))
    router.callback_query.register(
        handlers.on_nav, NavCb.filter((F.screen == "feed") & (F.arg == "open"))
    )
    return router
