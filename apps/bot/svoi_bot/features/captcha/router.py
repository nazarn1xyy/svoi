"""Captcha router: mounted before every feature so flagged users solve it first."""

from aiogram import F, Router

from svoi_bot.features.captcha import handlers
from svoi_bot.features.onboarding import context
from svoi_bot.ui.callbacks import PickCb


def make_router() -> Router:
    """Answers, then the gate for everything else."""
    router = Router(name="captcha")
    context.attach(router)
    router.callback_query.register(
        handlers.on_answer, handlers.CaptchaSG.solve, PickCb.filter(F.field == handlers.CAPTCHA)
    )
    router.message.register(handlers.gate, handlers.NeedsCaptcha())
    router.callback_query.register(handlers.gate, handlers.NeedsCaptcha())
    return router
