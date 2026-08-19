"""One-time project setup. Run this once before the first `python bot.py`.

Generates .env from .env.example, recreates any missing config/*.json
defaults, creates logs/ and data/, and applies the database schema.
Not used during normal operation.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"
ENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"
CONFIG_DIR = PROJECT_ROOT / "config"
LOGS_DIR = PROJECT_ROOT / "logs"
DATA_DIR = PROJECT_ROOT / "data"

DEFAULT_CONFIGS: dict[str, dict] = {
    "modules": {
        "modules": {
            "sesami": {"enabled": True, "auto_start": True},
            "panpipes": {"enabled": True, "auto_start": True},
            "abacus": {"enabled": False, "auto_start": False},
            "khartes": {"enabled": False, "auto_start": False},
        }
    },
    "permissions": {
        "admin_roles": ["Admin"],
        "command_roles": {
            "system": ["Admin"],
            "sesami": ["Admin", "Member"],
            "panpipes": ["Admin", "Member"],
            "abacus": ["Admin"],
            "khartes": ["Admin", "Member"],
        },
    },
    "system": {"log_level": "INFO", "timezone": "Asia/Tokyo"},
    "sesami": {
        "collector_interval_minutes": 10,
        "alert": {
            "enabled": True,
            "monitored_device_id": "",
            "channel_id": 0,
            "cooldown_minutes": 60,
            "thresholds": {"temperature_c": 28, "co2_ppm": 1000, "cpu_temperature_c": 80},
        },
        "dashboard": {"enabled": True, "port": 8420},
    },
    "panpipes": {"library_channel_id": 0, "borrow_days": 14, "overdue_check_hour": 9},
    "abacus": {"enabled": False},
    "khartes": {"enabled": False},
}


def ensure_env() -> None:
    if ENV_PATH.exists() and ENV_PATH.stat().st_size > 0:
        return
    if ENV_EXAMPLE_PATH.exists():
        shutil.copyfile(ENV_EXAMPLE_PATH, ENV_PATH)
        print(f"created {ENV_PATH} from .env.example -- fill in your tokens before running bot.py")
    else:
        ENV_PATH.write_text("", encoding="utf-8")


def ensure_config_files() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    for name, default in DEFAULT_CONFIGS.items():
        path = CONFIG_DIR / f"{name}.json"
        if path.exists():
            continue
        with path.open("w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"created {path} with defaults")


def ensure_directories() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _read_database_path() -> str:
    from dotenv import dotenv_values

    values = dotenv_values(ENV_PATH)
    return values.get("DATABASE_PATH") or "database/clubhouse.db"


async def ensure_database() -> None:
    from database.migration import apply_schema
    from shared.database import database

    database.init(_read_database_path())
    await apply_schema()
    print(f"database schema applied at {database.get_path()}")


def main() -> None:
    ensure_env()
    ensure_config_files()
    ensure_directories()
    asyncio.run(ensure_database())
    print("bootstrap complete.")


if __name__ == "__main__":
    main()
