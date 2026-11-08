"""bot.notify_likes and bot.notify_match: texts in the payload language, delivered once."""

from typing import Any

from aiogram import Bot
from svoi_contracts.jobs import NotifyLikes, NotifyMatch

from svoi_bot.api_client import ApiClient
from svoi_bot.features.likes.match import send_match
from svoi_bot.features.likes.views import notification
from svoi_bot.ui.i18n import set_locale
from svoi_bot.workers.delivery import Outcome, deliver_once, parse


async def notify_likes(ctx: dict[str, Any], payload: dict[str, Any]) -> Outcome:
    """«❤️ Ти сподобався N людям! Подивитися?» with 👀 and ⏰."""
    job = parse(NotifyLikes, payload)
    if job is None:
        return "invalid"
    bot: Bot = ctx["bot"]
    set_locale(job.lang)
    text, markup = notification(job.count)

    async def send() -> None:
        await bot.send_message(job.tg_id, text, reply_markup=markup)

    return await deliver_once(ctx, job.dedupe_key, job.tg_id, send)


async def notify_match(ctx: dict[str, Any], payload: dict[str, Any]) -> Outcome:
    """GET /matches/{id} as the recipient, then the same match screen as in the bot."""
    job = parse(NotifyMatch, payload)
    if job is None:
        return "invalid"
    bot: Bot = ctx["bot"]
    api: ApiClient = ctx["api"]
    set_locale(job.lang)
    match = await api.get_match(job.tg_id, job.match_id)

    async def send() -> None:
        await send_match(bot, job.tg_id, match)

    return await deliver_once(ctx, job.dedupe_key, job.tg_id, send)
