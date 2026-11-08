"""K12 acceptance: delivery rules of tech.md section 8 and the demo job through arq."""

import os
from typing import Any

import pytest
from aiogram.exceptions import TelegramForbiddenError, TelegramNetworkError, TelegramServerError
from aiogram.methods import SendMessage
from arq import Retry, create_pool
from arq.connections import RedisSettings
from arq.worker import Worker, func
from hypothesis import given, settings
from hypothesis import strategies as st
from redis.asyncio import Redis
from svoi_bot.api_client import FakeApiClient
from svoi_bot.workers.delivery import deliver_once, sent_key
from svoi_bot.workers.demo import demo
from svoi_contracts.jobs import DemoPing

METHOD = SendMessage(chat_id=1, text="x")


def _ctx(redis: Redis, api: FakeApiClient, job_try: int = 1) -> dict[str, Any]:
    return {"redis": redis, "api": api, "job_try": job_try}


class _Sender:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls = 0
        self.error = error

    async def __call__(self) -> None:
        self.calls += 1
        if self.error is not None:
            raise self.error


async def test_same_dedupe_key_twice_sends_once(redis: Redis, key: str) -> None:
    api, send = FakeApiClient(), _Sender()
    assert await deliver_once(_ctx(redis, api), key, 1, send) == "sent"
    assert await deliver_once(_ctx(redis, api), key, 1, send) == "duplicate"
    assert send.calls == 1
    assert api.sent_notifications == [key]
    assert 0 < await redis.ttl(sent_key(key)) <= 604_800


@pytest.mark.parametrize(
    "error", [TelegramServerError(METHOD, "502"), TelegramNetworkError(METHOD, "reset")]
)
async def test_server_or_network_error_drops_key_and_retries(
    redis: Redis, key: str, error: Exception
) -> None:
    api = FakeApiClient()
    with pytest.raises(Retry) as caught:
        await deliver_once(_ctx(redis, api, job_try=3), key, 1, _Sender(error))
    assert caught.value.defer_score == 30_000  # 10 s times try 3, in ms
    assert await redis.get(sent_key(key)) is None
    assert await deliver_once(_ctx(redis, api), key, 1, _Sender()) == "sent"  # retry delivers


async def test_forbidden_marks_bot_blocked_without_retry(redis: Redis, key: str) -> None:
    api = FakeApiClient()
    user = api.onboard(77)
    outcome = await deliver_once(
        _ctx(redis, api), key, user.tg_id, _Sender(TelegramForbiddenError(METHOD, "blocked"))
    )
    assert outcome == "blocked"
    assert api.bot_blocked == {77}
    assert api.sent_notifications == []


@settings(max_examples=20, deadline=None)
@given(st.lists(st.sampled_from(["ok", "5xx"]), min_size=1, max_size=6))
def test_any_failure_sequence_delivers_at_most_once(outcomes: list[str]) -> None:
    import asyncio  # noqa: PLC0415 - hypothesis drives a sync test
    import uuid  # noqa: PLC0415

    url = os.environ.get("REDIS_URL")
    if not url:
        pytest.skip("REDIS_URL is not set")

    async def run() -> int:
        client, api, dedupe = Redis.from_url(url), FakeApiClient(), uuid.uuid4().hex
        delivered = 0
        try:
            for outcome in outcomes:
                sender = _Sender(TelegramServerError(METHOD, "502") if outcome == "5xx" else None)
                try:
                    result = await deliver_once(_ctx(client, api), dedupe, 1, sender)
                except Retry:
                    continue
                delivered += result == "sent"
        finally:
            await client.aclose()
        return delivered

    assert asyncio.run(run()) == (1 if "ok" in outcomes else 0)


async def test_invalid_payload_is_dropped(redis: Redis) -> None:
    ctx = _ctx(redis, FakeApiClient())
    assert await demo(ctx, {"dedupe_key": "demo:x"}) == "invalid"
    assert "demo_received" not in ctx


async def test_demo_job_from_the_api_queue_reaches_the_worker(redis: Redis, key: str) -> None:
    settings_ = RedisSettings.from_dsn(os.environ["REDIS_URL"])
    queue = f"bot-test-{key}"
    pool = await create_pool(settings_, default_queue_name=queue)
    payload = DemoPing(dedupe_key=f"demo:{key}", note="hello").model_dump(mode="json")
    await pool.enqueue_job(DemoPing.topic, payload, _job_id=payload["dedupe_key"])
    # arq refuses a second job with the same _job_id while the first waits
    assert await pool.enqueue_job(DemoPing.topic, payload, _job_id=payload["dedupe_key"]) is None
    received: list[DemoPing] = []

    async def startup(ctx: dict[str, Any]) -> None:
        ctx["api"] = FakeApiClient()
        ctx["demo_received"] = received

    worker = Worker(
        functions=[func(demo, name=DemoPing.topic)],
        redis_pool=pool,
        queue_name=queue,
        burst=True,
        on_startup=startup,
        poll_delay=0.01,
    )
    await worker.main()
    await worker.close()
    assert [job.note for job in received] == ["hello"]
