"""Profile rules without I/O: age, name, completeness, distance buckets (S1, S4, S5)."""

import hashlib
import re
from collections.abc import Iterable
from datetime import datetime, timedelta

from svoi_contracts.constants import (
    ADULT_AGE,
    AGE_EDIT_WINDOW_HOURS,
    AGE_MAX,
    AGE_MIN,
    AGE_REJECT_COOLDOWN_DAYS,
    DEFAULT_AGE_RANGE_DELTA,
    DISTANCE_BUCKETS_KM,
    GEO_ROUND_DECIMALS,
    NAME_LEN,
)
from svoi_contracts.enums import DistanceBucket, Pool
from svoi_contracts.errors import ErrorCode

POOL_BOUNDS: dict[Pool, tuple[int, int]] = {
    Pool.minor: (AGE_MIN, ADULT_AGE - 1),
    Pool.adult: (ADULT_AGE, AGE_MAX),
}
_NAME = re.compile(r"^[^\W\d_]+(?:[ '\-ʼ’][^\W\d_]+)*$")
MAX_DISTANCE_KM = DISTANCE_BUCKETS_KM[-1]


def pool_for(age: int) -> Pool:
    """adult from ADULT_AGE."""
    return Pool.adult if age >= ADULT_AGE else Pool.minor


def age_decision(  # noqa: PLR0911, PLR0913 - one rule, one return per outcome
    new: int,
    *,
    current: int | None,
    set_at: datetime | None,
    edits: int,
    rejected_at: datetime | None,
    now: datetime,
) -> ErrorCode | None:
    """Why the new age is refused (BACKEND S1 age rules), None if accepted."""
    if rejected_at is not None and now - rejected_at < timedelta(days=AGE_REJECT_COOLDOWN_DAYS):
        return ErrorCode.age_locked
    if new < AGE_MIN:
        return ErrorCode.age_too_young
    if new > AGE_MAX:
        return ErrorCode.validation_error
    if current is None or new == current:
        return None
    if pool_for(current) is Pool.minor and pool_for(new) is Pool.adult:
        return ErrorCode.age_locked
    window = set_at is not None and now - set_at <= timedelta(hours=AGE_EDIT_WINDOW_HOURS)
    if edits >= 1 or not window:
        return ErrorCode.age_locked
    return None


def default_age_range(age: int) -> tuple[int, int]:
    """Own age ± DEFAULT_AGE_RANGE_DELTA, clipped to the pool."""
    low, high = POOL_BOUNDS[pool_for(age)]
    return max(low, age - DEFAULT_AGE_RANGE_DELTA), min(high, age + DEFAULT_AGE_RANGE_DELTA)


def valid_name(name: str) -> bool:
    """NAME_LEN letters with spaces, hyphens, apostrophes; no digits."""
    return NAME_LEN[0] <= len(name) <= NAME_LEN[1] and bool(_NAME.match(name))


def round_coord(value: float) -> float:
    """~1 km precision."""
    return round(value, GEO_ROUND_DECIMALS)


def completeness(
    *,
    required: bool,
    has_photo: bool,
    has_prompt: bool,
    has_institution: bool,
    has_height_or_note: bool,
) -> int:
    """0..100: required 40, approved photo 25, prompt 15, institution 10, height or note 10."""
    return (
        40 * required
        + 25 * has_photo
        + 15 * has_prompt
        + 10 * has_institution
        + 10 * has_height_or_note
    )


def snapshot_hash(interest_ids: Iterable[int], media_ids: Iterable[int]) -> str:
    """Changes when interests or media change ("profile changed" for skipped cards)."""
    raw = f"{sorted(interest_ids)}|{sorted(media_ids)}"
    return hashlib.sha256(raw.encode()).hexdigest()


def distance_bucket(km: float | None, *, same_city: bool, minor: bool) -> DistanceBucket | None:
    """Card distance: same city, then buckets; minors only ever see same_city."""
    if same_city:
        return DistanceBucket.same_city
    if minor or km is None or km > MAX_DISTANCE_KM:
        return None
    near, mid, _ = DISTANCE_BUCKETS_KM
    if km <= near:
        return DistanceBucket.km5
    if km <= mid:
        return DistanceBucket.km25
    return DistanceBucket.km100
