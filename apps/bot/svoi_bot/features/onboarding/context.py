"""Builds StepContext once per update so handlers take (event, callback_data, step)."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from svoi_bot.features.onboarding.registry import StepContext


class StepContextMiddleware(BaseMiddleware):
    """Inner middleware for feature routers that use the step registry."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user is not None and data.get("user_state") is not None:
            data["step"] = StepContext(
                bot=data["bot"],
                state=data["state"],
                api=data["api"],
                user_state=data["user_state"],
                tg_user=user,
            )
        return await handler(event, data)


def attach(router: Any) -> None:
    """Install the middleware on a router's messages and callbacks."""
    router.message.middleware(StepContextMiddleware())
    router.callback_query.middleware(StepContextMiddleware())
