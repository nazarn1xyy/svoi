"""Admin entry point. Non-admins get no answer at all, as if the command did not exist."""

from typing import Any

from aiogram import Router
from aiogram.filters import Command, Filter
from aiogram.types import Message, TelegramObject
from svoi_contracts.cards import UserState

from svoi_bot.ui.i18n import _


class IsAdmin(Filter):
    """Passes only when UserState.is_admin; the API enforces it again on /admin/*."""

    async def __call__(
        self, event: TelegramObject, user_state: UserState | None = None, **_: Any
    ) -> bool:
        return user_state is not None and user_state.is_admin


async def admin_home(message: Message) -> None:
    """Placeholder until S10 adds the moderation queues."""
    await message.answer(_("admin.home"))


def make_router() -> Router:
    """Admin routes; every handler is guarded by IsAdmin at router level."""
    router = Router(name="admin")
    router.message.filter(IsAdmin())
    router.callback_query.filter(IsAdmin())
    router.message.register(admin_home, Command("admin"))
    return router
