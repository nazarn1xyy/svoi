"""Admin entry point. Non-admins get no answer at all, as if the command did not exist."""

from typing import Any

from aiogram import Router
from aiogram.filters import Command, Filter
from aiogram.types import TelegramObject
from svoi_contracts.cards import UserState

from svoi_bot.admin.features.queue import handlers as queue
from svoi_bot.ui.callbacks import AdminCb


class IsAdmin(Filter):
    """Passes only when UserState.is_admin; the API enforces it again on /admin/*."""

    async def __call__(
        self, event: TelegramObject, user_state: UserState | None = None, **_: Any
    ) -> bool:
        return user_state is not None and user_state.is_admin


def make_router() -> Router:
    """Admin routes; every handler is guarded by IsAdmin at router level."""
    router = Router(name="admin")
    router.message.filter(IsAdmin())
    router.callback_query.filter(IsAdmin())
    router.message.register(queue.on_home, Command("admin"))
    router.message.register(queue.on_user, Command("user"))
    router.message.register(queue.on_metrics, Command("metrics"))
    router.callback_query.register(queue.on_callback, AdminCb.filter())
    return router
