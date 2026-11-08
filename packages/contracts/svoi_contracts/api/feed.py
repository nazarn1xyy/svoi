"""Matching domain: feed (S7)."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from svoi_contracts.base import Contract
from svoi_contracts.cards import ProfileCard
from svoi_contracts.enums import FeedEmptyReason, RadiusMode


class FeedItem(Contract):
    """Next card in the feed."""

    kind: Literal["item"] = "item"
    card: ProfileCard
    can_undo: bool


class FeedEmpty(Contract):
    """No card to show, with the reason and how to widen the search."""

    kind: Literal["empty"] = "empty"
    reason: FeedEmptyReason
    expand_options: list[RadiusMode]  # wider than the current radius
    resets_at: datetime | None  # for limit_reached


type FeedResponse = Annotated[FeedItem | FeedEmpty, Field(discriminator="kind")]


class ExpandIn(Contract):
    """Body of POST /feed/expand."""

    radius: RadiusMode
