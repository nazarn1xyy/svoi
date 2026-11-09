"""Clock: services call now() so tests can move time."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from svoi_contracts.constants import LIMITS_RESET_TZ

KYIV = ZoneInfo(LIMITS_RESET_TZ)
_frozen: datetime | None = None


def now() -> datetime:
    """Current UTC time (or the frozen test time)."""
    return _frozen if _frozen is not None else datetime.now(UTC)


def freeze(at: datetime | None) -> None:
    """Tests only: pin now() to `at`; None unpins."""
    global _frozen  # noqa: PLW0603 - a process-wide test clock is the point
    _frozen = at


def kyiv_today() -> date:
    """Today in Europe/Kyiv: limits and activity days reset at Kyiv midnight."""
    return now().astimezone(KYIV).date()


def next_kyiv_midnight() -> datetime:
    """When daily limits reset, in UTC."""
    tomorrow = kyiv_today() + timedelta(days=1)
    return datetime.combine(tomorrow, time(0, 0), KYIV).astimezone(UTC)
