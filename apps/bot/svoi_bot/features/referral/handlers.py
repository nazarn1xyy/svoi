"""Referral screen: personal deep link and a Telegram share button."""

from urllib.parse import quote

from aiogram.types import CallbackQuery

from svoi_bot.features.onboarding.registry import StepContext
from svoi_bot.middlewares.user_context import REFERRAL_PREFIX
from svoi_bot.ui import keyboards
from svoi_bot.ui.i18n import _
from svoi_bot.ui.keyboards import url_button


async def show(step: StepContext) -> None:
    """GET /referral → link https://t.me/<bot>?start=r_<code> with stats."""
    referral = await step.api.get_referral(step.tg_user.id)
    me = await step.bot.me()
    link = f"https://t.me/{me.username}?start={REFERRAL_PREFIX}{referral.code}"
    text = _(
        "referral.text", bonus=referral.bonus_per_invite, link=link, invited=referral.invited_count
    )
    share = (
        f"https://t.me/share/url?url={quote(link, safe='')}"
        f"&text={quote(_('referral.share_text'), safe='')}"
    )
    await step.bot.send_message(
        step.tg_user.id,
        text,
        reply_markup=keyboards.markup([[url_button(_("referral.share"), share)]]),
    )


async def on_open(query: CallbackQuery, step: StepContext) -> None:
    """From settings or the daily-limit screen."""
    await query.answer()
    await show(step)
