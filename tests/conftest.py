from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from pulse_capture.desktop.dpi import ensure_process_dpi_aware
from pulse_capture.store import SQLiteEventStore

# Must run before any test creates a window or makes a UIA/input call --
# see src/pulse_capture/desktop/dpi.py for the real bug this prevents.
ensure_process_dpi_aware()


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "pulse_test.db"


@pytest.fixture
def store(tmp_db_path: Path) -> Iterator[SQLiteEventStore]:
    s = SQLiteEventStore(tmp_db_path)
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def session_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def actor_id() -> str:
    return "test-actor-0000"
