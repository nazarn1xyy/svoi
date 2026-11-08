"""Loads seed data into Postgres. Catalogs upsert everywhere; demo users only in local and test."""

from collections.abc import Sequence
from datetime import UTC, datetime, time
from typing import Any

from geoalchemy2 import WKTElement
from sqlalchemy import Table, delete, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from svoi_contracts.constants import DEFAULT_AGE_RANGE_DELTA, QUIET_HOURS_DEFAULT
from svoi_contracts.enums import Pool

import svoi_api.db.models  # noqa: F401 - registers tables on Base.metadata
from svoi_api.db.base import Base
from svoi_api.seed import catalog
from svoi_api.seed.profiles import DemoUser, generate

DEMO_ENVS = frozenset({"local", "test"})
# fixed so repeated runs write identical rows
SEEDED_AT = datetime(2026, 11, 8, tzinfo=UTC)
POOL_BOUNDS = {Pool.minor: (16, 17), Pool.adult: (18, 99)}


def _table(name: str) -> Table:
    return Base.metadata.tables[name]


class DemoUsersForbidden(RuntimeError):
    """Demo users would mix fake people into a real feed."""


async def load(database_url: str, env: str, demo_users: bool | None = None) -> None:
    """Upsert catalogs and, outside production, the 50 demo users."""
    with_demo = env in DEMO_ENVS if demo_users is None else demo_users
    if with_demo and env not in DEMO_ENVS:
        raise DemoUsersForbidden(f"demo users are only allowed in {sorted(DEMO_ENVS)}")
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as conn:
            await _load_catalogs(conn)
            if with_demo:
                await _load_demo_users(conn, generate())
            await _sync_sequences(conn)
    finally:
        await engine.dispose()


