"""Real Redis for worker tests (REDIS_URL; CI provides redis:7)."""

import os
import uuid
from collections.abc import AsyncIterator

import pytest
from redis.asyncio import Redis


@pytest.fixture
async def redis() -> AsyncIterator[Redis]:
    url = os.environ.get("REDIS_URL")
    if not url:
        pytest.skip("REDIS_URL is not set; CI provides redis:7")
    client = Redis.from_url(url)
    yield client
    await client.aclose()


@pytest.fixture
def key() -> str:
    return f"test:{uuid.uuid4().hex}"
