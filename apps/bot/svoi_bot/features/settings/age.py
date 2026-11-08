"""Pure age-range reducer (property-tested): min never above max, both inside the pool."""

from typing import Literal

AgeAction = Literal["min_down", "min_up", "max_down", "max_up"]


def adjust(
    age_min: int, age_max: int, bounds: tuple[int, int], action: AgeAction
) -> tuple[int, int]:
    """One button press; impossible moves leave the range unchanged."""
    low, high = bounds
    age_min, age_max = max(low, min(age_min, high)), max(low, min(age_max, high))
    if action == "min_down":
        age_min = max(low, age_min - 1)
    elif action == "min_up":
        age_min = min(age_max, age_min + 1)
    elif action == "max_down":
        age_max = max(age_min, age_max - 1)
    else:
        age_max = min(high, age_max + 1)
    return age_min, age_max


def fixed(bounds: tuple[int, int]) -> bool:
    """The 16-17 pool cannot widen or narrow meaningfully: buttons stay inactive."""
    return bounds[1] - bounds[0] <= 1
