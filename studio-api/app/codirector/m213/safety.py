"""M2.13 safety: Manifest lock + no silent binary installs."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Final

EXPECTED_MANIFEST_SHA256: Final[str] = (
    "cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc"
)
MANIFEST_RELATIVE: Final[str] = "config/capabilities/adept-ui-v1.0-provider-manifest.json"


class VirtualEnvironmentStudioSafetyError(RuntimeError):
    pass


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def assert_manifest_unchanged(root: Path | None = None) -> str:
    base = root or repo_root()
    path = base / MANIFEST_RELATIVE
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != EXPECTED_MANIFEST_SHA256:
        raise VirtualEnvironmentStudioSafetyError(
            f"Provider Manifest sha256 changed: {digest} != {EXPECTED_MANIFEST_SHA256}"
        )
    return digest


def safety_contract() -> dict:
    return {
        "flagDefaultOff": True,
        "noSilentColmapInstall": True,
        "noSilentNerfstudioInstall": True,
        "noBlenderReplacement": True,
        "noSilentApprovalAdvance": True,
        "honestFixtureLabels": True,
        "manifestSha256": EXPECTED_MANIFEST_SHA256,
        "forbidden": [
            "silent_colmap_download",
            "silent_nerfstudio_download",
            "sculpt_rig_uv_authoring",
            "provider_manifest_edits",
            "claim_real_from_mock_alone",
        ],
    }
