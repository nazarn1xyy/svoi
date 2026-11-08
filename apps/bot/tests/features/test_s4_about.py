"""S4-FE acceptance (FRONTEND.md S4): optional steps and the preview."""

import json
from pathlib import Path

from flows import at_step
from harness import BotHarness
from svoi_bot.api_client.fixtures import fixtures_dir
from svoi_bot.ui.i18n import catalog
from svoi_contracts.enums import Lang, OnboardingStep, UserStatus
from svoi_contracts.errors import ApiError, ErrorCode


def _calls(harness: BotHarness, name: str) -> list[object]:
    return [c.body for c in harness.api.calls if c.name == name]


def _skips(harness: BotHarness) -> list[str]:
    return [b.model_dump()["step"].value for b in _calls(harness, "skip_step")]  # type: ignore[attr-defined]


async def test_skipping_every_optional_step_calls_skip_with_its_step() -> None:
    harness = BotHarness()
    await at_step(harness, OnboardingStep.clarify)
    assert "Граєш" in harness.last_text() or "граєш" in harness.last_text()
    await harness.tap("⏭ Пропустити")
    assert harness.last_text().startswith("Крок 7 з 10 · Де навчаєшся або працюєш?")
    assert "МПМЕФК" in harness.buttons()
    await harness.tap("⏭ Пропустити")
    assert harness.last_text().startswith("Крок 8 з 10 · Вкажеш зріст?")
    await harness.tap("⏭ Пропустити")
    assert harness.last_text().startswith("Крок 9 з 10 · Обери питання")
    await harness.tap("⏭ Пропустити")
    assert harness.last_text().startswith("Крок 10 з 10 · Додай до 3 фото")
    await harness.tap("⏭ Без фото")
    assert _skips(harness) == ["clarify", "institution", "height", "prompts", "media"]
    assert "Так тебе побачать інші:" in harness.texts()
    assert harness.api.user(100).step is OnboardingStep.preview


async def test_filling_every_optional_step() -> None:
    harness = BotHarness()
    await at_step(harness, OnboardingStep.clarify)
    await harness.tap(harness.buttons()[0])  # first option of the first question
    await harness.tap(harness.buttons()[0])  # second question
    assert harness.last_text().startswith("Крок 7 з 10")
    await harness.tap("МПМЕФК")
    await harness.send_text("100")
    assert harness.last_text() == "Зріст — число від 120 до 230"
    await harness.send_text("182")
    await harness.tap("🌅 Ідеальні вихідні — це…")
    assert harness.last_text() == "🌅 Ідеальні вихідні — це… Напиши відповідь до 300 символів."
    await harness.send_text("катка з друзями")
    await harness.tap("➕ Ще одне")
    assert "🌅 Ідеальні вихідні — це…" not in harness.buttons()
    await harness.tap("🎧 Зараз слухаю…")
    await harness.send_text("Kalush")
    assert harness.last_text().startswith("Крок 10 з 10")
    await harness.send_photo("p1")
    assert harness.last_text() == "Додано (1/3). Ще одне?"
    await harness.tap("✅ Готово")
    user = harness.api.user(100)
    assert user.institution_id == 1 and user.height_cm == 182
    assert [p for p, _ in user.prompts] == [1, 4]
    assert len([n for n in user.interests.values() if n]) == 2
    assert _skips(harness) == ["clarify", "media"]


async def test_album_of_three_makes_three_calls_and_fourth_hits_the_limit() -> None:
    harness = BotHarness()
    await at_step(harness, OnboardingStep.media)
    for i in range(3):
        await harness.send_photo(f"p{i}", media_group_id="g1")
    assert len(_calls(harness, "add_media")) == 3
    assert harness.last_text() == "Додано (3/3). Ще одне?"
    await harness.send_photo("p4")
    assert harness.last_text() == "Можна додати до 3 фото або відео."


async def test_other_file_types_are_refused() -> None:
    harness = BotHarness()
    await at_step(harness, OnboardingStep.media)
    await harness.send_voice(3)
    assert harness.last_text() == "Надішли фото або відео"
    assert _calls(harness, "add_media") == []


async def test_long_prompt_is_not_sent_and_blocked_text_stays_on_prompt() -> None:
    harness = BotHarness()
    await at_step(harness, OnboardingStep.prompts)
    await harness.tap("🔍 Шукаю людину, яка…")
    await harness.send_text("x" * 301)
    assert harness.last_text() == "Відповідь — до 300 символів. Скороти, будь ласка."
    assert _calls(harness, "set_prompts") == []
    await harness.send_text("пиши мені @ira")
    assert harness.last_text() == (
        "Згадки @ заборонені. Контакти відкриються після взаємної симпатії."
    )
    await harness.send_text("любить гори")
    assert harness.last_text() == "Додати ще одне питання?"


async def test_preview_shows_the_api_card_and_completes() -> None:
    harness = BotHarness(username=None)
    await at_step(harness, OnboardingStep.preview)
    card_text = next(t for t in harness.texts() if t.startswith("<b>Ірина, 19</b>"))
    assert "🏷 футбол · баскетбол · CS2" in card_text
    assert "Створи username" in " ".join(harness.texts()) or "створи username" in " ".join(
        harness.texts()
    )
    await harness.tap("✅ Все вірно, до анкет")
    assert harness.last_text() == "Готово! Тепер подивимось, хто поруч 👇"
    assert harness.api.user(100).status is UserStatus.active


async def test_profile_incomplete_returns_to_the_first_missing_step() -> None:
    harness = BotHarness()
    await at_step(harness, OnboardingStep.preview)
    harness.api.fail_next(
        "complete_onboarding",
        ApiError(code=ErrorCode.profile_incomplete, message="m", details={"missing": ["goals"]}),
    )
    await harness.tap("✅ Все вірно, до анкет")
    assert harness.last_text() == "Крок 5 з 10 · Навіщо ти тут? Можна обрати кілька."


def test_all_clarification_keys_translated() -> None:
    keys = [
        c["question_key"]
        for c in json.loads((Path(fixtures_dir()) / "clarifications.json").read_text())
    ]
    for lang in Lang:
        missing = [k for k in keys if f"clarify.{k}" not in catalog(lang)]
        assert not missing, lang
