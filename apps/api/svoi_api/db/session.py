"""Async engine and session factories; deps.py (B0.1) wires them to config."""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def make_engine(database_url: str) -> AsyncEngine:
    """Async engine for postgresql+asyncpg URLs."""
    return create_async_engine(database_url, pool_pre_ping=True)


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Session factory; objects stay readable after commit for response building."""
    return async_sessionmaker(engine, expire_on_commit=False)
