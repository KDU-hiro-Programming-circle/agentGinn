"""SwitchBot OpenAPI v1.1 client (HMAC-SHA256 request signing).

This is the only place that talks to the SwitchBot cloud API. If no
token/secret is configured (e.g. local dev without real hardware),
create_client() returns a mock so the rest of Sesami keeps working.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
import uuid
from typing import Any, Protocol

import httpx

from shared.logger import get_logger

logger = get_logger(__name__)

BASE_URL = "https://api.switch-bot.com/v1.1"


class SwitchBotError(Exception):
    pass


class MeterClient(Protocol):
    async def get_meter(self, device_id: str) -> dict[str, float | None]: ...
    async def list_devices(self) -> list[dict[str, Any]]: ...
    async def send_aircon_command(
        self, device_id: str, *, temperature: int, mode: int, fan_speed: int, power: str
    ) -> None: ...


class SwitchBotClient:
    def __init__(self, token: str, secret: str, timeout: float = 10.0) -> None:
        self._token = token
        self._secret = secret
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        t = str(int(time.time() * 1000))
        nonce = str(uuid.uuid4())
        string_to_sign = f"{self._token}{t}{nonce}".encode("utf-8")
        sign = base64.b64encode(
            hmac.new(self._secret.encode("utf-8"), string_to_sign, hashlib.sha256).digest()
        ).decode("utf-8")
        return {
            "Authorization": self._token,
            "t": t,
            "sign": sign,
            "nonce": nonce,
            "Content-Type": "application/json; charset=utf8",
        }

    async def get_device_status(self, device_id: str) -> dict[str, Any]:
        url = f"{BASE_URL}/devices/{device_id}/status"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, headers=self._headers())
        resp.raise_for_status()
        body = resp.json()
        if body.get("statusCode") != 100:
            raise SwitchBotError(f"SwitchBot API error: {body}")
        return body["body"]

    async def get_meter(self, device_id: str) -> dict[str, float | None]:
        status = await self.get_device_status(device_id)
        co2 = status.get("CO2")
        return {
            "temperature_c": float(status["temperature"]) if "temperature" in status else None,
            "humidity_pct": float(status["humidity"]) if "humidity" in status else None,
            "co2_ppm": float(co2) if co2 is not None else None,
            "battery_pct": float(status["battery"]) if "battery" in status else None,
        }

    async def list_devices(self) -> list[dict[str, Any]]:
        url = f"{BASE_URL}/devices"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, headers=self._headers())
        resp.raise_for_status()
        body = resp.json()
        if body.get("statusCode") != 100:
            raise SwitchBotError(f"SwitchBot API error: {body}")
        return body["body"].get("deviceList", [])

    async def send_aircon_command(
        self, device_id: str, *, temperature: int, mode: int, fan_speed: int, power: str
    ) -> None:
        """Send a "setAll" command to a virtual infrared-remote air
        conditioner device (deviceType "Air Conditioner"). mode/fan_speed
        are SwitchBot's numeric codes (see modules/sesami/aircon.py)."""
        url = f"{BASE_URL}/devices/{device_id}/commands"
        payload = {
            "commandType": "command",
            "command": "setAll",
            "parameter": f"{temperature},{mode},{fan_speed},{power}",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, headers=self._headers(), json=payload)
        resp.raise_for_status()
        body = resp.json()
        if body.get("statusCode") != 100:
            raise SwitchBotError(f"SwitchBot API error: {body}")


class MockMeterClient:
    """Returned when SwitchBot credentials aren't configured (local dev)."""

    async def get_meter(self, device_id: str) -> dict[str, float | None]:
        logger.warning("SwitchBot credentials not configured; returning mock meter reading")
        return {"temperature_c": 25.0, "humidity_pct": 50.0, "co2_ppm": 600.0, "battery_pct": 100.0}

    async def list_devices(self) -> list[dict[str, Any]]:
        logger.warning("SwitchBot credentials not configured; skipping sensor auto-discovery")
        return []

    async def send_aircon_command(
        self, device_id: str, *, temperature: int, mode: int, fan_speed: int, power: str
    ) -> None:
        logger.warning("SwitchBot credentials not configured; aircon command not sent")


def create_client(token: str, secret: str) -> MeterClient:
    if not token or not secret:
        return MockMeterClient()
    return SwitchBotClient(token, secret)
