"""Owns the single FastAPI app and uvicorn.Server lifecycle.

Runs in the same asyncio loop as discord.py (started as a task from
bot.py), so there is exactly one process writing to SQLite. Modules
only ever call register_router()/unregister_router() -- they never
touch uvicorn directly.
"""

from __future__ import annotations

import asyncio

import uvicorn
from fastapi import APIRouter, FastAPI

from shared.logger import get_logger

logger = get_logger(__name__)

app = FastAPI()

_registered_modules: set[str] = set()
_server: uvicorn.Server | None = None
_server_task: asyncio.Task | None = None


def register_router(module: str, router: APIRouter, prefix: str = "") -> None:
    app.include_router(router, prefix=prefix, tags=[module])
    _registered_modules.add(module)
    logger.info("web: registered router for %s", module)


def unregister_router(module: str) -> None:
    app.router.routes = [
        route for route in app.router.routes if module not in (getattr(route, "tags", None) or [])
    ]
    _registered_modules.discard(module)
    logger.info("web: unregistered router for %s", module)


def has_routers() -> bool:
    return bool(_registered_modules)


def is_running() -> bool:
    return _server is not None


async def start(host: str = "127.0.0.1", port: int = 8420) -> None:
    global _server, _server_task
    if _server is not None:
        return
    if not has_routers():
        logger.info("web: no routers registered, not starting server")
        return
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    _server = uvicorn.Server(config)
    _server_task = asyncio.create_task(_server.serve())
    logger.info("web: dashboard listening on http://%s:%s", host, port)


async def stop() -> None:
    global _server, _server_task
    if _server is None:
        return
    _server.should_exit = True
    if _server_task is not None:
        await _server_task
    _server = None
    _server_task = None
    logger.info("web: server stopped")
