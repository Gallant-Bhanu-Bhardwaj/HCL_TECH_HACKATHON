"""Shared fixtures for app/rag/ tests."""
from __future__ import annotations

import pytest

from app.db.connection import init_db


@pytest.fixture()
def conn(tmp_path):
    connection = init_db(str(tmp_path / "rag_test.db"))
    yield connection
    connection.close()
