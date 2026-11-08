"""S10 worker: notify_moderation texts, idempotency, 403, 500."""

from datetime import UTC, datetime
from typing import Any

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramServerError
from aiogram.methods import SendMessage
from arq import Retry
from redis.asyncio import Redis
from svoi_bot.api_client import FakeApiClient
from svoi_bot.workers.moderation import notify_moderation
from svoi_contracts.enums import Lang, ModerationResultKind
from svoi_contracts.jobs import NotifyModeration
from telegram_fakes import FailingSession as _FailingSession


def _payload(key: str, result: ModerationResultKind, until: datetime | None = None) -> Any:
    return NotifyModeration(
        dedupe_key=key, user_id=1, tg_id=77, lang=Lang.uk, result=result, until=until
    ).model_dump(mode="json")


def _ctx(redis: Redis, api: FakeApiClient, session: _FailingSession) -> dict[str, Any]:
    return {"redis": redis, "api": api, "bot": Bot("42:TEST", session=session), "job_try": 1}


@pytest.mark.parametrize("result", list(ModerationResultKind))
async def test_every_result_has_its_text_and_sends_once(
    redis: Redis, key: str, result: ModerationResultKind
) -> None:
    session = _FailingSession()
    ctx = _ctx(redis, FakeApiClient(), session)
    assert await notify_moderation(ctx, _payload(key, result)) == "sent"
    assert await notify_moderation(ctx, _payload(key, result)) == "duplicate"
    texts = [m.text for m in session.requests if isinstance(m, SendMessage)]
    assert len(texts) == 1 and texts[0]


async def test_ban_with_date(redis: Redis, key: str) -> None:
    session = _FailingSession()
    until = datetime(2026, 11, 15, tzinfo=UTC)
    await notify_moderation(
        _ctx(redis, FakeApiClient(), session), _payload(key, ModerationResultKind.banned, until)
    )
    assert [m.text for m in session.requests if isinstance(m, SendMessage)] == [
        "Твою анкету заблоковано до 15.11.2026. Причина — порушення правил."
    ]


async def test_500_retries_and_403_blocks(redis: Redis, key: str) -> None:
    api = FakeApiClient()
    api.onboard(77)
    with pytest.raises(Retry):
        await notify_moderation(
            _ctx(redis, api, _FailingSession(TelegramServerError)),
            _payload(key, ModerationResultKind.verified),
        )
    assert (
        await notify_moderation(
            _ctx(redis, api, _FailingSession(TelegramForbiddenError)),
            _payload(key, ModerationResultKind.verified),
        )
        == "blocked"
    )
    assert api.bot_blocked == {77}
