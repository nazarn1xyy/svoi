"""Report router."""

from aiogram import F, Router

from svoi_bot.features.onboarding import context
from svoi_bot.features.report import handlers
from svoi_bot.ui.callbacks import ReportCb


def make_router() -> Router:
    """⚠️ buttons from any context and the «Інше» text."""
    router = Router(name="report")
    context.attach(router)
    router.callback_query.register(handlers.on_report, ReportCb.filter())
    router.message.register(handlers.on_text, handlers.ReportSG.text, F.text)
    return router
