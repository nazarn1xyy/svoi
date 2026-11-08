"""Pure multi-select reducer shared by goals and interests (property-tested)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Toggle:
    """Result of one tap."""

    selected: tuple[str, ...]
    rejected: bool  # a new value would exceed the maximum


def toggle(selected: tuple[str, ...], value: str, maximum: int) -> Toggle:
    """Add or remove `value`; order of first selection is kept."""
    if value in selected:
        return Toggle(tuple(v for v in selected if v != value), rejected=False)
    if len(selected) >= maximum:
        return Toggle(selected, rejected=True)
    return Toggle((*selected, value), rejected=False)


def can_finish(count: int, bounds: tuple[int, int]) -> bool:
    """«Готово» works only inside the bounds."""
    return bounds[0] <= count <= bounds[1]
