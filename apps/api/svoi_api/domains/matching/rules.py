"""Scoring and batch mix without I/O (BACKEND S7 stage 2 and 3)."""

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from svoi_contracts.constants import (
    ACTIVITY_SCORE,
    AGE_SCORE_SPAN_YEARS,
    CATEGORY_PARTIAL_MATCH,
    FEED_BATCH_SIZE,
    FEED_MIX,
    GEO_WEIGHT_ONLINE_GOAL,
    NEWBIE_BOOST,
    SAME_INSTITUTION_TYPE_SCORE,
    SCORE_WEIGHTS,
)
from svoi_contracts.enums import GoalCode, InstitutionType, RadiusMode

RADIUS_ORDER: tuple[RadiusMode, ...] = (
    RadiusMode.city,
    RadiusMode.km25,
    RadiusMode.km50,
    RadiusMode.km100,
    RadiusMode.region,
    RadiusMode.country,
    RadiusMode.any_online,
)
RADIUS_KM: dict[RadiusMode, int] = {RadiusMode.km25: 25, RadiusMode.km50: 50, RadiusMode.km100: 100}
EXPAND_CHOICES = (RadiusMode.km50, RadiusMode.region, RadiusMode.country)
ONLINE_GOALS = frozenset({GoalCode.gaming, GoalCode.chat})
SAME_REGION_GEO = 0.5
OTHER_GEO = 0.2
EXPOSURE_STEP = 0.002
EXPOSURE_CAP = 0.2
REPORT_PENALTY = 0.1
REPORT_PENALTY_CAP = 0.3
REFERRAL_BOOST = 1.0
REFERRAL_CAP = 2.0
QUALITY_PHOTO, QUALITY_PROMPT, QUALITY_VERIFIED = 0.4, 0.3, 0.3
QUALITY_REPORTED = 0.5


@dataclass(frozen=True)
class Person:
    """Scoring inputs of one side."""

    user_id: int
    age: int
    city_id: int
    region: str
    interests: frozenset[int]
    goals: frozenset[GoalCode]
    institution_id: int | None = None
    institution_type: InstitutionType | None = None


@dataclass(frozen=True)
class Candidate:
    """A candidate with pair-specific facts."""

    person: Person
    km: float | None = None
    hours_inactive: float = 0.0
    has_photo: bool = False
    has_prompt: bool = False
    verified: bool = False
    open_reports: int = 0
    newbie: bool = False
    exposure_today: int = 0
    referral: bool = False


@dataclass(frozen=True)
class Catalog:
    """Interest metadata: idf and category."""

    idf: Mapping[int, float] = field(default_factory=dict)
    category: Mapping[int, int] = field(default_factory=dict)


def interests_score(a: frozenset[int], b: frozenset[int], cat: Catalog) -> float:
    """Weighted Jaccard plus partial credit for shared categories.

    Every shared category counts, also one with a shared tag: if it did not, turning a
    same-category pair into a shared tag could lower the score.
    """
    union = a | b
    if not union:
        return 0.0
    w = sum(cat.idf.get(i, 1.0) for i in a & b) / sum(cat.idf.get(i, 1.0) for i in union)
    cats_a = {cat.category.get(i) for i in a} - {None}
    cats_b = {cat.category.get(i) for i in b} - {None}
    cat_union = cats_a | cats_b
    shared = len(cats_a & cats_b) / len(cat_union) if cat_union else 0.0
    return min(1.0, w + CATEGORY_PARTIAL_MATCH * shared * (1 - w))


def geo_score(v: Person, t: Person, km: float | None, radius: RadiusMode) -> float:
    """Linear inside a km radius; else same city 1, same region 0.5, other 0.2."""
    limit = RADIUS_KM.get(radius)
    if limit is not None and km is not None:
        return max(0.0, 1 - km / limit)
    if v.city_id == t.city_id:
        return 1.0
    return SAME_REGION_GEO if v.region == t.region else OTHER_GEO


