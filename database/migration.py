"""Applies database/schema.py to the configured SQLite database.

Idempotent: safe to call on every bootstrap run.
"""

from __future__ import annotations

from database.schema import STATEMENTS
from shared.database import database


async def _drop_legacy_sesami_alert_state(conn) -> None:
    """One-time migration: the old sesami_alert_state was a singleton row
    (id=1) with one column set per metric. It's being replaced by a row per
    (sensor_key, metric) to support multiple sensors. Only alert tracking
    state is lost (not sensor history), and it's recreated fresh on the
    next collector run.
    """
    cur = await conn.execute("PRAGMA table_info(sesami_alert_state)")
    columns = {row["name"] async for row in cur}
    if "temperature_active" in columns:
        await conn.execute("DROP TABLE sesami_alert_state")


async def _drop_legacy_panpipes_books(conn) -> None:
    """One-time migration: panpipes_books briefly gained a guild_id column
    (per-guild book catalogs) before that was reverted back to a single
    shared catalog per bot deployment. If a DB already picked up the
    guild_id shape, rebuild it back to the original. Confirmed OK to reset
    (no real data in either shape yet). panpipes_borrow/panpipes_history
    reference panpipes_books via foreign key, and with PRAGMA foreign_keys
    = ON, DROP TABLE does an implicit delete-check against child rows -- so
    any leftover borrow/history rows must be cleared first or the DROP
    itself fails with a FOREIGN KEY constraint error.
    """
    cur = await conn.execute("PRAGMA table_info(panpipes_books)")
    columns = {row["name"] async for row in cur}
    if "guild_id" in columns:
        await conn.execute("DELETE FROM panpipes_history")
        await conn.execute("DELETE FROM panpipes_borrow")
        await conn.execute("DROP TABLE panpipes_books")


async def apply_schema() -> None:
    async with database.connect() as conn:
        await _drop_legacy_sesami_alert_state(conn)
        await _drop_legacy_panpipes_books(conn)
        for statement in STATEMENTS:
            await conn.execute(statement)
