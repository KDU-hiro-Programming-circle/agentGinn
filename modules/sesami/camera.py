"""Sesami camera registry (sesami_cameras) on top of shared/hardware/camera.

Startup discovers unregistered USB cameras via v4l2 by-id paths and
registers them automatically, then validates each device_path; a camera
whose path is missing is disabled on its own -- Sesami and the rest of the
bot keep running. The primary key is always the uuid (by-id paths can
collide/swap when identical camera models are plugged in).
"""

from __future__ import annotations

from shared.hardware import camera as hw_camera
from shared.logger import get_logger
from shared.utils import next_numbered_key

from . import models

logger = get_logger(__name__)


async def discover_and_register_cameras() -> list[models.Camera]:
    existing = await models.list_cameras()
    known_paths = {cam.device_path for cam in existing}
    display_names = [cam.display_name for cam in existing]

    registered: list[models.Camera] = []
    for path in hw_camera.list_v4l2_devices():
        device_path = str(path)
        if device_path in known_paths:
            continue
        display_name = next_numbered_key(display_names, "camera_")
        cam = await models.insert_camera(display_name, device_path)
        display_names.append(display_name)
        known_paths.add(device_path)
        registered.append(cam)
        logger.info("sesami camera auto-registered: %s (%s)", display_name, device_path)
    return registered


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
