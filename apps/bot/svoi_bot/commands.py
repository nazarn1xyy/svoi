"""setMyCommands per language (FRONTEND.md S5)."""

from aiogram import Bot
from aiogram.types import BotCommand
from svoi_contracts.enums import Lang

from svoi_bot.ui.i18n import _, set_locale

COMMANDS = (
    "start",
    "search",
    "likes",
    "profile",
    "contacts",
    "settings",
    "pause",
    "verify",
    "help",
)


def commands(lang: Lang) -> list[BotCommand]:
    """Command list with descriptions in one language."""
    set_locale(lang)
    return [BotCommand(command=c, description=_(f"commands.{c}")) for c in COMMANDS]


async def set_commands(bot: Bot) -> None:
    """uk is the default list; ru and en apply to clients in those languages."""
    await bot.set_my_commands(commands(Lang.uk))
    for lang in (Lang.ru, Lang.en):
        await bot.set_my_commands(commands(lang), language_code=lang.value)
    set_locale(Lang.uk)
