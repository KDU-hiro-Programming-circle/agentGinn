"""Load/save helpers for the JSON files under config/.

This is the only place that reads or writes config/*.json directly;
modules go through here so writes (e.g. Module Manager toggling
modules.json, Sesami's alert on/off writing back to sesami.json) are
consistent and easy to find.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared.utils import next_numbered_key

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"

DEFAULT_SENSOR_TEMPERATURE_C = 28
DEFAULT_SENSOR_CO2_PPM = 1000
DEFAULT_SENSOR_COOLDOWN_MINUTES = 60


def _path(name: str) -> Path:
    return CONFIG_DIR / f"{name}.json"


def load(name: str) -> dict[str, Any]:
    with _path(name).open("r", encoding="utf-8") as f:
        return json.load(f)


def save(name: str, data: dict[str, Any]) -> None:
    with _path(name).open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def set_module_enabled(module_name: str, enabled: bool) -> dict[str, Any]:
    data = load("modules")
    if module_name not in data["modules"]:
        raise KeyError(f"unknown module: {module_name}")
    data["modules"][module_name]["enabled"] = enabled
    save("modules", data)
    return data


def set_sesami_alert_enabled(enabled: bool) -> dict[str, Any]:
    data = load("sesami")
    data["alert"]["enabled"] = enabled
    save("sesami", data)
    return data


def add_sesami_sensor(
    device_id: str,
    name: str | None = None,
    *,
    temperature_c: float | None = None,
    co2_ppm: float | None = None,
    cooldown_minutes: int | None = None,
) -> str:
    """Register a SwitchBot sensor under an auto-numbered key (monitored_id_N).

    Returns the assigned key.
    """
    data = load("sesami")
    sensors = data.setdefault("sensors", {})
    key = next_numbered_key(sensors.keys(), "monitored_id_")
    sensors[key] = {
        "device_id": device_id,
        "name": name or key,
        "thresholds": {
            "temperature_c": DEFAULT_SENSOR_TEMPERATURE_C if temperature_c is None else temperature_c,
            "co2_ppm": DEFAULT_SENSOR_CO2_PPM if co2_ppm is None else co2_ppm,
        },
        "cooldown_minutes": DEFAULT_SENSOR_COOLDOWN_MINUTES if cooldown_minutes is None else cooldown_minutes,
    }
    save("sesami", data)
    return key


def remove_sesami_sensor(key: str) -> None:
    data = load("sesami")
    sensors = data.get("sensors", {})
    if key not in sensors:
        raise KeyError(f"unknown sesami sensor: {key}")
    del sensors[key]
    save("sesami", data)


def set_sesami_aircon(device_id: str, name: str | None = None) -> None:
    """Register the clubroom's SwitchBot virtual air conditioner remote.
    Unlike sensors there's only ever one, so this replaces the existing
    entry rather than being keyed/numbered."""
    data = load("sesami")
    data["aircon"] = {"device_id": device_id, "name": name or "エアコン"}
    save("sesami", data)
