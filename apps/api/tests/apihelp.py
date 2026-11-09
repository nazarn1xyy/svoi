"""Test client for the API: one object per Telegram user, contract checks on every response."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, TypeAdapter
from svoi_contracts.cards import UserState
from svoi_contracts.errors import ApiError

TOKEN = "test-token"  # noqa: S105 - test value
ADMIN_TG = 914462173
NOW = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
M = TypeVar("M")


def assert_contract(response: httpx.Response, model: Any) -> Any:
    """The body validates against the contract model (the bot would crash otherwise)."""
    assert response.status_code < 300, response.text
    return TypeAdapter(model).validate_json(response.content)


def assert_error(response: httpx.Response, status: int, code: str) -> ApiError:
    """ApiError body with this status and code."""
    assert response.status_code == status, response.text
    err = ApiError.model_validate_json(response.content)
    assert err.code.value == code, err
    return err


@dataclass
class Tg:
    """Requests on behalf of one tg_id."""

    http: httpx.AsyncClient
    tg_id: int

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {TOKEN}", "X-Tg-User-Id": str(self.tg_id)}

    async def call(
        self,
        method: str,
        path: str,
        body: BaseModel | dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Raw request under /v1."""
        payload = body.model_dump(mode="json") if isinstance(body, BaseModel) else body
        return await self.http.request(
            method, f"/v1{path}", json=payload, params=params, headers=self._headers()
        )

    async def ok(
        self,
        method: str,
        path: str,
        model: Any = UserState,
        body: BaseModel | dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Successful request validated against `model`."""
        response = await self.call(method, path, body, params)
        if model is None:
            assert response.status_code == 204, response.text
            return None
        return assert_contract(response, model)


async def city_id(tg: Tg, q: str) -> int:
    """First city the search finds."""
    from svoi_contracts.api.catalog import CityOut  # noqa: PLC0415

    found = await tg.ok("GET", "/catalog/cities/search", list[CityOut], params={"q": q})
    assert found, q
    return int(found[0].id)


async def interest_ids(tg: Tg, n: int = 3, offset: int = 0) -> list[int]:
    """n approved interest ids from the first categories."""
    from svoi_contracts.api.catalog import CategoryOut, InterestOut  # noqa: PLC0415

    cats = await tg.ok("GET", "/catalog/interest-categories", list[CategoryOut])
    ids: list[int] = []
    for cat in cats:
        ids += [
            i.id
            for i in await tg.ok(
                "GET", "/catalog/interests", list[InterestOut], params={"category_id": cat.id}
            )
        ]
    return ids[offset : offset + n]


async def start(tg: Tg, username: str | None = "user", **extra: Any) -> UserState:
    """POST /users/start."""
    body = {
        "tg_username": username,
        "tg_first_name": "Test",
        "tg_language_code": "uk",
        "has_tg_profile_photo": True,
        "referral_code": None,
    } | extra
    state: UserState = await tg.ok("POST", "/users/start", body=body)
    return state


async def onboard(  # noqa: PLR0913 - every field of a profile
    tg: Tg,
    *,
    age: int = 19,
    city: str = "Вінниця",
    name: str = "Ira",
    gender: str = "female",
    goals: tuple[str, ...] = ("friends",),
    interests: list[int] | None = None,
    complete: bool = True,
    **start_extra: Any,
) -> UserState:
    """Walk the whole onboarding the way the bot does."""
    await start(tg, **start_extra)
    await tg.ok("PUT", "/users/me/lang", body={"lang": "uk"})
    await tg.ok("POST", "/users/me/consent")
    await tg.ok("PUT", "/profile/age", body={"age": age})
    await tg.ok("PUT", "/profile/name", body={"name": name})
    await tg.ok("PUT", "/profile/gender", body={"gender": gender})
    await tg.ok("PUT", "/profile/city", body={"city_id": await city_id(tg, city)})
    await tg.ok("PUT", "/profile/goals", body={"codes": list(goals)})
    ids = interests if interests is not None else await interest_ids(tg)
    state: UserState = await tg.ok("PUT", "/profile/interests", body={"interest_ids": ids})
    for step in ("clarify", "institution", "height", "prompts", "media"):
        state = await tg.ok("POST", "/onboarding/skip", body={"step": step})
    if complete:
        state = await tg.ok("POST", "/onboarding/complete")
    return state


UserFactory = Callable[[int], Tg]
Freeze = Callable[[datetime | None], None]
