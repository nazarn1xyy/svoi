"""Property tests (hypothesis) on the pure rules of every domain."""

import random
from datetime import UTC, datetime, time, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st
from svoi_api.domains.matching import rules as m
from svoi_api.domains.notifications.rules import in_quiet, next_delivery
from svoi_api.domains.profiles import rules as p
from svoi_api.domains.safety.rules import check_text, normalize
from svoi_contracts.constants import FEED_BATCH_SIZE
from svoi_contracts.enums import (
    ContentBlockReason,
    GoalCode,
    NotificationKind,
    NotifyFrequency,
    Pool,
    RadiusMode,
)
from svoi_contracts.errors import ErrorCode

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)

# ---- safety -----------------------------------------------------------------------------


@given(st.text())
def test_check_text_never_crashes(text: str) -> None:
    check_text(text)


@given(st.text())
def test_normalize_is_idempotent(text: str) -> None:
    assert normalize(normalize(text)) == normalize(text)


@given(st.text(alphabet="абвгдежзийклмнопрстуф ", max_size=40), st.integers(0, 40))
def test_inserted_link_is_found(text: str, at: int) -> None:
    at = min(at, len(text))
    assert check_text(text[:at] + " https://spam.example " + text[at:]) is ContentBlockReason.link


# ---- matching ---------------------------------------------------------------------------

ids = st.frozensets(st.integers(1, 40), max_size=10)
goals = st.frozensets(st.sampled_from(list(GoalCode)), max_size=4)
cat = m.Catalog(
    idf={i: 1 + i / 10 for i in range(1, 41)}, category={i: i % 5 for i in range(1, 41)}
)


def person(uid: int, interests: frozenset[int], g: frozenset[GoalCode], age: int) -> m.Person:
    return m.Person(user_id=uid, age=age, city_id=1, region="r", interests=interests, goals=g)


@given(ids, ids)
def test_interests_symmetric_and_bounded(a: frozenset[int], b: frozenset[int]) -> None:
    s = m.interests_score(a, b, cat)
    assert 0 <= s <= 1
    assert s == m.interests_score(b, a, cat)


@given(ids, ids, st.integers(1, 40))
def test_shared_interest_never_lowers_score(
    a: frozenset[int], b: frozenset[int], extra: int
) -> None:
    before = m.interests_score(a, b, cat)
    assert m.interests_score(a | {extra}, b | {extra}, cat) >= before - 1e-9


@given(st.booleans())
def test_weights_sum_to_one(online: bool) -> None:
    assert abs(sum(m.weights(online).values()) - 1) < 1e-9


@given(
    ids,
    ids,
    goals,
    goals,
    st.integers(16, 99),
    st.integers(16, 99),
    st.sampled_from(list(RadiusMode)),
)
def test_base_score_in_unit_range(  # noqa: PLR0913, PLR0917
    a: frozenset[int], b: frozenset[int], ga: frozenset[GoalCode], gb: frozenset[GoalCode],
    x: int, y: int, radius: RadiusMode,
) -> None:  # fmt: skip
    c = m.Candidate(person=person(2, b, gb, y), km=10.0, hours_inactive=30)
    assert 0 <= m.base_score(person(1, a, ga, x), c, radius, cat) <= 1


@given(st.lists(st.integers(1, 10_000), unique=True, max_size=200), st.integers(0, 99))
def test_mix_has_no_duplicates(ranked: list[int], seed: int) -> None:
    out = m.mix_batch(ranked, random.Random(seed))  # noqa: S311
    assert len(out) == len(set(out)) <= FEED_BATCH_SIZE
    assert set(out) <= set(ranked)


# ---- notifications ----------------------------------------------------------------------

times = st.times().map(lambda t: t.replace(second=0, microsecond=0))


@settings(max_examples=200)
@given(
    st.datetimes(min_value=datetime(2026, 1, 1), max_value=datetime(2027, 1, 1)),
    st.sampled_from(list(NotificationKind)),
    st.sampled_from(list(NotifyFrequency)),
    times,
    times,
)
def test_delivery_never_in_quiet_hours(
    now: datetime, kind: NotificationKind, freq: NotifyFrequency, qf: time, qt: time
) -> None:
    now = now.replace(tzinfo=UTC)
    at = next_delivery(now, kind=kind, frequency=freq, quiet_from=qf, quiet_to=qt, tz="Europe/Kyiv")
    assert now - timedelta(seconds=1) <= at <= now + timedelta(hours=48)
    local = at.astimezone(__import__("zoneinfo").ZoneInfo("Europe/Kyiv")).time()
    assert not in_quiet(local, qf, qt)


# ---- profiles ---------------------------------------------------------------------------


@given(st.integers(16, 99))
def test_default_range_inside_pool_and_contains_age(age: int) -> None:
    low, high = p.default_age_range(age)
    bounds = p.POOL_BOUNDS[p.pool_for(age)]
    assert bounds[0] <= low <= age <= high <= bounds[1]


@given(st.integers(16, 17), st.integers(0, 150), st.integers(0, 3), st.integers(0, 48))
def test_minor_never_edits_into_adult(current: int, new: int, edits: int, hours: int) -> None:
    decision = p.age_decision(
        new,
        current=current,
        set_at=NOW - timedelta(hours=hours),
        edits=edits,
        rejected_at=None,
        now=NOW,
    )
    if new >= 18:
        assert decision is not None
    if decision is None:
        assert p.pool_for(new) is Pool.minor


@given(st.floats(-90, 90), st.floats(-180, 180))
def test_rounding_moves_less_than_half_a_cell(lat: float, lon: float) -> None:
    assert abs(p.round_coord(lat) - lat) <= 0.005 + 1e-9
    assert abs(p.round_coord(lon) - lon) <= 0.005 + 1e-9


@given(st.floats(0, 500) | st.none(), st.booleans())
def test_minor_distance_only_same_city(km: float | None, same: bool) -> None:
    bucket = p.distance_bucket(km, same_city=same, minor=True)
    assert bucket is None or bucket.value == "same_city"


def test_age_too_young_code() -> None:
    assert (
        p.age_decision(15, current=None, set_at=None, edits=0, rejected_at=None, now=NOW)
        is ErrorCode.age_too_young
    )
