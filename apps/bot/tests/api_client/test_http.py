"""K10 acceptance: HttpApiClient follows tech.md section 9 (headers, timeout, retries, errors)."""

import json

import httpx
import pytest
from svoi_bot.api_client import ApiException, ApiTimeout, HttpApiClient
from svoi_contracts.api.profile import AgeIn
from svoi_contracts.api.users import StartIn
from svoi_contracts.cards import UserState
from svoi_contracts.enums import Lang, OnboardingStep, UserStatus
from svoi_contracts.errors import ErrorCode

STATE = {
    "user_id": 1,
    "tg_id": 42,
    "status": "onboarding",
    "lang": "uk",
    "onboarding_step": "lang",
    "pool": None,
    "needs_username": False,
    "captcha_required": False,
    "is_admin": False,
    "counters": {"incoming_likes": 0},
}


def _client(handler: httpx.MockTransport) -> HttpApiClient:
    return HttpApiClient("http://api:8000/v1", "secret", transport=handler)


async def test_sends_token_user_header_and_json_body() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=STATE)

    state = await _client(httpx.MockTransport(handler)).start(
        42,
        StartIn(
            tg_username=None, tg_first_name="Ira", tg_language_code="uk", has_tg_profile_photo=True
        ),
    )
    assert state == UserState.model_validate(STATE)
    (request,) = seen
    assert request.method == "POST"
    assert request.url.path == "/v1/users/start"
    assert request.headers["Authorization"] == "Bearer secret"
    assert request.headers["X-Tg-User-Id"] == "42"
    assert json.loads(request.content)["tg_first_name"] == "Ira"
    assert state.onboarding_step is OnboardingStep.lang
    assert state.status is UserStatus.onboarding and state.lang is Lang.uk


async def test_api_error_body_becomes_api_exception() -> None:
    body = {"code": "age_too_young", "message": "too young", "details": None}
    client = _client(httpx.MockTransport(lambda r: httpx.Response(400, json=body)))
    with pytest.raises(ApiException) as caught:
        await client.set_age(42, AgeIn(age=15))
    assert caught.value.err.code is ErrorCode.age_too_young


async def test_unparseable_error_becomes_internal() -> None:
    client = _client(httpx.MockTransport(lambda r: httpx.Response(502, text="bad gateway")))
    with pytest.raises(ApiException) as caught:
        await client.get_me(42)
    assert caught.value.err.code is ErrorCode.internal


async def test_get_retries_once_on_network_error() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("down", request=request)
        return httpx.Response(200, json=STATE)

    await _client(httpx.MockTransport(handler)).get_me(42)
    assert attempts == 2


async def test_post_is_not_retried() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(ApiTimeout):
        await _client(httpx.MockTransport(handler)).consent(42)
    assert attempts == 1


async def test_timeout_becomes_api_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ApiTimeout):
        await _client(httpx.MockTransport(handler)).set_age(42, AgeIn(age=19))


async def test_no_content_and_query_params() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(200, json=[])

    client = _client(httpx.MockTransport(handler))
    await client.delete_me(42)
    assert seen[0].method == "DELETE"
    assert await client.search_cities(42, "Він") == []
    assert seen[1].url.params["q"] == "Він"
    assert seen[1].url.params["limit"] == "5"


async def test_internal_endpoints_skip_user_header() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    await _client(httpx.MockTransport(handler)).mark_bot_blocked(77)
    assert seen[0].url.path == "/v1/internal/users/77/bot-blocked"
    assert "X-Tg-User-Id" not in seen[0].headers
