"""Entry point. Loading only: instantiates the bot, loads enabled
modules, starts the scheduler/web server, and owns graceful shutdown.
No business logic lives here -- see modules/* and shared/*.
"""

from __future__ import annotations

import asyncio
import importlib

import discord
from discord.ext import commands

from shared import logger as log
from shared import scheduler, web
from shared.config import config as config_store
from shared.config.settings import Settings, load_settings
from shared.database import database
from shared.system_cog import SystemCog

logger = log.get_logger(__name__)

MODULE_NAMES = ("sesami", "panpipes", "abacus", "khartes")


class AgentGinnBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
        self.settings = settings
        self.loaded_modules: set[str] = set()

    async def setup_hook(self) -> None:
        await self.add_cog(SystemCog(self))

        modules_config = config_store.load("modules")["modules"]
        for name in MODULE_NAMES:
            entry = modules_config.get(name, {})
            if entry.get("enabled") and entry.get("auto_start"):
                await self.load_module(name)

        system_cfg = config_store.load("system")
        scheduler.configure(system_cfg.get("timezone"))
        scheduler.start()
        await self._maybe_start_web()
        await self.sync_commands()

    async def sync_commands(self) -> None:
        if self.settings.guild_id:
            guild = discord.Object(id=self.settings.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()
        logger.info("app commands synced")

    async def load_module(self, name: str) -> None:
        if name in self.loaded_modules:
            return
        module = importlib.import_module(f"modules.{name}")
        await module.setup(self)
        self.loaded_modules.add(name)
        await self._maybe_start_web()
        logger.info("module loaded: %s", name)

    async def unload_module(self, name: str) -> None:
        if name not in self.loaded_modules:
            return
        module = importlib.import_module(f"modules.{name}")
        await module.teardown(self)
        self.loaded_modules.discard(name)
        if not web.has_routers() and web.is_running():
            await web.stop()
        logger.info("module unloaded: %s", name)

    async def _maybe_start_web(self) -> None:
        if web.is_running() or not web.has_routers():
            return
        sesami_cfg = config_store.load("sesami")
        dashboard_cfg = sesami_cfg.get("dashboard", {})
        if dashboard_cfg.get("enabled", False):
            await web.start(port=dashboard_cfg.get("port", 8420))

    async def close(self) -> None:
        await web.stop()
        scheduler.shutdown(wait=False)
        await super().close()


async def main() -> None:
    settings = load_settings()
    system_cfg = config_store.load("system")
    log.setup(level=system_cfg.get("log_level", "INFO"))
    database.init(settings.database_path)

    if not settings.discord_token:
        raise SystemExit("DISCORD_TOKEN is not set. Run bootstrap.py first, then fill in .env.")

    bot = AgentGinnBot(settings)
    async with bot:
        await bot.start(settings.discord_token)


if __name__ == "__main__":
    asyncio.run(main())
