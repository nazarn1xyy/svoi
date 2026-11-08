"""Main menu (S5 extends it)."""

from aiogram.types import Message
from svoi_contracts.cards import UserState

from svoi_bot.ui import keyboards
from svoi_bot.ui.i18n import _


async def show_menu(message: Message, user_state: UserState) -> None:
    """Reply keyboard of the main menu with the likes counter."""
    await message.answer(_("menu.home"), reply_markup=keyboards.main_menu(user_state.counters))
