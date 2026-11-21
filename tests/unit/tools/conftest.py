"""Shared fixtures for app/tools/ unit tests — a real, schema+seed
initialized SQLite connection, isolated per test via tmp_path, plus a
minimal PassengerContext builder."""
from __future__ import annotations

from datetime import datetime

import pytest

from app.contracts.interfaces import PassengerContext
from app.db.connection import init_db


@pytest.fixture()
def conn(tmp_path):
    connection = init_db(str(tmp_path / "tools_test.db"))
    yield connection
    connection.close()


def make_ctx(as_of: datetime, passenger_id: str = "P007") -> PassengerContext:
    class _NullRecorder:
        def record(self, section, payload):
            pass

    return PassengerContext(
        passenger_id=passenger_id, preferred_language="en", as_of=as_of, trace=_NullRecorder()
    )
