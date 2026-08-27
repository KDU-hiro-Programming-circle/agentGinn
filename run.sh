#!/usr/bin/env bash
# One-shot launcher: sets up the venv if it doesn't exist yet, applies
# config/DB defaults via bootstrap.py (safe to re-run every time), then
# starts the bot. Usage: ./run.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -d venv ]; then
    echo "venv not found -- creating it and installing requirements..."
    python3 -m venv venv
    venv/bin/pip install -q -r requirements.txt
fi

source venv/bin/activate
python3 bootstrap.py
python3 bot.py
