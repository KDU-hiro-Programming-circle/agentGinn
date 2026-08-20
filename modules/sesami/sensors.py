"""Sesami SwitchBot sensor registry (config/sesami.json "sensors").

Sensor identity lives in config, not the DB -- sensors are registered by
an admin (unlike cameras, which are physically auto-discovered), so
config_store.add_sesami_sensor()/remove_sesami_sensor() stay the single
source of truth this module reads from.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.config import config as config_store


@dataclass
class Sensor:
    key: str
    device_id: str
    name: str
    temperature_c: float | None
    co2_ppm: float | None
    cooldown_minutes: int


def list_sensors() -> list[Sensor]:
    sensors_cfg = config_store.load("sesami").get("sensors", {})
    return [
        Sensor(
            key=key,
            device_id=cfg.get("device_id", ""),
            name=cfg.get("name", key),
            temperature_c=cfg.get("thresholds", {}).get("temperature_c"),
            co2_ppm=cfg.get("thresholds", {}).get("co2_ppm"),
            cooldown_minutes=cfg.get("cooldown_minutes", 60),
        )
        for key, cfg in sensors_cfg.items()
    ]


def resolve_sensor(identifier: str) -> Sensor | None:
    return next((s for s in list_sensors() if identifier in (s.key, s.name)), None)
