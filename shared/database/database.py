"""Single connection factory for the whole project.

Every module must go through :func:`connect` instead of calling
``aiosqlite.connect`` directly, so the WAL/busy_timeout/foreign_keys
PRAGMAs and the on-disk path stay centralized in one place.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import AsyncIterator

import aiosqlite

_db_path: Path | None = None
_busy_timeout_ms = 5000


def init(database_path: str | Path) -> None:
    """Set the database path. Must be called once before connect()."""
    global _db_path
    _db_path = Path(database_path)
    _db_path.parent.mkdir(parents=True, exist_ok=True)


def get_path() -> Path:
    if _db_path is None:
        raise RuntimeError("shared.database.database.init() must be called before use")
    return _db_path


@contextlib.asynccontextmanager
async def connect() -> AsyncIterator[aiosqlite.Connection]:
    """Open a connection with the project's standard PRAGMAs applied.

    Commits on clean exit, rolls back on exception.
    """
    path = get_path()
    conn = await aiosqlite.connect(path)
    conn.row_factory = aiosqlite.Row
    try:
        await conn.execute("PRAGMA journal_mode = WAL")
        await conn.execute(f"PRAGMA busy_timeout = {_busy_timeout_ms}")
        await conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
    finally:
        await conn.close()
