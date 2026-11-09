"""Catalog rules without I/O: search query normalization, goal titles."""

import re

from svoi_contracts.enums import GoalCode

from svoi_api.seed.catalog import GOALS, Goal

GOAL_BY_CODE: dict[GoalCode, Goal] = {g.code: g for g in GOALS}
CITY_SIMILARITY = 0.3
CUSTOM_TAG_SIMILARITY = 0.6
NEAREST_CITY_KM = 30
_APOSTROPHES = re.compile(r"[ʼ'’`]")


def normalize_query(q: str) -> str:
    """Lowercase, yo folded to ye, one apostrophe, trimmed spaces."""
    out = _APOSTROPHES.sub("’", q.strip().lower()).replace("ё", "е")
    return " ".join(out.split())
