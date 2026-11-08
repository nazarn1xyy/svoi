"""Feed router."""

from aiogram import F, Router
from aiogram.filters import Command

from svoi_bot.features.feed import handlers, views
from svoi_bot.features.feed.states import FeedSG
from svoi_bot.features.onboarding import context
from svoi_bot.ui.callbacks import NavCb, ReactCb
from svoi_bot.ui.i18n import all_translations


def make_router() -> Router:
    """Reply buttons act only while a card is on screen."""
    router = Router(name="feed")
    context.attach(router)
    msg, cq = router.message, router.callback_query
    msg.register(handlers.on_open, Command("search"))
    msg.register(handlers.on_open, F.text.in_(all_translations("ui.menu.search")))
    msg.register(handlers.on_pause, Command("pause"))
    msg.register(handlers.on_like, FeedSG.viewing, F.text == views.LIKE)
    msg.register(handlers.on_skip, FeedSG.viewing, F.text == views.SKIP)
    msg.register(handlers.on_message_start, FeedSG.viewing, F.text == views.MESSAGE)
    msg.register(handlers.on_pause, F.text == views.PAUSE)
    msg.register(handlers.on_message_content, FeedSG.message, F.text | F.voice | F.video_note)
    cq.register(handlers.on_nav, NavCb.filter(F.screen == views.FEED))
    cq.register(handlers.on_undo, ReactCb.filter(F.action == "undo"))
    return router
