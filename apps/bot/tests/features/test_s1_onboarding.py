"""S1-FE acceptance (FRONTEND.md S1): start, language, consent, age, name, gender, resume."""

import pytest
from harness import BotHarness
from hypothesis import given, settings
from hypothesis import strategies as st
from svoi_bot.api_client import ContractViolation, FakeApiClient
from svoi_bot.features.onboarding.states import OnboardingSG
from svoi_bot.features.onboarding.views import name_button_allowed
from svoi_contracts.api.profile import AgeIn
from svoi_contracts.constants import NAME_LEN
from svoi_contracts.enums import OnboardingStep
from svoi_contracts.errors import ApiError, ErrorCode

AGE_Q = "Крок 1 з 10 · Скільки тобі років?"
NAME_Q = "Крок 2 з 10 · Як до тебе звертатися?"
GENDER_Q = "Крок 3 з 10 · Ти…"


async def _to_step(harness: BotHarness, step: OnboardingStep) -> None:
    await harness.send_command("start")
    order = [
        OnboardingStep.lang,
        OnboardingStep.consent,
        OnboardingStep.age,
        OnboardingStep.name,
        OnboardingStep.gender,
    ]
    for current in order:
        if current is step:
            return
        if current is OnboardingStep.lang:
            await harness.tap("🇺🇦 Українська")
        elif current is OnboardingStep.consent:
            await harness.tap("👌 Поїхали")
        elif current is OnboardingStep.age:
            await harness.send_text("19")
        elif current is OnboardingStep.name:
            await harness.send_text("Ірина")
        else:
            await harness.tap("Дівчина")


async def test_new_user_sees_language_choice() -> None:
    harness = BotHarness()
    await harness.send_command("start")
    assert harness.last_text() == "Choose your language 👇"
    assert harness.buttons() == ["🇺🇦 Українська", "🇬🇧 English", "🇷🇺 Русский"]
    assert await harness.state() == OnboardingSG.lang.state


async def test_after_choosing_a_language_every_text_uses_it() -> None:
    harness = BotHarness(language_code="uk")
    await harness.send_command("start")
    await harness.tap("🇬🇧 English")
    assert harness.last_text().startswith("Hi! I help you find people")
    assert harness.buttons() == ["👌 Let's go", "❓ How it works"]
    await harness.tap("👌 Let's go")
    assert harness.last_text() == "Step 1 of 10 · How old are you?"
    await harness.send_text("abc")
    assert harness.last_text() == "Type your age in digits, for example 19"


async def test_how_it_works_and_back() -> None:
    harness = BotHarness()
    await _to_step(harness, OnboardingStep.consent)
    await harness.tap("❓ Як це працює")
    assert harness.last_text().startswith("1. Заповнюєш анкету")
    await harness.tap("◀️ Назад")
    assert harness.last_text().startswith("Привіт!")


async def test_full_s1_flow_reaches_the_city_step_with_one_message_per_inline_step() -> None:
    harness = BotHarness()
    await _to_step(harness, OnboardingStep.city)
    user = harness.api.user(100)
    assert (user.age, user.name, user.gender.value if user.gender else None) == (
        19,
        "Ірина",
        "female",
    )
    assert user.step is OnboardingStep.city
    names = [type(m).__name__ for m in harness.shown()]
    # lang → consent → age edit one message; typed age and name produce new messages
    assert names[:3] == ["SendMessage", "EditMessageText", "EditMessageText"]
    assert NAME_Q in harness.texts()
    assert any(t.startswith(GENDER_Q) for t in harness.texts())
    # S2 registered the city screen, so the next step follows right away
    assert harness.texts()[-1].startswith("Крок 4 з 10")


@pytest.mark.parametrize(
    "step",
    [
        OnboardingStep.lang,
        OnboardingStep.consent,
        OnboardingStep.age,
        OnboardingStep.name,
        OnboardingStep.gender,
    ],
)
async def test_any_message_resumes_the_saved_step(step: OnboardingStep) -> None:
    api = FakeApiClient()
    first = BotHarness(api)
    await _to_step(first, step)
    expected = first.last_text()
    # the user closes the chat; a new session starts with an empty FSM and cache
    later = BotHarness(api)
    await later.send_text("привіт")
    assert later.last_text() == expected


