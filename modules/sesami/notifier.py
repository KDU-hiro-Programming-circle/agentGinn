"""Sesami threshold alert state machine.

Cooldown gates only the "goes into alert" transition, keyed per
(sensor_key, metric) by last_alert_at (persisted in sesami_alert_state so
a restart doesn't reset it -- state is always restored from the DB before
the first comparison, so a stale active alert is never re-sent on
startup). Recovery notifications are never gated by cooldown -- they fire
the moment the reading drops back under the threshold. When alerting is
OFF, transitions still update sesami_alert_state (tracking continues) but
no Discord message is sent.

Each call evaluates a single metric for a single sensor -- collector.py
loops over configured sensors (temperature/co2) plus the fixed "system"
sensor_key (cpu_temperature), each with its own threshold/cooldown.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import discord

from shared.logger import get_logger
from shared.utils import utcnow_iso

from . import models

logger = get_logger(__name__)


def _parse_iso(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


async def evaluate(
    bot: discord.Client,
    *,
    sensor_key: str,
    label: str,
    metric: str,
    value: float | None,
    threshold: float | None,
    unit: str,
    cooldown_minutes: int,
    channel_id: int | None,
    alert_enabled: bool,
) -> None:
    if value is None or threshold is None:
        return

    cooldown = timedelta(minutes=cooldown_minutes)
    state = await models.get_alert_state(sensor_key, metric)
    now = datetime.now(timezone.utc)

    previous_active = bool(state["active"])
    last_alert_at = _parse_iso(state["last_alert_at"])
    over_threshold = value >= threshold

    if over_threshold and not previous_active:
        cooldown_ok = last_alert_at is None or (now - last_alert_at) >= cooldown
        new_last_alert_at = state["last_alert_at"]
        if cooldown_ok and alert_enabled:
            await _send(bot, channel_id, label, value, unit, is_recovery=False)
            new_last_alert_at = utcnow_iso()
        await models.update_alert_metric(sensor_key, metric, active=True, last_alert_at=new_last_alert_at)

    elif not over_threshold and previous_active:
        if alert_enabled:
            await _send(bot, channel_id, label, value, unit, is_recovery=True)
        await models.update_alert_metric(
            sensor_key, metric, active=False, last_alert_at=state["last_alert_at"]
        )


async def _send(
    bot: discord.Client, channel_id: int | None, label: str, value: float, unit: str, *, is_recovery: bool
) -> None:
    if not channel_id:
        logger.warning("sesami alert channel_id not configured; skipping notification")
        return
    channel = bot.get_channel(channel_id)
    if channel is None:
        logger.warning("sesami alert channel %s not found", channel_id)
        return
    if is_recovery:
        message = f":white_check_mark: {label}が正常範囲に戻りました（現在値: {value}{unit}）"
    else:
        message = f":warning: {label}が閾値を超えました（現在値: {value}{unit}）"
    await channel.send(message)
