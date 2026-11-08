"""Localized labels of contract enums."""

from svoi_contracts.enums import DistanceBucket, GestureCode, GoalCode, ReportReason

from svoi_bot.ui.i18n import _


def goal_label(code: GoalCode) -> str:
    """Goal as it reads after «Шукає:» on a card."""
    return _(f"format.goal.{code.value}")


def distance_label(bucket: DistanceBucket) -> str:
    """Distance bucket, never the exact distance."""
    return _(f"format.distance.{bucket.value}")


def gesture_label(code: GestureCode) -> str:
    """Gesture to show in a verification video note."""
    return _(f"format.gesture.{code.value}")


def reason_label(reason: ReportReason) -> str:
    """Report reason button text."""
    return _(f"format.reason.{reason.value}")
