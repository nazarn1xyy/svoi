"""S9 workers: notify_likes and notify_match deliver once, retry on 5xx, stop on 403."""

from typing import Any

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramServerError
from aiogram.methods import SendMessage, TelegramMethod
from aiogram.types import Chat
from arq import Retry
from harness import RecordingSession
from redis.asyncio import Redis
from svoi_bot.api_client import FakeApiClient
from svoi_bot.workers.notify import notify_likes, notify_match
from svoi_contracts.enums import Lang
from svoi_contracts.jobs import NotifyLikes, NotifyMatch


class _FailingSession(RecordingSession):
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


def _ctx(redis: Redis, api: FakeApiClient, session: RecordingSession) -> dict[str, Any]:
    return {"redis": redis, "api": api, "bot": Bot("42:TEST", session=session), "job_try": 1}


def _likes(key: str, lang: Lang = Lang.uk, count: int = 5) -> dict[str, Any]:
    return NotifyLikes(dedupe_key=key, user_id=1, tg_id=77, lang=lang, count=count).model_dump(
        mode="json"
    )


def _sent_texts(session: RecordingSession) -> list[str]:
    return [m.text for m in session.requests if isinstance(m, SendMessage)]


async def test_notify_likes_twice_sends_once_in_payload_language(redis: Redis, key: str) -> None:
    session, api = _FailingSession(), FakeApiClient()
    ctx = _ctx(redis, api, session)
    assert await notify_likes(ctx, _likes(key, Lang.uk, 5)) == "sent"
    assert await notify_likes(ctx, _likes(key, Lang.uk, 5)) == "duplicate"
    assert _sent_texts(session) == ["❤️ Ти сподобався 5 людям! Подивитися?"]
    session2 = _FailingSession()
    await notify_likes(_ctx(redis, api, session2), _likes(key + "en", Lang.en, 1))
    assert _sent_texts(session2) == ["❤️ You were liked by 1 person! Take a look?"]


@pytest.mark.parametrize(("count", "phrase"), [(1, "1 людині"), (2, "2 людям"), (5, "5 людям")])
async def test_plural_forms(redis: Redis, key: str, count: int, phrase: str) -> None:
    session = _FailingSession()
    await notify_likes(_ctx(redis, FakeApiClient(), session), _likes(key, count=count))
    assert phrase in _sent_texts(session)[0]


async def test_server_error_retries_and_frees_the_key(redis: Redis, key: str) -> None:
    api = FakeApiClient()
    with pytest.raises(Retry):
        await notify_likes(_ctx(redis, api, _FailingSession(TelegramServerError)), _likes(key))
    session = _FailingSession()
    assert await notify_likes(_ctx(redis, api, session), _likes(key)) == "sent"


async def test_forbidden_marks_bot_blocked_without_retry(redis: Redis, key: str) -> None:
    api = FakeApiClient()
    api.onboard(77)
    outcome = await notify_likes(
        _ctx(redis, api, _FailingSession(TelegramForbiddenError)), _likes(key)
    )
    assert outcome == "blocked"
    assert api.bot_blocked == {77}


async def test_invalid_payload_sends_nothing(redis: Redis) -> None:
    session = _FailingSession()
    assert await notify_likes(_ctx(redis, FakeApiClient(), session), {"tg_id": "x"}) == "invalid"
    assert session.requests == []


async def test_notify_match_twice_sends_once(redis: Redis, key: str) -> None:
    api = FakeApiClient()
    me = api.onboard(77)
    partner = api.demo_tg_ids()[0]
    api.add_like(partner, me.tg_id)
    like_id = api.likes[-1].id
    from svoi_contracts.api.likes import RespondIn  # noqa: PLC0415
    from svoi_contracts.enums import LikeDecision  # noqa: PLC0415

    result = await api.respond_like(me.tg_id, like_id, RespondIn(decision=LikeDecision.accept))
    assert result.match is not None
    payload = NotifyMatch(
        dedupe_key=key,
        match_id=result.match.match_id,
        recipient_user_id=me.id,
        tg_id=me.tg_id,
        lang=Lang.uk,
    ).model_dump(mode="json")
    session = _FailingSession()
    ctx = _ctx(redis, api, session)
    assert await notify_match(ctx, payload) == "sent"
    assert await notify_match(ctx, payload) == "duplicate"
    headers = [t for t in _sent_texts(session) if t and t.startswith("🎉")]
    assert len(headers) == 1
