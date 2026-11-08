"""API error contract from docs/tech.md section 6.2."""

from enum import StrEnum
from typing import Any

from svoi_contracts.base import Contract
from svoi_contracts.enums import ContentBlockReason, ContentField


class ErrorCode(StrEnum):
    """Error codes with their HTTP status."""

    validation_error = "validation_error"  # 422
    not_found = "not_found"  # 404
    conflict = "conflict"  # 409, e.g. the onboarding step is not current
    forbidden = "forbidden"  # 403
    banned = "banned"  # 403, details: {"until": datetime | None}
    age_too_young = "age_too_young"  # 400
    age_locked = "age_locked"  # 400, age can no longer change
    profile_incomplete = "profile_incomplete"  # 400, details: {"missing": list[str]}
    content_blocked = "content_blocked"  # 400, details: ContentBlockDetails
    media_forbidden = "media_forbidden"  # 400, media in a message for the minor pool
    limit_reached = "limit_reached"  # 429, details: Limits
    rate_limited = "rate_limited"  # 429
    captcha_required = "captcha_required"  # 403
    undo_unavailable = "undo_unavailable"  # 409
    media_limit = "media_limit"  # 400
    internal = "internal"  # 500


class ContentBlockDetails(Contract):
    """Why the content filter rejected a field."""

    field: ContentField
    reason: ContentBlockReason


class ApiError(Contract):
    """Error body of every non-2xx API response."""

    code: ErrorCode
    message: str  # English, for logs; the bot shows its own text by code
    details: dict[str, Any] | None = None
