"""P0/P1-2 / P0/P1-3 regression: image readiness must discover models once and
reuse the cached Comfy catalogue (no duplicate os.walk scans, no duplicate
/object_info fetch, no COMFY_URL env path)."""

from __future__ import annotations

from typing import Any, Iterable

import pytest

from app.image_runtime import capability_probe, readiness


def test_generate_readiness_report_discovers_models_once_and_reuses_catalogue(monkeypatch: pytest.MonkeyPatch) -> None:
    discovery_calls = {"count": 0}
    node_fetch_calls = {"count": 0}

    def _fake_discover() -> dict[str, Any]:
        discovery_calls["count"] += 1
        return {
            "families": {
                "zimage": {"installed": True, "statusHint": "Draft"},
                "flux": {"installed": True, "statusHint": "Draft"},
                "qwen": {"installed": True, "statusHint": "Draft"},
                "imagen": {"credentialConfigured": False, "statusHint": "Blocked"},
                "sd15": {"installed": False},
                "qwen_edit_2509": {"installed": False},
            },
            "discoveryComplete": True,
        }

    def _fake_node_names() -> tuple[set[str], bool]:
        node_fetch_calls["count"] += 1
        return {"TextEncodeZImageOmni", "UNETLoader", "VAEEncode", "CLIPTextEncode"}, True

    monkeypatch.setattr(capability_probe, "discover_modern_image_models", _fake_discover)
    monkeypatch.setattr(readiness, "discover_modern_image_models", _fake_discover)
    monkeypatch.setattr(capability_probe, "_comfy_node_names", _fake_node_names)

    warmed_names: Iterable[str] = ["TextEncodeZImageOmni", "UNETLoader", "VAEEncode"]

    report = readiness.generate_readiness_report(node_names=warmed_names)

    assert discovery_calls["count"] == 1, "models must be discovered exactly once per refresh"
    assert node_fetch_calls["count"] == 0, (
        "warmed node_names must be reused; no duplicate /object_info fetch"
    )
    caps = report["capabilities"]
    assert caps["comfyReachable"] is True
    assert caps["comfyNodesObserved"] == 3
    assert caps["supportsZImage"] is True


def test_probe_runtime_capabilities_falls_back_to_canonical_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    """When no warmed names are provided, probe fetches once via the canonical
    helper (settings.comfy_url), never via COMFY_URL env / urllib."""
    node_fetch_calls = {"count": 0}

    def _fake_discover() -> dict[str, Any]:
        return {"families": {"zimage": {"installed": True}}, "discoveryComplete": True}

    def _fake_node_names() -> tuple[set[str], bool]:
        node_fetch_calls["count"] += 1
        return {"TextEncodeZImageOmni"}, True

    monkeypatch.setattr(capability_probe, "discover_modern_image_models", _fake_discover)
    monkeypatch.setattr(capability_probe, "_comfy_node_names", _fake_node_names)

    result = capability_probe.probe_runtime_capabilities()
    assert node_fetch_calls["count"] == 1, "fallback fetches exactly once via canonical helper"
    assert result["capabilities"]["comfyReachable"] is True
    # The legacy defect signatures must be gone from executable code.
    import inspect

    src = inspect.getsource(capability_probe)
    assert "urllib.request" not in src, "legacy urllib /object_info path must be removed"
    assert 'os.environ.get("COMFY_URL")' not in src, "legacy COMFY_URL env path must be removed"
    assert "urlopen" not in src, "legacy urllib.urlopen fetch must be removed"
