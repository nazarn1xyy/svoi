"""S3-FE acceptance (FRONTEND.md S3): goals and interests."""

from flows import at_step
from harness import BotHarness
from hypothesis import given
from hypothesis import strategies as st
from svoi_bot.features.interests.selection import can_finish, toggle
from svoi_contracts.constants import INTERESTS_COUNT
from svoi_contracts.enums import GoalCode, OnboardingStep


def _puts(harness: BotHarness, name: str) -> list[object]:
    return [c.body for c in harness.api.calls if c.name == name]


async def test_goals_multi_select_done_inactive_until_one() -> None:
    harness = BotHarness()
    await at_step(harness, OnboardingStep.goals)
    assert harness.last_text() == "Крок 5 з 10 · Навіщо ти тут? Можна обрати кілька."
    assert harness.buttons()[0] == "👫 Знайти друзів"
    await harness.tap("Готово ▶️ (0)")
    assert harness.alerts()[-1] == "Обери хоча б одну мету"
    await harness.tap("👫 Знайти друзів")
    await harness.tap("🎮 Грати онлайн")
    assert "✅ 👫 Знайти друзів" in harness.buttons()
    await harness.tap("Готово ▶️ (2)")
    (body,) = _puts(harness, "set_goals")
    assert body.model_dump()["codes"] == [GoalCode.friends, GoalCode.gaming]  # type: ignore[attr-defined]


async def _interests(harness: BotHarness) -> None:
    await at_step(harness, OnboardingStep.interests)


async def test_selection_survives_switching_categories_and_one_put() -> None:
    harness = BotHarness()
    await _interests(harness)
    assert harness.last_text().startswith("Крок 6 з 10 · Що тобі подобається?")
    assert "Обрано: 0" in harness.last_text()
    await harness.tap("⚽ Спорт")
    await harness.tap("Футбол")
    await harness.tap("Біг")
    await harness.tap("◀️ Назад")
    assert "Обрано: 2" in harness.last_text()
    await harness.tap("🎮 Ігри")
    await harness.tap("CS2")
    await harness.tap("◀️ Назад")
    assert "Обрано: 3" in harness.last_text()
    await harness.tap("Готово ▶️ (3)")
    (body,) = _puts(harness, "set_interests")
    assert body.model_dump()["interest_ids"] == [1, 5, 14]  # type: ignore[attr-defined]
    assert harness.api.user(100).step is OnboardingStep.clarify


async def test_done_never_sends_fewer_than_three() -> None:
    harness = BotHarness()
    await _interests(harness)
    await harness.tap("⚽ Спорт")
    await harness.tap("Футбол")
    await harness.tap("◀️ Назад")
    await harness.tap("Готово ▶️ (1)")
    assert harness.alerts()[-1] == "Обери щонайменше 3 інтереси"
    assert _puts(harness, "set_interests") == []


async def test_sixteenth_interest_is_refused() -> None:
    harness = BotHarness()
    await _interests(harness)
    for category in ("⚽ Спорт", "🎮 Ігри"):
        await harness.tap(category)
        for label in [b for b in harness.buttons() if not b.startswith(("✅", "◀️", "▶️", "Готово"))][
            :8
        ]:
            await harness.tap(label)
        await harness.tap("◀️ Назад")
    assert "Обрано: 15" in harness.last_text()
    assert harness.alerts()[-1] == "Максимум 15 інтересів"


async def test_pages_of_twelve() -> None:
    harness = BotHarness()
    await _interests(harness)
    await harness.tap("⚽ Спорт")  # 13 tags
    assert "▶️" in harness.buttons()
    await harness.tap("▶️")
    assert "Теніс" in harness.buttons()


async def test_custom_tag_matched_and_pending() -> None:
    harness = BotHarness()
    await _interests(harness)
    await harness.tap("✍️ Своє")
    assert harness.last_text() == "Напиши свій інтерес одним-двома словами."
    await harness.send_text("футбол")
    assert "Знайшов: «Футбол» — додав до вибору." in harness.texts()
    assert "Обрано: 1" in harness.last_text()
    await harness.tap("✍️ Своє")
    await harness.send_text("кайтсерфінг")
    assert "Додав «кайтсерфінг» на перевірку." in " ".join(harness.texts())
    assert "Обрано: 1" in harness.last_text()


async def test_custom_tag_content_blocked_and_length() -> None:
    harness = BotHarness()
    await _interests(harness)
    await harness.tap("✍️ Своє")
    await harness.send_text("t.me/shop")
    assert harness.last_text() == "Посилання заборонені."
    await harness.send_text("x")
    assert harness.last_text() == "Інтерес — від 2 до 30 символів."


async def test_edit_mode_preselects_saved_interests() -> None:
    from svoi_bot.features.interests.handlers import show_interests  # noqa: PLC0415
    from svoi_bot.features.onboarding.registry import StepContext, open_edit  # noqa: PLC0415

    harness = BotHarness()
    harness.api.onboard(100)  # active user with interests 1, 2, 3
    await harness.send_text("hi")
    harness.clear()
    state = harness._context()
    ctx = StepContext(
        bot=harness.bot,
        state=state,
        api=harness.api,
        user_state=await harness.api.get_me(100),
        tg_user=harness.user,
    )
    assert show_interests is not None
    await open_edit(ctx, OnboardingStep.interests)
    assert "Обрано: 3" in harness.last_text()
    await harness.tap("⚽ Спорт")
    assert harness.buttons()[:2] == ["✅ Футбол", "✅ Баскетбол"]


@given(st.lists(st.sampled_from([str(i) for i in range(30)]), max_size=60))
def test_reducer_invariants(taps: list[str]) -> None:
    selected: tuple[str, ...] = ()
    for value in taps:
        before = selected
        result = toggle(selected, value, INTERESTS_COUNT[1])
        selected = result.selected
        assert len(selected) <= INTERESTS_COUNT[1]
        assert len(set(selected)) == len(selected)
        if not result.rejected:
            assert set(toggle(selected, value, INTERESTS_COUNT[1]).selected) == set(before)
    assert can_finish(len(selected), INTERESTS_COUNT) == (3 <= len(selected) <= 15)
