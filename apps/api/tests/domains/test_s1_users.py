"""S1-BE acceptance: start, language, consent, age, name, gender, step machine."""

import pytest
from apihelp import ADMIN_TG, UserFactory, assert_error, onboard, start
from svoi_contracts.cards import UserState
from svoi_contracts.enums import OnboardingStep


async def test_start_twice_creates_one_user(user: UserFactory) -> None:
    a = await start(user(1))
    b = await start(user(1))
    assert a.user_id == b.user_id
    assert b.onboarding_step is OnboardingStep.lang


async def test_unknown_user_is_404_and_bad_token_401(user: UserFactory) -> None:
    assert_error(await user(5).call("GET", "/users/me"), 404, "not_found")
    tg = user(5)
    response = await tg.http.get("/v1/users/me", headers={"X-Tg-User-Id": "5"})
    assert response.status_code == 401


async def test_state_fields(user: UserFactory) -> None:
    state = await start(user(ADMIN_TG), username=None)
    assert state.is_admin and state.needs_username
    assert not (await start(user(2))).is_admin


async def test_language_from_telegram(user: UserFactory) -> None:
    assert (await start(user(3), tg_language_code="ru")).lang.value == "ru"
    assert (await start(user(4), tg_language_code="de")).lang.value == "uk"


async def test_consent_only_on_its_step(user: UserFactory) -> None:
    tg = user(1)
    await start(tg)
    assert_error(await tg.call("POST", "/users/me/consent"), 409, "conflict")
    await tg.ok("PUT", "/users/me/lang", body={"lang": "uk"})
    state = await tg.ok("POST", "/users/me/consent")
    assert state.onboarding_step is OnboardingStep.age
    assert_error(await tg.call("POST", "/users/me/consent"), 409, "conflict")


async def test_future_step_is_conflict(user: UserFactory) -> None:
    tg = user(1)
    await start(tg)
    assert_error(await tg.call("PUT", "/profile/name", body={"name": "Ira"}), 409, "conflict")


async def _to_age(tg: object) -> None:
    await start(tg)  # type: ignore[arg-type]
    await tg.ok("PUT", "/users/me/lang", body={"lang": "uk"})  # type: ignore[attr-defined]
    await tg.ok("POST", "/users/me/consent")  # type: ignore[attr-defined]


async def test_age_15_then_18_is_locked(user: UserFactory) -> None:
    tg = user(1)
    await _to_age(tg)
    assert_error(await tg.call("PUT", "/profile/age", body={"age": 15}), 400, "age_too_young")
    assert_error(await tg.call("PUT", "/profile/age", body={"age": 18}), 400, "age_locked")


async def test_age_sets_pool_and_strict_type(user: UserFactory) -> None:
    tg = user(1)
    await _to_age(tg)
    assert_error(await tg.call("PUT", "/profile/age", body={"age": "18"}), 422, "validation_error")
    assert_error(await tg.call("PUT", "/profile/age", body={"age": 100}), 422, "validation_error")
    state: UserState = await tg.ok("PUT", "/profile/age", body={"age": 17})
    assert state.pool is not None and state.pool.value == "minor"
    assert state.onboarding_step is OnboardingStep.name


async def test_minor_cannot_become_adult(user: UserFactory) -> None:
    tg = user(1)
    await onboard(tg, age=17)
    assert_error(await tg.call("PUT", "/profile/age", body={"age": 18}), 400, "age_locked")


async def test_age_edit_once_in_window(user: UserFactory) -> None:
    tg = user(1)
    await onboard(tg, age=19)
    await tg.ok("PUT", "/profile/age", body={"age": 20})
    assert_error(await tg.call("PUT", "/profile/age", body={"age": 21}), 400, "age_locked")


@pytest.mark.parametrize(
    ("name", "status", "code"),
    [
        ("Ira https://x.com", 400, "content_blocked"),
        ("I", 422, "validation_error"),
        ("Ira2", 422, "validation_error"),
    ],
)
async def test_bad_names(user: UserFactory, name: str, status: int, code: str) -> None:
    tg = user(1)
    await _to_age(tg)
    await tg.ok("PUT", "/profile/age", body={"age": 19})
    assert_error(await tg.call("PUT", "/profile/name", body={"name": name}), status, code)


async def test_skip_only_current_optional_step(user: UserFactory) -> None:
    tg = user(1)
    await onboard(tg, complete=False)
    assert_error(await tg.call("POST", "/onboarding/skip", body={"step": "age"}), 409, "conflict")


async def test_full_onboarding_activates(user: UserFactory) -> None:
    state = await onboard(user(1))
    assert state.status.value == "active"
    assert state.onboarding_step is OnboardingStep.done


async def test_complete_reports_missing(user: UserFactory) -> None:
    tg = user(1)
    await _to_age(tg)
    err = assert_error(await tg.call("POST", "/onboarding/complete"), 400, "profile_incomplete")
    assert err.details is not None
    assert set(err.details["missing"]) == {"age", "name", "gender", "city", "goals", "interests"}
