"""At most 2 updates per second per user; extra updates are dropped silently."""

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

RATE = 2
WINDOW_S = 1.0


class ThrottleMiddleware(BaseMiddleware):
    """Sliding one-second window per Telegram user, in process memory."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._hits: defaultdict[int, deque[float]] = defaultdict(deque)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user is None:
            return await handler(event, data)
        now = self._clock()
        hits = self._hits[user.id]
        while hits and now - hits[0] >= WINDOW_S:
            hits.popleft()
        if len(hits) >= RATE:
            return None
        hits.append(now)
        return await handler(event, data)
