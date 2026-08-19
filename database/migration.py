"""Applies database/schema.py to the configured SQLite database.

Idempotent: safe to call on every bootstrap run.
"""

from __future__ import annotations

from database.schema import STATEMENTS
from shared.database import database


async def apply_schema() -> None:
    async with database.connect() as conn:
        for statement in STATEMENTS:
            await conn.execute(statement)
