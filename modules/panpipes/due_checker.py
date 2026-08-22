"""Daily scheduled job: mentions borrowers whose books are overdue.

Book data is scoped per guild, so this loops over every guild the bot is
currently in and notifies each one's own configured channel.
"""

from __future__ import annotations

import discord

from shared.config import config as config_store
from shared.logger import get_logger

from . import service

logger = get_logger(__name__)


async def run(bot: discord.Client) -> None:
    panpipes_cfg = config_store.load("panpipes")
    channel_ids = panpipes_cfg.get("library_channel_id", {})

    for guild in bot.guilds:
        guild_id = str(guild.id)
        channel_id = channel_ids.get(guild_id)
        channel = bot.get_channel(channel_id) if channel_id else None

        overdue = await service.check_overdue(guild_id)
        for borrow, book in overdue:
            message = f"<@{borrow.borrower_id}> 『{book.title}』の返却期限（{borrow.due_at}）を過ぎています。"
            if channel is not None:
                await channel.send(message)
            else:
                logger.warning(
                    "panpipes: library_channel_id not configured for guild %s; overdue notice not sent: %s",
                    guild_id,
                    message,
                )
