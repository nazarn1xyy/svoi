"""K7 acceptance: the seed loads into Postgres idempotently and keeps demo users out of prod."""

import asyncio
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from svoi_api.seed import catalog
from svoi_api.seed.load import DemoUsersForbidden, load

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
COUNTED = (
    "cities",
    "interest_categories",
    "interests",
    "clarifications",
    "prompts",
    "institutions",
    "users",
    "profiles",
    "profile_goals",
    "profile_interests",
    "profile_prompts",
    "filters",
    "settings",
)


def _run(coro: Coroutine[Any, Any, Any]) -> Any:
    return asyncio.run(coro)


async def _counts(url: str) -> dict[str, int]:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            return {
                t: (await conn.execute(text(f"SELECT count(*) FROM {t}"))).scalar_one()  # noqa: S608
                for t in COUNTED
            }
    finally:
        await engine.dispose()


@pytest.fixture(scope="module")
def migrated(database_url: str) -> str:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    return database_url


def test_load_twice_gives_the_same_rows(migrated: str) -> None:
    _run(load(migrated, env="test"))
    first = _run(_counts(migrated))
    _run(load(migrated, env="test"))
    assert _run(_counts(migrated)) == first
    assert first["users"] == 50
    assert first["profiles"] == 50
    assert first["filters"] == first["settings"] == 50  # completed onboarding creates both
    assert first["interest_categories"] == len(catalog.CATEGORIES)
    assert first["interests"] == len(catalog.INTERESTS)


def test_inserting_after_seed_does_not_collide_with_seeded_ids(migrated: str) -> None:
    async def insert() -> None:
        engine = create_async_engine(migrated)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO prompts (code, title_uk, title_ru, title_en, active)"
                        " VALUES ('probe', 'x', 'x', 'x', true)"
                    )
                )
                await conn.execute(text("DELETE FROM prompts WHERE code = 'probe'"))
        finally:
            await engine.dispose()

    _run(load(migrated, env="test"))
    _run(insert())  # sequences were moved past explicit ids


def test_production_refuses_demo_users(migrated: str) -> None:
    with pytest.raises(DemoUsersForbidden):
        _run(load(migrated, env="production", demo_users=True))


def test_production_loads_catalogs_only(migrated: str) -> None:
    _run(load(migrated, env="production"))
    assert _run(_counts(migrated))["cities"] == len(catalog.load_cities())
