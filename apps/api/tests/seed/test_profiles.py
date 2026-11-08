"""K7 acceptance: 50 demo profiles, 40 adult and 10 minor, in the three seed cities."""

from collections import Counter

from hypothesis import given, settings
from hypothesis import strategies as st
from svoi_api.seed import catalog
from svoi_api.seed.profiles import SEED, DemoUser, generate
from svoi_contracts.constants import (
    ADULT_AGE,
    AGE_MAX,
    AGE_MIN,
    GOALS_COUNT,
    HEIGHT_CM,
    INTERESTS_COUNT,
    NAME_LEN,
    PROMPT_TEXT_MAX,
    PROMPTS_MAX,
)
from svoi_contracts.enums import OnboardingStep, Pool, UserStatus

SEED_CITIES = {700918, 689558, 703448}


def _check(users: list[DemoUser]) -> None:
    interest_ids = {i.id for i in catalog.INTERESTS}
    institutions = {i.id: i for i in catalog.INSTITUTIONS}
    clarifications = {c.interest_code: c for c in catalog.CLARIFICATIONS}
    code_by_id = {i.id: i.code for i in catalog.INTERESTS}
    assert len({u.tg_id for u in users}) == len(users)
    assert len({u.referral_code for u in users}) == len(users)
    for u in users:
        assert u.status is UserStatus.active
        assert u.onboarding_step is OnboardingStep.done
        assert AGE_MIN <= u.age <= AGE_MAX
        assert u.pool is (Pool.adult if u.age >= ADULT_AGE else Pool.minor)
        assert NAME_LEN[0] <= len(u.name) <= NAME_LEN[1]
        assert u.city_geonames_id in SEED_CITIES
        assert GOALS_COUNT[0] <= len(u.goals) <= GOALS_COUNT[1]
        assert len(set(u.goals)) == len(u.goals)
        assert INTERESTS_COUNT[0] <= len(u.interests) <= INTERESTS_COUNT[1]
        assert len({i.interest_id for i in u.interests}) == len(u.interests)
        for chosen in u.interests:
            assert chosen.interest_id in interest_ids
            if chosen.note_key is not None:
                clarification = clarifications[code_by_id[chosen.interest_id]]
                assert chosen.note_key in {o.key for o in clarification.options}
        if u.institution_id is not None:
            assert institutions[u.institution_id].city_geonames_id == u.city_geonames_id
        assert u.height_cm is None or HEIGHT_CM[0] <= u.height_cm <= HEIGHT_CM[1]
        assert len(u.prompts) <= PROMPTS_MAX
        assert len({p.prompt_id for p in u.prompts}) == len(u.prompts)
        assert all(len(p.text) <= PROMPT_TEXT_MAX for p in u.prompts)


def test_fifty_profiles_forty_adult_ten_minor() -> None:
    users = generate()
    assert len(users) == 50
    pools = Counter(u.pool for u in users)
    assert pools == {Pool.adult: 40, Pool.minor: 10}


def test_profiles_live_in_all_three_seed_cities() -> None:
    cities = Counter(u.city_geonames_id for u in generate())
    assert set(cities) == SEED_CITIES
    # both pools exist in every city so feed tests can stay inside one city
    for city in SEED_CITIES:
        pools = {u.pool for u in generate() if u.city_geonames_id == city}
        assert pools == {Pool.adult, Pool.minor}, city


def test_default_profiles_respect_core_limits() -> None:
    _check(generate())


def test_generation_is_deterministic() -> None:
    assert generate() == generate()
    assert generate(SEED) == generate()


@settings(max_examples=25, deadline=None)
@given(st.integers(min_value=0, max_value=2**32))
def test_any_seed_yields_valid_profiles(seed: int) -> None:
    users = generate(seed)
    assert Counter(u.pool for u in users) == {Pool.adult: 40, Pool.minor: 10}
    _check(users)