async def test_age_15_is_refused_then_locked() -> None:
    harness = BotHarness()
    await _to_step(harness, OnboardingStep.age)
    await harness.send_text("15")
    assert harness.last_text() == "Бот доступний з 16 років. Повертайся, коли виповниться 16 🙂"
    await harness.send_text("17")
    assert harness.last_text() == (
        "Вік уже не можна змінити. Якщо помилився — напиши в підтримку: /help"
    )
    assert await harness.state() == OnboardingSG.age.state


async def test_age_too_young_from_the_api() -> None:
    harness = BotHarness()
    await _to_step(harness, OnboardingStep.age)
    harness.api.fail_next("set_age", ApiError(code=ErrorCode.age_too_young, message="m"))
    await harness.send_text("40")
    assert harness.last_text().startswith("Бот доступний з 16 років")


async def test_non_numbers_never_reach_the_api() -> None:
    harness = BotHarness()
    await _to_step(harness, OnboardingStep.age)
    before = len(harness.api.calls)
    for text in ("дев'ятнадцять", "19.5", "-3", "1000"):
        await harness.send_text(text)
        assert harness.last_text() == "Напиши вік цифрами, наприклад 19"
    assert [c.name for c in harness.api.calls[before:]] == []


async def test_fake_rejects_age_sent_as_a_string() -> None:
    # the S1 contract test: had the bot sent "19", the fake would fail the request
    with pytest.raises(ContractViolation):
        await FakeApiClient().set_age(1, AgeIn.model_construct(age="19"))


async def test_telegram_name_button_and_rules() -> None:
    harness = BotHarness(first_name="Ira")
    await _to_step(harness, OnboardingStep.name)
    assert harness.last_text() == NAME_Q
    assert harness.buttons() == ["Ira"]
    await harness.send_text("Ira2")
    assert harness.last_text() == "Ім'я — від 2 до 20 літер, без посилань і цифр"
    await harness.send_text("t.me/spam")
    assert harness.last_text() == "Ім'я — від 2 до 20 літер, без посилань і цифр"
    await harness.tap("Ira")
    assert harness.last_text().startswith(GENDER_Q)


async def test_long_telegram_name_gets_no_button() -> None:
    harness = BotHarness(first_name="Олександр-Максиміліан Великий")
    await _to_step(harness, OnboardingStep.name)
    assert harness.last_text() == NAME_Q
    assert harness.buttons() == []


async def test_timeout_on_name_keeps_the_step_and_retry_works() -> None:
    harness = BotHarness()
    await _to_step(harness, OnboardingStep.name)
    harness.api.timeout_next("set_name")
    await harness.send_text("Ірина")
    assert harness.last_text() == "Щось пішло не так. Спробуй ще раз за хвилину."
    assert await harness.state() == OnboardingSG.name.state
    await harness.send_text("Ірина")
    assert harness.last_text().startswith(GENDER_Q)


async def test_api_error_on_a_button_step_keeps_the_keyboard() -> None:
    harness = BotHarness()
    await _to_step(harness, OnboardingStep.gender)
    harness.api.fail_next("set_gender", ApiError(code=ErrorCode.internal, message="m"))
    await harness.tap("Хлопець")
    assert harness.alerts()[-1] == "Щось пішло не так. Спробуй ще раз за хвилину."
    assert await harness.state() == OnboardingSG.gender.state
    await harness.tap("Хлопець")
    assert harness.api.user(100).step is OnboardingStep.city


async def test_gender_hint_is_shown() -> None:
    harness = BotHarness()
    await _to_step(harness, OnboardingStep.gender)
    assert "Потрібно тільки для фільтра" in harness.last_text()
    assert harness.buttons() == ["Хлопець", "Дівчина", "Не вказувати"]


async def test_referral_code_reaches_start_in() -> None:
    harness = BotHarness()
    await harness.send_command("start", "r_ABC123")
    start = next(c for c in harness.api.calls if c.name == "start")
    assert start.body is not None
    assert start.body.model_dump()["referral_code"] == "ABC123"


async def test_banned_user_sees_only_the_ban_text() -> None:
    api = FakeApiClient()
    first = BotHarness(api)
    await _to_step(first, OnboardingStep.gender)
    api.ban(100, None)
    later = BotHarness(api)
    await later.send_command("start")
    assert later.texts() == ["Твою анкету заблоковано назавжди."]
    assert later.buttons() == []


@settings(max_examples=60, deadline=None)
@given(st.text(min_size=0, max_size=40))
def test_name_button_iff_length_within_name_len(first_name: str) -> None:
    expected = NAME_LEN[0] <= len(first_name.strip()) <= NAME_LEN[1]
    assert name_button_allowed(first_name) is expected
