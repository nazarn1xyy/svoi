"""One message per step: inline steps edit it, so the chat does not fill with old prompts."""

from contextlib import suppress

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove

KEY = "screen_message_id"
AnyMarkup = InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | None


class Screen:
    """Message of the current step; its id lives in FSM data."""

    def __init__(self, bot: Bot, state: FSMContext) -> None:
        self.bot = bot
        self.state = state
        self.chat_id = state.key.chat_id

    async def show(self, text: str, markup: AnyMarkup = None) -> None:
        """Send a new screen message and remember it."""
        message = await self.bot.send_message(
            chat_id=self.chat_id, text=text, reply_markup=markup, parse_mode="HTML"
        )
        # reply keyboards cannot be edited later, so only inline screens are remembered
        keep = markup is None or isinstance(markup, InlineKeyboardMarkup)
        await self.state.update_data({KEY: message.message_id if keep else None})

    async def replace(self, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
        """Edit the remembered message; send a new one when there is none."""
        message_id = (await self.state.get_data()).get(KEY)
        if message_id is None:
            await self.show(text, markup)
            return
        try:
            await self.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=message_id,
                text=text,
                reply_markup=markup,
                parse_mode="HTML",
            )
        except TelegramBadRequest as exc:
            if "message is not modified" not in str(exc):
                await self.show(text, markup)

    async def clear(self) -> None:
        """Drop the buttons of the remembered message and forget it."""
        message_id = (await self.state.get_data()).get(KEY)
        if message_id is not None:
            # the message may be gone or unchanged; either way there is nothing to clean up
            with suppress(TelegramBadRequest):
                await self.bot.edit_message_reply_markup(
                    chat_id=self.chat_id, message_id=message_id, reply_markup=None
                )
        await self.state.update_data({KEY: None})
