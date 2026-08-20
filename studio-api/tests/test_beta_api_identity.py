"""Supervisor adoption must not treat SHA-alone as currency."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from beta_runtime.api_identity import perception_contract_ok, should_adopt_studio_api


def test_healthy_sha_without_perception_is_not_adopted() -> None:
    assert (
        should_adopt_studio_api(
            healthy=True,
            revision_current=True,
            perception_ok=False,
        )
        is False
    )


def test_stale_sha_is_not_adopted_even_if_perception_answers() -> None:
    assert (
        should_adopt_studio_api(
            healthy=True,
            revision_current=False,
            perception_ok=True,
        )
        is False
    )


def test_healthy_sha_with_perception_is_adopted() -> None:
    assert (
        should_adopt_studio_api(
            healthy=True,
            revision_current=True,
            perception_ok=True,
        )
        is True
    )


def test_perception_contract_requires_scene_review_shape() -> None:
    assert perception_contract_ok({}) is False
    assert perception_contract_ok({"detail": "Not Found"}) is False
    assert (
        perception_contract_ok(
            {"capability": {"sceneReview": "available", "chatRequired": False}}
        )
        is True
    )
    assert (
        perception_contract_ok(
            {"capability": {"sceneReview": "unavailable", "chatRequired": False}}
        )
        is True
    )
    assert (
        perception_contract_ok(
            {"capability": {"sceneReview": "available", "chatRequired": True}}
        )
        is False
    )


def test_health_route_contract_lists_perception(client) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert "perception.capability" in (payload.get("routeContract") or [])
