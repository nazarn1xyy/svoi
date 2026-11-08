"""Onboarding router: step handlers by FSM state, then resume as the catch-all."""

from aiogram import F, Router

from svoi_bot.features.onboarding import context, handlers, views
from svoi_bot.features.onboarding.filters import Onboarding
from svoi_bot.features.onboarding.states import OnboardingSG
from svoi_bot.ui.callbacks import PickCb


def make_router() -> Router:
    """Steps of S1; S2-S4 attach theirs through their own routers before resume."""
    router = Router(name="onboarding")
    context.attach(router)
    router.callback_query.register(
        handlers.on_lang, OnboardingSG.lang, PickCb.filter(F.field == views.LANG_FIELD)
    )
    router.callback_query.register(
        handlers.on_consent, OnboardingSG.consent, PickCb.filter(F.field == views.CONSENT_FIELD)
    )
    router.message.register(handlers.on_age, OnboardingSG.age, F.text)
    router.message.register(handlers.on_name_typed, OnboardingSG.name, F.text)
    router.callback_query.register(
        handlers.on_name_button, OnboardingSG.name, PickCb.filter(F.field == views.NAME_FIELD)
    )
    router.callback_query.register(
        handlers.on_gender, OnboardingSG.gender, PickCb.filter(F.field == views.GENDER_FIELD)
    )
    return router


def make_resume_router() -> Router:
    """Last router: anything else from an onboarding user shows the saved step."""
    router = Router(name="onboarding_resume")
    context.attach(router)
    router.message.register(handlers.resume_message, Onboarding())
    router.callback_query.register(handlers.resume_callback, Onboarding())
    return router
