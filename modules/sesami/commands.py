"""Sesami Discord commands: /sesami status|camera|system|aircon|graph|history|
sensor add|remove|list|alert on|off."""

from __future__ import annotations

import io

import discord
from discord import app_commands
from discord.ext import commands

from shared import permissions
from shared.config import config as config_store
from shared.hardware import switchbot
from shared.hardware import system as hw_system
from shared.logger import get_logger

from . import camera as camera_service
from . import models
from . import sensors as sensor_service

logger = get_logger(__name__)


class SesamiCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    sesami_group = app_commands.Group(name="sesami", description="部室環境監視")
    alert_group = app_commands.Group(name="alert", description="アラート通知のON/OFF", parent=sesami_group)
    sensor_group = app_commands.Group(name="sensor", description="SwitchBotセンサーの登録管理", parent=sesami_group)

    async def _sensor_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=f"{s.name} ({s.key})", value=s.key)
            for s in sensor_service.list_sensors()
            if current.lower() in s.name.lower() or current.lower() in s.key.lower()
        ][:25]

    @sesami_group.command(name="status", description="SwitchBotから現在の温湿度・CO2をその場で取得して表示")
    @app_commands.describe(sensor="表示するセンサー（省略時は登録済み全センサー）")
    @permissions.require("sesami")
    async def status(self, interaction: discord.Interaction, sensor: str | None = None) -> None:
        all_sensors = sensor_service.list_sensors()
        if not all_sensors:
            await interaction.response.send_message(
                "登録されているセンサーがありません。`/sesami sensor add` で登録してください。"
            )
            return

        if sensor is not None:
            target = sensor_service.resolve_sensor(sensor)
            if target is None:
                await interaction.response.send_message(f"センサー `{sensor}` が見つかりません。")
                return
            targets = [target]
        else:
            targets = all_sensors

        # Reads SwitchBot live, at command time -- independent of the 10-
        # minute collector job and not written to sesami_sensor_log.
        await interaction.response.defer(thinking=True)
        client = switchbot.create_client(self.bot.settings.switchbot_token, self.bot.settings.switchbot_secret)

        lines = []
        for target in targets:
            try:
                meter = await client.get_meter(target.device_id)
            except Exception:
                logger.exception("sesami status: failed to read SwitchBot meter for %s", target.key)
                lines.append(f"**{target.name}**: 取得に失敗しました。")
                continue
            lines.append(
                f"**{target.name}**: 気温:{meter['temperature_c']}℃ 湿度:{meter['humidity_pct']}% "
                f"CO2:{meter['co2_ppm']}ppm バッテリー:{meter['battery_pct']}%"
            )
        await interaction.followup.send("\n".join(lines))

    @status.autocomplete("sensor")
    async def status_sensor_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._sensor_autocomplete(interaction, current)

    @sesami_group.command(name="system", description="部室PCのシステム状態をリアルタイム表示")
    @permissions.require("sesami")
    async def system(self, interaction: discord.Interaction) -> None:
        stats = hw_system.get_system_stats()
        cpu_temp = f"{stats['cpu_temperature_c']} ℃" if stats["cpu_temperature_c"] is not None else "N/A"
        embed = discord.Embed(title="System Status", color=discord.Color.green())
        embed.add_field(name="CPU使用率", value=f"{stats['cpu_usage_pct']} %")
        embed.add_field(name="CPU温度", value=cpu_temp)
        embed.add_field(name="メモリ使用率", value=f"{stats['memory_usage_pct']} %")
        embed.add_field(name="ディスク使用率", value=f"{stats['disk_usage_pct']} %")
        await interaction.response.send_message(embed=embed)

    @sesami_group.command(name="camera", description="部室のカメラで撮影して送信")
    @app_commands.describe(camera="カメラ名（省略時は先頭のカメラ）")
    @permissions.require("sesami")
    async def camera_command(self, interaction: discord.Interaction, camera: str | None = None) -> None:
        await interaction.response.defer(thinking=True)
        cameras = await camera_service.list_enabled_cameras()
        if not cameras:
            await interaction.followup.send("カメラが登録されていません。")
            return

        target = cameras[0]
        if camera is not None:
            matched = next((c for c in cameras if c.display_name == camera or c.uuid == camera), None)
            if matched is None:
                await interaction.followup.send(f"カメラ `{camera}` が見つかりません。")
                return
            target = matched

        try:
            jpeg_bytes = await camera_service.capture(target)
        except Exception:
            logger.exception("sesami camera capture failed: %s", target.uuid)
            await interaction.followup.send(f"カメラ `{target.display_name}` の撮影に失敗しました。")
            return

        file = discord.File(io.BytesIO(jpeg_bytes), filename="camera.jpg")
        await interaction.followup.send(content=f"\U0001f4f7 {target.display_name}", file=file)

    @camera_command.autocomplete("camera")
    async def camera_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        cameras = await camera_service.list_enabled_cameras()
        return [
            app_commands.Choice(name=c.display_name, value=c.display_name)
            for c in cameras
            if current.lower() in c.display_name.lower()
        ][:25]

    @sesami_group.command(name="aircon", description="エアコン制御（将来実装予定）")
    @permissions.require("sesami")
    async def aircon(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("エアコン自動制御は将来実装予定の機能です。")

    @sesami_group.command(name="graph", description="ダッシュボードの案内を表示")
    @permissions.require("sesami")
    async def graph(self, interaction: discord.Interaction) -> None:
        dashboard_cfg = config_store.load("sesami")["dashboard"]
        if not dashboard_cfg.get("enabled"):
            await interaction.response.send_message("ダッシュボードは無効化されています。")
            return
        port = dashboard_cfg.get("port", 8420)
        await interaction.response.send_message(
            f"ダッシュボードは部室のディスプレイから http://127.0.0.1:{port}/sesami/ で確認できます"
            "（ループバック限定で外部からはアクセスできません）。"
        )

    @sesami_group.command(name="history", description="直近の環境データ履歴を表示")
    @app_commands.describe(sensor="対象センサー（省略時は登録済み全センサーをまとめて表示）", count="表示件数（デフォルト10、最大25）")
    @permissions.require("sesami")
    async def history(
        self,
        interaction: discord.Interaction,
        sensor: str | None = None,
        count: app_commands.Range[int, 1, 25] = 10,
    ) -> None:
        all_sensors = sensor_service.list_sensors()
        if not all_sensors:
            await interaction.response.send_message(
                "登録されているセンサーがありません。`/sesami sensor add` で登録してください。"
            )
            return

        if sensor is not None:
            target = sensor_service.resolve_sensor(sensor)
            if target is None:
                await interaction.response.send_message(f"センサー `{sensor}` が見つかりません。")
                return
            name_by_device = {target.device_id: target.name}
            rows = await models.sensor_log_history(device_id=target.device_id, limit=count)
        else:
            name_by_device = {s.device_id: s.name for s in all_sensors}
            merged: list = []
            for s in all_sensors:
                merged.extend(await models.sensor_log_history(device_id=s.device_id, limit=count))
            rows = sorted(merged, key=lambda row: row["recorded_at"])[-count:]

        if not rows:
            await interaction.response.send_message("まだデータがありません。")
            return

        lines = [
            f"`{row['recorded_at']}` [{name_by_device.get(row['device_id'], row['device_id'])}]"
            f" 気温:{row['temperature_c']}℃ 湿度:{row['humidity_pct']}% CO2:{row['co2_ppm']}ppm"
            for row in rows
        ]
        await interaction.response.send_message("\n".join(lines))

    @history.autocomplete("sensor")
    async def history_sensor_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._sensor_autocomplete(interaction, current)

    @sensor_group.command(name="add", description="SwitchBotセンサーを登録")
    @app_commands.describe(
        device_id="SwitchBotのデバイスID",
        name="表示名（省略時は自動採番されたID）",
        temperature_threshold="気温アラートの閾値 ℃（省略時28）",
        co2_threshold="CO2アラートの閾値 ppm（省略時1000）",
        cooldown_minutes="アラート再送クールダウン 分（省略時60）",
    )
    @permissions.require("sesami")
    async def sensor_add(
        self,
        interaction: discord.Interaction,
        device_id: str,
        name: str | None = None,
        temperature_threshold: float | None = None,
        co2_threshold: float | None = None,
        cooldown_minutes: app_commands.Range[int, 1, 1440] | None = None,
    ) -> None:
        key = config_store.add_sesami_sensor(
            device_id,
            name,
            temperature_c=temperature_threshold,
            co2_ppm=co2_threshold,
            cooldown_minutes=cooldown_minutes,
        )
        await interaction.response.send_message(f"センサー `{key}` を登録しました。")

    @sensor_group.command(name="remove", description="登録済みSwitchBotセンサーを削除")
    @app_commands.describe(sensor="削除するセンサー")
    @permissions.require("sesami")
    async def sensor_remove(self, interaction: discord.Interaction, sensor: str) -> None:
        target = sensor_service.resolve_sensor(sensor)
        key = target.key if target is not None else sensor
        try:
            config_store.remove_sesami_sensor(key)
        except KeyError:
            await interaction.response.send_message(f"センサー `{sensor}` が見つかりません。")
            return
        await interaction.response.send_message(f"センサー `{key}` を削除しました。")

    @sensor_remove.autocomplete("sensor")
    async def sensor_remove_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._sensor_autocomplete(interaction, current)

    @sensor_group.command(name="list", description="登録済みSwitchBotセンサーの一覧を表示")
    @permissions.require("sesami")
    async def sensor_list(self, interaction: discord.Interaction) -> None:
        all_sensors = sensor_service.list_sensors()
        if not all_sensors:
            await interaction.response.send_message("登録されているセンサーがありません。")
            return
        lines = [
            f"`{s.key}` {s.name} (device_id: {s.device_id}) "
            f"気温閾値:{s.temperature_c}℃ CO2閾値:{s.co2_ppm}ppm クールダウン:{s.cooldown_minutes}分"
            for s in all_sensors
        ]
        await interaction.response.send_message("\n".join(lines))

    @alert_group.command(name="on", description="環境アラート通知をONにする")
    @permissions.require("sesami")
    async def alert_on(self, interaction: discord.Interaction) -> None:
        config_store.set_sesami_alert_enabled(True)
        await interaction.response.send_message("アラート通知をONにしました。")

    @alert_group.command(name="off", description="環境アラート通知をOFFにする")
    @permissions.require("sesami")
    async def alert_off(self, interaction: discord.Interaction) -> None:
        config_store.set_sesami_alert_enabled(False)
        await interaction.response.send_message("アラート通知をOFFにしました（状態の追跡は継続されます）。")
