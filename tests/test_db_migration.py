"""SQLite auto-migration (app.backend.db._add_missing_columns).

There's no Alembic here — create_all() only creates *missing tables*, it
never alters one that already exists. These tests build a deliberately
"old" schema (missing columns that were added to the ORM models later,
mirroring Plot.main_crop / Plot.soil_status / Diagnosis.crop_warning) on a
throwaway SQLite file, then confirm the auto-migration brings it up to date
without touching existing rows or breaking on a second run.

Uses its own temp-file engine — never the shared app engine/Base.metadata
that the other fixtures reset per test, so this can't interfere with them.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.backend.db import Base, _add_missing_columns
from app.backend.models.orm import Diagnosis, Plot

pytestmark = pytest.mark.asyncio

_TMP = Path(__file__).resolve().parent / "_tmp"


@pytest.fixture
async def old_schema_engine():
    """A SQLite file with 'plots' and 'diagnoses' tables built by hand,
    deliberately missing the columns added after those tables first shipped."""
    _TMP.mkdir(exist_ok=True)
    db_path = _TMP / f"migrate_{uuid.uuid4().hex}.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}", future=True)

    async with engine.begin() as conn:
        await conn.execute(text(
            "CREATE TABLE plots ("
            " id VARCHAR(32) PRIMARY KEY, owner_id VARCHAR(32), name VARCHAR(120),"
            " lat FLOAT, lon FLOAT, area_ha FLOAT, soil_snapshot JSON,"
            " soil_fetched_at DATETIME, created_at DATETIME"
            ")"  # missing: main_crop, soil_status
        ))
        await conn.execute(text(
            "CREATE TABLE diagnoses ("
            " id VARCHAR(32) PRIMARY KEY, owner_id VARCHAR(32), plot_id VARCHAR(32),"
            " planting_id VARCHAR(32), image_path VARCHAR(255), gradcam_path VARCHAR(255),"
            " predicted_class VARCHAR(120), confidence FLOAT, abstained BOOLEAN,"
            " precautions JSON, model_version VARCHAR(60), created_at DATETIME"
            ")"  # missing: crop_warning
        ))
        await conn.execute(text(
            "INSERT INTO plots (id, owner_id, name, lat, lon) VALUES "
            "('p1', 'u1', 'Old field', 22.3, 73.1)"
        ))

    try:
        yield engine
    finally:
        await engine.dispose()
        db_path.unlink(missing_ok=True)


async def _columns(engine, table: str) -> dict[str, dict]:
    async with engine.begin() as conn:
        return await conn.run_sync(
            lambda sync_conn: {c["name"]: c for c in inspect(sync_conn).get_columns(table)}
        )


async def test_migration_adds_missing_columns(old_schema_engine):
    before = await _columns(old_schema_engine, "plots")
    assert "main_crop" not in before and "soil_status" not in before

    async with old_schema_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # no-op for plots/diagnoses (already exist)
        await conn.run_sync(_add_missing_columns)

    after_plots = await _columns(old_schema_engine, "plots")
    after_diag = await _columns(old_schema_engine, "diagnoses")
    assert "main_crop" in after_plots
    assert "soil_status" in after_plots
    assert "crop_warning" in after_diag
    # every other table Plot.__table__ etc. didn't have yet gets created outright
    async with old_schema_engine.begin() as conn:
        tables = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
    assert {"plantings", "irrigation_events", "farmer_actions"} <= tables


async def test_migration_backfills_not_null_default_for_existing_rows(old_schema_engine):
    """Plot.soil_status is NOT NULL with default='pending' — an existing row
    (created before the column existed) must get a real value, not a failed
    ALTER or a NULL that then trips the NOT NULL constraint."""
    async with old_schema_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)

    async with old_schema_engine.begin() as conn:
        row = (await conn.execute(text("SELECT soil_status, main_crop FROM plots WHERE id='p1'"))).one()
    assert row.soil_status == "pending"
    assert row.main_crop is None


async def test_migration_is_idempotent(old_schema_engine):
    """Running it twice (e.g. two app restarts) must not raise — SQLite has
    no 'ADD COLUMN IF NOT EXISTS', so this relies on the existing-columns check."""
    async with old_schema_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)
    async with old_schema_engine.begin() as conn:
        await conn.run_sync(_add_missing_columns)  # must not raise "duplicate column"

    after = await _columns(old_schema_engine, "plots")
    assert "soil_status" in after


async def test_new_row_after_migration_uses_orm_defaults(old_schema_engine):
    """End-to-end: after migrating, the ORM can insert/read through the
    newly-added columns exactly like a table that had them from the start."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    async with old_schema_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)

    Session = async_sessionmaker(old_schema_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        plot = Plot(owner_id="u1", name="New field", lat=1.0, lon=2.0)
        session.add(plot)
        await session.commit()
        await session.refresh(plot)
        assert plot.soil_status == "pending"
        assert plot.main_crop is None

        diag = Diagnosis(owner_id="u1", plot_id=plot.id, image_path="x.jpg",
                          predicted_class="Tomato___healthy", confidence=0.9, abstained=False)
        session.add(diag)
        await session.commit()
        await session.refresh(diag)
        assert diag.crop_warning is None
