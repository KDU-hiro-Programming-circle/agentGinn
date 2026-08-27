"""USB camera capture. The only place that touches cv2/VideoCapture.

Frames are returned as JPEG bytes and never written to disk -- callers
(Sesami) send them to Discord and discard them. A per-device-path lock
prevents the Collector and a `/sesami camera` command from opening the
same device concurrently.
"""

from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path
from typing import Any

_locks: dict[str, asyncio.Lock] = {}
_OPEN_RETRIES = 3
_OPEN_RETRY_DELAY_S = 1.0
_VIDEO_NODE_RE = re.compile(r"^video(\d+)$")


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


def _video_index(device_path: str) -> int | None:
    """Resolve a /dev/v4l/by-id/... symlink (or a direct /dev/videoN path)
    to its videoN index. opencv-python's V4L2 backend can fail to "capture
    by name" (open by string path) at all on some builds -- WARN VIDEOIO(
    V4L2): backend is generally available but can't be used to capture by
    name -- so callers should prefer opening by this integer index instead.
    """
    match = _VIDEO_NODE_RE.match(Path(device_path).resolve().name)
    return int(match.group(1)) if match else None


def _open_and_read(device_path: str, cv2: Any) -> tuple[bool, Any]:
    # Explicit CAP_V4L2 avoids OpenCV probing other backends (seen falling
    # through to its image-file loader, which obviously can't read a V4L2
    # device node) when a by-id symlink isn't immediately recognized.
    index = _video_index(device_path)
    cap = cv2.VideoCapture(index, cv2.CAP_V4L2) if index is not None else cv2.VideoCapture(device_path, cv2.CAP_V4L2)
    try:
        if not cap.isOpened():
            return False, None
        return cap.read()
    finally:
        cap.release()


def _capture_jpeg_sync(device_path: str) -> bytes:
    import cv2  # lazy import: opencv isn't required unless a camera is used

    # A freshly (re)plugged/booted USB webcam can take a moment before it's
    # actually ready to open/stream, so a transient failure is retried
    # rather than treated as a hard error on the first attempt.
    ok = False
    frame = None
    for attempt in range(1, _OPEN_RETRIES + 1):
        ok, frame = _open_and_read(device_path, cv2)
        if ok:
            break
        if attempt < _OPEN_RETRIES:
            time.sleep(_OPEN_RETRY_DELAY_S)

    if not ok or frame is None:
        raise CameraCaptureError(f"could not open/read camera device: {device_path}")

    ok, buf = cv2.imencode(".jpg", frame)
    if not ok:
        raise CameraCaptureError("failed to encode captured frame as JPEG")
    return buf.tobytes()


async def capture_jpeg(device_path: str) -> bytes:
    async with _get_lock(device_path):
        return await asyncio.to_thread(_capture_jpeg_sync, device_path)
