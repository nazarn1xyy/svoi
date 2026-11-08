"""Bot sessions for worker tests."""

from typing import Any

from aiogram import Bot
from aiogram.methods import TelegramMethod
from aiogram.types import Chat
from harness import RecordingSession


class FailingSession(RecordingSession):
    """RecordingSession that raises a Telegram error on every call when asked to."""

    def __init__(self, error: type[Exception] | None = None) -> None:
        super().__init__(Chat(id=1, type="private"))
        self.error = error

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[Any],
        timeout: int | None = None,  # noqa: ASYNC109 - aiogram signature
    ) -> Any:
        if self.error is not None:
            raise self.error(method, "boom")
        return await super().make_request(bot, method, timeout)
