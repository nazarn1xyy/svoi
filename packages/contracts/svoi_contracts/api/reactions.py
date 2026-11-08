"""Reactions domain: likes, messages, skips, limits (S8)."""

from typing import Annotated, Self

from pydantic import Field, StrictInt, StrictStr, model_validator

from svoi_contracts.base import Contract
from svoi_contracts.cards import Limits, MatchResult
from svoi_contracts.constants import LIKE_MEDIA_MAX_SECONDS, LIKE_MESSAGE_MAX
from svoi_contracts.enums import MessageMediaKind, ReactionType


class MessageMedia(Contract):
    """Voice or video note attached to a like."""

    kind: MessageMediaKind
    file_id: StrictStr
    duration_s: Annotated[StrictInt, Field(le=LIKE_MEDIA_MAX_SECONDS)]


class ReactionIn(Contract):
    """Body of POST /reactions."""

    target_id: StrictInt
    type: ReactionType
    message: Annotated[StrictStr | None, Field(max_length=LIKE_MESSAGE_MAX)] = None
    media: MessageMedia | None = None

    @model_validator(mode="after")
    def _like_msg_has_content(self) -> Self:
        if self.type is ReactionType.like_msg and not (self.message or self.media):
            raise ValueError("like_msg needs a message or media")
        return self


class ReactionOut(Contract):
    """Reaction result: an instant match when the target already liked back."""

    match: MatchResult | None
    limits: Limits
