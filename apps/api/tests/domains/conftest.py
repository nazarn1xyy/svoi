"""App against a migrated, seeded Postgres and a real Redis (db 15); data wiped per test."""

import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from alembic import command
from alembic.config import Config
from apihelp import ADMIN_TG, TOKEN, Tg
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from svoi_api.clients import Clients, FakeNsfw, FakeTelegramFiles
from svoi_api.clients.hasher import PHasher
from svoi_api.config import Settings
from svoi_api.core import time
from svoi_api.core.queue import RecordingQueue
from svoi_api.deps import Ctx
from svoi_api.main import create_app
from svoi_api.seed.load import load

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"

# DELETE, not TRUNCATE ... CASCADE: that would also empty interests (created_by_id -> users)
WIPE = ("DELETE FROM users", "DELETE FROM interests WHERE is_custom")


async def _admin(url: str, sql: str) -> None:
    engine = create_async_engine(url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            await conn.execute(text(sql))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def seeded_url() -> Iterator[str]:
    """Own database: schema at head plus catalogs (tests build their own people)."""
    base = os.environ.get("DATABASE_URL")
    if not base:
        pytest.skip("DATABASE_URL is not set; CI provides postgis/postgis:16-3.4")
    name = f"svoi_domains_{uuid.uuid4().hex[:8]}"
    asyncio.run(_admin(base, f'CREATE DATABASE "{name}"'))
    url = make_url(base).set(database=name).render_as_string(hide_password=False)
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", url)
    try:
        command.upgrade(config, "head")
        asyncio.run(load(url, env="test", demo_users=False))
        yield url
    finally:
        asyncio.run(_admin(base, f'DROP DATABASE "{name}" WITH (FORCE)'))


@pytest.fixture
def redis_url() -> str:
    """Redis db 15: tests flush it."""
    base = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    return base.rsplit("/", 1)[0] + "/15"


@pytest.fixture
async def env(seeded_url: str, redis_url: str) -> AsyncIterator[dict[str, Any]]:
    """Fresh data, Redis, queue and fakes for one test."""
    engine = create_async_engine(seeded_url)
    async with engine.begin() as conn:
        for sql in WIPE:
            await conn.execute(text(sql))
    redis = Redis.from_url(redis_url)
    try:
        await redis.flushdb()
    except Exception:
        pytest.skip("Redis is not reachable")
    time.freeze(None)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    queue = RecordingQueue()
    clients = Clients(FakeTelegramFiles(), FakeNsfw(), PHasher())
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]  # pydantic-settings kwarg
        ENV="test",
        INTERNAL_API_TOKEN=TOKEN,
        ADMIN_TG_IDS=str(ADMIN_TG),  # type: ignore[arg-type]  # parsed by the validator
    )
    yield {
        "engine": engine,
        "maker": maker,
        "redis": redis,
        "queue": queue,
        "clients": clients,
        "settings": settings,
    }
    time.freeze(None)
    await redis.aclose()
    await engine.dispose()


@pytest.fixture
async def http(env: dict[str, Any]) -> AsyncIterator[httpx.AsyncClient]:
    """ASGI client of the app."""
    app = create_app(
        env["settings"],
        sessionmaker=env["maker"],
        redis=env["redis"],
        queue=env["queue"],
        clients=env["clients"],
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://api") as client:
        yield client


@pytest.fixture
def queue(env: dict[str, Any]) -> RecordingQueue:
    """Jobs the app put on the queues."""
    q: RecordingQueue = env["queue"]
    return q


@pytest.fixture
def clients(env: dict[str, Any]) -> Clients:
    """Fake external clients."""
    c: Clients = env["clients"]
    return c


@pytest.fixture
async def ctx(env: dict[str, Any]) -> AsyncIterator[Ctx]:
    """Service context for direct calls (jobs, crons)."""
    maker: async_sessionmaker[AsyncSession] = env["maker"]
    async with maker() as session:
        yield Ctx(session, env["redis"], env["queue"], env["settings"], env["clients"])


@pytest.fixture
def user(http: httpx.AsyncClient) -> Callable[[int], Tg]:
    """tg_id -> request helper."""
    return lambda tg_id: Tg(http, tg_id)


@pytest.fixture
def freeze() -> Callable[[datetime], None]:
    """Pin the clock."""
    return time.freeze
