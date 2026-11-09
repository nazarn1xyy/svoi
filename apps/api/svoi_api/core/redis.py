"""Typed await for redis-py asyncio calls (its stubs say `Awaitable[T] | T`)."""

from collections.abc import Awaitable
from typing import cast


async def aw[T](value: Awaitable[T] | T) -> T:
    """Await a redis.asyncio command with its precise result type."""
    return await cast(Awaitable[T], value)
