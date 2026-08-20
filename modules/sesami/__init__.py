"""Sesami module entrypoint: wires the cog, collector job, and dashboard router in."""

from __future__ import annotations

from discord.ext import commands as discord_commands

from shared import scheduler, web
from shared.config import config as config_store
from shared.logger import get_logger

from . import camera as camera_service
from . import collector
from . import sensors as sensor_service
from .commands import SesamiCog
from .dashboard.app import router as dashboard_router

logger = get_logger(__name__)

MODULE_NAME = "sesami"


async def setup(bot: discord_commands.Bot) -> None:
    await sensor_service.discover_and_register_sensors(bot.settings.switchbot_token, bot.settings.switchbot_secret)
    await camera_service.discover_and_register_cameras()
    await camera_service.validate_cameras_on_startup()

    await bot.add_cog(SesamiCog(bot))

    sesami_cfg = config_store.load("sesami")
    interval = sesami_cfg.get("collector_interval_minutes", 10)
    scheduler.register_job(MODULE_NAME, "collector", collector.run, "interval", minutes=interval, args=[bot])

    if sesami_cfg["dashboard"].get("enabled", False):
        web.register_router(MODULE_NAME, dashboard_router, prefix="/sesami")

    logger.info("sesami module set up")


async def teardown(bot: discord_commands.Bot) -> None:
    scheduler.unregister_module(MODULE_NAME)
    web.unregister_router(MODULE_NAME)
    await bot.remove_cog("SesamiCog")
    logger.info("sesami module torn down")
