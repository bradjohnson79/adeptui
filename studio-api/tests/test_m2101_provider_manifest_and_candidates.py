"""M2.10.1 provider manifest + candidate registry guards (no install/execution)."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "config/capabilities/adept-ui-v1.0-provider-manifest.json"
MANIFEST_SHA = ROOT / "config/capabilities/adept-ui-v1.0-provider-manifest.sha256"
MANIFEST_SCHEMA = ROOT / "config/capabilities/adept-ui-v1.0-provider-manifest.schema.json"
CANDIDATES = ROOT / "config/capabilities/adept-ui-v1.1-addon-candidates.json"
CANDIDATES_SCHEMA = ROOT / "config/capabilities/adept-ui-v1.1-addon-candidates.schema.json"
BASELINE = ROOT / "config/capabilities/adept-ui-v1.0-native.json"
PROPOSED = ROOT / "docs/codirector/M2.10.1_PROPOSED_SANDBOX_SHORTLIST.md"
APPROVED = ROOT / "docs/codirector/M2.10_PRODUCT_APPROVED_SANDBOX_SHORTLIST.md"
PREFLIGHT = ROOT / "docs/codirector/m2.10.1-preflight-checkpoint.md"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_provider_manifest_schema_and_hash():
    assert MANIFEST.is_file()
    assert MANIFEST_SCHEMA.is_file()
    payload = MANIFEST.read_text(encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    assert MANIFEST_SHA.read_text(encoding="utf-8").strip() == digest
    data = json.loads(payload)
    schema = _load(MANIFEST_SCHEMA)
    assert data["schemaVersion"] == schema["properties"]["schemaVersion"]["const"]
    assert data["status"] == "frozen"
    assert data["manifestId"] == "adept-ui-v1.0-provider-manifest"


def test_provider_manifest_consistency_vs_baseline():
    manifest = _load(MANIFEST)
    baseline = _load(BASELINE)
    assert manifest["providerKinds"] == baseline["providerKinds"]
    kind_ids = set(
        list(manifest["providerKinds"].get("builtInLocal") or [])
        + list(manifest["providerKinds"].get("externalApiApprovedOptional") or [])
        + list(manifest["providerKinds"].get("deterministicProcessor") or [])
        + list(manifest["providerKinds"].get("addon") or [])
    )
    listed = {p["providerId"] for p in manifest["providers"]}
    assert kind_ids == listed
    # Do not invent generative audio providers
    for slot in manifest["missingSlots"]:
        assert slot["capabilityId"] in {
            "audio.dialogue.generate",
            "audio.sfx.generate",
            "audio.music.generate",
        }
        assert slot.get("baselineProviderIds") in ([], None) or slot["baselineProviderIds"] == []


def test_candidate_registry_schema_and_uniqueness():
    assert CANDIDATES.is_file() and CANDIDATES_SCHEMA.is_file()
    data = _load(CANDIDATES)
    assert data["schemaVersion"] == 1
    ids = [c["id"] for c in data["candidates"]]
    assert len(ids) == len(set(ids))
    keys = [(c["capabilityCategory"], c["source"], c["sourceKey"]) for c in data["candidates"]]
    # uniqueness within area+source+key
    assert len(keys) == len(set(keys))


def test_qualification_gates_and_shortlist_limits():
    data = _load(CANDIDATES)
    by_area = defaultdict(list)
    for c in data["candidates"]:
        by_area[c["capabilityCategory"]].append(c)
    for area, items in by_area.items():
        assert len(items) <= 20
        qual = [c for c in items if c.get("qualificationStatus") == "qualified"]
        prop = [c for c in items if c.get("proposedSandbox")]
        assert len(qual) <= 8
        assert len(prop) <= 3
        for c in prop:
            assert c["qualificationStatus"] == "qualified"
            assert c["approvalStatus"] == "not_product_approved"


def test_no_install_no_execution_guards():
    data = _load(CANDIDATES)
    assert data["safety"]["noInstall"] is True
    assert data["safety"]["noExecution"] is True
    assert data["safety"]["noWeightDownload"] is True
    assert data["safety"]["m210bStillBlocked"] is True
    for c in data["candidates"]:
        assert c["sandboxStatus"] == "not_installed"
        assert c["validationStatus"] == "not_run"
        assert c["promotionStatus"] == "not_promoted"
        assert c["approvalStatus"] == "not_product_approved"


def test_product_approval_separation():
    assert PROPOSED.is_file()
    text = PROPOSED.read_text(encoding="utf-8")
    assert "PROPOSAL ONLY" in text or "NOT PRODUCT APPROVED" in text
    assert not APPROVED.exists()
    data = _load(CANDIDATES)
    assert data["buckets"]["approved_v1_1_additions"] == []
    assert "not_product_approved" in data["status"]


def test_preflight_verdict_ready():
    text = PREFLIGHT.read_text(encoding="utf-8")
    assert "READY FOR M2.10.1 DISCOVERY" in text
    assert "NOT READY" not in text.split("## Verdict")[-1]
