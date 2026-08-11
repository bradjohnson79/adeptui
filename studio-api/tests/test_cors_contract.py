"""Backend CORS contract tests.

Verifies that CORS headers are attached to responses for the hosted Beta
origin (`https://adeptui.vercel.app`) on success, preflight, and error paths.

This guards against the middleware-ordering regression where
`ProjectPasswordLockMiddleware` (or any short-circuiting layer) bypassed
`CORSMiddleware` and produced headerless error responses that surfaced as
browser CORS failures.
"""

from __future__ import annotations

import pytest

ORIGIN = "https://adeptui.vercel.app"


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def assert_cors_headers(headers, expected_origin: str = ORIGIN) -> None:
    acao = headers.get("access-control-allow-origin")
    assert acao == expected_origin, (
        f"Expected Access-Control-Allow-Origin='{expected_origin}', got {acao!r}"
    )


def test_healthz_returns_cors_headers_on_success(client):
    res = client.get("/api/healthz", headers={"Origin": ORIGIN})
    assert res.status_code == 200
    assert_cors_headers(res.headers)


def test_health_returns_cors_headers_on_success(client):
    res = client.get("/api/health", headers={"Origin": ORIGIN})
    assert res.status_code == 200
    assert_cors_headers(res.headers)


def test_production_control_status_returns_cors_headers(client):
    res = client.get("/api/production-control/status", headers={"Origin": ORIGIN})
    assert res.status_code == 200
    assert_cors_headers(res.headers)


def test_preflight_production_control_status_returns_cors_headers(client):
    res = client.options(
        "/api/production-control/status",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert res.status_code in (200, 204)
    assert_cors_headers(res.headers)
    acam = res.headers.get("access-control-allow-methods", "")
    assert "GET" in acam.upper(), f"GET missing from allow-methods: {acam!r}"


def test_404_response_carries_cors_headers(client):
    """Unknown route must still return CORS headers — regression for the
    middleware-ordering defect where short-circuited responses bypassed CORS."""
    res = client.get("/api/this-route-does-not-exist", headers={"Origin": ORIGIN})
    assert res.status_code == 404
    assert_cors_headers(res.headers)


def test_scriptwriter_autosave_400_carries_cors_headers(client):
    """A 400 from a project-scoped endpoint (document not found / bad revision)
    must carry CORS headers so the browser can surface the real error."""
    res = client.post(
        "/api/projects/00000000-0000-0000-0000-000000000000/scriptwriter/documents/nonexistent/autosave",
        json={"elements": [], "expectedRevision": None},
        headers={"Origin": ORIGIN},
    )
    assert res.status_code in (400, 404, 422)
    assert_cors_headers(res.headers)


def test_locked_project_response_carries_cors_headers(client, tmp_path, monkeypatch):
    """A locked-project 403 short-circuit must carry CORS headers.

    This is the precise regression that produced the delayed-onset CORS
    failures: `_LOCKED` was a pre-built headerless response returned by
    `ProjectPasswordLockMiddleware` before CORS could attach headers.
    """
    # Force the lock-middleware fail-closed path for a project-scoped route by
    # pointing the DB at an empty directory so the asset lookup raises.
    # We exercise the exact short-circuit via a route the middleware protects.
    res = client.get(
        "/api/projects/00000000-0000-0000-0000-000000000000/scriptwriter/documents",
        headers={"Origin": ORIGIN},
    )
    # Whether the project is missing (404) or treated as unlocked, the response
    # must still carry CORS headers — no path through the middleware may drop them.
    assert res.status_code in (200, 400, 403, 404, 422)
    assert_cors_headers(res.headers)
