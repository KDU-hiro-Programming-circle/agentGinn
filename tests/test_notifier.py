"""Covers the alert state-machine requirements from the doc: cooldown
gates only the firing side, recovery is always immediate, OFF still
tracks state, and a restart (simulated by clearing in-memory state
while keeping the DB) must not re-send a stale alert."""

from __future__ import annotations

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


async def _evaluate(bot, *, value: float | None, enabled: bool = True, cooldown_minutes: int = 60):
    await notifier.evaluate(
        bot,
        sensor_key="monitored_id_1",
        label="気温",
        metric="temperature",
        value=value,
        threshold=28,
        unit="℃",
        cooldown_minutes=cooldown_minutes,
        channel_id=12345,
        alert_enabled=enabled,
    )


@pytest.mark.asyncio
async def test_first_breach_sends_alert_and_sets_active(temp_db):
    channel = FakeChannel()
    bot = FakeBot(channel)

    await _evaluate(bot, value=30)

    assert len(channel.messages) == 1
    assert "気温" in channel.messages[0]

    state = await models.get_alert_state("monitored_id_1", "temperature")
    assert state["active"] == 1
    assert state["last_alert_at"] is not None


@pytest.mark.asyncio
async def test_repeated_breach_within_cooldown_does_not_resend(temp_db):
    channel = FakeChannel()
    bot = FakeBot(channel)

    await _evaluate(bot, value=30)
    await _evaluate(bot, value=31)

    assert len(channel.messages) == 1


@pytest.mark.asyncio
async def test_recovery_sends_immediately_regardless_of_cooldown(temp_db):
    channel = FakeChannel()
    bot = FakeBot(channel)

    await _evaluate(bot, value=30)
    await _evaluate(bot, value=20)

    assert len(channel.messages) == 2
    assert "正常範囲に戻りました" in channel.messages[1]

    state = await models.get_alert_state("monitored_id_1", "temperature")
    assert state["active"] == 0


@pytest.mark.asyncio
async def test_off_suppresses_messages_but_still_tracks_state(temp_db):
    channel = FakeChannel()
    bot = FakeBot(channel)

    await _evaluate(bot, value=30, enabled=False)

    assert channel.messages == []
    state = await models.get_alert_state("monitored_id_1", "temperature")
    assert state["active"] == 1


@pytest.mark.asyncio
async def test_restart_restores_state_and_does_not_resend(temp_db):
    channel = FakeChannel()
    bot = FakeBot(channel)

    await _evaluate(bot, value=30)

    channel.messages.clear()  # simulate a restart: in-memory state is gone, DB state remains

    await _evaluate(bot, value=30)

    assert channel.messages == []


@pytest.mark.asyncio
async def test_different_sensors_track_state_independently(temp_db):
    channel = FakeChannel()
    bot = FakeBot(channel)

    await notifier.evaluate(
        bot,
        sensor_key="monitored_id_1",
        label="気温1",
        metric="temperature",
        value=30,
        threshold=28,
        unit="℃",
        cooldown_minutes=60,
        channel_id=12345,
        alert_enabled=True,
    )
    await notifier.evaluate(
        bot,
        sensor_key="monitored_id_2",
        label="気温2",
        metric="temperature",
        value=30,
        threshold=28,
        unit="℃",
        cooldown_minutes=60,
        channel_id=12345,
        alert_enabled=True,
    )

    assert len(channel.messages) == 2
    state_1 = await models.get_alert_state("monitored_id_1", "temperature")
    state_2 = await models.get_alert_state("monitored_id_2", "temperature")
    assert state_1["active"] == 1
    assert state_2["active"] == 1
