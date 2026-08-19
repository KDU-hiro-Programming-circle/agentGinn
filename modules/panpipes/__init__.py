"""Panpipes module entrypoint: wires the cog and the daily overdue-check job in."""

from __future__ import annotations

from discord.ext import commands as discord_commands

from shared import scheduler
from shared.config import config as config_store
from shared.logger import get_logger

from . import due_checker
from .commands import PanpipesCog

logger = get_logger(__name__)

MODULE_NAME = "panpipes"


async def setup(bot: discord_commands.Bot) -> None:
    await bot.add_cog(PanpipesCog(bot))
    hour = config_store.load("panpipes").get("overdue_check_hour", 9)
    scheduler.register_job(MODULE_NAME, "due_checker", due_checker.run, "cron", hour=hour, args=[bot])
    logger.info("panpipes module set up")


async def teardown(bot: discord_commands.Bot) -> None:
    scheduler.unregister_module(MODULE_NAME)
    await bot.remove_cog("PanpipesCog")
    logger.info("panpipes module torn down")
