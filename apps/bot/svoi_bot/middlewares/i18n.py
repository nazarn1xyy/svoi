"""Sets the gettext language from UserState.lang (or Telegram's language before that)."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from svoi_contracts.cards import UserState
from svoi_contracts.enums import Lang

from svoi_bot.ui.i18n import set_locale

_KNOWN = {lang.value for lang in Lang}


class I18nMiddleware(BaseMiddleware):
    """Runs before UserContext so its own messages are localized too."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        state: UserState | None = data.get("user_state")
        if state is not None:
            set_locale(state.lang)
        else:
            user: User | None = data.get("event_from_user")
            code = (user.language_code or "")[:2] if user else ""
            set_locale(Lang(code) if code in _KNOWN else Lang.uk)
        return await handler(event, data)
