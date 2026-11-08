"""Referral router."""

from aiogram import F, Router

from svoi_bot.features.onboarding import context
from svoi_bot.features.referral import handlers
from svoi_bot.ui.callbacks import NavCb


def make_router() -> Router:
    """NavCb(referral) from the limit screen and settings."""
    router = Router(name="referral")
    context.attach(router)
    router.callback_query.register(handlers.on_open, NavCb.filter(F.screen == "referral"))
    return router
