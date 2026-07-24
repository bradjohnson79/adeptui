from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest


# This must happen before any test module can import app.*. Both Settings and the
# SQLAlchemy engine are constructed at import time.
_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="aivideostudio-phase0-")).resolve()
os.environ["STUDIO_DATA_DIR"] = str(_TEST_DATA_DIR)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    db_module = sys.modules.get("app.db")
    if db_module is not None:
        db_module.engine.dispose()
    shutil.rmtree(_TEST_DATA_DIR, ignore_errors=True)


@pytest.fixture(scope="session")
def isolated_data_dir() -> Path:
    return _TEST_DATA_DIR


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch):
    from fastapi.testclient import TestClient

    from app.main import app, job_queue
    from app.routers import api

    monkeypatch.setattr(job_queue, "start", lambda: None)
    monkeypatch.setattr(api.job_queue, "enqueue", AsyncMock())

    with TestClient(app) as test_client:
        yield test_client
