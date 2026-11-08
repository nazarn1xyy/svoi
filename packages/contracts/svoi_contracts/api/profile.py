"""Profiles domain: onboarding steps, card fields and media (S1-S4)."""

from typing import Annotated, Self

from pydantic import Field, StrictInt, StrictStr, model_validator

from svoi_contracts.base import Contract
from svoi_contracts.constants import GOALS_COUNT, INTERESTS_COUNT, PROMPT_TEXT_MAX, PROMPTS_MAX
from svoi_contracts.enums import Gender, GoalCode, MediaKind, OnboardingStep


class AgeIn(Contract):
    """Body of PUT /profile/age; business bounds live in the domain."""

    age: Annotated[StrictInt, Field(ge=0, le=150)]


class NameIn(Contract):
    """Body of PUT /profile/name."""

    name: StrictStr


class GenderIn(Contract):
    """Body of PUT /profile/gender."""

    gender: Gender


class SkipIn(Contract):
    """Body of POST /onboarding/skip."""

    step: OnboardingStep


class CityIn(Contract):
    """Body of PUT /profile/city."""

    city_id: StrictInt
    lat: float | None = None  # only when the user shared a location
    lon: float | None = None


class GoalsIn(Contract):
    """Body of PUT /profile/goals."""

    codes: Annotated[list[GoalCode], Field(min_length=GOALS_COUNT[0], max_length=GOALS_COUNT[1])]


class InterestsIn(Contract):
    """Body of PUT /profile/interests."""

    interest_ids: Annotated[
        list[StrictInt], Field(min_length=INTERESTS_COUNT[0], max_length=INTERESTS_COUNT[1])
    ]

    @model_validator(mode="after")
    def _no_duplicates(self) -> Self:
        if len(set(self.interest_ids)) != len(self.interest_ids):
            raise ValueError("interest_ids must not repeat")
        return self


class OptionOut(Contract):
    """Clarification answer option."""

    key: str
    title: str


class ClarificationOut(Contract):
    """Clarification question for one interest."""

    interest_id: int
    interest_title: str
    question_key: str  # bot i18n key: clarify.<question_key>
    options: list[OptionOut]


class NoteIn(Contract):
    """Body of PUT /profile/interests/{interest_id}/note."""

    option_key: StrictStr


class InstitutionIn(Contract):
    """Body of PUT /profile/institution; None removes it."""

    institution_id: StrictInt | None


class HeightIn(Contract):
    """Body of PUT /profile/height; None removes it."""

    height_cm: StrictInt | None


class PromptAnswerIn(Contract):
    """One prompt answer."""

    prompt_id: StrictInt
    text: Annotated[StrictStr, Field(max_length=PROMPT_TEXT_MAX)]


class PromptsIn(Contract):
    """Body of PUT /profile/prompts; an empty list removes all."""

    answers: Annotated[list[PromptAnswerIn], Field(max_length=PROMPTS_MAX)]


class MediaIn(Contract):
    """Body of POST /profile/media."""

    kind: MediaKind
    file_id: StrictStr
    file_unique_id: StrictStr


class MediaOrderIn(Contract):
    """Body of PUT /profile/media/order."""

    ids: list[StrictInt]