def goals_score(a: frozenset[GoalCode], b: frozenset[GoalCode]) -> float:
    """Jaccard of goals."""
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def institution_score(v: Person, t: Person) -> float:
    """Same institution 1, same type 0.3."""
    if v.institution_id is not None and v.institution_id == t.institution_id:
        return 1.0
    if v.institution_type is not None and v.institution_type == t.institution_type:
        return SAME_INSTITUTION_TYPE_SCORE
    return 0.0


def activity_score(hours: float) -> float:
    """ACTIVITY_SCORE steps, 0 after the last one."""
    for limit, score in sorted(ACTIVITY_SCORE.items()):
        if hours <= limit:
            return score
    return 0.0


def age_score(a: int, b: int) -> float:
    """1 for the same age, 0 at AGE_SCORE_SPAN_YEARS apart."""
    return max(0.0, 1 - abs(a - b) / AGE_SCORE_SPAN_YEARS)


def quality_score(c: Candidate) -> float:
    """Photo, prompt, verified; halved with open reports."""
    raw = (
        QUALITY_PHOTO * c.has_photo + QUALITY_PROMPT * c.has_prompt + QUALITY_VERIFIED * c.verified
    )
    return raw * (QUALITY_REPORTED if c.open_reports else 1.0)


def weights(online_gaming: bool) -> dict[str, float]:
    """SCORE_WEIGHTS; online gamers barely care about geo. Always sums to 1."""
    w = dict(SCORE_WEIGHTS)
    if online_gaming:
        w["geo"] = GEO_WEIGHT_ONLINE_GOAL
    total = sum(w.values())
    return {k: v / total for k, v in w.items()}


def base_score(v: Person, c: Candidate, radius: RadiusMode, cat: Catalog) -> float:
    """Weighted sum of factors in [0, 1]."""
    t = c.person
    online = (
        GoalCode.gaming in v.goals
        and GoalCode.gaming in t.goals
        and radius is RadiusMode.any_online
    )
    w = weights(online)
    factors = {
        "interests": interests_score(v.interests, t.interests, cat),
        "geo": geo_score(v, t, c.km, radius),
        "goals": goals_score(v.goals, t.goals),
        "institution": institution_score(v, t),
        "activity": activity_score(c.hours_inactive),
        "age": age_score(v.age, t.age),
        "quality": quality_score(c),
    }
    return min(1.0, max(0.0, sum(w[k] * factors[k] for k in w)))


def match_percent(base: float) -> int:
    """Shown on the card."""
    return round(100 * base)


def rank_score(base: float, c: Candidate) -> float:
    """Ranking only: newbie boost, exposure and report penalties, referral boost."""
    score = base
    if c.newbie:
        score += NEWBIE_BOOST
    score -= min(EXPOSURE_CAP, EXPOSURE_STEP * c.exposure_today)
    score -= min(REPORT_PENALTY_CAP, REPORT_PENALTY * c.open_reports)
    if c.referral:
        return min(REFERRAL_CAP, max(0.0, score) + REFERRAL_BOOST)
    return min(1.0, max(0.0, score))


def mix_batch(ranked: Sequence[int], rng: random.Random, size: int = FEED_BATCH_SIZE) -> list[int]:
    """Top 30% / middle 40% / bottom 30% buckets, taken 70/20/10, shuffled inside each."""
    n = len(ranked)
    if n <= size:
        return list(ranked)
    cut1, cut2 = round(n * 0.3), round(n * 0.7)
    buckets = [list(ranked[:cut1]), list(ranked[cut1:cut2]), list(ranked[cut2:])]
    out: list[int] = []
    for bucket, share in zip(buckets, FEED_MIX, strict=True):
        rng.shuffle(bucket)
        out.extend(bucket[: round(size * share)])
    taken = set(out)
    leftovers = [i for i in ranked if i not in taken]
    out.extend(leftovers[: size - len(out)])
    return out[:size]


def expand_options(current: RadiusMode, *, has_geo: bool, gaming: bool) -> list[RadiusMode]:
    """Wider radii than the current one for an empty feed."""
    rank = RADIUS_ORDER.index(current)
    out = [
        r
        for r in EXPAND_CHOICES
        if RADIUS_ORDER.index(r) > rank and (has_geo or r not in RADIUS_KM)
    ]
    if gaming and current is not RadiusMode.any_online:
        out.append(RadiusMode.any_online)
    return out
