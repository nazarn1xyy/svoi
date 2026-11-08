"""Settings router."""

from aiogram import F, Router
from aiogram.filters import Command

from svoi_bot.features.onboarding import context
from svoi_bot.features.settings import handlers, views
from svoi_bot.ui.callbacks import NavCb, PickCb
from svoi_bot.ui.i18n import all_translations
from svoi_bot.ui.keyboards import BACK

FIELDS = (views.GENDER, views.RADIUS, views.FREQ, views.QUIET, views.LANG)


def make_router() -> Router:
    """Menu button, /settings, and the buttons of the settings screens."""
    router = Router(name="settings")
    context.attach(router)
    router.message.register(handlers.on_open, Command("settings"))
    router.message.register(handlers.on_open, F.text.in_(all_translations("ui.menu.settings")))
    router.callback_query.register(handlers.on_nav, NavCb.filter(F.screen == views.SET))
    router.callback_query.register(
        handlers.on_back, NavCb.filter(F.screen.in_(FIELDS) & (F.arg == BACK))
    )
    router.callback_query.register(handlers.on_pick, PickCb.filter(F.field.in_(FIELDS)))
    return router
