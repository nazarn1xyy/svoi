"""Last-resort handling of API failures: say it in plain words, keep the FSM state."""

from aiogram import Router
from aiogram.types import ErrorEvent

from svoi_bot.api_client import ApiException, ApiTimeout
from svoi_bot.ui.errors import render_api_error, timeout_text


async def on_api_error(event: ErrorEvent) -> bool:
    """ApiException → its text, ApiTimeout → the generic retry text; other errors propagate."""
    exc = event.exception
    if isinstance(exc, ApiException):
        text = render_api_error(exc.err)
    elif isinstance(exc, ApiTimeout):
        text = timeout_text()
    else:
        return False
    update = event.update
    if update.message is not None:
        await update.message.answer(text)
    elif update.callback_query is not None:
        await update.callback_query.answer(text, show_alert=True)
    return True


def make_router() -> Router:
    """Fresh router: aiogram attaches a router to one dispatcher only."""
    router = Router(name="errors")
    router.errors.register(on_api_error)
    return router
