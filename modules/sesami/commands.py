"""Sesami Discord commands: /sesami status|camera|system|aircon|graph|history|alert on|off."""

from __future__ import annotations

import io

import discord
from discord import app_commands
from discord.ext import commands

from shared import permissions
from shared.config import config as config_store
from shared.hardware import system as hw_system
from shared.logger import get_logger

from . import camera as camera_service
from . import models

logger = get_logger(__name__)


class SesamiCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    sesami_group = app_commands.Group(name="sesami", description="部室環境監視")
    alert_group = app_commands.Group(name="alert", description="アラート通知のON/OFF", parent=sesami_group)

    @sesami_group.command(name="status", description="現在の温湿度・CO2の最新値を表示")
    @permissions.require("sesami")
    async def status(self, interaction: discord.Interaction) -> None:
        sensor = await models.latest_sensor_log()
        if sensor is None:
            await interaction.response.send_message("まだデータがありません。")
            return
        embed = discord.Embed(title="Sesami Status", color=discord.Color.blue())
        embed.add_field(name="気温", value=f"{sensor['temperature_c']} ℃")
        embed.add_field(name="湿度", value=f"{sensor['humidity_pct']} %")
        embed.add_field(name="CO2", value=f"{sensor['co2_ppm']} ppm")
        embed.add_field(name="バッテリー", value=f"{sensor['battery_pct']} %")
        embed.set_footer(text=f"記録時刻: {sensor['recorded_at']}")
        await interaction.response.send_message(embed=embed)

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
    @app_commands.describe(count="表示件数（デフォルト10、最大25）")
    @permissions.require("sesami")
    async def history(
        self, interaction: discord.Interaction, count: app_commands.Range[int, 1, 25] = 10
    ) -> None:
        rows = await models.sensor_log_history(limit=count)
        if not rows:
            await interaction.response.send_message("まだデータがありません。")
            return
        lines = [
            f"`{row['recorded_at']}` 気温:{row['temperature_c']}℃ 湿度:{row['humidity_pct']}%"
            f" CO2:{row['co2_ppm']}ppm"
            for row in rows
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
