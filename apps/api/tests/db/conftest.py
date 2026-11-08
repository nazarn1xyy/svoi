"""Ephemeral Postgres database per test session (needs DATABASE_URL, set in CI)."""

import asyncio
import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import asyncpg
import pytest
from alembic.config import Config
from sqlalchemy.engine import make_url

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def _admin_dsn(url: str) -> str:
    return make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)


async def _exec(dsn: str, sql: str) -> None:
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(sql)
    finally:
        await conn.close()


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    base = os.environ.get("DATABASE_URL")
    if not base:
        pytest.skip("DATABASE_URL is not set; CI provides postgis/postgis:16-3.4")
    name = f"svoi_test_{uuid.uuid4().hex[:8]}"
    admin = _admin_dsn(base)
    asyncio.run(_exec(admin, f'CREATE DATABASE "{name}"'))
    try:
        yield make_url(base).set(database=name).render_as_string(hide_password=False)
    finally:
        asyncio.run(_exec(admin, f'DROP DATABASE "{name}" WITH (FORCE)'))


@pytest.fixture
def alembic_config(database_url: str) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", database_url)
    return config
