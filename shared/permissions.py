"""Role-based command permission checks, backed by config/permissions.json."""

from __future__ import annotations

import discord
from discord import app_commands

from shared.config import config as config_store
from shared.logger import get_logger

logger = get_logger(__name__)


def _user_role_names(member: discord.Member) -> set[str]:
    return {role.name for role in member.roles}


def has_permission(member: discord.Member, group: str) -> bool:
    perms = config_store.load("permissions")
    admin_roles = set(perms.get("admin_roles", []))
    allowed_roles = set(perms.get("command_roles", {}).get(group, []))
    user_roles = _user_role_names(member)
    return bool(user_roles & admin_roles) or bool(user_roles & allowed_roles)


def require(group: str):
    """app_commands check decorator: @permissions.require("sesami")."""

    def predicate(interaction: discord.Interaction) -> bool:
        member = interaction.user
        if not isinstance(member, discord.Member):
            return False
        allowed = has_permission(member, group)
        if not allowed:
            logger.info("permission denied: user=%s group=%s", member.id, group)
        return allowed

    return app_commands.check(predicate)
