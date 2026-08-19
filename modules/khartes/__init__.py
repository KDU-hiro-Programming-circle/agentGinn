"""Khartes module entrypoint (scaffold only -- disabled by default in config/modules.json)."""

from __future__ import annotations

from discord.ext import commands as discord_commands

from shared.logger import get_logger

from .commands import KhartesCog

logger = get_logger(__name__)

MODULE_NAME = "khartes"


async def setup(bot: discord_commands.Bot) -> None:
    await bot.add_cog(KhartesCog(bot))
    logger.info("khartes module set up (scaffold)")


async def teardown(bot: discord_commands.Bot) -> None:
    await bot.remove_cog("KhartesCog")
    logger.info("khartes module torn down")
