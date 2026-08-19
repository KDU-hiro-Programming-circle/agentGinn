"""Core /system commands: module list/enable/disable.

Always loaded (not a toggleable module itself). Owns the full
enable/disable sequence the handoff doc requires: modules.json write,
command tree re-sync, scheduler job unregister, and web router
unregister.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from shared import permissions
from shared.config import config as config_store
from shared.logger import get_logger

if TYPE_CHECKING:
    from bot import AgentGinnBot

logger = get_logger(__name__)

MODULE_NAMES = ("sesami", "panpipes", "abacus", "khartes")


class SystemCog(commands.Cog):
    def __init__(self, bot: "AgentGinnBot") -> None:
        self.bot = bot

    system_group = app_commands.Group(name="system", description="Bot管理コマンド")
    module_group = app_commands.Group(name="module", description="モジュール管理", parent=system_group)

    @module_group.command(name="list", description="モジュールの有効/無効状態を表示")
    @permissions.require("system")
    async def module_list(self, interaction: discord.Interaction) -> None:
        modules_config = config_store.load("modules")["modules"]
        lines = []
        for name in MODULE_NAMES:
            entry = modules_config.get(name, {})
            state = "有効" if entry.get("enabled") else "無効"
            loaded = "loaded" if name in self.bot.loaded_modules else "unloaded"
            lines.append(f"- **{name}**: {state} ({loaded})")
        await interaction.response.send_message("\n".join(lines))

    @module_group.command(name="enable", description="モジュールを有効化")
    @app_commands.choices(
        module=[app_commands.Choice(name=name, value=name) for name in MODULE_NAMES]
    )
    @permissions.require("system")
    async def module_enable(self, interaction: discord.Interaction, module: str) -> None:
        await interaction.response.defer(thinking=True)
        config_store.set_module_enabled(module, True)
        await self.bot.load_module(module)
        await self.bot.sync_commands()
        await interaction.followup.send(f"モジュール `{module}` を有効化しました。")

    @module_group.command(name="disable", description="モジュールを無効化")
    @app_commands.choices(
        module=[app_commands.Choice(name=name, value=name) for name in MODULE_NAMES]
    )
    @permissions.require("system")
    async def module_disable(self, interaction: discord.Interaction, module: str) -> None:
        await interaction.response.defer(thinking=True)
        config_store.set_module_enabled(module, False)
        await self.bot.unload_module(module)
        await self.bot.sync_commands()
        await interaction.followup.send(f"モジュール `{module}` を無効化しました。")
