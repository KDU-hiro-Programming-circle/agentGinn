"""Loads .env into a small typed Settings object.

Not to be confused with shared/config/config.py, which handles the
JSON files under config/ (module toggles, thresholds, etc).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    discord_token: str
    guild_id: int | None
    switchbot_token: str
    switchbot_secret: str
    database_path: str


def load_settings(env_path: str | Path | None = None) -> Settings:
    load_dotenv(env_path or PROJECT_ROOT / ".env")

    guild_id_raw = os.getenv("GUILD_ID", "").strip()

    return Settings(
        discord_token=os.getenv("DISCORD_TOKEN", "").strip(),
        guild_id=int(guild_id_raw) if guild_id_raw else None,
        switchbot_token=os.getenv("SWITCHBOT_TOKEN", "").strip(),
        switchbot_secret=os.getenv("SWITCHBOT_SECRET", "").strip(),
        database_path=os.getenv("DATABASE_PATH", "database/agentginn.db").strip(),
    )
