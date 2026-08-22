"""Sesami dashboard FastAPI router, registered with shared/web.

shared/web binds to 127.0.0.1 only, so there's no auth here by design
(loopback-only, viewed from the display attached to the clubroom PC).
Static assets are served via plain routes (not app.mount) so they get
tagged with the module name and cleanly removed by unregister_router()
when Sesami is disabled.
"""

from __future__ import annotations

from pathlib import Path

import jinja2
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from .. import sensors as sensor_service
from ..models import latest_sensor_log, latest_system_log, sensor_log_history, system_log_history

DASHBOARD_DIR = Path(__file__).resolve().parent
STATIC_DIR = DASHBOARD_DIR / "static"
# Built manually (rather than Jinja2Templates(directory=...)) so cache_size=0
# can be set: on some Jinja2/Python version combinations (seen on Python
# 3.14) the template LRUCache's cache-key hashing raises `TypeError: cannot
# use 'tuple' as a dict key (unhashable type: 'dict')`. The dashboard has
# one template and is loopback-only/low-traffic, so skipping the cache
# entirely has no meaningful cost.
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(DASHBOARD_DIR / "templates")),
    autoescape=jinja2.select_autoescape(),
    cache_size=0,
)
templates = Jinja2Templates(env=_jinja_env)

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html")


@router.get("/static/style.css")
async def static_style() -> FileResponse:
    return FileResponse(STATIC_DIR / "style.css", media_type="text/css")


@router.get("/static/script.js")
async def static_script() -> FileResponse:
    return FileResponse(STATIC_DIR / "script.js", media_type="application/javascript")


@router.get("/static/chart.min.js")
async def static_chartjs() -> FileResponse:
    return FileResponse(STATIC_DIR / "chart.min.js", media_type="application/javascript")


@router.get("/api/sensors")
async def api_sensors() -> list[dict]:
    """Registered sensors, so the dashboard can render one section per
    sensor -- sensor count isn't fixed, it grows as more are registered."""
    return [{"key": s.key, "name": s.name} for s in sensor_service.list_sensors()]


@router.get("/api/latest")
async def api_latest() -> dict:
    sensors = {s.key: await latest_sensor_log(device_id=s.device_id) for s in sensor_service.list_sensors()}
    return {"sensors": sensors, "system": await latest_system_log()}


@router.get("/api/history")
async def api_history(limit: int = 144) -> dict:
    sensors = {
        s.key: await sensor_log_history(device_id=s.device_id, limit=limit)
        for s in sensor_service.list_sensors()
    }
    return {"sensors": sensors, "system": await system_log_history(limit=limit)}
