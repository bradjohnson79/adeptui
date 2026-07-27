"""M3.0a fal.ai BYOK: live key validation, honest status, and credential redaction."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

SECRET_KEY = "fal-secret-value-do-not-leak"


@pytest.fixture(autouse=True)
def isolated_secrets(tmp_path, monkeypatch: pytest.MonkeyPatch):
    from app import secrets_store

    secrets_dir = tmp_path / "secrets"
    monkeypatch.setattr(secrets_store, "SECRETS_DIR", secrets_dir)
    monkeypatch.setattr(secrets_store, "MASTER_KEY_FILE", secrets_dir / "master.key")
    return secrets_dir


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.text = ""


class _FakeAsyncClient:
    """Records the probe request so tests can assert on how the key is transmitted."""

    calls: list[dict[str, Any]] = []
    status_code = 404
    raise_exc: Exception | None = None

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *exc) -> None:
        return None

    async def get(self, url: str, headers: dict[str, str] | None = None) -> _FakeResponse:
        type(self).calls.append({"url": url, "headers": headers or {}})
        if type(self).raise_exc:
            raise type(self).raise_exc
        return _FakeResponse(type(self).status_code)


@pytest.fixture()
def fal_probe(monkeypatch: pytest.MonkeyPatch):
    import httpx

    _FakeAsyncClient.calls = []
    _FakeAsyncClient.status_code = 404
    _FakeAsyncClient.raise_exc = None
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    return _FakeAsyncClient


def _client() -> TestClient:
    from app.main import app

    return TestClient(app)


def test_probe_classifies_rejected_key_as_invalid(fal_probe):
    import asyncio

    from app.fal_client import validate_fal_key

    fal_probe.status_code = 401
    out = asyncio.run(validate_fal_key(SECRET_KEY))
    assert out["valid"] is False
    assert out["status"] == "invalid"


def test_probe_treats_unreachable_service_as_unverified(fal_probe):
    import asyncio

    from app.fal_client import validate_fal_key

    fal_probe.raise_exc = RuntimeError("dns failure")
    out = asyncio.run(validate_fal_key(SECRET_KEY))
    assert out["valid"] is None
    assert out["status"] == "unverified"


def test_put_key_rejects_a_key_fal_refuses(fal_probe):
    from app.secrets_store import get_secret

    fal_probe.status_code = 403
    with _client() as c:
        r = c.put("/api/fal/key", json={"api_key": SECRET_KEY})
    assert r.status_code == 400
    assert SECRET_KEY not in r.text
    assert get_secret("fal_api_key") is None


def test_put_key_stores_and_reports_verified(fal_probe):
    fal_probe.status_code = 404  # unknown request id => the key authenticated
    with _client() as c:
        put = c.put("/api/fal/key", json={"api_key": SECRET_KEY})
        assert put.status_code == 200
        body = put.json()
        assert body["configured"] is True
        assert body["state"] == "verified"
        assert body["verified"] is True

        status = c.get("/api/fal/key").json()
        assert status["state"] == "verified"
        assert status["verifiedAt"]


def test_status_never_returns_the_key(fal_probe):
    with _client() as c:
        c.put("/api/fal/key", json={"api_key": SECRET_KEY})
        get = c.get("/api/fal/key")
        validate = c.post("/api/fal/key/validate")
    for response in (get, validate):
        assert SECRET_KEY not in response.text
        assert "api_key" not in response.json()
    # The key travels in the Authorization header only, never in a URL that could be logged.
    for call in fal_probe.calls:
        assert SECRET_KEY not in call["url"]
        assert SECRET_KEY in call["headers"].get("Authorization", "")


def test_revalidation_downgrades_a_revoked_key(fal_probe):
    with _client() as c:
        c.put("/api/fal/key", json={"api_key": SECRET_KEY})
        fal_probe.status_code = 401
        again = c.post("/api/fal/key/validate")
    assert again.status_code == 200
    assert again.json()["state"] == "invalid"


def test_replacing_the_key_invalidates_the_previous_verification(fal_probe):
    from app.secrets_store import secret_status, set_secret

    with _client() as c:
        c.put("/api/fal/key", json={"api_key": SECRET_KEY})
        assert secret_status("fal_api_key")["state"] == "verified"
        # A key swapped in behind the API must not inherit the old "verified" badge.
        set_secret("fal_api_key", "some-other-key")
        assert secret_status("fal_api_key")["state"] == "unverified"


def test_diagnostics_reports_the_verified_state(fal_probe):
    from app.setup.diagnostics import verify_component

    assert verify_component("fal_key").issue_code == "credential_missing"

    with _client() as c:
        c.put("/api/fal/key", json={"api_key": SECRET_KEY})
    assert verify_component("fal_key").healthy is True

    fal_probe.status_code = 401
    with _client() as c:
        c.post("/api/fal/key/validate")
    assert verify_component("fal_key").issue_code == "credential_invalid"


def test_catalog_declares_media_types_and_no_unwired_image_models():
    from app.fal_catalog import FAL_IMAGE_MODELS, list_fal_models, list_fal_models_by_media

    models = list_fal_models()
    assert models
    assert all(m["media_type"] == "video" for m in models)
    assert list_fal_models_by_media("image") == []
    assert FAL_IMAGE_MODELS == {}


def test_queue_worker_records_the_fal_request_id():
    import json

    from app.db import Job
    from app.queue_worker import JobQueue

    class _FakeDb:
        def commit(self) -> None:
            self.committed = True

    job = Job(id="job-1", project_id="p", kind="txt2vid", status="running", history_json='{"a": 1}')
    JobQueue._record_fal_request_id(_FakeDb(), job, model_id="fal-ai/veo3.1", request_id="req-42")
    history = json.loads(job.history_json)
    assert history["falRequestId"] == "req-42"
    assert history["falModelId"] == "fal-ai/veo3.1"
    assert history["a"] == 1
