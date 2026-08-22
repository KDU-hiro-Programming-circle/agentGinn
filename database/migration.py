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
    """One-time migration: panpipes_books gained a guild_id column and its
    ISBN uniqueness constraint moved from global to per-guild (SQLite
    requires recreating the table to change a UNIQUE constraint). Confirmed
    empty in practice at migration time; panpipes_borrow/panpipes_history
    are untouched since their schema didn't change.
    """
    cur = await conn.execute("PRAGMA table_info(panpipes_books)")
    columns = {row["name"] async for row in cur}
    if columns and "guild_id" not in columns:
        await conn.execute("DROP TABLE panpipes_books")


async def apply_schema() -> None:
    async with database.connect() as conn:
        await _drop_legacy_sesami_alert_state(conn)
        await _drop_legacy_panpipes_books(conn)
        for statement in STATEMENTS:
            await conn.execute(statement)
