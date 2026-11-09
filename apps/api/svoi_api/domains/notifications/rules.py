"""Delivery time: frequency, daily hour, quiet hours across midnight (BACKEND S13)."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from svoi_contracts.constants import DAILY_DIGEST_HOUR
from svoi_contracts.enums import NotificationKind, NotifyFrequency


def in_quiet(t: time, quiet_from: time, quiet_to: time) -> bool:
    """quiet_from == quiet_to means no quiet hours; the window may cross midnight."""
    if quiet_from == quiet_to:
        return False
    if quiet_from < quiet_to:
        return quiet_from <= t < quiet_to
    return t >= quiet_from or t < quiet_to


def next_delivery(  # noqa: PLR0913 - the settings row flattened
    now: datetime,
    *,
    kind: NotificationKind,
    frequency: NotifyFrequency,
    quiet_from: time,
    quiet_to: time,
    tz: str,
) -> datetime:
    """When to deliver, in UTC: >= now, never inside quiet hours."""
    zone = ZoneInfo(tz)
    local = now.astimezone(zone)
    at = local
    if kind is NotificationKind.likes and frequency is NotifyFrequency.hourly:
        at = local.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    elif kind is NotificationKind.likes and frequency is NotifyFrequency.daily:
        at = local.replace(hour=DAILY_DIGEST_HOUR, minute=0, second=0, microsecond=0)
        if at < local:
            at += timedelta(days=1)
    if in_quiet(at.time(), quiet_from, quiet_to):
        end = datetime.combine(at.date(), quiet_to, zone)
        if end <= at:
            end += timedelta(days=1)
        at = end
    return at.astimezone(UTC)
