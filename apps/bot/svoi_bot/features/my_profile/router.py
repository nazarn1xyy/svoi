"""«Моя анкета» router."""

from aiogram import F, Router
from aiogram.filters import Command

from svoi_bot.features.my_profile import handlers, views
from svoi_bot.features.my_profile.states import MyProfileSG
from svoi_bot.features.onboarding import context
from svoi_bot.ui.callbacks import NavCb, PickCb
from svoi_bot.ui.i18n import all_translations


def make_router() -> Router:
    """Menu button and /profile open the screen; buttons act on it."""
    router = Router(name="my_profile")
    context.attach(router)
    router.message.register(handlers.on_open, Command("profile"))
    router.message.register(handlers.on_open, F.text.in_(all_translations("ui.menu.profile")))
    router.callback_query.register(handlers.on_action, NavCb.filter(F.screen == views.ME))
    router.callback_query.register(
        handlers.on_photos, MyProfileSG.photos, NavCb.filter(F.screen == views.PHOTOS)
    )
    router.callback_query.register(
        handlers.on_confirm_delete,
        MyProfileSG.confirm_delete,
        PickCb.filter(F.field == views.DELETE),
    )
    router.callback_query.register(
        handlers.on_confirm_reset, MyProfileSG.confirm_reset, PickCb.filter(F.field == views.RESET)
    )
    return router
