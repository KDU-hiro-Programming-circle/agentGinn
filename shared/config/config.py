"""Load/save helpers for the JSON files under config/.

This is the only place that reads or writes config/*.json directly;
modules go through here so writes (e.g. Module Manager toggling
modules.json, Sesami's alert on/off writing back to sesami.json) are
consistent and easy to find.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _path(name: str) -> Path:
    return CONFIG_DIR / f"{name}.json"


def load(name: str) -> dict[str, Any]:
    with _path(name).open("r", encoding="utf-8") as f:
        return json.load(f)


def save(name: str, data: dict[str, Any]) -> None:
    with _path(name).open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def set_module_enabled(module_name: str, enabled: bool) -> dict[str, Any]:
    data = load("modules")
    if module_name not in data["modules"]:
        raise KeyError(f"unknown module: {module_name}")
    data["modules"][module_name]["enabled"] = enabled
    save("modules", data)
    return data


def set_sesami_alert_enabled(enabled: bool) -> dict[str, Any]:
    data = load("sesami")
    data["alert"]["enabled"] = enabled
    save("sesami", data)
    return data
