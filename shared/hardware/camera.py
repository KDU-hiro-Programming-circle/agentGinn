"""USB camera capture. The only place that shells out to ffmpeg for a frame.

Frames are returned as JPEG bytes and never written to disk -- callers
(Sesami) send them to Discord and discard them. A per-device-path lock
prevents the Collector and a `/sesami camera` command from opening the
same device concurrently.

Capture goes through the `ffmpeg` binary (its v4l2 input demuxer) rather
than cv2.VideoCapture: opencv-python-headless wheels have been observed
with a V4L2 backend that's registered as available but can't actually
open a device by name OR by index ("VIDEOIO(V4L2): backend is generally
available but can't be used to capture by name/index"), making it
unusable here. ffmpeg's v4l2 support is much more mature and doesn't
depend on how the OpenCV wheel happened to be built. Requires the
`ffmpeg` package to be installed on the host (`sudo apt install ffmpeg`).
"""

from __future__ import annotations

import asyncio
import subprocess
import time
from pathlib import Path

_locks: dict[str, asyncio.Lock] = {}
_OPEN_RETRIES = 3
_OPEN_RETRY_DELAY_S = 1.0
_CAPTURE_TIMEOUT_S = 10.0


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
    # -f v4l2 -i <device>: read one frame from the V4L2 capture device.
    # -frames:v 1: stop after a single frame. -f image2 pipe:1: encode
    # that frame as a JPEG and write it to stdout instead of a file.
    cmd = [
        "ffmpeg",
        "-loglevel", "error",
        "-f", "v4l2",
        "-i", device_path,
        "-frames:v", "1",
        "-q:v", "2",
        "-f", "image2",
        "pipe:1",
    ]

    last_error = ""
    for attempt in range(1, _OPEN_RETRIES + 1):
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=_CAPTURE_TIMEOUT_S)
        except FileNotFoundError as exc:
            raise CameraCaptureError(
                "ffmpeg が見つかりません。`sudo apt install ffmpeg` でインストールしてください。"
            ) from exc
        except subprocess.TimeoutExpired:
            last_error = "capture timed out"
        else:
            if result.returncode == 0 and result.stdout:
                return result.stdout
            last_error = result.stderr.decode("utf-8", errors="replace").strip()

        # A freshly (re)plugged/booted USB webcam can take a moment before
        # it's actually ready to stream, so a transient failure is retried
        # rather than treated as a hard error on the first attempt.
        if attempt < _OPEN_RETRIES:
            time.sleep(_OPEN_RETRY_DELAY_S)

    raise CameraCaptureError(f"could not capture from camera device: {device_path} ({last_error})")


async def capture_jpeg(device_path: str) -> bytes:
    async with _get_lock(device_path):
        return await asyncio.to_thread(_capture_jpeg_sync, device_path)