async def _upsert(conn: AsyncConnection, table: Table, rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        return
    keys = [c.name for c in table.primary_key.columns]
    stmt = insert(table).values(list(rows))
    updates = {c: stmt.excluded[c] for c in rows[0] if c not in keys}
    if not updates:  # key-only tables such as profile_goals
        await conn.execute(stmt.on_conflict_do_nothing(index_elements=keys))
        return
    await conn.execute(stmt.on_conflict_do_update(index_elements=keys, set_=updates))


def _titles(row: Any, prefix: str = "title") -> dict[str, str]:
    return {f"{prefix}_{lang}": getattr(row, f"{prefix}_{lang}") for lang in ("uk", "ru", "en")}


async def _load_catalogs(conn: AsyncConnection) -> None:
    category_ids = {c.code: c.id for c in catalog.CATEGORIES}
    interest_ids = {i.code: i.id for i in catalog.INTERESTS}
    await _upsert(
        conn,
        _table("cities"),
        [
            {
                "id": c.geonames_id,
                "geonames_id": c.geonames_id,
                **_titles(c, "name"),
                **_titles(c, "region"),
                "country_code": c.country_code,
                "location": WKTElement(f"POINT({c.lon} {c.lat})", srid=4326),
                "population": c.population,
            }
            for c in catalog.load_cities()
        ],
    )
    await _upsert(
        conn,
        _table("interest_categories"),
        [
            {"id": c.id, "code": c.code, "emoji": c.emoji, **_titles(c), "position": c.position}
            for c in catalog.CATEGORIES
        ],
    )
    await _upsert(
        conn,
        _table("interests"),
        [
            {
                "id": i.id,
                "category_id": category_ids[i.category_code],
                "code": i.code,
                **_titles(i),
                "idf": 1.0,
                "is_custom": False,
                "moderation_status": "approved",
            }
            for i in catalog.INTERESTS
        ],
    )
    await _upsert(
        conn,
        _table("clarifications"),
        [
            {
                "id": c.id,
                "interest_id": interest_ids[c.interest_code],
                "question_key": c.question_key,
                "options": [{"key": o.key, **_titles(o)} for o in c.options],
                "priority": c.priority,
            }
            for c in catalog.CLARIFICATIONS
        ],
    )
    await _upsert(
        conn,
        _table("prompts"),
        [{"id": p.id, "code": p.code, **_titles(p), "active": True} for p in catalog.PROMPTS],
    )
    await _upsert(
        conn,
        _table("institutions"),
        [
            {
                "id": i.id,
                "city_id": i.city_geonames_id,
                "name": i.name,
                "short_name": i.short_name,
                "type": i.type.value,
                "source_id": i.source_id,
            }
            for i in catalog.INSTITUTIONS
        ],
    )


async def _load_demo_users(conn: AsyncConnection, users: list[DemoUser]) -> None:
    await _upsert(conn, _table("users"), [_user_row(u) for u in users])
    await _upsert(conn, _table("profiles"), [_profile_row(u) for u in users])
    ids = [u.id for u in users]
    # child rows are replaced wholesale so a changed generator never leaves stale picks behind
    for name in ("profile_goals", "profile_interests", "profile_prompts"):
        table = _table(name)
        await conn.execute(delete(table).where(table.c.user_id.in_(ids)))
    await _upsert(
        conn,
        _table("profile_goals"),
        [{"user_id": u.id, "goal": g.value} for u in users for g in u.goals],
    )
    await _upsert(
        conn,
        _table("profile_interests"),
        [
            {"user_id": u.id, "interest_id": i.interest_id, "note_key": i.note_key}
            for u in users
            for i in u.interests
        ],
    )
    await _upsert(
        conn,
        _table("profile_prompts"),
        [
            {
                "user_id": u.id,
                "prompt_id": p.prompt_id,
                "text": p.text,
                "moderation_status": "approved",
            }
            for u in users
            for p in u.prompts
        ],
    )
    await _upsert(conn, _table("filters"), [_filters_row(u) for u in users])
    await _upsert(
        conn,
        _table("settings"),
        [
            {
                "user_id": u.id,
                "notify_frequency": "instant",
                "quiet_from": time.fromisoformat(QUIET_HOURS_DEFAULT[0]),
                "quiet_to": time.fromisoformat(QUIET_HOURS_DEFAULT[1]),
                "tz": "Europe/Kyiv",
                "show_distance": True,
                "show_institution": True,
            }
            for u in users
        ],
    )


def _user_row(u: DemoUser) -> dict[str, Any]:
    return {
        "id": u.id,
        "tg_id": u.tg_id,
        "tg_username": u.tg_username,
        "tg_first_name": u.tg_first_name,
        "lang": u.lang.value,
        "status": u.status.value,
        "onboarding_step": u.onboarding_step.value,
        "consent_at": SEEDED_AT,
        "risk_score": 0,
        "verified": False,
        "shadow_banned": False,
        "bot_blocked": False,
        "report_weight": 1.0,
        "referral_code": u.referral_code,
        "created_at": SEEDED_AT,
        "last_active_at": SEEDED_AT,
    }


def _profile_row(u: DemoUser) -> dict[str, Any]:
    return {
        "user_id": u.id,
        "name": u.name,
        "age": u.age,
        "age_set_at": SEEDED_AT,
        "age_edits": 0,
        "gender": u.gender.value,
        "pool": u.pool.value,
        "city_id": u.city_geonames_id,
        "institution_id": u.institution_id,
        "height_cm": u.height_cm,
        "completeness": 0,  # the profiles domain recomputes it on the next profile change
        "hidden_by_moderation": False,
        "updated_at": SEEDED_AT,
    }


def _filters_row(u: DemoUser) -> dict[str, Any]:
    low, high = POOL_BOUNDS[u.pool]
    return {
        "user_id": u.id,
        "age_min": max(low, u.age - DEFAULT_AGE_RANGE_DELTA),
        "age_max": min(high, u.age + DEFAULT_AGE_RANGE_DELTA),
        "gender": "all",
        "radius": "city",
        "verified_only": False,
    }


async def _sync_sequences(conn: AsyncConnection) -> None:
    # explicit ids leave serial sequences behind; move them past the seeded rows
    for table in (
        "cities",
        "interest_categories",
        "interests",
        "clarifications",
        "prompts",
        "institutions",
        "users",
    ):
        await conn.execute(
            text(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'),"  # noqa: S608
                f" GREATEST((SELECT max(id) FROM {table}), 1))"
            )
        )
