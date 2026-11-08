"""S7/S8-FE acceptance (FRONTEND.md S7/S8): feed, reactions, empty states, matches."""

import asyncio
from typing import Any

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from harness import BotHarness
from svoi_bot.api_client import FakeApiClient
from svoi_contracts.api.feed import FeedEmpty
from svoi_contracts.enums import FeedEmptyReason, Pool, ReactionType, UserStatus
from svoi_contracts.errors import ApiError, ErrorCode

TG = 100


async def _feed(age: int = 19, username: str | None = "tester") -> BotHarness:
    api = FakeApiClient()
    api.onboard(TG, age=age, username=username)
    harness = BotHarness(api, user_id=TG, username=username)
    await harness.send_text("🔍 Дивитися анкети")
    return harness


def _reactions(harness: BotHarness) -> list[Any]:
    return [c.body for c in harness.api.calls if c.name == "react"]


def _cards(harness: BotHarness) -> list[str]:
    return [t for t in harness.texts() if t.startswith("<b>")]


async def test_card_with_reaction_keyboard_and_report_button() -> None:
    harness = await _feed()
    assert any(
        isinstance(getattr(m, "reply_markup", None), ReplyKeyboardMarkup)
        and [b.text for b in m.reply_markup.keyboard[0]] == ["❤️", "💌", "👎", "💤"]  # type: ignore[attr-defined]
        for m in harness.shown()
    )
    assert _cards(harness)
    assert isinstance(harness.last_markup(), InlineKeyboardMarkup)
    assert harness.buttons() == ["⚠️ Поскаржитися"]


async def test_like_and_skip_act_on_the_card_on_screen() -> None:
    harness = await _feed()
    first = harness.api.user(TG).current
    await harness.send_text("❤️")
    second = harness.api.user(TG).current
    await harness.send_text("👎")
    bodies = _reactions(harness)
    assert [(b.target_id, b.type) for b in bodies] == [
        (first, ReactionType.like),
        (second, ReactionType.skip),
    ]
    assert len(_cards(harness)) == 3


async def test_like_with_text_voice_and_video_note() -> None:
    harness = await _feed()
    await harness.send_text("💌")
    assert harness.last_text().startswith("Напиши повідомлення для")
    assert "голосове або кружок" in harness.last_text()
    await harness.send_text("привіт, теж люблю футбол")
    assert "Лайк з повідомленням надіслано 💌" in harness.texts()
    await harness.send_text("💌")
    await harness.send_voice(12)
    await harness.send_text("💌")
    await harness.send_video_note(9)
    kinds = [
        (b.type, b.message, b.media.kind.value if b.media else None) for b in _reactions(harness)
    ]
    assert kinds == [
        (ReactionType.like_msg, "привіт, теж люблю футбол", None),
        (ReactionType.like_msg, None, "voice"),
        (ReactionType.like_msg, None, "video_note"),
    ]


async def test_long_recording_is_refused_locally() -> None:
    harness = await _feed()
    await harness.send_text("💌")
    await harness.send_voice(31)
    assert harness.last_text() == "Запис до 30 секунд"
    assert _reactions(harness) == []


async def test_minor_pool_gets_text_only_and_media_forbidden() -> None:
    harness = await _feed(age=16)
    await harness.send_text("💌")
    assert "голосове" not in harness.last_text()
    await harness.send_voice(5)
    assert harness.last_text() == "Для твого віку доступні тільки текстові повідомлення"
    assert harness.api.user(TG).pool is Pool.minor


async def test_contacts_in_a_message_are_blocked() -> None:
    harness = await _feed()
    await harness.send_text("💌")
    await harness.send_text("пиши в t.me/ira")
    assert harness.last_text() == "Контакти відкриються після взаємної симпатії."


async def test_pause_returns_to_the_menu() -> None:
    harness = await _feed()
    await harness.send_text("💤")
    assert harness.last_text() == "Почекаємо, поки хтось побачить твою анкету."
    assert harness.buttons()[0] == "🔍 Дивитися анкети"


async def test_match_from_reaction_out() -> None:
    api = FakeApiClient()
    me = api.onboard(TG)
    harness = BotHarness(api, user_id=TG)
    await harness.send_text("🔍 Дивитися анкети")
    target = api.user(TG).current
    assert target is not None
    partner = next(u for u in api.users.values() if u.id == target)
    api.add_like(partner.tg_id, me.tg_id)
    await harness.send_text("❤️")
    assert any(t.startswith("🎉 Взаємна симпатія з") for t in harness.texts())
    markups = [getattr(m, "reply_markup", None) for m in harness.shown()]
    assert any(
        isinstance(mk, InlineKeyboardMarkup) and mk.inline_keyboard[0][0].url for mk in markups
    )


