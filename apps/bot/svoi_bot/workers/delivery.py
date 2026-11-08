"""Exactly-once delivery rules for every bot job (tech.md section 8).

SET notify:sent:{dedupe_key} NX before sending; network or 5xx → drop the key and retry;
403 → bot-blocked without retry; success → notifications/{dedupe_key}/sent.
"""

from collections.abc import Awaitable, Callable
from typing import Any, Literal

import structlog
from aiogram.exceptions import (
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from arq import Retry
from pydantic import BaseModel, ValidationError

from svoi_bot.api_client import ApiClient

log = structlog.get_logger()
SENT_TTL_S = 604_800  # 7 days
RETRY_BASE_S = 10
MAX_TRIES = 5
Outcome = Literal["sent", "duplicate", "blocked", "invalid"]


def sent_key(dedupe_key: str) -> str:
    """Redis key that marks a notification as sent."""
    return f"notify:sent:{dedupe_key}"


def parse[M: BaseModel](model: type[M], payload: Any) -> M | None:
    """Payload or None; an invalid payload is logged and never retried."""
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        log.warning("invalid_job_payload", model=model.__name__, errors=exc.error_count())
        return None


async def deliver_once(
    ctx: dict[str, Any], dedupe_key: str, tg_id: int, send: Callable[[], Awaitable[object]]
) -> Outcome:
    """Run `send` at most once per dedupe_key across retries and re-enqueues."""
    redis = ctx["redis"]
    api: ApiClient = ctx["api"]
    if not await redis.set(sent_key(dedupe_key), "1", nx=True, ex=SENT_TTL_S):
        return "duplicate"
    try:
        await send()
    except TelegramForbiddenError:
        await api.mark_bot_blocked(tg_id)
        return "blocked"
    except (TelegramNetworkError, TelegramServerError, TelegramRetryAfter) as exc:
        await redis.delete(sent_key(dedupe_key))
        job_try = int(ctx.get("job_try", 1))
        log.warning("job_retry", dedupe_key=dedupe_key, job_try=job_try, error=type(exc).__name__)
        raise Retry(defer=RETRY_BASE_S * job_try) from exc
    await api.mark_notification_sent(dedupe_key)
    return "sent"
