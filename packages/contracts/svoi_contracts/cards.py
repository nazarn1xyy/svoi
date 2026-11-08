"""Cards and shared models from docs/tech.md section 6.3."""

from datetime import datetime
from typing import Annotated

from pydantic import Field

from svoi_contracts.base import Contract
from svoi_contracts.enums import (
    DistanceBucket,
    Gender,
    GoalCode,
    IcebreakerTemplate,
    Lang,
    MediaKind,
    ModerationStatus,
    OnboardingStep,
    Pool,
    UserStatus,
)


class InterestChip(Contract):
    """Interest tag on a card."""

    id: int
    title: str
    note: str | None = None  # localized clarification note, e.g. "plays"
    common: bool = False  # the viewer has this interest too


class CommonBlock(Contract):
    """What the viewer and the card owner share."""

    interest_titles: list[str]
    same_institution: bool
    match_percent: Annotated[int, Field(ge=0, le=100)]


class MediaRef(Contract):
    """Photo or video attached to a profile."""

    id: int
    kind: MediaKind
    file_id: str
    moderation_status: ModerationStatus  # always approved on someone else's card


class PromptAnswer(Contract):
    """Answer to a profile prompt."""

    prompt_id: int
    title: str
    text: str


class ProfileCard(Contract):
    """Full profile card, rendered by ui.cards.render_card."""

    user_id: int
    name: str
    age: int
    verified: bool
    gender: Gender | None  # None when hidden
    city_name: str
    # None when either side lacks geo, show_distance is off, or a minor is outside the city
    distance: DistanceBucket | None
    goals: list[GoalCode]
    interests: list[InterestChip]  # shared ones first
    institution_name: str | None
    height_cm: int | None
    prompts: list[PromptAnswer]
    media: list[MediaRef]  # others' card: approved only; own card: all
    common: CommonBlock | None  # feed and incoming likes only
    completeness: int | None  # own card only


class ProfileCardShort(Contract):
    """Short card for contact lists."""

    user_id: int
    name: str
    age: int
    city_name: str


class Icebreaker(Contract):
    """Conversation starter shown on a match."""

    template: IcebreakerTemplate
    interest_title: str | None = None
    institution_name: str | None = None
    goal: GoalCode | None = None


class MatchResult(Contract):
    """Mutual like with the partner's contact."""

    match_id: int
    partner: ProfileCard
    partner_username: str | None
    partner_tg_id: int
    icebreaker: Icebreaker | None


class Limits(Contract):
    """Daily reaction and message limits."""

    reactions_left: int
    messages_left: int
    resets_at: datetime


class Counters(Contract):
    """Badge counters for the main menu."""

    incoming_likes: int


class UserState(Contract):
    """User status the bot routes on."""

    user_id: int
    tg_id: int
    status: UserStatus
    lang: Lang
    onboarding_step: OnboardingStep
    pool: Pool | None
    needs_username: bool  # tg_username is empty
    captcha_required: bool
    is_admin: bool
    counters: Counters


class Page[T](Contract):
    """Cursor page of a list endpoint."""

    items: list[T]
    next_cursor: str | None
