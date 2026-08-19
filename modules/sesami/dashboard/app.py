"""Sesami dashboard FastAPI router, registered with shared/web.

shared/web binds to 127.0.0.1 only, so there's no auth here by design
(loopback-only, viewed from the display attached to the clubroom PC).
Static assets are served via plain routes (not app.mount) so they get
tagged with the module name and cleanly removed by unregister_router()
when Sesami is disabled.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from ..models import latest_sensor_log, latest_system_log, sensor_log_history, system_log_history

DASHBOARD_DIR = Path(__file__).resolve().parent
STATIC_DIR = DASHBOARD_DIR / "static"
templates = Jinja2Templates(directory=str(DASHBOARD_DIR / "templates"))

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/static/style.css")
async def static_style() -> FileResponse:
    return FileResponse(STATIC_DIR / "style.css", media_type="text/css")


@router.get("/static/script.js")
async def static_script() -> FileResponse:
    return FileResponse(STATIC_DIR / "script.js", media_type="application/javascript")


@router.get("/static/chart.min.js")
async def static_chartjs() -> FileResponse:
    return FileResponse(STATIC_DIR / "chart.min.js", media_type="application/javascript")


@router.get("/api/latest")
async def api_latest() -> dict:
    return {"sensor": await latest_sensor_log(), "system": await latest_system_log()}


@router.get("/api/history")
async def api_history(limit: int = 144) -> dict:
    return {
        "sensor": await sensor_log_history(limit=limit),
        "system": await system_log_history(limit=limit),
    }
