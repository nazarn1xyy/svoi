"""Texts and keyboards of S1 steps (FRONTEND.md S1)."""

from aiogram.types import InlineKeyboardMarkup
from svoi_contracts.constants import NAME_LEN
from svoi_contracts.enums import Gender, Lang, OnboardingStep

from svoi_bot.ui import keyboards
from svoi_bot.ui.i18n import _
from svoi_bot.ui.keyboards import Option
from svoi_bot.ui.progress import step_header

LANG_FIELD, CONSENT_FIELD, NAME_FIELD, GENDER_FIELD = "lang", "consent", "name", "gender"
GO, HOW, BACK = "go", "how", "back"
AGE_INPUT_MAX = 150  # AgeIn accepts 0..150; anything else never reaches the API


def titled(step: OnboardingStep, question: str) -> str:
    """«Крок N з 10 · question»."""
    header = step_header(step)
    return f"{header} · {question}" if header else question


def language() -> tuple[str, InlineKeyboardMarkup]:
    """Language choice, always in English so everyone can read it."""
    options = [
        Option(Lang.uk.value, "🇺🇦 Українська"),
        Option(Lang.en.value, "🇬🇧 English"),
        Option(Lang.ru.value, "🇷🇺 Русский"),
    ]
    return _("onboarding.lang.ask"), keyboards.inline_choice(options, LANG_FIELD, columns=1)


def consent() -> tuple[str, InlineKeyboardMarkup]:
    """Greeting, safety note and terms."""
    options = [Option(GO, _("onboarding.consent.go")), Option(HOW, _("onboarding.consent.how"))]
    return _("onboarding.consent.text"), keyboards.inline_choice(options, CONSENT_FIELD)


def how_it_works() -> tuple[str, InlineKeyboardMarkup]:
    """Three-step explanation with a way back."""
    options = [Option(BACK, _("ui.button.back"))]
    return _("onboarding.consent.how_text"), keyboards.inline_choice(options, CONSENT_FIELD)


def age() -> str:
    """Age question; the answer is typed."""
    return titled(OnboardingStep.age, _("onboarding.age.ask"))


def age_not_a_number() -> str:
    """Typed something other than a plausible number."""
    return _("onboarding.age.not_a_number")


def parse_age(text: str) -> int | None:
    """Digits only, within what AgeIn accepts."""
    value = text.strip()
    if not value.isdecimal():
        return None
    number = int(value)
    return number if number <= AGE_INPUT_MAX else None


def name_button_allowed(first_name: str | None) -> bool:
    """The Telegram name is offered only when it already fits NAME_LEN."""
    return first_name is not None and NAME_LEN[0] <= len(first_name.strip()) <= NAME_LEN[1]


def name(first_name: str | None) -> tuple[str, InlineKeyboardMarkup | None]:
    """Name question with the Telegram name as a one-tap answer."""
    text = titled(OnboardingStep.name, _("onboarding.name.ask"))
    if not name_button_allowed(first_name):
        return text, None
    clean = (first_name or "").strip()
    return text, keyboards.inline_choice([Option("tg", clean)], NAME_FIELD, columns=1)


def name_rules() -> str:
    """Name rejected by the API."""
    return _("onboarding.name.rules")


def gender() -> tuple[str, InlineKeyboardMarkup]:
    """Gender with the hint that it only feeds the filter."""
    options = [
        Option(Gender.male.value, _("onboarding.gender.male")),
        Option(Gender.female.value, _("onboarding.gender.female")),
        Option(Gender.hidden.value, _("onboarding.gender.hidden")),
    ]
    text = (
        titled(OnboardingStep.gender, _("onboarding.gender.ask"))
        + "\n\n"
        + _("onboarding.gender.hint")
    )
    return text, keyboards.inline_choice(options, GENDER_FIELD, columns=2)
