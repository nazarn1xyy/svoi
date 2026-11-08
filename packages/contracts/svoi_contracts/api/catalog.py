"""Catalog domain: cities, goals, interests, institutions, prompts (S2-S4)."""

from typing import Annotated

from pydantic import Field, StrictStr

from svoi_contracts.base import Contract
from svoi_contracts.constants import CUSTOM_INTEREST_LEN
from svoi_contracts.enums import GoalCode, InstitutionType


class CityOut(Contract):
    """City search or geolocation result."""

    id: int
    name: str
    region: str
    country_code: str


class GoalOut(Contract):
    """Communication goal."""

    code: GoalCode
    title: str
    emoji: str


class CategoryOut(Contract):
    """Interest category."""

    id: int
    code: str
    emoji: str
    title: str


class InterestOut(Contract):
    """Interest tag in a category."""

    id: int
    category_id: int
    title: str


class CustomInterestIn(Contract):
    """Body of POST /catalog/interests/custom."""

    title: Annotated[
        StrictStr, Field(min_length=CUSTOM_INTEREST_LEN[0], max_length=CUSTOM_INTEREST_LEN[1])
    ]


class CustomInterestOut(Contract):
    """Result of a custom interest request."""

    matched: InterestOut | None  # existing tag with similarity ≥ 0.6, added to the selection
    pending: bool  # new custom tag under moderation, shown after approval


class InstitutionOut(Contract):
    """College, university or other institution."""

    id: int
    name: str
    short_name: str | None
    type: InstitutionType


class PromptOut(Contract):
    """Profile prompt."""

    id: int
    title: str
