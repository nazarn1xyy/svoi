"""Puts UserState into data["user_state"], cached for 60 s in FSM data.

The first update of a session (and every /start) calls ApiClient.start. Banned users get the
ban text and nothing else; the admin section is exempt so moderators never lock themselves out.
"""

import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, TelegramObject, User
from svoi_contracts.api.users import StartIn
from svoi_contracts.cards import UserState
from svoi_contracts.errors import ErrorCode

from svoi_bot.api_client import ApiClient, ApiException
from svoi_bot.ui.errors import render_api_error
from svoi_bot.ui.i18n import set_locale

CACHE_TTL_S = 60.0
_STATE, _AT = "user_state", "user_state_at"
REFERRAL_PREFIX = "r_"


async def remember_state(state: FSMContext, user_state: UserState) -> None:
    """Refresh the cached UserState after an API call returned a new one.

    The 60 s window still counts from the last start call, so the API is asked again soon.
    """
    await state.update_data({_STATE: user_state.model_dump(mode="json")})


def start_payload(event: TelegramObject) -> str | None:
    """Text after /start, or None when the update is not /start."""
    if isinstance(event, Message) and event.text and event.text.split()[0] == "/start":
        parts = event.text.split(maxsplit=1)
        return parts[1].strip() if len(parts) > 1 else ""
    return None


class UserContextMiddleware(BaseMiddleware):
    """Loads or refreshes UserState for every update with a user."""

    def __init__(self, api: ApiClient, clock: Callable[[], float] = time.monotonic) -> None:
        self.api = api
        self._clock = clock

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        state: FSMContext | None = data.get("state")
        if user is None or state is None or user.is_bot:
            return await handler(event, data)
        cached = await state.get_data()
        payload = start_payload(event)
        fresh = (
            payload is None
            and cached.get(_STATE) is not None
            and self._clock() - float(cached.get(_AT, 0.0)) < CACHE_TTL_S
        )
        if fresh:
            data["user_state"] = UserState.model_validate(cached[_STATE])
            set_locale(data["user_state"].lang)
            return await handler(event, data)
        bot: Bot = data["bot"]
        try:
            user_state = await self.api.start(user.id, await self._start_in(bot, user, payload))
        except ApiException as exc:
            if exc.err.code is ErrorCode.banned and isinstance(event, Message):
                await event.answer(render_api_error(exc.err), reply_markup=None)
                return None
            raise
        await state.update_data({_STATE: user_state.model_dump(mode="json"), _AT: self._clock()})
        set_locale(user_state.lang)
        data["user_state"] = user_state
        return await handler(event, data)

    @staticmethod
    async def _start_in(bot: Bot, user: User, payload: str | None) -> StartIn:
        photos = await bot.get_user_profile_photos(user.id, limit=1)
        referral = None
        if payload and payload.startswith(REFERRAL_PREFIX):
            referral = payload.removeprefix(REFERRAL_PREFIX) or None
        return StartIn(
            tg_username=user.username,
            tg_first_name=user.first_name,
            tg_language_code=user.language_code,
            has_tg_profile_photo=photos.total_count > 0,
            referral_code=referral,
        )
