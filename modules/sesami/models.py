"""Data access for sesami_* tables. All Sesami SQL lives here."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from shared.database import database
from shared.utils import utcnow_iso

ALERT_METRICS = ("temperature", "co2", "cpu_temperature")


@dataclass
class Camera:
    uuid: str
    display_name: str
    location: str | None
    device_path: str
    enabled: bool


# ---- Sensor / system logs (written by Collector) ------------------------


async def insert_sensor_log(
    device_id: str,
    temperature_c: float | None,
    humidity_pct: float | None,
    co2_ppm: float | None,
    battery_pct: float | None,
) -> None:
    async with database.connect() as conn:
        await conn.execute(
            """
            INSERT INTO sesami_sensor_log
                (device_id, temperature_c, humidity_pct, co2_ppm, battery_pct, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (device_id, temperature_c, humidity_pct, co2_ppm, battery_pct, utcnow_iso()),
        )


async def insert_system_log(
    cpu_temperature_c: float | None,
    cpu_usage_pct: float | None,
    memory_usage_pct: float | None,
    disk_usage_pct: float | None,
) -> None:
    async with database.connect() as conn:
        await conn.execute(
            """
            INSERT INTO sesami_system_log
                (cpu_temperature_c, cpu_usage_pct, memory_usage_pct, disk_usage_pct, recorded_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (cpu_temperature_c, cpu_usage_pct, memory_usage_pct, disk_usage_pct, utcnow_iso()),
        )


async def latest_sensor_log() -> dict[str, Any] | None:
    async with database.connect() as conn:
        cur = await conn.execute("SELECT * FROM sesami_sensor_log ORDER BY id DESC LIMIT 1")
        row = await cur.fetchone()
        return dict(row) if row else None


async def latest_system_log() -> dict[str, Any] | None:
    async with database.connect() as conn:
        cur = await conn.execute("SELECT * FROM sesami_system_log ORDER BY id DESC LIMIT 1")
        row = await cur.fetchone()
        return dict(row) if row else None


async def sensor_log_history(limit: int = 144) -> list[dict[str, Any]]:
    async with database.connect() as conn:
        cur = await conn.execute("SELECT * FROM sesami_sensor_log ORDER BY id DESC LIMIT ?", (limit,))
        rows = await cur.fetchall()
        return [dict(row) for row in reversed(rows)]


async def system_log_history(limit: int = 144) -> list[dict[str, Any]]:
    async with database.connect() as conn:
        cur = await conn.execute("SELECT * FROM sesami_system_log ORDER BY id DESC LIMIT ?", (limit,))
        rows = await cur.fetchall()
        return [dict(row) for row in reversed(rows)]


# ---- Cameras --------------------------------------------------------------


async def list_cameras() -> list[Camera]:
    async with database.connect() as conn:
        cur = await conn.execute("SELECT * FROM sesami_cameras ORDER BY display_name")
        rows = await cur.fetchall()
        return [
            Camera(
                uuid=row["uuid"],
                display_name=row["display_name"],
                location=row["location"],
                device_path=row["device_path"],
                enabled=bool(row["enabled"]),
            )
            for row in rows
        ]


async def set_camera_enabled(uuid: str, enabled: bool) -> None:
    async with database.connect() as conn:
        await conn.execute("UPDATE sesami_cameras SET enabled = ? WHERE uuid = ?", (int(enabled), uuid))


# ---- Alert state (singleton row, id = 1) -----------------------------------


async def get_alert_state() -> dict[str, Any]:
    async with database.connect() as conn:
        cur = await conn.execute("SELECT * FROM sesami_alert_state WHERE id = 1")
        row = await cur.fetchone()
        if row is not None:
            return dict(row)
        await conn.execute(
            "INSERT INTO sesami_alert_state (id, enabled, updated_at) VALUES (1, 1, ?)",
            (utcnow_iso(),),
        )
        cur = await conn.execute("SELECT * FROM sesami_alert_state WHERE id = 1")
        row = await cur.fetchone()
        return dict(row)


async def update_alert_metric(metric: str, *, active: bool, last_alert_at: str | None) -> None:
    if metric not in ALERT_METRICS:
        raise ValueError(f"unknown alert metric: {metric}")
    async with database.connect() as conn:
        await conn.execute(
            f"""
            UPDATE sesami_alert_state
            SET {metric}_active = ?, {metric}_last_alert_at = ?, updated_at = ?
            WHERE id = 1
            """,
            (int(active), last_alert_at, utcnow_iso()),
        )
