# Sesami

部室環境監視モジュール。SwitchBot Meter Pro(CO2)とホストのシステム状態を10分毎に収集し、
閾値超過時にDiscord通知します。カメラ撮影とローカル限定のダッシュボードも提供します。

## システム依存

- カメラ撮影（`/sesami camera`, `/sesami tomocore`）には `ffmpeg` が必要です: `sudo apt install ffmpeg`
- `/sesami tomocore` の文字描画には日本語フォントが必要です: `sudo apt install fonts-noto-cjk`
