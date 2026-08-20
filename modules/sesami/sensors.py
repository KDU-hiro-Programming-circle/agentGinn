"""Sesami SwitchBot sensor registry (config/sesami.json "sensors").

Sensor identity lives in config, not the DB. Entries can be added by hand
via /sesami sensor add, or auto-discovered from the SwitchBot cloud API
(mirrors how modules/sesami/camera.py auto-registers USB cameras from
v4l2) -- either way config_store.add_sesami_sensor()/remove_sesami_sensor()
stay the single source of truth this module reads from.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.config import config as config_store
from shared.hardware import switchbot
from shared.logger import get_logger

logger = get_logger(__name__)

# SwitchBot deviceType strings that expose meter readings (temperature/
# humidity, some also CO2): "Meter", "MeterPlus", "Outdoor Meter",
# "MeterPro", "MeterPro(CO2)". All contain "meter" case-insensitively.
_METER_DEVICE_TYPE_HINT = "meter"


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


async def discover_and_register_sensors(token: str, secret: str) -> list[str]:
    """Auto-register SwitchBot meters not yet in config/sesami.json "sensors".

    Uses the account's actual SwitchBot app device name when available,
    falling back to the auto-numbered key otherwise.
    """
    client = switchbot.create_client(token, secret)
    try:
        devices = await client.list_devices()
    except Exception:
        logger.exception("sesami sensor discovery: failed to list SwitchBot devices")
        return []

    known_device_ids = {s.device_id for s in list_sensors()}
    registered_keys: list[str] = []
    for device in devices:
        device_id = device.get("deviceId")
        device_type = device.get("deviceType", "")
        if not device_id or _METER_DEVICE_TYPE_HINT not in device_type.lower():
            continue
        if device_id in known_device_ids:
            continue
        key = config_store.add_sesami_sensor(device_id, device.get("deviceName") or None)
        known_device_ids.add(device_id)
        registered_keys.append(key)
        logger.info(
            "sesami sensor auto-registered: %s (%s, %s)", key, device.get("deviceName"), device_id
        )
    return registered_keys
