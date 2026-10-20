"""Dark-frame enhancement shared by every Sesami feature that returns a
camera capture (currently /sesami camera and /sesami tomocore, via
modules/sesami/camera.py's capture()) -- when the caller explicitly asks
for night mode, the frame is turned into a denoised, contrast-enhanced
grayscale/binary silhouette instead of being sent out as a nearly-black,
unreadable photo.

This used to auto-detect darkness from mean brightness, but that was
replaced with an explicit night_mode flag the user controls per capture
(/sesami camera / /sesami tomocore's night_mode option) -- simpler and
more predictable than a heuristic threshold guessing what counts as
"dark enough".
"""

from __future__ import annotations

import asyncio
import io

import cv2
import numpy as np
from PIL import Image


def binarize_dark_image(image: Image.Image) -> Image.Image:
    """Grayscale + binarize a dark-room capture so a person's silhouette is
    at least visible, instead of returning a nearly-black, unreadable photo.

    Tuned against a real near-total-darkness sample (mean brightness ~4/255):
    plain global thresholding (even Otsu's automatic variant) on the raw
    frame only picks out the single brightest highlight, because almost
    every pixel sits in the camera's noise floor. The fix is to denoise
    first (median blur), then apply a *mild* CLAHE (strong settings just
    amplify sensor noise into speckle) to recover local contrast, blur
    again to smooth the result, and only then run Otsu -- which picks its
    threshold per-frame rather than a fixed magic number that would be
    overfit to one exposure level.
    """
    gray = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    denoised = cv2.medianBlur(gray, 5)
    clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(16, 16))
    enhanced = clahe.apply(denoised)
    smoothed = cv2.GaussianBlur(enhanced, (9, 9), 0)
    _threshold, binary = cv2.threshold(smoothed, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(binary).convert("RGB")


def _apply_night_mode_sync(jpeg_bytes: bytes) -> bytes:
    image = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
    enhanced = binarize_dark_image(image)
    buf = io.BytesIO()
    enhanced.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


async def apply_night_mode(jpeg_bytes: bytes, night_mode: bool) -> bytes:
    """Returns jpeg_bytes unchanged unless night_mode is True, in which
    case a binarized-silhouette JPEG is returned in its place."""
    if not night_mode:
        return jpeg_bytes
    return await asyncio.to_thread(_apply_night_mode_sync, jpeg_bytes)
