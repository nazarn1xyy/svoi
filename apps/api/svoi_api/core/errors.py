"""DomainError and its mapping to ApiError responses (docs/tech.md 6.2)."""

from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from svoi_contracts.errors import ApiError, ErrorCode

log = structlog.get_logger()

STATUS: dict[ErrorCode, int] = {
    ErrorCode.validation_error: 422,
    ErrorCode.not_found: 404,
    ErrorCode.conflict: 409,
    ErrorCode.forbidden: 403,
    ErrorCode.banned: 403,
    ErrorCode.age_too_young: 400,
    ErrorCode.age_locked: 400,
    ErrorCode.profile_incomplete: 400,
    ErrorCode.content_blocked: 400,
    ErrorCode.media_forbidden: 400,
    ErrorCode.limit_reached: 429,
    ErrorCode.rate_limited: 429,
    ErrorCode.captcha_required: 403,
    ErrorCode.undo_unavailable: 409,
    ErrorCode.media_limit: 400,
    ErrorCode.internal: 500,
}


class DomainError(Exception):
    """A business rule refused the request; services raise it, the app maps it."""

    def __init__(
        self, code: ErrorCode, details: dict[str, Any] | None = None, message: str = ""
    ) -> None:
        super().__init__(message or code.value)
        self.code = code
        self.details = details
        self.message = message or code.value


class Unauthorized(Exception):
    """Missing or wrong internal token."""


def _response(status: int, err: ApiError) -> JSONResponse:
    return JSONResponse(status_code=status, content=err.model_dump(mode="json"))


async def _domain(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, DomainError):
        raise exc
    err = ApiError(code=exc.code, message=exc.message, details=exc.details)
    return _response(STATUS[exc.code], err)


async def _validation(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(p) for p in first.get("loc", ()))
    message = f"{where}: {first.get('msg', 'invalid')}"
    return _response(422, ApiError(code=ErrorCode.validation_error, message=message))


async def _unauthorized(_: Request, __: Exception) -> JSONResponse:
    # ErrorCode has no "unauthorized"; the status tells the bot what happened
    return _response(401, ApiError(code=ErrorCode.forbidden, message="bad internal token"))


async def _http(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, HTTPException):
        raise exc
    code = ErrorCode.not_found if exc.status_code == 404 else ErrorCode.internal  # noqa: PLR2004
    return _response(exc.status_code, ApiError(code=code, message=str(exc.detail)))


async def _crash(_: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled", exc_info=exc)
    return _response(500, ApiError(code=ErrorCode.internal, message="internal error"))


def install(app: FastAPI) -> None:
    """Every error leaves the API as an ApiError body."""
    app.add_exception_handler(DomainError, _domain)
    app.add_exception_handler(RequestValidationError, _validation)
    app.add_exception_handler(Unauthorized, _unauthorized)
    app.add_exception_handler(HTTPException, _http)
    app.add_exception_handler(Exception, _crash)
