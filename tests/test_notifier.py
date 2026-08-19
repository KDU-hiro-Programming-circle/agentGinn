"""Covers the alert state-machine requirements from the doc: cooldown
gates only the firing side, recovery is always immediate, OFF still
tracks state, and a restart (simulated by clearing in-memory state
while keeping the DB) must not re-send a stale alert."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from modules.sesami import models, notifier


class FakeChannel:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def send(self, content: str) -> None:
        self.messages.append(content)


class FakeBot:
    def __init__(self, channel: FakeChannel) -> None:
        self._channel = channel

    def get_channel(self, channel_id: int):
        return self._channel


def _sesami_config(*, enabled: bool = True, cooldown_minutes: int = 60) -> dict:
    return {
        "alert": {
            "enabled": enabled,
            "channel_id": 12345,
            "cooldown_minutes": cooldown_minutes,
            "thresholds": {"temperature_c": 28, "co2_ppm": 1000, "cpu_temperature_c": 80},
        }
    }


@pytest.mark.asyncio
async def test_first_breach_sends_alert_and_sets_active(temp_db):
    channel = FakeChannel()
    bot = FakeBot(channel)

    with patch("modules.sesami.notifier.config_store.load", return_value=_sesami_config()):
        await notifier.evaluate(bot, temperature_c=30, co2_ppm=None, cpu_temperature_c=None)

    assert len(channel.messages) == 1
    assert "気温" in channel.messages[0]

    state = await models.get_alert_state()
    assert state["temperature_active"] == 1
    assert state["temperature_last_alert_at"] is not None


@pytest.mark.asyncio
async def test_repeated_breach_within_cooldown_does_not_resend(temp_db):
    channel = FakeChannel()
    bot = FakeBot(channel)
    cfg = _sesami_config()

    with patch("modules.sesami.notifier.config_store.load", return_value=cfg):
        await notifier.evaluate(bot, temperature_c=30, co2_ppm=None, cpu_temperature_c=None)
        await notifier.evaluate(bot, temperature_c=31, co2_ppm=None, cpu_temperature_c=None)

    assert len(channel.messages) == 1


@pytest.mark.asyncio
async def test_recovery_sends_immediately_regardless_of_cooldown(temp_db):
    channel = FakeChannel()
    bot = FakeBot(channel)
    cfg = _sesami_config()

    with patch("modules.sesami.notifier.config_store.load", return_value=cfg):
        await notifier.evaluate(bot, temperature_c=30, co2_ppm=None, cpu_temperature_c=None)
        await notifier.evaluate(bot, temperature_c=20, co2_ppm=None, cpu_temperature_c=None)

    assert len(channel.messages) == 2
    assert "正常範囲に戻りました" in channel.messages[1]

    state = await models.get_alert_state()
    assert state["temperature_active"] == 0


@pytest.mark.asyncio
async def test_off_suppresses_messages_but_still_tracks_state(temp_db):
    channel = FakeChannel()
    bot = FakeBot(channel)
    cfg = _sesami_config(enabled=False)

    with patch("modules.sesami.notifier.config_store.load", return_value=cfg):
        await notifier.evaluate(bot, temperature_c=30, co2_ppm=None, cpu_temperature_c=None)

    assert channel.messages == []
    state = await models.get_alert_state()
    assert state["temperature_active"] == 1


@pytest.mark.asyncio
async def test_restart_restores_state_and_does_not_resend(temp_db):
    channel = FakeChannel()
    bot = FakeBot(channel)
    cfg = _sesami_config()

    with patch("modules.sesami.notifier.config_store.load", return_value=cfg):
        await notifier.evaluate(bot, temperature_c=30, co2_ppm=None, cpu_temperature_c=None)

    channel.messages.clear()  # simulate a restart: in-memory state is gone, DB state remains

    with patch("modules.sesami.notifier.config_store.load", return_value=cfg):
        await notifier.evaluate(bot, temperature_c=30, co2_ppm=None, cpu_temperature_c=None)

    assert channel.messages == []
