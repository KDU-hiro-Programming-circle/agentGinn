"""Host system stats (CPU/memory/disk/temperature) via psutil."""

from __future__ import annotations

import os

import psutil


def get_cpu_temperature_c() -> float | None:
    sensors_fn = getattr(psutil, "sensors_temperatures", None)
    if sensors_fn is None:
        return None
    sensors = sensors_fn()
    for name in ("cpu_thermal", "coretemp", "k10temp"):
        entries = sensors.get(name)
        if entries:
            return entries[0].current
    for entries in sensors.values():
        if entries:
            return entries[0].current
    return None


def get_system_stats() -> dict[str, float | None]:
    disk_path = os.path.abspath(os.sep)
    return {
        "cpu_temperature_c": get_cpu_temperature_c(),
        "cpu_usage_pct": psutil.cpu_percent(interval=None),
        "memory_usage_pct": psutil.virtual_memory().percent,
        "disk_usage_pct": psutil.disk_usage(disk_path).percent,
    }
