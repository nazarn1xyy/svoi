"""Prefs domain: feed filters and settings (S6)."""

from datetime import time

from pydantic import StrictBool, StrictInt

from svoi_contracts.base import Contract
from svoi_contracts.enums import GenderFilter, NotifyFrequency, RadiusMode


class FiltersOut(Contract):
    """Feed filters with the bounds allowed for the user's pool."""

    age_min: int
    age_max: int
    age_bounds: tuple[int, int]  # (16, 17) or (18, 99)
    gender: GenderFilter
    radius: RadiusMode
    verified_only: bool


class FiltersIn(Contract):
    """Body of PUT /filters."""

    age_min: StrictInt
    age_max: StrictInt
    gender: GenderFilter
    radius: RadiusMode
    verified_only: StrictBool


class SettingsOut(Contract):
    """Notification and privacy settings."""

    notify_frequency: NotifyFrequency
    quiet_from: time
    quiet_to: time
    show_distance: StrictBool
    show_institution: StrictBool


class SettingsIn(SettingsOut):
    """Body of PUT /settings."""
