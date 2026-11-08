"""K5 acceptance: request models reject what tech.md comments forbid, so FakeApiClient can too."""

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError
from svoi_contracts.api.catalog import CustomInterestIn
from svoi_contracts.api.moderation import ReportIn
from svoi_contracts.api.profile import (
    AgeIn,
    GoalsIn,
    InterestsIn,
    PromptAnswerIn,
    PromptsIn,
)
from svoi_contracts.api.reactions import MessageMedia, ReactionIn
from svoi_contracts.cards import CommonBlock
from svoi_contracts.constants import (
    CUSTOM_INTEREST_LEN,
    GOALS_COUNT,
    INTERESTS_COUNT,
    LIKE_MEDIA_MAX_SECONDS,
    LIKE_MESSAGE_MAX,
    PROMPT_TEXT_MAX,
    PROMPTS_MAX,
    REPORT_TEXT_MAX,
)
from svoi_contracts.enums import (
    GoalCode,
    MessageMediaKind,
    ReactionType,
    ReportContext,
    ReportReason,
)


def _valid(build: object) -> bool:
    try:
        build() if callable(build) else None
    except ValidationError:
        return False
    return True


def test_age_sent_as_string_is_a_contract_violation() -> None:
    # FRONTEND S1: FakeApiClient must fail when the bot sends age as a string
    with pytest.raises(ValidationError):
        AgeIn(age="19")  # type: ignore[arg-type]  # deliberately wrong type


@given(st.integers(min_value=-1000, max_value=1000))
def test_age_accepts_exactly_0_to_150(age: int) -> None:
    # 15 must reach the API so the domain can answer age_too_young
    assert _valid(lambda: AgeIn(age=age)) == (0 <= age <= 150)


@given(st.lists(st.sampled_from(list(GoalCode)), max_size=10))
def test_goals_count_bounds(codes: list[GoalCode]) -> None:
    low, high = GOALS_COUNT
    assert _valid(lambda: GoalsIn(codes=codes)) == (low <= len(codes) <= high)


@given(st.lists(st.integers(min_value=1, max_value=40), max_size=20))
def test_interests_need_count_bounds_and_no_duplicates(ids: list[int]) -> None:
    low, high = INTERESTS_COUNT
    expected = low <= len(ids) <= high and len(set(ids)) == len(ids)
    assert _valid(lambda: InterestsIn(interest_ids=ids)) == expected


@given(st.text(max_size=40))
def test_custom_interest_length(title: str) -> None:
    low, high = CUSTOM_INTEREST_LEN
    assert _valid(lambda: CustomInterestIn(title=title)) == (low <= len(title) <= high)


@given(st.text(max_size=PROMPT_TEXT_MAX + 20))
def test_prompt_answer_length(text: str) -> None:
    assert _valid(lambda: PromptAnswerIn(prompt_id=1, text=text)) == (len(text) <= PROMPT_TEXT_MAX)


@given(st.integers(min_value=0, max_value=5))
def test_prompts_at_most_max(count: int) -> None:
    answers = [PromptAnswerIn(prompt_id=i, text="x") for i in range(count)]
    assert _valid(lambda: PromptsIn(answers=answers)) == (count <= PROMPTS_MAX)


@given(st.integers(min_value=0, max_value=120))
def test_message_media_duration_limit(seconds: int) -> None:
    media = lambda: MessageMedia(  # noqa: E731
        kind=MessageMediaKind.voice, file_id="f", duration_s=seconds
    )
    assert _valid(media) == (seconds <= LIKE_MEDIA_MAX_SECONDS)


@given(
    st.sampled_from(list(ReactionType)),
    st.one_of(st.none(), st.text(max_size=LIKE_MESSAGE_MAX + 20)),
    st.booleans(),
)
def test_like_msg_needs_message_or_media_within_limit(
    kind: ReactionType, message: str | None, with_media: bool
) -> None:
    media = (
        MessageMedia(kind=MessageMediaKind.voice, file_id="f", duration_s=5) if with_media else None
    )
    expected = (message is None or len(message) <= LIKE_MESSAGE_MAX) and (
        kind is not ReactionType.like_msg or bool(message) or with_media
    )
    assert _valid(lambda: ReactionIn(target_id=1, type=kind, message=message, media=media)) == (
        expected
    )


@given(
    st.sampled_from(list(ReportReason)),
    st.sampled_from(list(ReportContext)),
    st.one_of(st.none(), st.text(max_size=REPORT_TEXT_MAX + 20)),
)
def test_report_rules(reason: ReportReason, context: ReportContext, text: str | None) -> None:
    # "other" needs text; "system" is reserved for safety; text is capped
    expected = (
        context is not ReportContext.system
        and (text is None or len(text) <= REPORT_TEXT_MAX)
        and (reason is not ReportReason.other or bool(text and text.strip()))
    )
    assert (
        _valid(lambda: ReportIn(target_id=1, reason=reason, text=text, context=context)) == expected
    )


@given(st.integers(min_value=-50, max_value=150))
def test_match_percent_is_0_to_100(percent: int) -> None:
    block = lambda: CommonBlock(  # noqa: E731
        interest_titles=[], same_institution=False, match_percent=percent
    )
    assert _valid(block) == (0 <= percent <= 100)
