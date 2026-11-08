"""Likes domain: incoming likes, matches, contacts (S9)."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from svoi_contracts.api.reactions import MessageMedia
from svoi_contracts.base import Contract
from svoi_contracts.cards import MatchResult, ProfileCard, ProfileCardShort
from svoi_contracts.enums import LikeDecision


class CountOut(Contract):
    """Incoming likes count."""

    count: int


class IncomingLike(Contract):
    """Next incoming like."""

    kind: Literal["like"] = "like"
    like_id: int
    card: ProfileCard
    message: str | None
    media: MessageMedia | None


class NoIncoming(Contract):
    """No incoming likes left."""

    kind: Literal["none"] = "none"


type IncomingResponse = Annotated[IncomingLike | NoIncoming, Field(discriminator="kind")]


class RespondIn(Contract):
    """Body of POST /likes/{like_id}/respond."""

    decision: LikeDecision


class RespondOut(Contract):
    """Response result: a match on accept."""

    match: MatchResult | None


class ContactOut(Contract):
    """Mutual contact in the contacts list."""

    match_id: int
    partner: ProfileCardShort
    partner_username: str | None
    partner_tg_id: int
    matched_at: datetime
