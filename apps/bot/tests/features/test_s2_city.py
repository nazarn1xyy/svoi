"""S2-FE acceptance (FRONTEND.md S2): city by text or location."""

from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove
from flows import at_step
from harness import BotHarness
from svoi_bot.features.city.states import CitySG
from svoi_contracts.api.profile import CityIn
from svoi_contracts.enums import OnboardingStep
from svoi_contracts.errors import ApiError, ErrorCode

ASK = "Крок 4 з 10 · З якого ти міста?"


async def _city_step() -> BotHarness:
    harness = BotHarness()
    await at_step(harness, OnboardingStep.city)
    return harness


def _set_city_bodies(harness: BotHarness) -> list[CityIn]:
    return [c.body for c in harness.api.calls if c.name == "set_city"]  # type: ignore[misc]


async def test_screen_has_the_location_button_and_privacy_note() -> None:
    harness = await _city_step()
    assert harness.last_text().startswith(ASK)
    assert "±1 км" in harness.last_text()
    markup = harness.last_markup()
    assert isinstance(markup, ReplyKeyboardMarkup)
    assert markup.keyboard[0][0].request_location is True
    assert await harness.state() == CitySG.input.state


async def test_one_result_confirm_saves_without_coordinates() -> None:
    harness = await _city_step()
    await harness.send_text("Могилів")
    assert harness.last_text() == "Могилів-Подільський, Вінницька область?"
    await harness.tap("✅ Так")
    assert _set_city_bodies(harness) == [CityIn(city_id=700918)]
    assert harness.api.user(100).step is OnboardingStep.goals


async def test_several_results_list_with_other() -> None:
    harness = await _city_step()
    await harness.send_text("Ки")
    buttons = harness.buttons()
    assert 2 <= len(buttons) - 1 <= 5
    assert buttons[-1] == "🔄 Інше"
    assert "Київ, Київ" in buttons
    await harness.tap("Київ, Київ")
    assert _set_city_bodies(harness)[0].city_id == 703448


async def test_no_results() -> None:
    harness = await _city_step()
    await harness.send_text("Атлантида")
    assert harness.last_text() == "Не знайшов таке місто. Спробуй написати інакше."
    assert await harness.state() == CitySG.input.state


async def test_short_query_never_reaches_the_api() -> None:
    harness = await _city_step()
    before = len(harness.api.calls)
    await harness.send_text("К")
    assert harness.last_text() == "Напиши хоча б 2 літери"
    assert [c.name for c in harness.api.calls[before:]] == []


async def test_location_confirmed_sends_coordinates() -> None:
    harness = await _city_step()
    await harness.send_location(48.4431, 27.7998)
    assert harness.last_text() == "Ти в місті Могилів-Подільський?"
    await harness.tap("✅ Так")
    assert _set_city_bodies(harness) == [CityIn(city_id=700918, lat=48.4431, lon=27.7998)]


async def test_location_refused_goes_back_to_typing() -> None:
    harness = await _city_step()
    await harness.send_location(48.4431, 27.7998)
    await harness.tap("🔄 Ні, інше")
    assert harness.last_text() == "Напиши назву свого міста."
    assert await harness.state() == CitySG.input.state
    await harness.send_text("Вінниця")
    await harness.tap("✅ Так")
    assert _set_city_bodies(harness) == [CityIn(city_id=689558)]


async def test_location_far_from_any_city() -> None:
    harness = await _city_step()
    await harness.send_location(0.0, 0.0)
    assert harness.last_text() == "Не вдалося визначити місто. Напиши його назву."


async def test_by_location_500_shows_error_and_typing_still_works() -> None:
    harness = await _city_step()
    harness.api.fail_next("city_by_location", ApiError(code=ErrorCode.internal, message="m"))
    await harness.send_location(48.44, 27.80)
    assert harness.last_text() == "Щось пішло не так. Спробуй ще раз за хвилину."
    await harness.send_text("Могилів")
    assert harness.last_text().startswith("Могилів-Подільський")


async def test_desktop_users_can_type_and_keyboard_is_removed_after_success() -> None:
    harness = await _city_step()
    await harness.send_text("✍️ Напишу назву")
    assert harness.last_text() == "Напиши назву свого міста."
    await harness.send_text("Вінниця")
    await harness.tap("✅ Так")
    removals = [
        m
        for m in harness.shown()
        if isinstance(getattr(m, "reply_markup", None), ReplyKeyboardRemove)
    ]
    assert len(removals) == 1
