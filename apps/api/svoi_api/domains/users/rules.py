"""Onboarding step machine (BACKEND 4.4): pure functions."""

import secrets

from svoi_contracts.enums import Lang, OnboardingStep

ORDER: tuple[OnboardingStep, ...] = tuple(OnboardingStep)
OPTIONAL_STEPS = frozenset(
    {
        OnboardingStep.clarify,
        OnboardingStep.institution,
        OnboardingStep.height,
        OnboardingStep.prompts,
        OnboardingStep.media,
    }
)
REFERRAL_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"  # base32
REFERRAL_LEN = 8


def next_step(step: OnboardingStep) -> OnboardingStep:
    """Step after `step` in OnboardingStep order (done stays done)."""
    i = ORDER.index(step)
    return ORDER[min(i + 1, len(ORDER) - 1)]


def is_ahead(step: OnboardingStep, current: OnboardingStep) -> bool:
    """`step` is not reached yet."""
    return ORDER.index(step) > ORDER.index(current)


def default_lang(tg_language_code: str | None) -> Lang:
    """uk -> uk, ru -> ru, anything else -> uk."""
    code = (tg_language_code or "").split("-")[0].lower()
    return Lang.ru if code == "ru" else Lang.uk


def new_referral_code() -> str:
    """8 random base32 characters."""
    return "".join(secrets.choice(REFERRAL_ALPHABET) for _ in range(REFERRAL_LEN))
