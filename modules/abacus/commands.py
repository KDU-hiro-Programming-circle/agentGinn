"""Abacus scaffold -- not implemented yet."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from shared import permissions


class AbacusCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    abacus_group = app_commands.Group(name="abacus", description="部費管理（未実装）")

    @abacus_group.command(name="status", description="部費管理は未実装です")
    @permissions.require("abacus")
    async def status(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("Abacus はまだ実装されていません。")
