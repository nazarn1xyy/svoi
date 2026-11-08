"""Tables from docs/tech.md section 5. Change them only through the core and a migration."""

from datetime import date, datetime, time
from typing import Any

from geoalchemy2 import Geography, WKBElement
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from svoi_contracts.enums import (
    AdminAction,
    AdminQueueKind,
    BonusSource,
    Gender,
    GenderFilter,
    GestureCode,
    GoalCode,
    InstitutionType,
    Lang,
    LikeStatus,
    MediaKind,
    MessageMediaKind,
    ModerationStatus,
    NotificationKind,
    NotifyFrequency,
    OnboardingStep,
    OutboxStatus,
    Pool,
    RadiusMode,
    ReportContext,
    ReportReason,
    ReportStatus,
    UserStatus,
    ViewAction,
)

from svoi_api.db.base import Base, pg_enum


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    tg_username: Mapped[str | None] = mapped_column(String(32))
    tg_first_name: Mapped[str | None] = mapped_column(String(64))
    lang: Mapped[Lang] = mapped_column(pg_enum(Lang), default=Lang.uk)
    status: Mapped[UserStatus] = mapped_column(pg_enum(UserStatus), default=UserStatus.onboarding)
    onboarding_step: Mapped[OnboardingStep] = mapped_column(
        pg_enum(OnboardingStep), default=OnboardingStep.lang
    )
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    risk_score: Mapped[int] = mapped_column(SmallInteger, default=0)
    captcha_passed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    shadow_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    banned_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )  # NULL with status=banned means forever
    bot_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    report_weight: Mapped[float] = mapped_column(Float, default=1.0)  # lowered for false reports
    referral_code: Mapped[str] = mapped_column(String(12), unique=True)
    referred_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    __table_args__ = (Index("ix_users_status_active", "status", "last_active_at"),)


class Profile(Base):
    __tablename__ = "profiles"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str | None] = mapped_column(String(20))
    age: Mapped[int | None] = mapped_column(SmallInteger)
    age_set_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    age_edits: Mapped[int] = mapped_column(SmallInteger, default=0)
    age_incremented_on: Mapped[date | None] = mapped_column(Date)
    age_rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )  # last attempt with age < AGE_MIN
    gender: Mapped[Gender | None] = mapped_column(pg_enum(Gender))
    pool: Mapped[Pool | None] = mapped_column(pg_enum(Pool))
    city_id: Mapped[int | None] = mapped_column(ForeignKey("cities.id"))
    geo: Mapped[WKBElement | None] = mapped_column(
        Geography("POINT", srid=4326, spatial_index=False)
    )  # rounded to GEO_ROUND_DECIMALS
    institution_id: Mapped[int | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="SET NULL")
    )
    height_cm: Mapped[int | None] = mapped_column(SmallInteger)
    completeness: Mapped[int] = mapped_column(SmallInteger, default=0)  # 0..100
    hidden_by_moderation: Mapped[bool] = mapped_column(Boolean, default=False)
    snapshot_hash: Mapped[str | None] = mapped_column(
        String(64)
    )  # hash of interests + media for "profile changed"
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        CheckConstraint("age IS NULL OR age BETWEEN 16 AND 99", name="ck_profiles_age"),
        CheckConstraint(
            # COALESCE: a NULL result would pass the CHECK (core v3)
            "COALESCE((age IS NULL AND pool IS NULL) OR (age < 18 AND pool = 'minor')"
            " OR (age >= 18 AND pool = 'adult'), false)",
            name="ck_profiles_pool",
        ),
        Index("ix_profiles_pool_city", "pool", "city_id"),
        Index("ix_profiles_geo", "geo", postgresql_using="gist"),
    )


class ProfileGoal(Base):
    __tablename__ = "profile_goals"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    goal: Mapped[GoalCode] = mapped_column(pg_enum(GoalCode), primary_key=True)


class InterestCategory(Base):
    __tablename__ = "interest_categories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    emoji: Mapped[str] = mapped_column(String(8))
    title_uk: Mapped[str] = mapped_column(String(40))
    title_ru: Mapped[str] = mapped_column(String(40))
    title_en: Mapped[str] = mapped_column(String(40))
    position: Mapped[int] = mapped_column(SmallInteger)


