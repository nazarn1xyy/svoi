"""Shortcuts that put a harness user on a given onboarding step through the fake API."""

from harness import BotHarness
from svoi_bot.middlewares.user_context import CACHE_TTL_S
from svoi_contracts.enums import Gender, GoalCode, OnboardingStep

FILLED_BEFORE = {
    OnboardingStep.city: ("age", "name", "gender"),
    OnboardingStep.goals: ("age", "name", "gender", "city"),
    OnboardingStep.interests: ("age", "name", "gender", "city", "goals"),
}


async def at_step(harness: BotHarness, step: OnboardingStep, *, age: int = 19) -> None:
    """Register the user, fill earlier answers in the fake, and show `step`."""
    await harness.send_command("start")
    user = harness.api.user(harness.user.id)
    user.age, user.name, user.gender = age, "Ірина", Gender.female
    order = list(OnboardingStep)
    if order.index(step) > order.index(OnboardingStep.city):
        user.city_id = 700918
    if order.index(step) > order.index(OnboardingStep.goals):
        user.goals = [GoalCode.friends]
    if order.index(step) > order.index(OnboardingStep.interests):
        user.interests = {1: None, 2: None, 14: None}
    user.step = step
    harness.clock.tick(CACHE_TTL_S + 1)  # the next update asks the API again
    harness.clear()
    await harness.send_text("…")  # any message resumes the saved step
