"""S6-FE acceptance (FRONTEND.md S6): filters and settings, one full PUT per change."""

from datetime import time

import pytest
from harness import BotHarness
from hypothesis import given
from hypothesis import strategies as st
from svoi_bot.api_client import FakeApiClient
from svoi_bot.features.settings.age import adjust
from svoi_contracts.api.prefs import FiltersIn, SettingsIn
from svoi_contracts.enums import GenderFilter, NotifyFrequency, RadiusMode

TG = 100


async def _settings(age: int = 19) -> BotHarness:
    api = FakeApiClient()
    api.onboard(TG, age=age)
    harness = BotHarness(api, user_id=TG)
    await harness.send_text("⚙️ Налаштування")
    return harness


def _bodies(harness: BotHarness, name: str) -> list[object]:
    return [c.body for c in harness.api.calls if c.name == name]


async def test_screen_lists_current_values() -> None:
    harness = await _settings()
    text = harness.last_text()
    for line in (
        "🎂 Вік: 18–22",
        "👥 З ким: Усі",
        "📍 Де шукати: Моє місто",
        "✅ Тільки верифіковані: вимк",
        "🌐 Мова: 🇺🇦 Українська",
    ):
        assert line in text, line


async def test_gender_and_radius_each_send_one_full_put() -> None:
    harness = await _settings()
    await harness.tap("👥 З ким: Усі")
    await harness.tap("З дівчатами")
    await harness.tap("📍 Де шукати: Моє місто")
    await harness.tap("Уся область")
    assert _bodies(harness, "set_filters") == [
        FiltersIn(
            age_min=18,
            age_max=22,
            gender=GenderFilter.female,
            radius=RadiusMode.city,
            verified_only=False,
        ),
        FiltersIn(
            age_min=18,
            age_max=22,
            gender=GenderFilter.female,
            radius=RadiusMode.region,
            verified_only=False,
        ),
    ]
    assert "📍 Де шукати: Уся область" in harness.last_text()


async def test_verified_toggle() -> None:
    harness = await _settings()
    await harness.tap("✅ Тільки верифіковані: вимк")
    (body,) = _bodies(harness, "set_filters")
    assert body.model_dump()["verified_only"] is True  # type: ignore[attr-defined]
    assert "✅ Тільки верифіковані: увімк" in harness.last_text()


async def test_adult_age_range_moves_within_bounds() -> None:
    harness = await _settings(age=19)
    await harness.tap("🎂 Вік: 18–22")
    await harness.tap("+ мін")
    await harness.tap("− макс")
    assert harness.last_text().startswith("🎂 Вік: 19–21")
    for _ in range(5):
        await harness.tap("− мін")
    assert harness.api.user(TG).filters.age_min == 18  # type: ignore[union-attr]


async def test_minor_pool_range_is_fixed_with_explanation() -> None:
    harness = await _settings(age=16)
    await harness.tap("🎂 Вік: 16–17")
    assert "Для твого віку пошук тільки серед 16–17" in harness.last_text()
    assert "+ мін" not in harness.buttons()
    assert _bodies(harness, "set_filters") == []


async def test_privacy_and_notifications() -> None:
    harness = await _settings()
    await harness.tap("🔒 Приватність")
    await harness.tap("Показувати відстань: увімк")
    await harness.tap("◀️ Назад")
    await harness.tap("🔔 Сповіщення")
    await harness.tap("Раз на день")
    await harness.tap("🔔 Сповіщення")
    await harness.tap("Без тихих годин")
    bodies = _bodies(harness, "set_settings")
    assert bodies[0] == SettingsIn(
        notify_frequency=NotifyFrequency.instant,
        quiet_from=time(23, 0),
        quiet_to=time(8, 0),
        show_distance=False,
        show_institution=True,
    )
    assert bodies[1].model_dump()["notify_frequency"] is NotifyFrequency.daily  # type: ignore[attr-defined]
    assert bodies[2].model_dump()["quiet_from"] == bodies[2].model_dump()["quiet_to"]  # type: ignore[attr-defined]
    assert "тихі години немає" in harness.last_text()


async def test_language_change_redraws_in_the_new_language() -> None:
    harness = await _settings()
    await harness.tap("🌐 Мова")
    await harness.tap("🇬🇧 English")
    assert harness.last_text().startswith("⚙️ Settings")
    assert "🌐 Language: 🇬🇧 English" in harness.last_text()


@pytest.mark.parametrize("bounds", [(16, 17), (18, 99)])
@given(
    st.lists(st.sampled_from(["min_down", "min_up", "max_down", "max_up"]), max_size=80),
    st.integers(min_value=0, max_value=120),
    st.integers(min_value=0, max_value=120),
)
def test_age_reducer_keeps_order_and_bounds(
    bounds: tuple[int, int], presses: list[str], start_min: int, start_max: int
) -> None:
    low, high = bounds
    age_min, age_max = sorted((start_min, start_max))
    for press in presses:
        age_min, age_max = adjust(age_min, age_max, bounds, press)  # type: ignore[arg-type]
        assert low <= age_min <= age_max <= high