class Interest(Base):
    __tablename__ = "interests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("interest_categories.id"))
    code: Mapped[str] = mapped_column(String(48), unique=True)
    title_uk: Mapped[str] = mapped_column(String(30))
    title_ru: Mapped[str] = mapped_column(String(30))
    title_en: Mapped[str] = mapped_column(String(30))
    idf: Mapped[float] = mapped_column(Float, default=1.0)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)
    moderation_status: Mapped[ModerationStatus] = mapped_column(
        pg_enum(ModerationStatus), default=ModerationStatus.approved
    )
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    __table_args__ = (
        Index(
            "ix_interests_title_uk_trgm",
            "title_uk",
            postgresql_using="gin",
            postgresql_ops={"title_uk": "gin_trgm_ops"},
        ),
        Index(
            "ix_interests_title_ru_trgm",
            "title_ru",
            postgresql_using="gin",
            postgresql_ops={"title_ru": "gin_trgm_ops"},
        ),
    )


class ProfileInterest(Base):
    __tablename__ = "profile_interests"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    interest_id: Mapped[int] = mapped_column(
        ForeignKey("interests.id", ondelete="CASCADE"), primary_key=True
    )
    note_key: Mapped[str | None] = mapped_column(String(32))  # clarification answer, e.g. "plays"
    __table_args__ = (Index("ix_profile_interests_interest", "interest_id"),)


class Clarification(Base):
    __tablename__ = "clarifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    interest_id: Mapped[int] = mapped_column(
        ForeignKey("interests.id", ondelete="CASCADE"), unique=True
    )
    question_key: Mapped[str] = mapped_column(String(48))  # bot i18n key
    options: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB
    )  # [{"key": "plays", "title_uk": "...", "title_ru": "...", "title_en": "..."}]
    priority: Mapped[int] = mapped_column(SmallInteger, default=0)


class Prompt(Base):
    __tablename__ = "prompts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    title_uk: Mapped[str] = mapped_column(String(80))
    title_ru: Mapped[str] = mapped_column(String(80))
    title_en: Mapped[str] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ProfilePrompt(Base):
    __tablename__ = "profile_prompts"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    prompt_id: Mapped[int] = mapped_column(ForeignKey("prompts.id"), primary_key=True)
    text: Mapped[str] = mapped_column(String(300))
    moderation_status: Mapped[ModerationStatus] = mapped_column(
        pg_enum(ModerationStatus), default=ModerationStatus.approved
    )


class Media(Base):
    __tablename__ = "media"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[MediaKind] = mapped_column(pg_enum(MediaKind))
    file_id: Mapped[str] = mapped_column(String(256))
    file_unique_id: Mapped[str] = mapped_column(String(64))
    phash: Mapped[str | None] = mapped_column(String(32))
    nsfw_score: Mapped[float | None] = mapped_column(Float)
    position: Mapped[int] = mapped_column(SmallInteger)
    moderation_status: Mapped[ModerationStatus] = mapped_column(
        pg_enum(ModerationStatus), default=ModerationStatus.pending
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("user_id", "position"), Index("ix_media_phash", "phash"))


class City(Base):
    __tablename__ = "cities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    geonames_id: Mapped[int] = mapped_column(Integer, unique=True)
    name_uk: Mapped[str] = mapped_column(String(80))
    name_ru: Mapped[str] = mapped_column(String(80))
    name_en: Mapped[str] = mapped_column(String(80))
    region_uk: Mapped[str] = mapped_column(String(80))
    region_ru: Mapped[str] = mapped_column(String(80))
    region_en: Mapped[str] = mapped_column(String(80))
    country_code: Mapped[str] = mapped_column(String(2))
    location: Mapped[WKBElement] = mapped_column(Geography("POINT", srid=4326, spatial_index=False))
    population: Mapped[int] = mapped_column(Integer)
    __table_args__ = (
        Index("ix_cities_location", "location", postgresql_using="gist"),
        Index(
            "ix_cities_name_uk_trgm",
            "name_uk",
            postgresql_using="gin",
            postgresql_ops={"name_uk": "gin_trgm_ops"},
        ),
        Index(
            "ix_cities_name_ru_trgm",
            "name_ru",
            postgresql_using="gin",
            postgresql_ops={"name_ru": "gin_trgm_ops"},
        ),
        Index(
            "ix_cities_name_en_trgm",
            "name_en",
            postgresql_using="gin",
            postgresql_ops={"name_en": "gin_trgm_ops"},
        ),
    )


