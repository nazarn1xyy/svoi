"""bot.demo (core v4): local/test only, proves an API job reaches bot-worker."""

from typing import Any

import structlog
from svoi_contracts.jobs import DemoPing

from svoi_bot.workers.delivery import Outcome, parse

log = structlog.get_logger()


async def demo(ctx: dict[str, Any], payload: dict[str, Any]) -> Outcome:
    """Log the ping; no Telegram message, so nothing to deduplicate."""
    job = parse(DemoPing, payload)
    if job is None:
        return "invalid"
    log.info("demo_job_received", dedupe_key=job.dedupe_key, note=job.note)
    ctx.setdefault("demo_received", []).append(job)
    return "sent"
