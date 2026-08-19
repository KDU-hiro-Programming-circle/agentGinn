"""Write-then-reload round trip for the config.json paths the Module
Manager and Sesami's alert on/off command write back to."""

from __future__ import annotations

import json

import pytest

from shared.config import config as config_store


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    modules_json = {
        "modules": {
            "sesami": {"enabled": True, "auto_start": True},
            "panpipes": {"enabled": True, "auto_start": True},
        }
    }
    sesami_json = {"alert": {"enabled": True, "channel_id": 0}}

    (tmp_path / "modules.json").write_text(json.dumps(modules_json), encoding="utf-8")
    (tmp_path / "sesami.json").write_text(json.dumps(sesami_json), encoding="utf-8")

    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path)
    return tmp_path


def test_set_module_enabled_persists(temp_config_dir):
    config_store.set_module_enabled("sesami", False)

    reloaded = config_store.load("modules")
    assert reloaded["modules"]["sesami"]["enabled"] is False
    assert reloaded["modules"]["panpipes"]["enabled"] is True  # untouched


def test_set_module_enabled_unknown_module_raises(temp_config_dir):
    with pytest.raises(KeyError):
        config_store.set_module_enabled("nonexistent", True)


def test_set_sesami_alert_enabled_persists(temp_config_dir):
    config_store.set_sesami_alert_enabled(False)

    reloaded = config_store.load("sesami")
    assert reloaded["alert"]["enabled"] is False
