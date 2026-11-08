"""Mutual-like screen, shared by reactions (S8), answers to likes and the worker (S9)."""

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from svoi_contracts.cards import Icebreaker, MatchResult
from svoi_contracts.enums import IcebreakerTemplate

from svoi_bot.ui import keyboards
from svoi_bot.ui.cards import render_card, send_card
from svoi_bot.ui.format import goal_label
from svoi_bot.ui.i18n import _


def icebreaker_text(icebreaker: Icebreaker | None) -> str | None:
    """«Привід почати…» by template (1.1)."""
    if icebreaker is None:
        return None
    if icebreaker.template is IcebreakerTemplate.common_interest and icebreaker.interest_title:
        return _("match.ice.interest", interest=icebreaker.interest_title.lower())
    if icebreaker.template is IcebreakerTemplate.same_institution and icebreaker.institution_name:
        return _("match.ice.institution", institution=icebreaker.institution_name)
    if icebreaker.template is IcebreakerTemplate.common_goal and icebreaker.goal is not None:
        return _("match.ice.goal", goal=goal_label(icebreaker.goal))
    return None


def match_message(match: MatchResult) -> tuple[str, InlineKeyboardMarkup]:
    """Header text and the «💬 Написати» button."""
    name = match.partner.name
    if match.partner_username:
        text = _("match.title", name=name, username=match.partner_username)
        url = f"https://t.me/{match.partner_username}"
    else:
        text = _("match.no_username", name=name) + "\n" + _("match.privacy_note")
        url = f"tg://user?id={match.partner_tg_id}"
    ice = icebreaker_text(match.icebreaker)
    if ice:
        text += "\n\n" + ice
    return text, keyboards.markup([[keyboards.url_button(_("match.write"), url)]])


async def send_match(bot: Bot, chat_id: int, match: MatchResult) -> None:
    """🎉 header, then the partner card with the write button."""
    text, markup = match_message(match)
    await bot.send_message(chat_id, text)
    await send_card(bot, chat_id, render_card(match.partner, "match"), markup)