async def test_double_tap_like_posts_once() -> None:
    harness = await _feed()
    original = harness.api._h_react

    async def slow(*args: Any, **kwargs: Any) -> Any:
        await asyncio.sleep(0)
        return await original(*args, **kwargs)

    harness.api._h_react = slow  # type: ignore[method-assign]
    await asyncio.gather(harness.send_text("❤️"), harness.send_text("❤️"))
    assert len(_reactions(harness)) == 1


async def test_username_hint_once_per_session() -> None:
    harness = await _feed(username=None)
    await harness.send_text("❤️")
    await harness.send_text("❤️")
    hints = [t for t in harness.texts() if "створи username" in t]
    assert len(hints) == 1


async def test_no_candidates_offers_api_expand_options() -> None:
    api = FakeApiClient()
    api.onboard(TG)
    api.user(TG).filters = api.user(TG).filters.model_copy(update={"verified_only": True})  # type: ignore[union-attr]
    harness = BotHarness(api, user_id=TG)
    await harness.send_text("🔍 Дивитися анкети")
    assert "Розширити пошук?" in " ".join(harness.texts())
    assert harness.buttons() == [
        "🔭 До 50 км",
        "🗺 Уся область",
        "🇺🇦 Уся країна",
        "🎮 Тільки онлайн-інтереси",
        "⏰ Пізніше",
    ]
    await harness.tap("🗺 Уся область")
    expand = [c.body for c in api.calls if c.name == "feed_expand" and c.body is not None]
    assert expand[0].model_dump()["radius"].value == "region"


async def test_limit_reached_and_hidden_profile() -> None:
    api = FakeApiClient()
    api.onboard(TG).reactions_left = 0
    harness = BotHarness(api, user_id=TG)
    await harness.send_text("🔍 Дивитися анкети")
    assert "На сьогодні анкети закінчились." in " ".join(harness.texts())
    assert harness.buttons() == ["🎁 Запросити друга"]
    api.user(TG).reactions_left = 10
    api.user(TG).status = UserStatus.hidden
    await harness.send_text("🔍 Дивитися анкети")
    assert "Твоя анкета прихована. Показати її знову?" in harness.texts()
    await harness.tap("👁 Показати")
    assert api.user(TG).status is UserStatus.active
    assert _cards(harness)


async def test_profile_incomplete_and_banned_empty_states() -> None:
    api = FakeApiClient()
    api.onboard(TG)
    harness = BotHarness(api, user_id=TG)
    original = api._h_feed_next

    async def empty(tg_id: int, **_: Any) -> FeedEmpty:
        return FeedEmpty(reason=reason, expand_options=[], resets_at=None)

    api._h_feed_next = empty  # type: ignore[method-assign]
    reason = FeedEmptyReason.banned
    await harness.send_text("🔍 Дивитися анкети")
    assert harness.last_text() == "Твою анкету заблоковано."
    reason = FeedEmptyReason.profile_incomplete
    api.user(TG).status, api.user(TG).step = (
        UserStatus.onboarding,
        api.user(TG).step.__class__("city"),
    )
    await harness.send_text("🔍 Дивитися анкети")
    assert harness.last_text().startswith("Крок 4 з 10")
    api._h_feed_next = original  # type: ignore[method-assign]


async def test_feed_error_shows_text_and_retry_works() -> None:
    api = FakeApiClient()
    api.onboard(TG)
    harness = BotHarness(api, user_id=TG)
    api.fail_next("feed_next", ApiError(code=ErrorCode.internal, message="m"))
    await harness.send_text("🔍 Дивитися анкети")
    assert harness.last_text() == "Щось пішло не так. Спробуй ще раз за хвилину."
    await harness.send_text("🔍 Дивитися анкети")
    assert _cards(harness)


async def test_rate_limit_and_conflict_on_reaction() -> None:
    harness = await _feed()
    harness.api.fail_next("react", ApiError(code=ErrorCode.rate_limited, message="m"))
    await harness.send_text("❤️")
    assert harness.last_text() == "Повільніше 🙂 Зроби паузу на хвилину."
    await harness.send_text("🔍 Дивитися анкети")
    cards_before = len(_cards(harness))
    harness.api.fail_next("react", ApiError(code=ErrorCode.conflict, message="m"))
    await harness.send_text("👎")
    assert len(_cards(harness)) == cards_before + 1  # silently the next card


async def test_undo_brings_back_the_skipped_card() -> None:
    harness = await _feed()
    skipped = harness.api.user(TG).current
    await harness.send_text("👎")
    assert "↩️ Повернути" in harness.buttons()
    await harness.tap("↩️ Повернути")
    assert harness.api.user(TG).current == skipped
    await harness.tap("↩️ Повернути")
    assert harness.alerts()[-1] == "Повернути вже не можна"
