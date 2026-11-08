"""/start [r_<code>] and /help."""

from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from svoi_contracts.cards import UserState
from svoi_contracts.enums import UserStatus

from svoi_bot.config import Settings
from svoi_bot.features.onboarding.registry import StepContext, show_step
from svoi_bot.features.start.menu import send_menu
from svoi_bot.ui.i18n import _


async def on_start(
    message: Message, state: FSMContext, user_state: UserState, step: StepContext
) -> None:
    """Onboarding users see their saved step as a fresh message; others get the menu."""
    if user_state.status is UserStatus.onboarding:
        await step.screen.clear()
        await show_step(step, user_state.onboarding_step)
        return
    await state.set_state(None)
    await send_menu(step.bot, step.api, step.tg_user.id)


async def on_help(message: Message, settings: Settings) -> None:
    """Support contact and a short guide."""
    await message.answer(_("menu.help", support=settings.support_username))
