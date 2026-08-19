"""10-minute periodic job: reads SwitchBot meter + system stats and
persists them. Persistence only -- notification is notifier's job,
triggered here right after the readings are written.
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
    device_id = sesami_cfg["alert"].get("monitored_device_id") or ""

    temperature_c = co2_ppm = None
    if device_id:
        client = switchbot.create_client(bot.settings.switchbot_token, bot.settings.switchbot_secret)
        try:
            meter = await client.get_meter(device_id)
        except Exception:
            logger.exception("sesami collector: failed to read SwitchBot meter")
        else:
            temperature_c = meter["temperature_c"]
            co2_ppm = meter["co2_ppm"]
            await models.insert_sensor_log(
                device_id, temperature_c, meter["humidity_pct"], co2_ppm, meter["battery_pct"]
            )
    else:
        logger.warning("sesami collector: no monitored_device_id configured, skipping meter read")

    stats = hw_system.get_system_stats()
    await models.insert_system_log(
        stats["cpu_temperature_c"],
        stats["cpu_usage_pct"],
        stats["memory_usage_pct"],
        stats["disk_usage_pct"],
    )

    await notifier.evaluate(
        bot,
        temperature_c=temperature_c,
        co2_ppm=co2_ppm,
        cpu_temperature_c=stats["cpu_temperature_c"],
    )
