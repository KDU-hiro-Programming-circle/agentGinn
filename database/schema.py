"""CREATE TABLE statements for every table in the project.

Applied idempotently (``CREATE TABLE IF NOT EXISTS``) by migration.py.
"""

from __future__ import annotations

STATEMENTS: list[str] = [
    # ---- Sesami -----------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS sesami_devices (
        device_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        kind TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sesami_cameras (
        uuid TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        location TEXT,
        device_path TEXT NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sesami_sensor_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT NOT NULL,
        temperature_c REAL,
        humidity_pct REAL,
        co2_ppm REAL,
        battery_pct REAL,
        recorded_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_sesami_sensor_log_recorded_at
        ON sesami_sensor_log (recorded_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS sesami_system_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cpu_temperature_c REAL,
        cpu_usage_pct REAL,
        memory_usage_pct REAL,
        disk_usage_pct REAL,
        recorded_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_sesami_system_log_recorded_at
        ON sesami_system_log (recorded_at)
    """,
    # Singleton row (id = 1). last_alert_at columns persist cooldown
    # across restarts; active columns persist state-machine state so
    # OFF-mode tracking survives a restart too.
    """
    CREATE TABLE IF NOT EXISTS sesami_alert_state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        enabled INTEGER NOT NULL DEFAULT 1,
        temperature_active INTEGER NOT NULL DEFAULT 0,
        temperature_last_alert_at TEXT,
        co2_active INTEGER NOT NULL DEFAULT 0,
        co2_last_alert_at TEXT,
        cpu_temperature_active INTEGER NOT NULL DEFAULT 0,
        cpu_temperature_last_alert_at TEXT,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sesami_aircon_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT NOT NULL,
        source TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    # ---- Panpipes -----------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS panpipes_books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        isbn TEXT UNIQUE,
        title TEXT NOT NULL,
        author TEXT,
        publisher TEXT,
        thumbnail_url TEXT,
        registered_by TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS panpipes_borrow (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER NOT NULL REFERENCES panpipes_books(id),
        borrower_id TEXT NOT NULL,
        borrowed_at TEXT NOT NULL,
        due_at TEXT NOT NULL,
        returned_at TEXT,
        overdue_notified INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_panpipes_borrow_open
        ON panpipes_borrow (book_id, returned_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS panpipes_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER NOT NULL REFERENCES panpipes_books(id),
        event_type TEXT NOT NULL,
        actor_id TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    # ---- Abacus (schema only; module is a scaffold) --------------------
    """
    CREATE TABLE IF NOT EXISTS abacus_income (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount INTEGER NOT NULL,
        description TEXT,
        recorded_by TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS abacus_expense (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount INTEGER NOT NULL,
        description TEXT,
        recorded_by TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS abacus_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        amount INTEGER,
        description TEXT,
        actor_id TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    # ---- Khartes (schema only; module is a scaffold) -------------------
    """
    CREATE TABLE IF NOT EXISTS khartes_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        requested_by TEXT NOT NULL,
        template TEXT,
        created_at TEXT NOT NULL
    )
    """,
]
