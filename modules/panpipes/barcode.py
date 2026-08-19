"""Barcode decoding for book cover photos.

Books print two stacked EAN-13 barcodes: the top one is the
978/979-prefixed ISBN, the bottom one is a 192-prefixed price code.
Only 978/979 codes are ever returned, so the price code never gets
mistaken for an ISBN.
"""

from __future__ import annotations

import io
import re

from shared.logger import get_logger

logger = get_logger(__name__)

_ISBN_EAN13_RE = re.compile(r"^(978|979)\d{10}$")

try:
    from PIL import Image
    from pyzbar.pyzbar import decode as _zbar_decode

    BARCODE_SUPPORT = True
except ImportError:  # native zbar lib not installed (e.g. local Windows dev)
    BARCODE_SUPPORT = False
    logger.warning(
        "pyzbar/Pillow not available -- barcode decoding disabled; "
        "manual entry via /panpipes register still works"
    )


def extract_isbns(image_bytes: bytes) -> list[str]:
    """Decode all barcodes in an image, keeping only 978/979 13-digit ISBNs."""
    if not BARCODE_SUPPORT:
        raise RuntimeError("barcode decoding is not available in this environment")

    image = Image.open(io.BytesIO(image_bytes))
    decoded = _zbar_decode(image)
    codes = [result.data.decode("utf-8", errors="ignore") for result in decoded]
    return [code for code in codes if _ISBN_EAN13_RE.match(code)]
