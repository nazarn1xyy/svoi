"""S5-FE acceptance (FRONTEND.md S5): main menu, «Моя анкета», edits, hide, delete, reset."""

import pytest
from aiogram.types import ReplyKeyboardMarkup
from harness import BotHarness
from svoi_bot.api_client import FakeApiClient
from svoi_contracts.enums import OnboardingStep, UserStatus

TG = 100


async def _profile() -> BotHarness:
    api = FakeApiClient()
    api.onboard(TG)
    harness = BotHarness(api, user_id=TG)
    await harness.send_text("👤 Моя анкета")
    return harness


def _menu_counter(harness: BotHarness) -> str:
    for method in reversed(harness.shown()):
        markup = getattr(method, "reply_markup", None)
        if isinstance(markup, ReplyKeyboardMarkup):
            return markup.keyboard[0][1].text
    raise AssertionError("no menu")


async def test_profile_screen_shows_card_completeness_and_buttons() -> None:
    harness = await _profile()
    assert harness.last_text().startswith("<b>Тест, 19</b>")
    assert "Анкета заповнена на 60% — додай фото" in harness.last_text()
    buttons = harness.buttons()
    for label in (
        "✏️ Ім'я",
        "🎂 Вік",
        "📍 Місто",
        "🎯 Мета",
        "🏷 Інтереси",
        "🎓 Навчання",
        "📏 Зріст",
        "💬 Про себе",
        "🖼 Фото",
        "🔄 Заповнити заново",
        "⏸ Приховати анкету",
        "🗑 Видалити анкету",
    ):
        assert label in buttons, label


@pytest.mark.parametrize(
    ("button", "answer", "field", "value"),
    [
        ("✏️ Ім'я", "Оля", "name", "Оля"),
        ("📏 Зріст", "175", "height_cm", 175),
    ],
)
async def test_editing_a_typed_field_returns_to_my_profile(
    button: str, answer: str, field: str, value: object
) -> None:
    harness = await _profile()
    await harness.tap(button)
    await harness.send_text(answer)
    assert getattr(harness.api.user(TG), field) == value
    assert harness.last_text().startswith("<b>")
    assert "✏️ Ім'я" in harness.buttons()
    assert harness.api.user(TG).step is OnboardingStep.done  # no onboarding restart


@pytest.mark.parametrize(("button", "pick"), [("🎓 Навчання", "МПМЕФК")])
async def test_editing_a_button_field_returns_to_my_profile(button: str, pick: str) -> None:
    harness = await _profile()
    await harness._context().update_data({"city_id": 700918})
    await harness.tap(button)
    await harness.tap(pick)
    assert harness.api.user(TG).institution_id == 1
    assert "✏️ Ім'я" in harness.buttons()


async def test_editing_goals_starts_from_saved_goals() -> None:
    harness = await _profile()
    await harness.tap("🎯 Мета")
    assert "✅ 👫 Знайти друзів" in harness.buttons()
    await harness.tap("📚 Разом навчатися")
    await harness.tap("Готово ▶️ (2)")
    assert [g.value for g in harness.api.user(TG).goals] == ["friends", "study"]
    assert "✏️ Ім'я" in harness.buttons()


async def test_age_edit_after_the_window_shows_the_lock_text() -> None:
    harness = await _profile()
    harness.api.user(TG).age_edits = 1
    await harness.tap("🎂 Вік")
    await harness.send_text("20")
    assert harness.last_text() == (
        "Вік уже не можна змінити. Якщо помилився — напиши в підтримку: /help"
    )


async def test_delete_needs_two_taps() -> None:
    harness = await _profile()
    await harness.tap("🗑 Видалити анкету")
    assert harness.last_text().startswith("Видалити анкету назавжди?")
    await harness.tap("◀️ Ні")
    assert TG in harness.api.users
    await harness.tap("🗑 Видалити анкету")
    await harness.tap("🗑 Так, видалити")
    assert TG not in harness.api.users
    assert harness.last_text() == "Анкету видалено. Щоб повернутися, натисни /start."


async def test_hide_and_show() -> None:
    harness = await _profile()
    await harness.tap("⏸ Приховати анкету")
    assert "Анкету приховано." in " ".join(harness.texts())
    assert harness.api.user(TG).status is UserStatus.hidden
    await harness.tap("👁 Показати анкету")
    assert harness.api.user(TG).status is UserStatus.active


async def test_reset_restarts_onboarding_from_age() -> None:
    harness = await _profile()
    await harness.tap("🔄 Заповнити заново")
    await harness.tap("🔄 Так, заново")
    assert harness.last_text() == "Крок 1 з 10 · Скільки тобі років?"
    assert harness.api.user(TG).step is OnboardingStep.age


async def test_photo_manager_delete_and_reorder() -> None:
    harness = await _profile()
    from svoi_contracts.api.profile import MediaIn  # noqa: PLC0415
    from svoi_contracts.enums import MediaKind  # noqa: PLC0415

    for name in ("a", "b"):
        await harness.api.add_media(
            TG, MediaIn(kind=MediaKind.photo, file_id=name, file_unique_id=name)
        )
    await harness.tap("🖼 Фото")
    assert "1. 📷 фото · на перевірці" in harness.last_text()
    await harness.tap("↕️ 2")
    assert [m.file_id for m in harness.api.user(TG).media] == ["b", "a"]
    await harness.tap("🗑 1")
    assert [m.file_id for m in harness.api.user(TG).media] == ["a"]


async def test_menu_counter_comes_from_the_api_each_time() -> None:
    api = FakeApiClient()
    api.onboard(TG)
    harness = BotHarness(api, user_id=TG)
    await harness.send_command("start")
    assert _menu_counter(harness) == "❤️ Мене лайкнули"
    api.add_like(api.demo_tg_ids()[0], TG)
    api.add_like(api.demo_tg_ids()[1], TG)
    await harness.send_command("start")
    assert _menu_counter(harness) == "❤️ Мене лайкнули (2)"


async def test_help_names_support() -> None:
    harness = await _profile()
    await harness.send_command("help")
    assert harness.last_text().startswith("Питання і скарги: @svoi_support")
