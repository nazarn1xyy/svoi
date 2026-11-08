"""City router."""

from aiogram import F, Router

from svoi_bot.features.city import handlers, views
from svoi_bot.features.city.states import CitySG
from svoi_bot.features.onboarding import context
from svoi_bot.ui.callbacks import PickCb


def make_router() -> Router:
    """Typing and location in both states; buttons only while confirming."""
    router = Router(name="city")
    context.attach(router)
    router.message.register(handlers.on_location, CitySG.input, F.location)
    router.message.register(handlers.on_location, CitySG.confirm, F.location)
    router.message.register(handlers.on_text, CitySG.input, F.text)
    router.message.register(handlers.on_text, CitySG.confirm, F.text)
    router.callback_query.register(
        handlers.on_pick, CitySG.confirm, PickCb.filter(F.field == views.PICK)
    )
    router.callback_query.register(
        handlers.on_geo, CitySG.confirm, PickCb.filter(F.field == views.GEO)
    )
    return router
