"""Admin section: moderation queues, actions, user lookup, metrics (S10, S10b)."""

from datetime import date, datetime

from pydantic import StrictInt, StrictStr

from svoi_contracts.base import Contract
from svoi_contracts.cards import MediaRef, ProfileCard
from svoi_contracts.enums import (
    AdminAction,
    AdminQueueKind,
    GestureCode,
    Pool,
    ReportReason,
    UserStatus,
)


class ReportBrief(Contract):
    """Report summary inside a queue item."""

    reason: ReportReason
    text: str | None
    created_at: datetime


class AdminQueueItem(Contract):
    """Oldest item of a moderation queue."""

    item_id: int  # id of a report, media, verification, interest or profile_prompt
    kind: AdminQueueKind
    target_user_id: int
    target_tg_id: int
    target_card: ProfileCard  # full card, pending media included
    reports: list[ReportBrief]
    media: MediaRef | None  # photos
    verification_file_id: str | None  # verifications
    verification_gesture: GestureCode | None
    custom_interest_title: str | None  # custom_tags
    flagged_text: str | None  # texts
    created_at: datetime


class AdminActionIn(Contract):
    """Body of POST /admin/actions."""

    kind: AdminQueueKind
    item_id: StrictInt
    action: AdminAction
    reason: StrictStr | None = None


class MetricsOut(Contract):
    """Product metrics for a period."""

    period_from: date
    period_to: date
    starts: int  # new users in the period
    onboarding_completed: int
    onboarding_rate: float  # completed / starts
    likes_total: int
    matches_total: int
    mutual_rate: float  # matched likes / all likes
    d1_retention: float  # share of new users active the next day
    d7_retention: float  # share of new users active on day 7
    reports_per_1000_views: float
    confirmed_reports_rate: float  # accepted / (accepted + rejected)
    # v5: totals right now, activity and more period counts
    users_total: int
    users_by_status: dict[UserStatus, int]  # every status, zeros included
    users_by_pool: dict[Pool, int]  # profiles with an age
    verified_total: int
    shadow_banned_total: int
    bot_blocked_total: int
    active_today: int  # activity day today (Europe/Kyiv)
    active_7d: int
    active_30d: int
    views_total: int  # period
    skips_total: int  # period
    likes_with_message: int  # period
    reports_total: int  # user reports in the period
    likes_all_time: int
    matches_all_time: int
    likes_pending: int


class AdminUserOut(Contract):
    """User lookup for moderators."""

    user_id: int
    tg_id: int
    status: UserStatus
    shadow_banned: bool
    banned_until: datetime | None
    risk_score: int
    card: ProfileCard | None
    reports_total: int
    mod_actions: list[str]
