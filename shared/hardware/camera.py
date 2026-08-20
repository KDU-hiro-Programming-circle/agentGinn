"""USB camera capture. The only place that touches cv2/VideoCapture.

Frames are returned as JPEG bytes and never written to disk -- callers
(Sesami) send them to Discord and discard them. A per-device-path lock
prevents the Collector and a `/sesami camera` command from opening the
same device concurrently.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

_locks: dict[str, asyncio.Lock] = {}


class CameraCaptureError(Exception):
    pass


def device_exists(device_path: str) -> bool:
    return Path(device_path).exists()


def list_v4l2_devices() -> list[Path]:
    """Stable-path USB camera capture nodes under /dev/v4l/by-id/.

    By-id symlinks survive replugging (unlike /dev/videoN, whose index can
    shift), which is why Sesami registers cameras by this path. A camera
    exposing multiple V4L2 nodes (e.g. a separate metadata node) lists one
    by-id entry per node ending in "-indexN"; only "-index0" (the actual
    video capture stream) is returned so it isn't registered twice.
    Returns an empty list on platforms without /dev/v4l (e.g. Windows dev
    machines) instead of raising.
    """
    by_id_dir = Path("/dev/v4l/by-id")
    if not by_id_dir.is_dir():
        return []
    return sorted(p for p in by_id_dir.iterdir() if p.name.endswith("-index0"))


def _get_lock(device_path: str) -> asyncio.Lock:
    lock = _locks.get(device_path)
    if lock is None:
        lock = asyncio.Lock()
        _locks[device_path] = lock
    return lock


def _capture_jpeg_sync(device_path: str) -> bytes:
    import cv2  # lazy import: opencv isn't required unless a camera is used

    cap = cv2.VideoCapture(device_path)
    try:
        if not cap.isOpened():
            raise CameraCaptureError(f"could not open camera device: {device_path}")
        ok, frame = cap.read()
        if not ok:
            raise CameraCaptureError(f"could not read frame from camera device: {device_path}")
        ok, buf = cv2.imencode(".jpg", frame)
        if not ok:
            raise CameraCaptureError("failed to encode captured frame as JPEG")
        return buf.tobytes()
    finally:
        cap.release()


async def capture_jpeg(device_path: str) -> bytes:
    async with _get_lock(device_path):
        return await asyncio.to_thread(_capture_jpeg_sync, device_path)
