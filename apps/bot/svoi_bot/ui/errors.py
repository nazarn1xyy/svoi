"""Texts for API errors; features never word errors themselves."""

from datetime import datetime

from svoi_contracts.enums import ContentBlockReason
from svoi_contracts.errors import ApiError, ErrorCode

from svoi_bot.ui.i18n import _

_GENERIC = "errors.generic"
_BY_CODE = {
    ErrorCode.age_too_young: "errors.age_too_young",
    ErrorCode.age_locked: "errors.age_locked",
    ErrorCode.media_limit: "errors.media_limit",
    ErrorCode.media_forbidden: "errors.media_forbidden",
    ErrorCode.limit_reached: "errors.limit_reached",
    ErrorCode.rate_limited: "errors.rate_limited",
    ErrorCode.undo_unavailable: "errors.undo_unavailable",
    ErrorCode.captcha_required: "errors.captcha_required",
    ErrorCode.forbidden: "errors.forbidden",
    ErrorCode.profile_incomplete: "errors.profile_incomplete",
    ErrorCode.validation_error: "errors.validation_error",
    ErrorCode.not_found: _GENERIC,
    ErrorCode.conflict: _GENERIC,
    ErrorCode.internal: _GENERIC,
}


def render_api_error(err: ApiError) -> str:
    """User text for an ApiError, by code and content-block reason."""
    details = err.details or {}
    if err.code is ErrorCode.content_blocked:
        reason = details.get("reason")
        if reason in {r.value for r in ContentBlockReason}:
            return _(f"errors.content_blocked.{reason}")
        return _("errors.content_blocked.stopword")
    if err.code is ErrorCode.banned:
        until = details.get("until")
        if not until:
            return _("errors.banned_forever")
        return _("errors.banned_until", date=datetime.fromisoformat(until).strftime("%d.%m.%Y"))
    return _(_BY_CODE.get(err.code, _GENERIC))


def timeout_text() -> str:
    """API did not answer."""
    return _(_GENERIC)
