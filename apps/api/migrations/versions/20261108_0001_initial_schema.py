"""Initial schema from docs/tech.md section 5 (core v2).

Revision ID: 0001
Revises:
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Section 5: the first migration enables PostGIS and trigram search.
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_geospatial_table(
        "cities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("geonames_id", sa.Integer(), nullable=False),
        sa.Column("name_uk", sa.String(length=80), nullable=False),
        sa.Column("name_ru", sa.String(length=80), nullable=False),
        sa.Column("name_en", sa.String(length=80), nullable=False),
        sa.Column("region_uk", sa.String(length=80), nullable=False),
        sa.Column("region_ru", sa.String(length=80), nullable=False),
        sa.Column("region_en", sa.String(length=80), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column(
            "location",
            Geography(
                geometry_type="POINT",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeogFromText",
                name="geography",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column("population", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("geonames_id"),
    )
    op.create_geospatial_index(
        "ix_cities_location",
        "cities",
        ["location"],
        unique=False,
        postgresql_using="gist",
        postgresql_ops={},
    )
    op.create_index(
        "ix_cities_name_en_trgm",
        "cities",
        ["name_en"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"name_en": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_cities_name_ru_trgm",
        "cities",
        ["name_ru"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"name_ru": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_cities_name_uk_trgm",
        "cities",
        ["name_uk"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"name_uk": "gin_trgm_ops"},
    )
    op.create_table(
        "interest_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("emoji", sa.String(length=8), nullable=False),
        sa.Column("title_uk", sa.String(length=40), nullable=False),
        sa.Column("title_ru", sa.String(length=40), nullable=False),
        sa.Column("title_en", sa.String(length=40), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "prompts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("title_uk", sa.String(length=80), nullable=False),
        sa.Column("title_ru", sa.String(length=80), nullable=False),
        sa.Column("title_en", sa.String(length=80), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("tg_id", sa.BigInteger(), nullable=False),
        sa.Column("tg_username", sa.String(length=32), nullable=True),
        sa.Column("tg_first_name", sa.String(length=64), nullable=True),
        sa.Column("lang", sa.Enum("uk", "ru", "en", name="lang"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("onboarding", "active", "hidden", "banned", "deleted", name="userstatus"),
            nullable=False,
        ),
        sa.Column(
            "onboarding_step",
            sa.Enum(
                "lang",
                "consent",
                "age",
                "name",
                "gender",
                "city",
                "goals",
                "interests",
                "clarify",
                "institution",
                "height",
                "prompts",
                "media",
                "preview",
                "done",
                name="onboardingstep",
            ),
            nullable=False,
        ),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("risk_score", sa.SmallInteger(), nullable=False),
        sa.Column("captcha_passed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("shadow_banned", sa.Boolean(), nullable=False),
        sa.Column("banned_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bot_blocked", sa.Boolean(), nullable=False),
        sa.Column("report_weight", sa.Float(), nullable=False),
        sa.Column("referral_code", sa.String(length=12), nullable=False),
        sa.Column("referred_by_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_active_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["referred_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("referral_code"),
        sa.UniqueConstraint("tg_id"),
    )
    op.create_index("ix_users_status_active", "users", ["status", "last_active_at"], unique=False)
    op.create_table(
        "blocks",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("blocked_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["blocked_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "blocked_id"),
    )
    op.create_table(
        "filters",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("age_min", sa.SmallInteger(), nullable=False),
        sa.Column("age_max", sa.SmallInteger(), nullable=False),
        sa.Column("gender", sa.Enum("all", "male", "female", name="genderfilter"), nullable=False),
        sa.Column(
            "radius",
            sa.Enum(
                "city",
                "km25",
                "km50",
                "km100",
                "region",
                "country",
                "any_online",
                name="radiusmode",
            ),
            nullable=False,
        ),
        sa.Column("verified_only", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "institutions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("city_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("short_name", sa.String(length=40), nullable=True),
        sa.Column(
            "type",
            sa.Enum("university", "college", "other", name="institutiontype"),
            nullable=False,
        ),
        sa.Column("source_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["city_id"],
            ["cities.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_institutions_city", "institutions", ["city_id"], unique=False)
    op.create_index(
        "ix_institutions_name_trgm",
        "institutions",
        ["name"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )
    op.create_table(
        "interests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=48), nullable=False),
        sa.Column("title_uk", sa.String(length=30), nullable=False),
        sa.Column("title_ru", sa.String(length=30), nullable=False),
        sa.Column("title_en", sa.String(length=30), nullable=False),
        sa.Column("idf", sa.Float(), nullable=False),
        sa.Column("is_custom", sa.Boolean(), nullable=False),
        sa.Column(
            "moderation_status",
            sa.Enum("pending", "approved", "rejected", name="moderationstatus"),
            nullable=False,
        ),
        sa.Column("created_by_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["interest_categories.id"],
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(
        "ix_interests_title_ru_trgm",
        "interests",
        ["title_ru"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"title_ru": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_interests_title_uk_trgm",
        "interests",
        ["title_uk"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"title_uk": "gin_trgm_ops"},
    )
    op.create_table(
        "likes",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("from_id", sa.BigInteger(), nullable=False),
        sa.Column("to_id", sa.BigInteger(), nullable=False),
        sa.Column("message", sa.String(length=300), nullable=True),
        sa.Column(
            "media_kind", sa.Enum("voice", "video_note", name="messagemediakind"), nullable=True
        ),
        sa.Column("media_file_id", sa.String(length=256), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "matched", "declined", "expired", name="likestatus"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["from_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("from_id", "to_id"),
    )
    op.create_index("ix_likes_to_status", "likes", ["to_id", "status", "created_at"], unique=False)
    op.create_table(
        "matches",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_a_id", sa.BigInteger(), nullable=False),
        sa.Column("user_b_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("removed_by_id", sa.BigInteger(), nullable=True),
        sa.CheckConstraint("user_a_id < user_b_id", name="ck_matches_order"),
        sa.ForeignKeyConstraint(["removed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_a_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_b_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_a_id", "user_b_id"),
    )
    op.create_table(
        "media",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.Enum("photo", "video", name="mediakind"), nullable=False),
        sa.Column("file_id", sa.String(length=256), nullable=False),
        sa.Column("file_unique_id", sa.String(length=64), nullable=False),
        sa.Column("phash", sa.String(length=32), nullable=True),
        sa.Column("nsfw_score", sa.Float(), nullable=True),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column(
            "moderation_status",
            sa.Enum("pending", "approved", "rejected", name="moderationstatus"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "position"),
    )
    op.create_index("ix_media_phash", "media", ["phash"], unique=False)
    op.create_table(
        "mod_actions",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("moderator_tg_id", sa.BigInteger(), nullable=False),
        sa.Column("target_user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "queue_kind",
            sa.Enum(
                "reports", "photos", "verifications", "custom_tags", "texts", name="adminqueuekind"
            ),
            nullable=False,
        ),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "action",
            sa.Enum(
                "ok",
                "delete_media",
                "delete_text",
                "ban_7d",
                "ban_forever",
                "move_to_minor_pool",
                "approve",
                "reject",
                name="adminaction",
            ),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=300), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "notification_outbox",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "likes", "match", "reminder", "new_people", "moderation", name="notificationkind"
            ),
            nullable=False,
        ),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("dedupe_key", sa.String(length=128), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "enqueued", "sent", "failed", "cancelled", name="outboxstatus"),
            nullable=False,
        ),
        sa.Column("attempts", sa.SmallInteger(), nullable=False),
        sa.Column("enqueued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key"),
    )
    op.create_index(
        "ix_outbox_status_sched", "notification_outbox", ["status", "scheduled_for"], unique=False
    )
    op.create_table(
        "profile_goals",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "goal",
            sa.Enum(
                "friends", "walks", "sport", "study", "gaming", "creative", "chat", name="goalcode"
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "goal"),
    )
    op.create_table(
        "profile_prompts",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("prompt_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(length=300), nullable=False),
        sa.Column(
            "moderation_status",
            sa.Enum("pending", "approved", "rejected", name="moderationstatus"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["prompt_id"],
            ["prompts.id"],
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "prompt_id"),
    )
    op.create_table(
        "reaction_bonuses",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("on_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.SmallInteger(), nullable=False),
        sa.Column("source", sa.Enum("referral", "admin", name="bonussource"), nullable=False),
        sa.Column("source_ref", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "source", "source_ref"),
    )
    op.create_table(
        "reports",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("reporter_id", sa.BigInteger(), nullable=True),
        sa.Column("target_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "reason",
            sa.Enum(
                "spam", "fake", "nsfw", "abuse", "underage", "scam", "other", name="reportreason"
            ),
            nullable=False,
        ),
        sa.Column("text", sa.String(length=500), nullable=True),
        sa.Column(
            "context",
            sa.Enum("feed", "incoming", "contact", "system", name="reportcontext"),
            nullable=False,
        ),
        sa.Column(
            "status", sa.Enum("open", "accepted", "rejected", name="reportstatus"), nullable=False
        ),
        sa.Column("moderator_tg_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reporter_id", "target_id"),
    )
    op.create_index("ix_reports_target_status", "reports", ["target_id", "status"], unique=False)
    op.create_table(
        "settings",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "notify_frequency",
            sa.Enum("instant", "hourly", "daily", name="notifyfrequency"),
            nullable=False,
        ),
        sa.Column("quiet_from", sa.Time(), nullable=False),
        sa.Column("quiet_to", sa.Time(), nullable=False),
        sa.Column("tz", sa.String(length=40), nullable=False),
        sa.Column("show_distance", sa.Boolean(), nullable=False),
        sa.Column("show_institution", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "user_activity_days",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "day"),
    )
    op.create_table(
        "verifications",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "gesture",
            sa.Enum(
                "three_fingers",
                "thumb_up",
                "peace",
                "wave",
                "ok_sign",
                "point_up",
                name="gesturecode",
            ),
            nullable=False,
        ),
        sa.Column("video_note_file_id", sa.String(length=256), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "rejected", name="moderationstatus"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_verifications_status", "verifications", ["status", "created_at"], unique=False
    )
    op.create_table(
        "views",
        sa.Column("viewer_id", sa.BigInteger(), nullable=False),
        sa.Column("target_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "action",
            sa.Enum(
                "shown", "like", "like_msg", "skip", "undo", "report", "block", name="viewaction"
            ),
            nullable=False,
        ),
        sa.Column("target_snapshot_hash", sa.String(length=64), nullable=True),
        sa.Column("reshown", sa.Boolean(), nullable=False),
        sa.Column(
            "shown_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("acted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["target_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["viewer_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("viewer_id", "target_id"),
    )
    op.create_index("ix_views_viewer_action", "views", ["viewer_id", "action"], unique=False)
    op.create_table(
        "clarifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("interest_id", sa.Integer(), nullable=False),
        sa.Column("question_key", sa.String(length=48), nullable=False),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("priority", sa.SmallInteger(), nullable=False),
        sa.ForeignKeyConstraint(["interest_id"], ["interests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("interest_id"),
    )
    op.create_table(
        "profile_interests",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("interest_id", sa.Integer(), nullable=False),
        sa.Column("note_key", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(["interest_id"], ["interests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "interest_id"),
    )
    op.create_index(
        "ix_profile_interests_interest", "profile_interests", ["interest_id"], unique=False
    )
    op.create_geospatial_table(
        "profiles",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=20), nullable=True),
        sa.Column("age", sa.SmallInteger(), nullable=True),
        sa.Column("age_set_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("age_edits", sa.SmallInteger(), nullable=False),
        sa.Column("age_incremented_on", sa.Date(), nullable=True),
        sa.Column("age_rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gender", sa.Enum("male", "female", "hidden", name="gender"), nullable=True),
        sa.Column("pool", sa.Enum("minor", "adult", name="pool"), nullable=True),
        sa.Column("city_id", sa.Integer(), nullable=True),
        sa.Column(
            "geo",
            Geography(
                geometry_type="POINT",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeogFromText",
                name="geography",
            ),
            nullable=True,
        ),
        sa.Column("institution_id", sa.Integer(), nullable=True),
        sa.Column("height_cm", sa.SmallInteger(), nullable=True),
        sa.Column("completeness", sa.SmallInteger(), nullable=False),
        sa.Column("hidden_by_moderation", sa.Boolean(), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(age IS NULL AND pool IS NULL) OR (age < 18 AND pool = 'minor') OR (age >= 18 AND pool = 'adult')",
            name="ck_profiles_pool",
        ),
        sa.CheckConstraint("age IS NULL OR age BETWEEN 16 AND 99", name="ck_profiles_age"),
        sa.ForeignKeyConstraint(
            ["city_id"],
            ["cities.id"],
        ),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_geospatial_index(
        "ix_profiles_geo",
        "profiles",
        ["geo"],
        unique=False,
        postgresql_using="gist",
        postgresql_ops={},
    )
    op.create_index("ix_profiles_pool_city", "profiles", ["pool", "city_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_profiles_pool_city", table_name="profiles")
    op.drop_geospatial_index(
        "ix_profiles_geo", table_name="profiles", postgresql_using="gist", column_name="geo"
    )
    op.drop_geospatial_table("profiles")
    op.drop_index("ix_profile_interests_interest", table_name="profile_interests")
    op.drop_table("profile_interests")
    op.drop_table("clarifications")
    op.drop_index("ix_views_viewer_action", table_name="views")
    op.drop_table("views")
    op.drop_index("ix_verifications_status", table_name="verifications")
    op.drop_table("verifications")
    op.drop_table("user_activity_days")
    op.drop_table("settings")
    op.drop_index("ix_reports_target_status", table_name="reports")
    op.drop_table("reports")
    op.drop_table("reaction_bonuses")
    op.drop_table("profile_prompts")
    op.drop_table("profile_goals")
    op.drop_index("ix_outbox_status_sched", table_name="notification_outbox")
    op.drop_table("notification_outbox")
    op.drop_table("mod_actions")
    op.drop_index("ix_media_phash", table_name="media")
    op.drop_table("media")
    op.drop_table("matches")
    op.drop_index("ix_likes_to_status", table_name="likes")
    op.drop_table("likes")
    op.drop_index(
        "ix_interests_title_uk_trgm",
        table_name="interests",
        postgresql_using="gin",
        postgresql_ops={"title_uk": "gin_trgm_ops"},
    )
    op.drop_index(
        "ix_interests_title_ru_trgm",
        table_name="interests",
        postgresql_using="gin",
        postgresql_ops={"title_ru": "gin_trgm_ops"},
    )
    op.drop_table("interests")
    op.drop_index(
        "ix_institutions_name_trgm",
        table_name="institutions",
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )
    op.drop_index("ix_institutions_city", table_name="institutions")
    op.drop_table("institutions")
    op.drop_table("filters")
    op.drop_table("blocks")
    op.drop_index("ix_users_status_active", table_name="users")
    op.drop_table("users")
    op.drop_table("prompts")
    op.drop_table("interest_categories")
    op.drop_index(
        "ix_cities_name_uk_trgm",
        table_name="cities",
        postgresql_using="gin",
        postgresql_ops={"name_uk": "gin_trgm_ops"},
    )
    op.drop_index(
        "ix_cities_name_ru_trgm",
        table_name="cities",
        postgresql_using="gin",
        postgresql_ops={"name_ru": "gin_trgm_ops"},
    )
    op.drop_index(
        "ix_cities_name_en_trgm",
        table_name="cities",
        postgresql_using="gin",
        postgresql_ops={"name_en": "gin_trgm_ops"},
    )
    op.drop_geospatial_index(
        "ix_cities_location", table_name="cities", postgresql_using="gist", column_name="location"
    )
    op.drop_geospatial_table("cities")
    # drop_table leaves PostgreSQL ENUM types behind; extensions stay because the PostGIS
    # image's topology and tiger extensions depend on postgis
    bind = op.get_bind()
    sa.Enum(name="adminaction").drop(bind, checkfirst=True)
    sa.Enum(name="adminqueuekind").drop(bind, checkfirst=True)
    sa.Enum(name="bonussource").drop(bind, checkfirst=True)
    sa.Enum(name="gender").drop(bind, checkfirst=True)
    sa.Enum(name="genderfilter").drop(bind, checkfirst=True)
    sa.Enum(name="gesturecode").drop(bind, checkfirst=True)
    sa.Enum(name="goalcode").drop(bind, checkfirst=True)
    sa.Enum(name="institutiontype").drop(bind, checkfirst=True)
    sa.Enum(name="lang").drop(bind, checkfirst=True)
    sa.Enum(name="likestatus").drop(bind, checkfirst=True)
    sa.Enum(name="mediakind").drop(bind, checkfirst=True)
    sa.Enum(name="messagemediakind").drop(bind, checkfirst=True)
    sa.Enum(name="moderationstatus").drop(bind, checkfirst=True)
    sa.Enum(name="notificationkind").drop(bind, checkfirst=True)
    sa.Enum(name="notifyfrequency").drop(bind, checkfirst=True)
    sa.Enum(name="onboardingstep").drop(bind, checkfirst=True)
    sa.Enum(name="outboxstatus").drop(bind, checkfirst=True)
    sa.Enum(name="pool").drop(bind, checkfirst=True)
    sa.Enum(name="radiusmode").drop(bind, checkfirst=True)
    sa.Enum(name="reportcontext").drop(bind, checkfirst=True)
    sa.Enum(name="reportreason").drop(bind, checkfirst=True)
    sa.Enum(name="reportstatus").drop(bind, checkfirst=True)
    sa.Enum(name="userstatus").drop(bind, checkfirst=True)
    sa.Enum(name="viewaction").drop(bind, checkfirst=True)
