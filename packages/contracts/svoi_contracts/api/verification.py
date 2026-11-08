"""Verification domain: video note verification (S12)."""

from pydantic import StrictInt, StrictStr

from svoi_contracts.base import Contract
from svoi_contracts.enums import GestureCode, ModerationStatus


class GestureOut(Contract):
    """Gesture the user has to show."""

    verification_id: int
    gesture: GestureCode


class VerificationIn(Contract):
    """Body of POST /verification/submit."""

    verification_id: StrictInt
    video_note_file_id: StrictStr


class VerificationOut(Contract):
    """Verification status; None when never submitted."""

    status: ModerationStatus | None
