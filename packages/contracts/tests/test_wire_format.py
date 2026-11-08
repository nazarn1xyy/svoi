"""K5 acceptance: contracts survive the wire formats tech.md prescribes."""

from datetime import UTC, datetime, time

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import BaseModel, ValidationError
from svoi_contracts import CORE_VERSION
from svoi_contracts.api.likes import ContactOut
from svoi_contracts.api.moderation import ReportIn
from svoi_contracts.api.prefs import FiltersOut, SettingsIn, SettingsOut
from svoi_contracts.api.profile import AgeIn
from svoi_contracts.api.users import LangIn
from svoi_contracts.cards import Counters, Page, ProfileCardShort, UserState
from svoi_contracts.enums import (
    GenderFilter,
    Lang,
    ModerationResultKind,
    NotifyFrequency,
    OnboardingStep,
    Pool,
    RadiusMode,
    RebuildReason,
    ReminderKind,
    ReportContext,
    ReportReason,
    UserStatus,
)
from svoi_contracts.errors import ApiError, ErrorCode
from svoi_contracts.jobs import (
    JobBase,
    ModeratePhoto,
    NotifyLikes,
    NotifyMatch,
    NotifyModeration,
    NotifyNewPeople,
    NotifyReminder,
    RebuildFeed,
)

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)

SAMPLES: list[BaseModel] = [
    UserState(
        user_id=1,
        tg_id=100,
        status=UserStatus.onboarding,
        lang=Lang.ru,
        onboarding_step=OnboardingStep.gender,
        pool=Pool.minor,
        needs_username=True,
        captcha_required=False,
        is_admin=False,
        counters=Counters(incoming_likes=0),
    ),
    FiltersOut(
        age_min=16,
        age_max=17,
        age_bounds=(16, 17),
        gender=GenderFilter.all,
        radius=RadiusMode.region,
        verified_only=False,
    ),
    SettingsOut(
        notify_frequency=NotifyFrequency.hourly,
        quiet_from=time(22, 0),
        quiet_to=time(9, 0),
        show_distance=False,
        show_institution=True,
    ),
    ApiError(code=ErrorCode.banned, message="banned", details={"until": None}),
    Page[ContactOut](
        items=[
            ContactOut(
                match_id=7,
                partner=ProfileCardShort(user_id=2, name="Ira", age=17, city_name="Kyiv"),
                partner_username=None,
                partner_tg_id=200,
                matched_at=NOW,
            )
        ],
        next_cursor="c2",
    ),
]

REQUESTS: list[BaseModel] = [
    LangIn(lang=Lang.uk),
    AgeIn(age=19),
    ReportIn(target_id=2, reason=ReportReason.other, text="spam bot", context=ReportContext.feed),
    SettingsIn(
        notify_frequency=NotifyFrequency.daily,
        quiet_from=time(23, 0),
        quiet_to=time(8, 0),
        show_distance=True,
        show_institution=False,
    ),
]

JOBS: list[JobBase] = [
    NotifyLikes(dedupe_key="likes:1:2026-11-08T12:00", user_id=1, tg_id=100, lang=Lang.uk, count=3),
    NotifyMatch(dedupe_key="match:7:1", match_id=7, recipient_user_id=1, tg_id=100, lang=Lang.en),
    NotifyReminder(
        dedupe_key="reminder:1:day3:2026-11-05",
        user_id=1,
        tg_id=100,
        lang=Lang.uk,
        kind=ReminderKind.day3,
    ),
    NotifyNewPeople(
        dedupe_key="newpeople:1:20261108",
        user_id=1,
        tg_id=100,
        lang=Lang.uk,
        interest_title="CS2",
        count=4,
    ),
    NotifyModeration(
        dedupe_key="mod:reports:9:ban_7d",
        user_id=1,
        tg_id=100,
        lang=Lang.ru,
        result=ModerationResultKind.banned,
        until=NOW,
    ),
    ModeratePhoto(dedupe_key="photo:5", media_id=5),
    RebuildFeed(dedupe_key="feed:1:expand:202611081200", user_id=1, reason=RebuildReason.expand),
]


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda s: type(s).__name__)
def test_api_json_round_trips_in_strict_mode(sample: BaseModel) -> None:
    # HttpApiClient and FakeApiClient fixtures parse JSON text
    assert type(sample).model_validate_json(sample.model_dump_json()) == sample


@pytest.mark.parametrize("job", JOBS, ids=lambda j: type(j).__name__)
def test_job_payload_dict_round_trips(job: JobBase) -> None:
    # arq carries model_dump(mode="json"); the consumer validates the plain dict
    assert type(job).model_validate(job.model_dump(mode="json")) == job


@pytest.mark.parametrize("job", JOBS, ids=lambda j: type(j).__name__)
def test_job_rejects_unknown_fields(job: JobBase) -> None:
    # invalid payload → log without retry (tech.md section 8) needs a hard failure here
    with pytest.raises(ValidationError):
        type(job).model_validate({**job.model_dump(mode="json"), "extra": 1})


def test_job_from_older_core_still_validates() -> None:
    payload = {**JOBS[0].model_dump(mode="json"), "core_version": 1}
    assert NotifyLikes.model_validate(payload).core_version == 1


@given(st.integers(min_value=0, max_value=10**6), st.text(max_size=20))
def test_jobs_default_to_current_core(count: int, key: str) -> None:
    job = NotifyLikes(dedupe_key=key, user_id=1, tg_id=1, lang=Lang.uk, count=count)
    assert job.core_version == CORE_VERSION


@pytest.mark.parametrize("sample", SAMPLES + REQUESTS, ids=lambda s: type(s).__name__)
def test_json_mode_dicts_validate_like_fastapi_bodies(sample: BaseModel) -> None:
    # FastAPI validates decoded JSON in python mode: enums arrive as "uk", dates as ISO strings
    assert type(sample).model_validate(sample.model_dump(mode="json")) == sample


def test_request_rejects_number_as_string() -> None:
    with pytest.raises(ValidationError):
        AgeIn.model_validate({"age": "19"})
