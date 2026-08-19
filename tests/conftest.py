from __future__ import annotations

import pytest

from database.migration import apply_schema
from shared.database import database


@pytest.fixture
async def temp_db(tmp_path):
    database.init(tmp_path / "test.db")
    await apply_schema()
    yield
