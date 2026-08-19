"""Khartes scaffold -- not implemented yet."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from shared import permissions


class KhartesCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    khartes_group = app_commands.Group(name="khartes", description="名刺作成（未実装）")

    @khartes_group.command(name="create", description="名刺作成は未実装です")
    @permissions.require("khartes")
    async def create(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("Khartes はまだ実装されていません。")
