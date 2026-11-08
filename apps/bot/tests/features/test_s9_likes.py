"""S9-FE acceptance (FRONTEND.md S9): incoming likes, matches, contacts."""

from aiogram.methods import SendVoice
from harness import BotHarness
from svoi_bot.api_client import FakeApiClient
from svoi_contracts.api.reactions import MessageMedia
from svoi_contracts.enums import MessageMediaKind, Pool

TG = 100


def _setup(likes: int = 2) -> tuple[FakeApiClient, list[int]]:
    api = FakeApiClient()
    api.onboard(TG)
    authors = api.demo_tg_ids(Pool.adult)[:likes]
    return api, authors


async def test_incoming_likes_come_before_the_feed() -> None:
    api, authors = _setup()
    api.add_like(authors[0], TG, message="привіт!")
    harness = BotHarness(api, user_id=TG)
    await harness.send_text("🔍 Дивитися анкети")
    assert [c.name for c in api.calls if c.name in ("feed_next", "incoming_next")] == [
        "incoming_next"
    ]
    assert "💌 Повідомлення для тебе: привіт!" in harness.texts()


async def test_incoming_with_voice_and_without_message() -> None:
    api, authors = _setup()
    api.add_like(
        authors[0], TG, media=MessageMedia(kind=MessageMediaKind.voice, file_id="v1", duration_s=5)
    )
    harness = BotHarness(api, user_id=TG)
    await harness.send_text("❤️ Мене лайкнули (1)")
    assert any(isinstance(m, SendVoice) for m in harness.sent())
    assert harness.callback("❤️ Взаємно").startswith("lk:accept:")


async def test_accept_shows_match_then_next_like() -> None:
    api, authors = _setup()
    api.add_like(authors[0], TG)
    api.add_like(authors[1], TG)
    harness = BotHarness(api, user_id=TG)
    await harness.send_command("likes")
    await harness.tap("❤️ Взаємно")
    assert any(t.startswith("🎉 Взаємна симпатія") for t in harness.texts())
    assert len(api.matches) == 1
    assert harness.buttons() == ["❤️ Взаємно", "👎 Ні", "⚠️"]  # the second like


async def test_decline_creates_nothing_for_the_author_and_ends_with_no_more() -> None:
    api, authors = _setup(1)
    api.add_like(authors[0], TG)
    harness = BotHarness(api, user_id=TG)
    await harness.send_command("likes")
    await harness.tap("👎 Ні")
    assert api.matches == []
    assert harness.last_text() == "Це всі. Повертаємось до анкет?"
    await harness.tap("🔍 Дивитися анкети")
    assert harness.last_text().startswith("<b>")


async def test_contacts_paginate_by_ten_and_delete() -> None:
    api, _ = _setup(12)
    for author in api.demo_tg_ids(Pool.adult)[:12]:
        api.add_like(author, TG)
    harness = BotHarness(api, user_id=TG)
    await harness.send_command("likes")
    for _ in range(12):
        await harness.tap("❤️ Взаємно")
    harness.clear()
    await harness.send_text("🤝 Мої контакти")
    assert len(harness.buttons()) == 11  # 10 contacts + ▶️
    await harness.tap("▶️")
    assert len(harness.buttons()) == 3  # 2 contacts + ◀️
    first = harness.buttons()[0]
    await harness.tap(first)
    assert harness.buttons()[:2] == ["💬 Написати", "🚫 Видалити контакт"]
    await harness.tap("🚫 Видалити контакт")
    assert len([m for m in api.matches if not m.removed]) == 11


async def test_empty_contacts() -> None:
    api, _ = _setup(0)
    harness = BotHarness(api, user_id=TG)
    await harness.send_command("contacts")
    assert harness.last_text() == "Поки немає контактів. Взаємні симпатії з'являться тут."
