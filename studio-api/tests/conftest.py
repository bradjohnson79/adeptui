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
# App startup would otherwise promote a real .env fal key into the store, which means a
# live network probe on every test that exercises the lifespan.
os.environ["STUDIO_FAL_ENV_BRIDGE"] = "0"


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    db_module = sys.modules.get("app.db")
    if db_module is not None:
        db_module.engine.dispose()
    shutil.rmtree(_TEST_DATA_DIR, ignore_errors=True)


@pytest.fixture(scope="session")
def isolated_data_dir() -> Path:
    return _TEST_DATA_DIR


@pytest.fixture(autouse=True)
def restore_process_data_dir(monkeypatch: pytest.MonkeyPatch):
    """Prevent tests that mutate global Settings from leaking into later tests."""
    from app.config import settings

    settings.data_dir = _TEST_DATA_DIR
    monkeypatch.setenv("STUDIO_DATA_DIR", str(_TEST_DATA_DIR))
    # Clear the image-modality verify cache so a prior test's monkeypatched
    # verify_component result cannot leak into this test.
    try:
        from app.production_control.model_registry import _IMAGE_VERIFY_CACHE

        _IMAGE_VERIFY_CACHE.clear()
    except Exception:
        pass
    yield
    settings.data_dir = _TEST_DATA_DIR


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch):
    from fastapi.testclient import TestClient

    from app.main import app, job_queue
    from app.routers import api

    monkeypatch.setattr(job_queue, "start", lambda: None)
    monkeypatch.setattr(api.job_queue, "enqueue", AsyncMock())

    with TestClient(app) as test_client:
        yield test_client

# ===========================================================================
# CDX-093 - LIVE certification layer (opt-in, SKIPPED by default)
# ===========================================================================
# The default `client` fixture above mocks api.job_queue.enqueue, so no API
# test proves REAL execution. This opt-in layer exists for operators who want
# to certify the REAL enqueue path end-to-end. Tests that need it request the
# `live_cert` gate (skipped unless ADEPT_LIVE_CERT=1) and use `live_cert_client`
# (a TestClient with the enqueue mock removed). Default tests stay mock-based;
# nothing here turns a default test into live generation.

LIVE_CERT_ENV_VAR = "ADEPT_LIVE_CERT"


def live_cert_enabled() -> bool:
    """True when ADEPT_LIVE_CERT is set to a truthy value."""
    return os.environ.get(LIVE_CERT_ENV_VAR, "").strip().lower() in {"1", "true", "yes", "on"}


@pytest.fixture()
def live_cert() -> bool:
    """CDX-093 gate: LIVE certification tests are SKIPPED unless
    ADEPT_LIVE_CERT=1 is set. Returns True when the layer is enabled."""
    if not live_cert_enabled():
        pytest.skip(
            "LIVE certification layer is opt-in: set ADEPT_LIVE_CERT=1 to run "
            "the real-enqueue-path scaffolds (test_live_cert_scaffolds.py)."
        )
    return True


@pytest.fixture()
def live_cert_client(monkeypatch: pytest.MonkeyPatch, live_cert: bool):
    """TestClient with the REAL job_queue.enqueue path (no mock).

    Only usable when the `live_cert` gate is enabled (otherwise the gate
    already skipped the requesting test). job_queue.start is still stubbed so
    no background worker loop runs; enqueue itself is the real implementation,
    so jobs are durably queued through the real queue object (a live-path
    scaffold can then assert the queue receipt + persisted Job row).
    """
    from fastapi.testclient import TestClient

    from app.main import app, job_queue

    monkeypatch.setattr(job_queue, "start", lambda: None)
    with TestClient(app) as test_client:
        yield test_client

