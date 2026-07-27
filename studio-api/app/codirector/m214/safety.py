"""M2.14 safety: Manifest lock + hard bans."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Final

EXPECTED_MANIFEST_SHA256: Final[str] = (
    "cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc"
)
MANIFEST_RELATIVE: Final[str] = "config/capabilities/adept-ui-v1.0-provider-manifest.json"


class UnifiedExperienceSafetyError(RuntimeError):
    """Raised when M2.14 safety invariants are violated."""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def assert_manifest_unchanged(root: Path | None = None) -> str:
    base = root or repo_root()
    path = base / MANIFEST_RELATIVE
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != EXPECTED_MANIFEST_SHA256:
        raise UnifiedExperienceSafetyError(
            f"Provider Manifest sha256 mismatch: got {digest}, expected {EXPECTED_MANIFEST_SHA256}"
        )
    return digest


def safety_contract() -> dict:
    return {
        "noNewProviders": True,
        "noManifestOrLockChanges": True,
        "noSilentBibleOrTimelineMutation": True,
        "noFineTuning": True,
        "noAutonomousCodeRewrite": True,
        "noSystemLessonAutoActivate": True,
        "extendM211DoNotForkOrchestration": True,
        "labelMockedVsReal": True,
        "manifestSha256": EXPECTED_MANIFEST_SHA256,
        "flagDefaultOff": True,
        "apis404WhenOff": True,
    }
