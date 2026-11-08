"""bot.notify_reminder and bot.notify_new_people (1.1); batching and quiet hours are the API's."""

from typing import Any

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from svoi_contracts.jobs import NotifyNewPeople, NotifyReminder

from svoi_bot.ui import keyboards
from svoi_bot.ui.i18n import _, set_locale
from svoi_bot.ui.keyboards import nav_button
from svoi_bot.workers.delivery import Outcome, deliver_once, parse


def look_button() -> InlineKeyboardMarkup:
    """🔍 opens the feed (handled by the feed router)."""
    return keyboards.markup([[nav_button(_("notify.look"), "feed", "open")]])


async def _send(ctx: dict[str, Any], dedupe_key: str, tg_id: int, text: str) -> Outcome:
    bot: Bot = ctx["bot"]
    markup = look_button()

    async def send() -> None:
        await bot.send_message(tg_id, text, reply_markup=markup)

    return await deliver_once(ctx, dedupe_key, tg_id, send)


async def notify_reminder(ctx: dict[str, Any], payload: dict[str, Any]) -> Outcome:
    """day3 / day7 come-back reminder."""
    job = parse(NotifyReminder, payload)
    if job is None:
        return "invalid"
    set_locale(job.lang)
    return await _send(ctx, job.dedupe_key, job.tg_id, _(f"notify.{job.kind.value}"))


async def notify_new_people(ctx: dict[str, Any], payload: dict[str, Any]) -> Outcome:
    """Daily digest of new people sharing an interest."""
    job = parse(NotifyNewPeople, payload)
    if job is None:
        return "invalid"
    set_locale(job.lang)
    text = _("notify.new_people", count=job.count, interest=job.interest_title.lower())
    return await _send(ctx, job.dedupe_key, job.tg_id, text)
