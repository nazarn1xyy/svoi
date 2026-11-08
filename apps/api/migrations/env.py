"""Alembic environment: async engine, PostGIS-aware autogenerate."""

import asyncio
import os

import svoi_api.db.models  # noqa: F401 - registers every table on Base.metadata
from alembic import context
from alembic.environment import NameFilterParentNames, NameFilterType
from geoalchemy2 import alembic_helpers
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from svoi_api.db.base import Base

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    # tests pass a per-session database through the config; deploy uses DATABASE_URL
    url = config.get_main_option("sqlalchemy.url") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("set DATABASE_URL or sqlalchemy.url")
    return url


def _include_name(name: str | None, type_: NameFilterType, _parents: NameFilterParentNames) -> bool:
    # The PostGIS image puts topology and tiger on search_path, so reflection sees their
    # tables. Tables outside our models belong to extensions: never create or drop them.
    if type_ == "table":
        return name in target_metadata.tables
    return True


def _configure(connection: Connection | None = None, url: str | None = None) -> None:
    context.configure(
        connection=connection,
        url=url,
        target_metadata=target_metadata,
        compare_type=True,
        # geoalchemy2 helpers skip spatial_ref_sys and render geospatial ops
        include_name=_include_name,
        include_object=alembic_helpers.include_object,
        process_revision_directives=alembic_helpers.writer,
        render_item=alembic_helpers.render_item,
        literal_binds=connection is None,
    )


def _run_sync(connection: Connection) -> None:
    _configure(connection)
    with context.begin_transaction():
        context.run_migrations()


async def _run_online() -> None:
    engine = create_async_engine(_url())
    async with engine.connect() as connection:
        await connection.run_sync(_run_sync)
    await engine.dispose()


if context.is_offline_mode():
    _configure(url=_url())
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(_run_online())
