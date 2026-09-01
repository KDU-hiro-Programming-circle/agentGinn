"""Sesami air conditioner control via a SwitchBot Hub's virtual infrared
remote (deviceType "Air Conditioner"). Device identity lives in config,
auto-discovered from the SwitchBot cloud API the same way sensors are
(see modules/sesami/sensors.py) -- config_store.set_sesami_aircon() stays
the single source of truth this module reads from. Unlike sensors, a
clubroom only ever has one A/C unit, so this is a single entry rather
than a numbered collection.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.config import config as config_store
from shared.hardware import switchbot
from shared.logger import get_logger

from . import models

logger = get_logger(__name__)

_AIRCON_DEVICE_TYPE = "Air Conditioner"

# SwitchBot's setAll command numeric codes.
MODES: dict[str, int] = {"auto": 1, "cool": 2, "dry": 3, "fan": 4, "heat": 5}
FAN_SPEEDS: dict[str, int] = {"auto": 1, "low": 2, "medium": 3, "high": 4}

MODE_LABELS: dict[str, str] = {"auto": "自動", "cool": "冷房", "dry": "除湿", "fan": "送風", "heat": "暖房"}
FAN_SPEED_LABELS: dict[str, str] = {"auto": "自動", "low": "弱", "medium": "中", "high": "強"}

DEFAULT_TEMPERATURE = 26
DEFAULT_MODE = "cool"
DEFAULT_FAN_SPEED = "auto"


@dataclass
class Aircon:
    device_id: str
    name: str


def get_aircon() -> Aircon | None:
    cfg = config_store.load("sesami").get("aircon", {})
    device_id = cfg.get("device_id") or ""
    if not device_id:
        return None
    return Aircon(device_id=device_id, name=cfg.get("name") or "エアコン")


async def discover_and_register_aircon(token: str, secret: str) -> str | None:
    """Auto-register the clubroom's SwitchBot virtual A/C remote, if one
    exists in the account and none is registered yet. A manually-set
    device_id is never overwritten. Returns the device name if newly
    registered, else None."""
    if get_aircon() is not None:
        return None

    client = switchbot.create_client(token, secret)
    try:
        devices = await client.list_devices()
    except Exception:
        logger.exception("sesami aircon discovery: failed to list SwitchBot devices")
        return None

    aircon_device = next((d for d in devices if d.get("deviceType") == _AIRCON_DEVICE_TYPE), None)
    if aircon_device is None:
        return None

    device_id = aircon_device.get("deviceId")
    if not device_id:
        return None
    name = aircon_device.get("deviceName") or "エアコン"

    config_store.set_sesami_aircon(device_id, name)
    logger.info("sesami aircon auto-registered: %s (%s)", name, device_id)
    return name


async def set_power(
    client: switchbot.MeterClient,
    aircon: Aircon,
    *,
    power: str,
    temperature: int,
    mode: str,
    fan_speed: str,
    source: str,
) -> None:
    await client.send_aircon_command(
        aircon.device_id,
        temperature=temperature,
        mode=MODES[mode],
        fan_speed=FAN_SPEEDS[fan_speed],
        power=power,
    )
    action = f"on({temperature}c,{mode},{fan_speed})" if power == "on" else "off"
    await models.insert_aircon_log(action, source)
