"""Deterministic fixtures for M2.8 CI / Playwright acceptance.

Never executes remote repository code. Never writes outside a sandbox root under
the studio data directory. Live HF/GitHub discovery is not performed here.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ...config import settings
from . import fixture_mode_enabled


CLASSIFICATIONS = (
    "official",
    "community",
    "announcement_only",
    "gated",
    "api_only",
)

_TRUE = {"1", "true", "TRUE", "yes", "YES", "on"}


def fixture_execution_enabled() -> bool:
    """Whether simulated M2.8 execution results may be produced.

    Only the environment grants this (ADEPT_M28_FIXTURE_MODE / STUDIO_E2E); a request
    payload never can. Outside it, services refuse instead of fabricating a success.
    """
    return fixture_mode_enabled() or os.environ.get("STUDIO_E2E", "").strip() in _TRUE


def fixture_hf_discoveries() -> list[dict[str, Any]]:
    return [
        {
            "source": "huggingface",
            "source_key": "adept/fixture-zimage-turbo",
            "display_name": "Fixture Z-Image Turbo",
            "classification": "official",
            "metadata": {
                "vramGb": 12,
                "storageGb": 8,
                "os": ["windows", "linux"],
                "deps": ["torch", "comfyui"],
                "license": "apache-2.0",
                "installable": True,
            },
        },
        {
            "source": "huggingface",
            "source_key": "community/fixture-style-lora",
            "display_name": "Fixture Community Style LoRA",
            "classification": "community",
            "metadata": {
                "vramGb": 6,
                "storageGb": 1,
                "os": ["windows", "linux"],
                "deps": ["comfyui"],
                "license": "cc-by-4.0",
                "installable": True,
            },
        },
        {
            "source": "huggingface",
            "source_key": "vendor/fixture-announcement",
            "display_name": "Fixture Announcement Only Model",
            "classification": "announcement_only",
            "metadata": {
                "vramGb": 48,
                "storageGb": 40,
                "os": ["linux"],
                "deps": [],
                "license": "proprietary",
                "installable": False,
            },
        },
    ]


def fixture_github_discoveries() -> list[dict[str, Any]]:
    return [
        {
            "source": "github",
            "source_key": "adept-filmworks/fixture-comfy-nodes",
            "display_name": "Fixture Comfy Nodes",
            "classification": "community",
            "metadata": {
                "vramGb": 0,
                "storageGb": 1,
                "os": ["windows", "linux"],
                "deps": ["comfyui"],
                "license": "mit",
                "installable": True,
                "commit": "abc123fixture",
            },
        },
        {
            "source": "github",
            "source_key": "vendor/fixture-gated-api",
            "display_name": "Fixture Gated API Wrapper",
            "classification": "gated",
            "metadata": {
                "vramGb": 0,
                "storageGb": 0,
                "os": ["windows", "linux"],
                "deps": ["httpx"],
                "license": "proprietary",
                "installable": False,
                "apiOnly": False,
            },
        },
        {
            "source": "github",
            "source_key": "vendor/fixture-api-only",
            "display_name": "Fixture API-Only Service",
            "classification": "api_only",
            "metadata": {
                "vramGb": 0,
                "storageGb": 0,
                "os": ["windows", "linux"],
                "deps": [],
                "license": "proprietary",
                "installable": False,
                "apiOnly": True,
            },
        },
    ]


def default_env_profile() -> dict[str, Any]:
    return {
        "vramGb": int(os.environ.get("ADEPT_M28_FIXTURE_VRAM_GB", "24")),
        "storageGb": int(os.environ.get("ADEPT_M28_FIXTURE_STORAGE_GB", "200")),
        "os": os.environ.get("ADEPT_M28_FIXTURE_OS", "windows"),
        "deps": ["torch", "comfyui", "httpx"],
        "allowedLicenses": ["apache-2.0", "mit", "cc-by-4.0", "openrail"],
    }


def sandbox_root(sandbox_id: str) -> Path:
    """Sandbox filesystem root under studio data dir. Never escapes this tree."""
    root = Path(settings.data_dir) / "m28_sandboxes" / sandbox_id
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def assert_path_inside_sandbox(sandbox_id: str, target: Path) -> None:
    root = sandbox_root(sandbox_id)
    resolved = target.resolve()
    if root not in resolved.parents and resolved != root:
        raise PermissionError(f"Refusing write outside sandbox root: {resolved}")


def simulate_sandbox_detect(sandbox_id: str) -> dict[str, Any]:
    root = sandbox_root(sandbox_id)
    return {
        "sandboxId": sandbox_id,
        "root": str(root),
        "models": ["fixture-zimage-turbo"],
        "customNodes": ["fixture-comfy-nodes"],
        "fixtureMode": fixture_mode_enabled(),
    }


def mock_generation_result(*, stage: str, seed: int = 1) -> dict[str, Any]:
    return {
        "provider": "fixture_mock",
        "stage": stage,
        "seed": seed,
        "assetId": f"fixture-asset-{stage}-{seed}",
        "ok": True,
    }


def require_fixture_or_allow_live() -> bool:
    """CI/Playwright should set ADEPT_M28_FIXTURE_MODE=1. Live discovery is out of M2.8 scope."""
    return fixture_mode_enabled()
