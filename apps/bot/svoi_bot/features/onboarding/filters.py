"""Filters on UserState for onboarding routing."""

from typing import Any

from aiogram.filters import Filter
from aiogram.types import TelegramObject
from svoi_contracts.cards import UserState
from svoi_contracts.enums import UserStatus


class Onboarding(Filter):
    """User has not finished the profile yet."""

    async def __call__(
        self, event: TelegramObject, user_state: UserState | None = None, **_: Any
    ) -> bool:
        return user_state is not None and user_state.status is UserStatus.onboarding
