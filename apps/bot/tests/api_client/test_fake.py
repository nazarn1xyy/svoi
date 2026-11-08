"""K10 acceptance: FakeApiClient serves seed fixtures, validates contracts, injects failures."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from svoi_bot.api_client import ApiException, ApiTimeout, ContractViolation, FakeApiClient
from svoi_contracts.api.catalog import CustomInterestIn
from svoi_contracts.api.profile import AgeIn, CityIn, GenderIn, GoalsIn, InterestsIn, NameIn
from svoi_contracts.api.users import LangIn, StartIn
from svoi_contracts.api.verification import VerificationIn
from svoi_contracts.constants import AGE_MAX, AGE_MIN
from svoi_contracts.enums import Gender, GoalCode, Lang, OnboardingStep, Pool, UserStatus
from svoi_contracts.errors import ApiError, ErrorCode

TG = 100


def _start() -> StartIn:
    return StartIn(
        tg_username="ira", tg_first_name="Ira", tg_language_code="uk", has_tg_profile_photo=True
    )


async def _onboarded_to(fake: FakeApiClient, step: OnboardingStep) -> None:
    await fake.start(TG, _start())
    order = [
        OnboardingStep.lang,
        OnboardingStep.consent,
        OnboardingStep.age,
        OnboardingStep.name,
        OnboardingStep.gender,
    ]
    for current in order:
        if current == step:
            return
        if current is OnboardingStep.lang:
            await fake.set_lang(TG, LangIn(lang=Lang.uk))
        elif current is OnboardingStep.consent:
            await fake.consent(TG)
        elif current is OnboardingStep.age:
            await fake.set_age(TG, AgeIn(age=19))
        elif current is OnboardingStep.name:
            await fake.set_name(TG, NameIn(name="Ira"))
        else:
            await fake.set_gender(TG, GenderIn(gender=Gender.female))


async def test_new_user_starts_at_language_step() -> None:
    state = await FakeApiClient().start(TG, _start())
    assert state.onboarding_step is OnboardingStep.lang
    assert state.status is UserStatus.onboarding


async def test_each_step_put_advances_onboarding() -> None:
    fake = FakeApiClient()
    await _onboarded_to(fake, OnboardingStep.city)
    state = await fake.get_me(TG)
    assert state.onboarding_step is OnboardingStep.city
    assert state.pool is Pool.adult


async def test_referral_code_is_recorded() -> None:
    fake = FakeApiClient()
    body = _start().model_copy(update={"referral_code": "ABC123"})
    await fake.start(TG, body)
    assert fake.calls[-1].body == body


async def test_unknown_user_gets_not_found() -> None:
    with pytest.raises(ApiException) as caught:
        await FakeApiClient().get_me(TG)
    assert caught.value.err.code is ErrorCode.not_found


async def test_age_below_min_is_refused_then_locked() -> None:
    fake = FakeApiClient()
    await _onboarded_to(fake, OnboardingStep.age)
    with pytest.raises(ApiException) as first:
        await fake.set_age(TG, AgeIn(age=15))
    assert first.value.err.code is ErrorCode.age_too_young
    with pytest.raises(ApiException) as second:
        await fake.set_age(TG, AgeIn(age=17))
    assert second.value.err.code is ErrorCode.age_locked


@settings(max_examples=30, deadline=None)
@given(st.integers(min_value=0, max_value=150))
def test_age_outcome_follows_age_min(age: int) -> None:
    import asyncio  # noqa: PLC0415 - hypothesis runs sync

    async def run() -> bool:
        fake = FakeApiClient()
        await _onboarded_to(fake, OnboardingStep.age)
        try:
            await fake.set_age(TG, AgeIn(age=age))
        except ApiException as exc:
            expected = ErrorCode.age_too_young if age < AGE_MIN else ErrorCode.validation_error
            assert exc.err.code is expected
            return False
        return True

    assert asyncio.run(run()) == (AGE_MIN <= age <= AGE_MAX)


async def test_name_rules() -> None:
    fake = FakeApiClient()
    await _onboarded_to(fake, OnboardingStep.name)
    for bad, code in (
        ("I", ErrorCode.validation_error),
        ("Ira2", ErrorCode.validation_error),
        ("t.me/x", ErrorCode.content_blocked),
        ("@ira", ErrorCode.content_blocked),
    ):
        with pytest.raises(ApiException) as caught:
            await fake.set_name(TG, NameIn(name=bad))
        assert caught.value.err.code is code, bad
    assert (await fake.set_name(TG, NameIn(name="Ірина"))).onboarding_step is OnboardingStep.gender


async def test_contract_violation_on_wrong_body_type() -> None:
    fake = FakeApiClient()
    await _onboarded_to(fake, OnboardingStep.age)
    with pytest.raises(ContractViolation):
        await fake.set_age(
            TG, AgeIn.model_construct(age="19")
        )  # bypasses validation like buggy code
    with pytest.raises(ContractViolation):
        await fake.set_age(TG, NameIn(name="x"))  # type: ignore[arg-type]  # wrong model


async def test_contract_violation_on_short_city_query() -> None:
    fake = FakeApiClient()
    await _onboarded_to(fake, OnboardingStep.city)
    with pytest.raises(ContractViolation):
        await fake.search_cities(TG, "В")


async def test_fail_next_and_timeout_next_fire_once() -> None:
    fake = FakeApiClient()
    await _onboarded_to(fake, OnboardingStep.age)
    fake.fail_next("set_age", ApiError(code=ErrorCode.internal, message="boom"))
    with pytest.raises(ApiException):
        await fake.set_age(TG, AgeIn(age=19))
    fake.timeout_next("set_age")
    with pytest.raises(ApiTimeout):
        await fake.set_age(TG, AgeIn(age=19))
    assert (await fake.set_age(TG, AgeIn(age=19))).onboarding_step is OnboardingStep.name
    assert [c.name for c in fake.calls[-3:]] == ["set_age", "set_age", "set_age"]


async def test_catalogs_come_from_seed_fixtures_localized() -> None:
    fake = FakeApiClient()
    await _onboarded_to(fake, OnboardingStep.city)
    cities = await fake.search_cities(TG, "Могилів")
    assert cities[0].name == "Могилів-Подільський"
    assert cities[0].region == "Вінницька область"
    await fake.set_lang(TG, LangIn(lang=Lang.en))
    assert (await fake.search_cities(TG, "Vinnyts"))[0].name == "Vinnytsia"
    categories = await fake.get_categories(TG)
    assert len(categories) == 12 and "other" not in {c.code for c in categories}
    goals = await fake.get_goals(TG)
    assert [g.code for g in goals] == list(GoalCode)


async def test_city_by_location_picks_nearest_seed_city() -> None:
    fake = FakeApiClient()
    await _onboarded_to(fake, OnboardingStep.city)
    city = await fake.city_by_location(TG, 48.44, 27.80)
    assert city.name == "Могилів-Подільський"
    with pytest.raises(ApiException) as caught:
        await fake.city_by_location(TG, 0.0, 0.0)
    assert caught.value.err.code is ErrorCode.not_found


async def test_full_onboarding_then_feed_serves_same_pool_demo_profiles() -> None:
    fake = FakeApiClient()
    await _onboarded_to(fake, OnboardingStep.city)
    await fake.set_city(TG, CityIn(city_id=700918))
    await fake.set_goals(TG, GoalsIn(codes=[GoalCode.friends]))
    ids = [i.id for i in (await fake.get_interests(TG, 1))[:3]]
    await fake.set_interests(TG, InterestsIn(interest_ids=ids))
    state = await fake.complete_onboarding(TG)
    assert state.status is UserStatus.active and state.onboarding_step is OnboardingStep.done
    item = await fake.feed_next(TG)
    assert item.kind == "item"
    assert item.card.age >= 18


async def test_complete_reports_missing_steps() -> None:
    fake = FakeApiClient()
    await _onboarded_to(fake, OnboardingStep.city)
    with pytest.raises(ApiException) as caught:
        await fake.complete_onboarding(TG)
    assert caught.value.err.code is ErrorCode.profile_incomplete
    assert caught.value.err.details == {"missing": ["city", "goals", "interests"]}


async def test_custom_interest_matches_existing_or_goes_pending() -> None:
    fake = FakeApiClient()
    await _onboarded_to(fake, OnboardingStep.city)
    matched = await fake.custom_interest(TG, CustomInterestIn(title="футбол"))
    assert matched.matched is not None and matched.matched.title == "Футбол"
    pending = await fake.custom_interest(TG, CustomInterestIn(title="кайтсерфінг"))
    assert pending.matched is None and pending.pending


async def test_verification_conflict_without_photo() -> None:
    fake = FakeApiClient()
    await _onboarded_to(fake, OnboardingStep.city)
    with pytest.raises(ApiException) as caught:
        await fake.verification_start(TG)
    assert caught.value.err.details == {"reason": "no_photo"}
    with pytest.raises(ApiException):
        await fake.verification_submit(
            TG, VerificationIn(verification_id=1, video_note_file_id="v")
        )
