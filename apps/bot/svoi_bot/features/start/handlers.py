"""/start [r_<code>]: UserContextMiddleware already called POST /users/start with the code."""

from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from svoi_contracts.cards import UserState
from svoi_contracts.enums import UserStatus

from svoi_bot.features.onboarding.registry import StepContext, show_step
from svoi_bot.features.start.menu import show_menu


async def on_start(
    message: Message, state: FSMContext, user_state: UserState, step: StepContext
) -> None:
    """Onboarding users see their saved step as a fresh message; others get the menu."""
    if user_state.status is UserStatus.onboarding:
        await step.screen.clear()
        await show_step(step, user_state.onboarding_step)
        return
    await state.set_state(None)
    await show_menu(message, user_state)
