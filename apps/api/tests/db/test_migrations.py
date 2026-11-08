"""K6 acceptance: alembic upgrade head and alembic check are green on ephemeral Postgres."""

import asyncio
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from svoi_api.db.base import Base

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def _run(coro: Coroutine[Any, Any, Any]) -> Any:
    return asyncio.run(coro)


async def _scalar(url: str, sql: str) -> Any:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            return (await conn.execute(text(sql))).scalar()
    finally:
        await engine.dispose()


def test_upgrade_head_then_check_has_no_drift(alembic_config: Config) -> None:
    command.upgrade(alembic_config, "head")
    command.check(alembic_config)  # raises when models and migrations disagree


def test_first_migration_enables_postgis_and_pg_trgm(
    alembic_config: Config, database_url: str
) -> None:
    command.upgrade(alembic_config, "head")
    sql = "SELECT count(*) FROM pg_extension WHERE extname IN ('postgis', 'pg_trgm')"
    assert _run(_scalar(database_url, sql)) == 2


def test_downgrade_to_base_and_back(alembic_config: Config, database_url: str) -> None:
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")
    remaining = _run(
        _scalar(
            database_url,
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
            " AND table_name NOT IN ('alembic_version', 'spatial_ref_sys')",
        )
    )
    assert remaining == 0
    enum_types = _run(_scalar(database_url, "SELECT count(*) FROM pg_type WHERE typtype = 'e'"))
    assert enum_types == 0
    command.upgrade(alembic_config, "head")
    command.check(alembic_config)


def test_every_model_table_exists_after_upgrade(alembic_config: Config, database_url: str) -> None:
    command.upgrade(alembic_config, "head")
    for table in Base.metadata.tables:
        exists = _run(_scalar(database_url, f"SELECT to_regclass('public.{table}') IS NOT NULL"))
        assert exists, table


async def _insert_profile(url: str, age: int | None, pool: str | None) -> bool:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            trans = await conn.begin()
            user_id = (
                await conn.execute(
                    text(
                        "INSERT INTO users (tg_id, lang, status, onboarding_step, risk_score,"
                        " verified, shadow_banned, bot_blocked, report_weight, referral_code)"
                        " VALUES (1, 'uk', 'onboarding', 'age', 0, false, false, false, 1.0,"
                        " 'R1') RETURNING id"
                    )
                )
            ).scalar_one()
            try:
                await conn.execute(
                    text(
                        "INSERT INTO profiles (user_id, age, pool, age_edits, completeness,"
                        " hidden_by_moderation) VALUES (:u, :a, CAST(:p AS pool), 0, 0, false)"
                    ),
                    {"u": user_id, "a": age, "p": pool},
                )
            except IntegrityError:
                return False
            finally:
                await trans.rollback()
            return True
    finally:
        await engine.dispose()


@pytest.fixture(scope="module")
def migrated(database_url: str) -> str:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    return database_url


@pytest.mark.xfail(
    strict=True,
    reason="CONTRACT GAP core v2 section 5: ck_profiles_pool evaluates to NULL, so age without"
    " pool and pool without age pass; strict xfail turns red once the core fixes it",
)
@settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    st.one_of(st.none(), st.integers(min_value=0, max_value=130)),
    st.sampled_from([None, "minor", "adult"]),
)
def test_profile_age_and_pool_checks(migrated: str, age: int | None, pool: str | None) -> None:
    # ck_profiles_age and ck_profiles_pool keep 16-17 and 18+ pools apart at the DB level
    allowed = (age is None and pool is None) or (
        age is not None
        and 16 <= age <= 99
        and ((age < 18 and pool == "minor") or (age >= 18 and pool == "adult"))
    )
    assert _run(_insert_profile(migrated, age, pool)) == allowed
