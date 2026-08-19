"""The doc calls out explicitly: book barcodes are two stacked EAN-13
codes (978/979 ISBN on top, 192 price code below) and only the ISBN
row must ever be used."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from modules.panpipes import barcode


class FakeResult:
    def __init__(self, data: bytes) -> None:
        self.data = data


def test_extracts_only_978_979_prefixed_codes():
    fake_codes = [
        FakeResult(b"9784873119485"),  # valid ISBN (978-)
        FakeResult(b"1920000123458"),  # price code (192-) -- must be dropped
        FakeResult(b"9791234567896"),  # valid ISBN (979-)
        FakeResult(b"4901234567894"),  # unrelated EAN-13 -- must be dropped
    ]
    with (
        patch("modules.panpipes.barcode._zbar_decode", return_value=fake_codes),
        patch("modules.panpipes.barcode.Image") as mock_image,
        patch("modules.panpipes.barcode.BARCODE_SUPPORT", True),
    ):
        mock_image.open.return_value = object()
        result = barcode.extract_isbns(b"fake-jpeg-bytes")

    assert result == ["9784873119485", "9791234567896"]


def test_no_barcodes_returns_empty_list():
    with (
        patch("modules.panpipes.barcode._zbar_decode", return_value=[]),
        patch("modules.panpipes.barcode.Image") as mock_image,
        patch("modules.panpipes.barcode.BARCODE_SUPPORT", True),
    ):
        mock_image.open.return_value = object()
        assert barcode.extract_isbns(b"fake") == []


def test_raises_when_barcode_support_unavailable():
    with patch("modules.panpipes.barcode.BARCODE_SUPPORT", False):
        with pytest.raises(RuntimeError):
            barcode.extract_isbns(b"fake")
