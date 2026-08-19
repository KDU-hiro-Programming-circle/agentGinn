"""Sesami threshold alert state machine.

Cooldown gates only the "goes into alert" transition, keyed per metric
by last_alert_at (persisted in sesami_alert_state so a restart doesn't
reset it -- state is always restored from the DB before the first
comparison, so a stale active alert is never re-sent on startup).
Recovery notifications are never gated by cooldown -- they fire the
moment the reading drops back under the threshold. When alerting is
OFF, transitions still update sesami_alert_state (tracking continues)
but no Discord message is sent.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import discord

from shared.config import config as config_store
from shared.logger import get_logger
from shared.utils import utcnow_iso

from . import models

logger = get_logger(__name__)

METRIC_LABELS = {
    "temperature": ("気温", "℃"),
    "co2": ("CO2濃度", "ppm"),
    "cpu_temperature": ("CPU温度", "℃"),
}


def _parse_iso(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


async def evaluate(
    bot: discord.Client,
    *,
    temperature_c: float | None,
    co2_ppm: float | None,
    cpu_temperature_c: float | None,
) -> None:
    sesami_cfg = config_store.load("sesami")
    alert_cfg = sesami_cfg["alert"]
    alert_enabled: bool = alert_cfg["enabled"]
    cooldown = timedelta(minutes=alert_cfg["cooldown_minutes"])
    thresholds = alert_cfg["thresholds"]
    channel_id = alert_cfg.get("channel_id")

    readings = {
        "temperature": (temperature_c, thresholds.get("temperature_c")),
        "co2": (co2_ppm, thresholds.get("co2_ppm")),
        "cpu_temperature": (cpu_temperature_c, thresholds.get("cpu_temperature_c")),
    }

    state = await models.get_alert_state()
    now = datetime.now(timezone.utc)

    for metric, (value, threshold) in readings.items():
        if value is None or threshold is None:
            continue

        previous_active = bool(state[f"{metric}_active"])
        last_alert_at = _parse_iso(state[f"{metric}_last_alert_at"])
        over_threshold = value >= threshold

        if over_threshold and not previous_active:
            cooldown_ok = last_alert_at is None or (now - last_alert_at) >= cooldown
            new_last_alert_at = state[f"{metric}_last_alert_at"]
            if cooldown_ok and alert_enabled:
                await _send(bot, channel_id, metric, value, is_recovery=False)
                new_last_alert_at = utcnow_iso()
            await models.update_alert_metric(metric, active=True, last_alert_at=new_last_alert_at)

        elif not over_threshold and previous_active:
            if alert_enabled:
                await _send(bot, channel_id, metric, value, is_recovery=True)
            await models.update_alert_metric(
                metric, active=False, last_alert_at=state[f"{metric}_last_alert_at"]
            )


async def _send(
    bot: discord.Client, channel_id: int | None, metric: str, value: float, *, is_recovery: bool
) -> None:
    if not channel_id:
        logger.warning("sesami alert channel_id not configured; skipping notification")
        return
    channel = bot.get_channel(channel_id)
    if channel is None:
        logger.warning("sesami alert channel %s not found", channel_id)
        return
    label, unit = METRIC_LABELS[metric]
    if is_recovery:
        message = f":white_check_mark: {label}が正常範囲に戻りました（現在値: {value}{unit}）"
    else:
        message = f":warning: {label}が閾値を超えました（現在値: {value}{unit}）"
    await channel.send(message)
