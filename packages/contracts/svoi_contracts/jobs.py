"""Queue payloads from docs/tech.md section 8. The arq function name equals `topic`."""

from datetime import datetime
from typing import ClassVar

from svoi_contracts import CORE_VERSION
from svoi_contracts.base import Contract
from svoi_contracts.enums import Lang, ModerationResultKind, RebuildReason, ReminderKind


class JobBase(Contract):
    """Common job fields; enqueue with _job_id=dedupe_key."""

    topic: ClassVar[str]

    dedupe_key: str
    core_version: int = CORE_VERSION


class NotifyLikes(JobBase):
    """Queue bot: new incoming likes."""

    topic: ClassVar[str] = "bot.notify_likes"

    user_id: int
    tg_id: int
    lang: Lang
    count: int


class NotifyMatch(JobBase):
    """Queue bot: mutual like."""

    topic: ClassVar[str] = "bot.notify_match"

    match_id: int
    recipient_user_id: int
    tg_id: int
    lang: Lang


class NotifyReminder(JobBase):
    """Queue bot: come-back reminder."""

    topic: ClassVar[str] = "bot.notify_reminder"

    user_id: int
    tg_id: int
    lang: Lang
    kind: ReminderKind


class NotifyNewPeople(JobBase):
    """Queue bot: new people digest."""

    topic: ClassVar[str] = "bot.notify_new_people"

    user_id: int
    tg_id: int
    lang: Lang
    interest_title: str
    count: int


class NotifyModeration(JobBase):
    """Queue bot: moderation result."""

    topic: ClassVar[str] = "bot.notify_moderation"

    user_id: int
    tg_id: int
    lang: Lang
    result: ModerationResultKind
    until: datetime | None = None


class ModeratePhoto(JobBase):
    """Queue api: classify an uploaded photo."""

    topic: ClassVar[str] = "api.moderate_photo"

    media_id: int


class RebuildFeed(JobBase):
    """Queue api: rebuild a user's candidate batch."""

    topic: ClassVar[str] = "api.rebuild_feed"

    user_id: int
    reason: RebuildReason
