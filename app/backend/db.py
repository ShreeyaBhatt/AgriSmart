"""Async SQLAlchemy engine + session for the SQLite app database.

SQLite (not MongoDB as in the build‑plan PDF) — a single file, zero setup, so the
project runs from the README on any machine. The schema is a portable superset of
the plan's data model.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings

log = logging.getLogger(__name__)
_settings = get_settings()

engine = create_async_engine(_settings.database_url, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def _sql_literal(value: object) -> str:
    """Render a trusted, ORM-declared scalar default as a SQL literal for an
    ALTER TABLE ... DEFAULT clause. Not for untrusted input — values here
    only ever come from this codebase's own mapped_column(default=...)."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _add_missing_columns(conn) -> None:
    """SQLite-only lightweight auto-migration, run unconditionally on every
    startup. Alembic (``alembic.ini`` / ``migrations/``) exists in this repo
    for explicit, versioned, reviewable schema changes — use it for anything
    beyond "add a column" — but nothing invokes ``alembic upgrade head``
    automatically, so a machine that boots the app straight from a fresh
    clone or an older on-disk agrismart.db (the project's "zero setup"
    philosophy: no required manual migration step) would otherwise 500 on
    every request touching a table that gained a column since. create_all()
    only creates *missing tables* — it never alters one that already exists.
    Confirmed against this repo's own on-disk dev database, not hypothetical.

    This and Alembic don't conflict: Alembic's own bookkeeping table isn't
    part of Base.metadata, so this function never touches it, and whichever
    of the two adds a column first, the other just sees it already there.

    Handles the two shapes every column added here so far has had: a
    nullable column with no default, or a NOT NULL column with a plain
    scalar Python-side default (mapped_column(default=...), translated into
    the ALTER's DEFAULT clause so existing rows get a real value instead of
    the ALTER failing outright). A column needing anything more — a
    callable default, a NOT NULL column with neither — is logged and
    skipped rather than risking a destructive ALTER on someone's real data;
    that needs a real (Alembic) migration.
    """
    inspector = inspect(conn)
    existing_tables = set(inspector.get_table_names())
    dialect = conn.engine.dialect
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue  # brand new table — create_all() above already made it whole
        existing_cols = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing_cols:
                continue
            col_type = column.type.compile(dialect=dialect)
            ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}'
            if not column.nullable:
                default = column.default
                if column.server_default is not None:
                    pass  # has its own DDL-level default already, ADD COLUMN as-is
                elif default is not None and getattr(default, "is_scalar", False):
                    ddl += f" NOT NULL DEFAULT {_sql_literal(default.arg)}"
                else:
                    log.warning(
                        "Not auto-adding %s.%s: NOT NULL with no simple scalar "
                        "default — write a real migration for it.",
                        table.name, column.name,
                    )
                    continue
            conn.execute(text(ddl))
            log.info("Auto-migrated %s: added column %s (%s)", table.name, column.name, col_type)


async def init_db() -> None:
    """Create tables, then add any columns a model gained since. Called on
    FastAPI startup."""
    from . import models  # noqa: F401  (ensure ORM models are imported/registered)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yields a session, rolls back on error, always closes."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
