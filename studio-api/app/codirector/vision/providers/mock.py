"""Deterministic mock vision provider for tests and E2E."""

from __future__ import annotations

from typing import Any, Optional

# Named fixture profiles drive validator scores without inventing ML certainty.
_FIXTURES: dict[str, dict[str, Any]] = {
    "pass": {
        "fixtureDefaultScore": 97.0,
        "fixtureScores": {
            "technical": 98.0,
            "identity": 97.0,
            "continuity": 96.0,
            "lighting": 96.0,
            "camera": 95.0,
            "composition": 95.0,
            "color": 96.0,
            "motion": 95.0,
        },
        "fixtureBlocking": {},
    },
    "warnings": {
        "fixtureDefaultScore": 91.0,
        "fixtureScores": {
            "technical": 94.0,
            "identity": 91.0,
            "continuity": 90.0,
            "lighting": 88.0,
            "camera": 90.0,
            "composition": 89.0,
            "color": 90.0,
        },
        "fixtureBlocking": {},
    },
    "fail_technical": {
        "fixtureDefaultScore": 70.0,
        "fixtureScores": {
            "technical": 40.0,
            "identity": 92.0,
            "continuity": 90.0,
            "lighting": 88.0,
            "camera": 90.0,
            "composition": 90.0,
            "color": 90.0,
        },
        "fixtureBlocking": {"technical": True},
    },
    "fail_identity": {
        "fixtureDefaultScore": 75.0,
        "fixtureScores": {
            "technical": 96.0,
            "identity": 55.0,
            "continuity": 88.0,
            "lighting": 90.0,
            "camera": 90.0,
            "composition": 90.0,
            "color": 90.0,
        },
        "fixtureBlocking": {"identity": True},
    },
    "corrections": {
        "fixtureDefaultScore": 84.0,
        "fixtureScores": {
            "technical": 88.0,
            "identity": 82.0,
            "continuity": 81.0,
            "lighting": 80.0,
            "camera": 85.0,
            "composition": 83.0,
            "color": 84.0,
        },
        "fixtureBlocking": {},
    },
}


class MockVisionProvider:
    provider_id = "mock"

    def prepare_asset_context(
        self,
        *,
        asset_path: Optional[str],
        reference_path: Optional[str],
        requirements: dict[str, Any],
        fixture_profile: Optional[str] = None,
    ) -> dict[str, Any]:
        profile = fixture_profile or str(requirements.get("fixtureProfile") or "pass")
        fixture = dict(_FIXTURES.get(profile) or _FIXTURES["pass"])
        media_kind = str(requirements.get("mediaKind") or "image")
        return {
            "provider": self.provider_id,
            "mediaKind": media_kind,
            "assetPath": asset_path,
            "referencePath": reference_path,
            "fixtureProfile": profile,
            "technicalMetrics": {
                "width": 1024,
                "height": 576,
                "laplacianVariance": 120.0,
                "meanLuma": 118.0,
                "source": "mock",
            },
            **fixture,
        }
