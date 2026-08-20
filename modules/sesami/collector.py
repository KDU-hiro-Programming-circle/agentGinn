"""10-minute periodic job: reads every configured SwitchBot meter + system
stats and persists them. Persistence only -- notification is notifier's
job, triggered here right after each reading is written.
"""

from __future__ import annotations

import discord

from shared.config import config as config_store
from shared.hardware import switchbot
from shared.hardware import system as hw_system
from shared.logger import get_logger

from . import models, notifier

logger = get_logger(__name__)


async def run(bot: discord.Client) -> None:
    sesami_cfg = config_store.load("sesami")
    sensors = sesami_cfg.get("sensors", {})
    alert_cfg = sesami_cfg["alert"]
    alert_enabled: bool = alert_cfg["enabled"]
    channel_id = alert_cfg.get("channel_id")

    if not sensors:
        logger.warning("sesami collector: no sensors configured, skipping meter read")
    else:
        client = switchbot.create_client(bot.settings.switchbot_token, bot.settings.switchbot_secret)
        for sensor_key, sensor_cfg in sensors.items():
            device_id = sensor_cfg.get("device_id") or ""
            if not device_id:
                continue
            try:
                meter = await client.get_meter(device_id)
            except Exception:
                logger.exception("sesami collector: failed to read SwitchBot meter for %s", sensor_key)
                continue

            await models.insert_sensor_log(
                device_id, meter["temperature_c"], meter["humidity_pct"], meter["co2_ppm"], meter["battery_pct"]
            )

            name = sensor_cfg.get("name", sensor_key)
            thresholds = sensor_cfg.get("thresholds", {})
            cooldown_minutes = sensor_cfg.get("cooldown_minutes", 60)
            await notifier.evaluate(
                bot,
                sensor_key=sensor_key,
                label=f"{name} 気温",
                metric="temperature",
                value=meter["temperature_c"],
                threshold=thresholds.get("temperature_c"),
                unit="℃",
                cooldown_minutes=cooldown_minutes,
                channel_id=channel_id,
                alert_enabled=alert_enabled,
            )
            await notifier.evaluate(
                bot,
                sensor_key=sensor_key,
                label=f"{name} CO2濃度",
                metric="co2",
                value=meter["co2_ppm"],
                threshold=thresholds.get("co2_ppm"),
                unit="ppm",
                cooldown_minutes=cooldown_minutes,
                channel_id=channel_id,
                alert_enabled=alert_enabled,
            )

    stats = hw_system.get_system_stats()
    await models.insert_system_log(
        stats["cpu_temperature_c"],
        stats["cpu_usage_pct"],
        stats["memory_usage_pct"],
        stats["disk_usage_pct"],
    )

    cpu_cfg = alert_cfg.get("cpu_temperature", {})
    await notifier.evaluate(
        bot,
        sensor_key="system",
        label="CPU温度",
        metric="cpu_temperature",
        value=stats["cpu_temperature_c"],
        threshold=cpu_cfg.get("threshold_c"),
        unit="℃",
        cooldown_minutes=cpu_cfg.get("cooldown_minutes", 60),
        channel_id=channel_id,
        alert_enabled=alert_enabled,
    )
