"""S13 workers: reminders and new-people digest (FRONTEND.md S13)."""

from typing import Any

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramServerError
from aiogram.methods import SendMessage
from arq import Retry
from redis.asyncio import Redis
from svoi_bot.api_client import FakeApiClient
from svoi_bot.config import Settings
from svoi_bot.workers.main import functions
from svoi_bot.workers.reminders import notify_new_people, notify_reminder
from svoi_contracts.enums import Lang, ReminderKind
from svoi_contracts.jobs import NotifyNewPeople, NotifyReminder
from telegram_fakes import FailingSession


def _ctx(redis: Redis, api: FakeApiClient, session: FailingSession) -> dict[str, Any]:
    return {"redis": redis, "api": api, "bot": Bot("42:TEST", session=session), "job_try": 1}


def _texts(session: FailingSession) -> list[str | None]:
    return [m.text for m in session.requests if isinstance(m, SendMessage)]


@pytest.mark.parametrize(
    ("kind", "lang", "text"),
    [
        (ReminderKind.day3, Lang.uk, "Тебе вже чекають нові анкети 👀 Подивимось?"),
        (ReminderKind.day7, Lang.en, "Long time no see! New people have joined in your city."),
    ],
)
async def test_reminder_once_in_payload_language(
    redis: Redis, key: str, kind: ReminderKind, lang: Lang, text: str
) -> None:
    session = FailingSession()
    payload = NotifyReminder(dedupe_key=key, user_id=1, tg_id=77, lang=lang, kind=kind).model_dump(
        mode="json"
    )
    ctx = _ctx(redis, FakeApiClient(), session)
    assert await notify_reminder(ctx, payload) == "sent"
    assert await notify_reminder(ctx, payload) == "duplicate"
    assert _texts(session) == [text]


async def test_new_people_digest(redis: Redis, key: str) -> None:
    session = FailingSession()
    payload = NotifyNewPeople(
        dedupe_key=key, user_id=1, tg_id=77, lang=Lang.uk, interest_title="Футбол", count=4
    ).model_dump(mode="json")
    await notify_new_people(_ctx(redis, FakeApiClient(), session), payload)
    assert _texts(session) == ["У твоєму місті 4 нових людей, які люблять футбол 👀"]


async def test_500_and_403(redis: Redis, key: str) -> None:
    api = FakeApiClient()
    api.onboard(77)
    payload = NotifyReminder(
        dedupe_key=key, user_id=1, tg_id=77, lang=Lang.uk, kind=ReminderKind.day3
    ).model_dump(mode="json")
    with pytest.raises(Retry):
        await notify_reminder(_ctx(redis, api, FailingSession(TelegramServerError)), payload)
    assert (
        await notify_reminder(_ctx(redis, api, FailingSession(TelegramForbiddenError)), payload)
        == "blocked"
    )


def test_every_bot_topic_is_registered() -> None:
    names = {f.name for f in functions(Settings(_env_file=None))}  # type: ignore[call-arg]  # pydantic-settings kwarg
    assert {
        "bot.notify_likes",
        "bot.notify_match",
        "bot.notify_moderation",
        "bot.notify_reminder",
        "bot.notify_new_people",
    } <= names
