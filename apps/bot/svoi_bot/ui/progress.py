"""Onboarding step numbering from FRONTEND.md section 9."""

from svoi_contracts.enums import OnboardingStep

from svoi_bot.ui.i18n import _

NUMBERED = (
    OnboardingStep.age,
    OnboardingStep.name,
    OnboardingStep.gender,
    OnboardingStep.city,
    OnboardingStep.goals,
    OnboardingStep.interests,
    OnboardingStep.institution,
    OnboardingStep.height,
    OnboardingStep.prompts,
    OnboardingStep.media,
)


def step_header(step: OnboardingStep) -> str:
    """«Крок N з 10»; empty for unnumbered steps (clarify, preview)."""
    if step not in NUMBERED:
        return ""
    return _("ui.step_header", n=NUMBERED.index(step) + 1, total=len(NUMBERED))
