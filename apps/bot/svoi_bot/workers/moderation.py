"""bot.notify_moderation: result texts in the payload language, delivered once."""

from typing import Any

from aiogram import Bot
from svoi_contracts.enums import ModerationResultKind
from svoi_contracts.jobs import NotifyModeration

from svoi_bot.ui.i18n import _, set_locale
from svoi_bot.workers.delivery import Outcome, deliver_once, parse


def text(job: NotifyModeration) -> str:
    """FRONTEND S10 text for each ModerationResultKind."""
    if job.result is ModerationResultKind.banned:
        return (
            _("moderation.banned_until", date=f"{job.until:%d.%m.%Y}")
            if job.until
            else _("moderation.banned")
        )
    return _(f"moderation.{job.result.value}")


async def notify_moderation(ctx: dict[str, Any], payload: dict[str, Any]) -> Outcome:
    """Send the moderation result."""
    job = parse(NotifyModeration, payload)
    if job is None:
        return "invalid"
    bot: Bot = ctx["bot"]
    set_locale(job.lang)
    message = text(job)

    async def send() -> None:
        await bot.send_message(job.tg_id, message)

    return await deliver_once(ctx, job.dedupe_key, job.tg_id, send)
