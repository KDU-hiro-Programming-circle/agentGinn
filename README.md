# agentGinn
this is agent for KDU programming circle.

## Setup

```
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python bootstrap.py   # generates .env, applies the DB schema
```

Fill in `DISCORD_TOKEN` / `SWITCHBOT_TOKEN` / `SWITCHBOT_SECRET` in `.env`, then:

```
.venv/Scripts/python bot.py
```

Sesami's dashboard (loopback only) is at `http://127.0.0.1:8420/sesami/` once the bot is running,
port configurable in `config/sesami.json`.

## Tests

```
.venv/Scripts/python -m pytest
```
