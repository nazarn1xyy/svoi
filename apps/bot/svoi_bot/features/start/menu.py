"""Main menu; the likes counter is fetched every time the menu is shown (S5)."""

from aiogram import Bot
from svoi_contracts.cards import Counters

from svoi_bot.api_client import ApiClient
from svoi_bot.ui import keyboards
from svoi_bot.ui.i18n import _


async def send_menu(bot: Bot, api: ApiClient, tg_id: int, text: str | None = None) -> None:
    """Reply keyboard of the main menu with a fresh incoming-likes count."""
    count = (await api.incoming_count(tg_id)).count
    await bot.send_message(
        tg_id,
        text or _("menu.home"),
        reply_markup=keyboards.main_menu(Counters(incoming_likes=count)),
    )
