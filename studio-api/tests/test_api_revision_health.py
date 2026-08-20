from __future__ import annotations


def test_health_reports_api_revision_and_start_time(client) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert isinstance(payload.get("apiStartedAt"), str) and payload["apiStartedAt"]
    assert "T" in payload["apiStartedAt"]
    revision = payload.get("apiRevision")
    assert revision is None or (isinstance(revision, str) and len(revision) >= 7)
    assert "perception.capability" in (payload.get("routeContract") or [])
