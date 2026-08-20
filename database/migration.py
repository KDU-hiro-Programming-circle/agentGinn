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


async def apply_schema() -> None:
    async with database.connect() as conn:
        await _drop_legacy_sesami_alert_state(conn)
        for statement in STATEMENTS:
            await conn.execute(statement)
