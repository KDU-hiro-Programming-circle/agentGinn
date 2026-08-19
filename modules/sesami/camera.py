"""Sesami camera registry (sesami_cameras) on top of shared/hardware/camera.

Startup validates each device_path; a camera whose path is missing is
disabled on its own -- Sesami and the rest of the bot keep running.
The primary key is always the uuid (by-id paths can collide/swap when
identical camera models are plugged in).
"""

from __future__ import annotations

from shared.hardware import camera as hw_camera
from shared.logger import get_logger

from . import models

logger = get_logger(__name__)


async def validate_cameras_on_startup() -> None:
    for cam in await models.list_cameras():
        if not cam.enabled:
            continue
        if not hw_camera.device_exists(cam.device_path):
            await models.set_camera_enabled(cam.uuid, False)
            logger.warning(
                "sesami camera '%s' (%s) not found at %s -- disabled",
                cam.display_name,
                cam.uuid,
                cam.device_path,
            )


async def list_enabled_cameras() -> list[models.Camera]:
    return [cam for cam in await models.list_cameras() if cam.enabled]


async def capture(camera: models.Camera) -> bytes:
    return await hw_camera.capture_jpeg(camera.device_path)