class Institution(Base):
    __tablename__ = "institutions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"))
    name: Mapped[str] = mapped_column(String(200))
    short_name: Mapped[str | None] = mapped_column(String(40))
    type: Mapped[InstitutionType] = mapped_column(pg_enum(InstitutionType))
    source_id: Mapped[str | None] = mapped_column(String(64))
    __table_args__ = (
        Index("ix_institutions_city", "city_id"),
        Index(
            "ix_institutions_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )


class Filters(Base):
    __tablename__ = "filters"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    age_min: Mapped[int] = mapped_column(SmallInteger)
    age_max: Mapped[int] = mapped_column(SmallInteger)
    gender: Mapped[GenderFilter] = mapped_column(pg_enum(GenderFilter), default=GenderFilter.all)
    radius: Mapped[RadiusMode] = mapped_column(pg_enum(RadiusMode), default=RadiusMode.city)
    verified_only: Mapped[bool] = mapped_column(Boolean, default=False)


class Settings(Base):
    __tablename__ = "settings"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    notify_frequency: Mapped[NotifyFrequency] = mapped_column(
        pg_enum(NotifyFrequency), default=NotifyFrequency.instant
    )
    quiet_from: Mapped[time] = mapped_column(Time, default=time(23, 0))
    quiet_to: Mapped[time] = mapped_column(Time, default=time(8, 0))
    tz: Mapped[str] = mapped_column(String(40), default="Europe/Kyiv")
    show_distance: Mapped[bool] = mapped_column(Boolean, default=True)
    show_institution: Mapped[bool] = mapped_column(Boolean, default=True)


class View(Base):
    __tablename__ = "views"
    viewer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    target_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    action: Mapped[ViewAction] = mapped_column(pg_enum(ViewAction), default=ViewAction.shown)
    target_snapshot_hash: Mapped[str | None] = mapped_column(String(64))
    reshown: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # an unanswered show was already returned once
    shown_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    acted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index("ix_views_viewer_action", "viewer_id", "action"),)


class Like(Base):
    __tablename__ = "likes"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    from_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    to_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    message: Mapped[str | None] = mapped_column(String(300))
    media_kind: Mapped[MessageMediaKind | None] = mapped_column(pg_enum(MessageMediaKind))
    media_file_id: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[LikeStatus] = mapped_column(pg_enum(LikeStatus), default=LikeStatus.pending)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("from_id", "to_id"),
        Index("ix_likes_to_status", "to_id", "status", "created_at"),
    )


class Match(Base):
    __tablename__ = "matches"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_a_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))  # smaller id
    user_b_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))  # larger id
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    removed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    __table_args__ = (
        UniqueConstraint("user_a_id", "user_b_id"),
        CheckConstraint("user_a_id < user_b_id", name="ck_matches_order"),
    )


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    reporter_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )  # NULL for automatic reports (safety)
    target_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    reason: Mapped[ReportReason] = mapped_column(pg_enum(ReportReason))
    text: Mapped[str | None] = mapped_column(String(500))
    context: Mapped[ReportContext] = mapped_column(pg_enum(ReportContext))
    status: Mapped[ReportStatus] = mapped_column(pg_enum(ReportStatus), default=ReportStatus.open)
    moderator_tg_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("reporter_id", "target_id"),
        Index("ix_reports_target_status", "target_id", "status"),
    )


class Block(Base):
    __tablename__ = "blocks"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    blocked_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Verification(Base):
    __tablename__ = "verifications"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    gesture: Mapped[GestureCode] = mapped_column(pg_enum(GestureCode))
    video_note_file_id: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[ModerationStatus] = mapped_column(
        pg_enum(ModerationStatus), default=ModerationStatus.pending
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index("ix_verifications_status", "status", "created_at"),)


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[NotificationKind] = mapped_column(pg_enum(NotificationKind))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    dedupe_key: Mapped[str] = mapped_column(String(128), unique=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[OutboxStatus] = mapped_column(
        pg_enum(OutboxStatus), default=OutboxStatus.pending
    )
    attempts: Mapped[int] = mapped_column(
        SmallInteger, default=0
    )  # times enqueued to the bot queue
    enqueued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index("ix_outbox_status_sched", "status", "scheduled_for"),)


class ReactionBonus(Base):
    __tablename__ = "reaction_bonuses"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    on_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[int] = mapped_column(SmallInteger)
    source: Mapped[BonusSource] = mapped_column(pg_enum(BonusSource))
    source_ref: Mapped[str] = mapped_column(String(64))  # e.g. id of the invited user
    __table_args__ = (UniqueConstraint("user_id", "source", "source_ref"),)


class UserActivityDay(Base):
    __tablename__ = "user_activity_days"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(
        Date, primary_key=True
    )  # Europe/Kyiv day; upserted on the first request of the day


class ModAction(Base):
    __tablename__ = "mod_actions"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    moderator_tg_id: Mapped[int] = mapped_column(BigInteger)
    target_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    queue_kind: Mapped[AdminQueueKind] = mapped_column(pg_enum(AdminQueueKind))
    item_id: Mapped[int] = mapped_column(BigInteger)
    action: Mapped[AdminAction] = mapped_column(pg_enum(AdminAction))
    reason: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
