"""Data access for sesami_* tables. All Sesami SQL lives here."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from shared.database import database
from shared.utils import utcnow_iso


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


async def latest_sensor_log(device_id: str | None = None) -> dict[str, Any] | None:
    async with database.connect() as conn:
        if device_id is None:
            cur = await conn.execute("SELECT * FROM sesami_sensor_log ORDER BY id DESC LIMIT 1")
        else:
            cur = await conn.execute(
                "SELECT * FROM sesami_sensor_log WHERE device_id = ? ORDER BY id DESC LIMIT 1",
                (device_id,),
            )
        row = await cur.fetchone()
        return dict(row) if row else None


async def latest_system_log() -> dict[str, Any] | None:
    async with database.connect() as conn:
        cur = await conn.execute("SELECT * FROM sesami_system_log ORDER BY id DESC LIMIT 1")
        row = await cur.fetchone()
        return dict(row) if row else None


async def sensor_log_history(device_id: str | None = None, limit: int = 144) -> list[dict[str, Any]]:
    async with database.connect() as conn:
        if device_id is None:
            cur = await conn.execute("SELECT * FROM sesami_sensor_log ORDER BY id DESC LIMIT ?", (limit,))
        else:
            cur = await conn.execute(
                "SELECT * FROM sesami_sensor_log WHERE device_id = ? ORDER BY id DESC LIMIT ?",
                (device_id, limit),
            )
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


async def insert_camera(display_name: str, device_path: str, location: str | None = None) -> Camera:
    cam_uuid = str(uuid.uuid4())
    async with database.connect() as conn:
        await conn.execute(
            """
            INSERT INTO sesami_cameras (uuid, display_name, location, device_path, enabled, created_at)
            VALUES (?, ?, ?, ?, 1, ?)
            """,
            (cam_uuid, display_name, location, device_path, utcnow_iso()),
        )
    return Camera(uuid=cam_uuid, display_name=display_name, location=location, device_path=device_path, enabled=True)


# ---- Alert state (one row per sensor_key + metric) -------------------------


async def get_alert_state(sensor_key: str, metric: str) -> dict[str, Any]:
    async with database.connect() as conn:
        cur = await conn.execute(
            "SELECT * FROM sesami_alert_state WHERE sensor_key = ? AND metric = ?", (sensor_key, metric)
        )
        row = await cur.fetchone()
        if row is not None:
            return dict(row)
        await conn.execute(
            "INSERT INTO sesami_alert_state (sensor_key, metric, active, updated_at) VALUES (?, ?, 0, ?)",
            (sensor_key, metric, utcnow_iso()),
        )
        cur = await conn.execute(
            "SELECT * FROM sesami_alert_state WHERE sensor_key = ? AND metric = ?", (sensor_key, metric)
        )
        row = await cur.fetchone()
        return dict(row)


async def update_alert_metric(
    sensor_key: str, metric: str, *, active: bool, last_alert_at: str | None
) -> None:
    async with database.connect() as conn:
        await conn.execute(
            """
            UPDATE sesami_alert_state
            SET active = ?, last_alert_at = ?, updated_at = ?
            WHERE sensor_key = ? AND metric = ?
            """,
            (int(active), last_alert_at, utcnow_iso(), sensor_key, metric),
        )
