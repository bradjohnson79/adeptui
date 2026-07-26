"""M2.10.2 Product-approved sandbox lock guards (no install/execution)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APPROVED_MD = ROOT / "docs/codirector/M2.10_PRODUCT_APPROVED_SANDBOX_SHORTLIST.md"
APPROVED_MD_SHA = ROOT / "docs/codirector/M2.10_PRODUCT_APPROVED_SANDBOX_SHORTLIST.md.sha256"
LOCK = ROOT / "config/capabilities/adept-ui-v1.1-product-approved-sandbox-lock.json"
LOCK_SHA = ROOT / "config/capabilities/adept-ui-v1.1-product-approved-sandbox-lock.sha256"
LOCK_SCHEMA = ROOT / "config/capabilities/adept-ui-v1.1-product-approved-sandbox-lock.schema.json"
LOCK_SCHEMA_SHA = ROOT / "config/capabilities/adept-ui-v1.1-product-approved-sandbox-lock.schema.sha256"
CANDIDATES = ROOT / "config/capabilities/adept-ui-v1.1-addon-candidates.json"
CANDIDATES_SHA = ROOT / "config/capabilities/adept-ui-v1.1-addon-candidates.sha256"
MANIFEST = ROOT / "config/capabilities/adept-ui-v1.0-provider-manifest.json"
MANIFEST_SHA = ROOT / "config/capabilities/adept-ui-v1.0-provider-manifest.sha256"
PREFLIGHT_M2102 = ROOT / "docs/codirector/m2.10.2-preflight-checkpoint.md"
PREFLIGHT_M210B = ROOT / "docs/codirector/m2.10b-preflight.md"
PROPOSED = ROOT / "docs/codirector/M2.10.1_PROPOSED_SANDBOX_SHORTLIST.md"

EXPECTED_MANIFEST_SHA = "cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc"
CAPABILITIES = (
    "audio.dialogue.generate",
    "audio.sfx.generate",
    "audio.music.generate",
)
EXPECTED_KEYS = {
    "audio.dialogue.generate": {
        "hexgrad/Kokoro-82M",
        "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        "ResembleAI/chatterbox",
    },
    "audio.sfx.generate": {
        "Stability-AI/stable-audio-tools",
        "open-mmlab/Amphion",
        "hkchengrex/MMAudio",
    },
    "audio.music.generate": {
        "ace-step/ACE-Step",
        "multimodal-art-projection/YuE",
        "riffusion/riffusion-hobby",
    },
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _all_lock_candidates(lock: dict) -> list[dict]:
    out: list[dict] = []
    for cap in CAPABILITIES:
        out.extend(lock["candidatesByCapability"][cap])
    return out


def test_01_product_approved_shortlist_exists():
    assert APPROVED_MD.is_file()
    text = APPROVED_MD.read_text(encoding="utf-8")
    assert "PRODUCT APPROVED FOR SANDBOX EVALUATION ONLY" in text
    assert "READY FOR M2.10.2 PRODUCT APPROVAL" in PREFLIGHT_M2102.read_text(encoding="utf-8")


def test_02_candidate_lock_exists():
    assert LOCK.is_file()
    assert LOCK_SCHEMA.is_file()


def test_03_lock_validates_against_schema():
    lock = _load(LOCK)
    schema = _load(LOCK_SCHEMA)
    assert lock["schemaVersion"] == schema["properties"]["schemaVersion"]["const"]
    for key in schema["required"]:
        assert key in lock
    assert lock["productionApproved"] is False
    assert lock["installationAuthorized"] is False
    assert lock["executionAuthorized"] is False
    assert lock["weightDownloadAuthorized"] is False


def test_04_exactly_nine_candidates_approved():
    lock = _load(LOCK)
    assert lock["approvedCandidateCount"] == 9
    assert len(_all_lock_candidates(lock)) == 9


def test_05_exactly_three_per_capability():
    lock = _load(LOCK)
    for cap in CAPABILITIES:
        items = lock["candidatesByCapability"][cap]
        assert len(items) == 3
        keys = {c["sourceKey"] for c in items}
        assert keys == EXPECTED_KEYS[cap]


def test_06_every_approved_id_in_registry():
    lock = _load(LOCK)
    registry = _load(CANDIDATES)
    by_id = {c["id"]: c for c in registry["candidates"]}
    for c in _all_lock_candidates(lock):
        assert c["registryId"] in by_id
        reg = by_id[c["registryId"]]
        assert reg["sourceKey"] == c["sourceKey"]
        assert reg["capabilityCategory"] == c["capabilityId"]


def test_07_no_unqualified_or_rejected_approved():
    lock = _load(LOCK)
    registry = _load(CANDIDATES)
    by_id = {c["id"]: c for c in registry["candidates"]}
    for c in _all_lock_candidates(lock):
        reg = by_id[c["registryId"]]
        assert reg["qualificationStatus"] == "qualified"
        assert reg.get("bucket") != "rejected"
        assert c["qualificationStatus"] == "qualified"


def test_08_every_approved_sandbox_only():
    lock = _load(LOCK)
    assert lock["approvalScope"] == "sandbox_evaluation_only"
    for c in _all_lock_candidates(lock):
        assert c["sandboxOnly"] is True


def test_09_authorization_flags_false():
    lock = _load(LOCK)
    for c in _all_lock_candidates(lock):
        assert c["productionApproved"] is False
        assert c["installationAuthorized"] is False
        assert c["executionAuthorized"] is False
        assert c["weightDownloadAuthorized"] is False
    registry = _load(CANDIDATES)
    approved_ids = {c["registryId"] for c in _all_lock_candidates(lock)}
    for reg in registry["candidates"]:
        if reg["id"] in approved_ids:
            assert reg["sandboxApproved"] is True
            assert reg["productionApproved"] is False
            assert reg["installationAuthorized"] is False
            assert reg["executionAuthorized"] is False
            pd = reg["productDecision"]
            assert pd["weightDownloadAuthorized"] is False


def test_10_provider_manifest_unchanged():
    digest = _sha(MANIFEST)
    assert digest == EXPECTED_MANIFEST_SHA
    assert MANIFEST_SHA.read_text(encoding="utf-8").strip() == digest
    lock = _load(LOCK)
    assert lock["providerManifestSha256"] == digest


def test_11_provider_manifest_only_three_providers():
    manifest = _load(MANIFEST)
    ids = {p["providerId"] for p in manifest["providers"]}
    assert ids == {"comfy.local", "vision.local", "fal.api"}


def test_12_audio_fill_targets_remain():
    manifest = _load(MANIFEST)
    missing = {s["capabilityId"] for s in manifest["missingSlots"]}
    assert set(CAPABILITIES).issubset(missing)


def test_13_no_candidate_promoted_into_manifest():
    manifest = _load(MANIFEST)
    provider_ids = {p["providerId"] for p in manifest["providers"]}
    lock = _load(LOCK)
    for c in _all_lock_candidates(lock):
        assert c["sourceKey"] not in provider_ids
        assert c["registryId"] not in provider_ids
    registry = _load(CANDIDATES)
    assert registry["buckets"]["approved_v1_1_additions"] == []
    for reg in registry["candidates"]:
        if reg.get("sandboxApproved"):
            assert reg["promotionStatus"] == "not_promoted"
            assert reg["sandboxStatus"] == "not_installed"


def test_14_hash_files_match_artifacts():
    assert LOCK_SHA.read_text(encoding="utf-8").strip() == _sha(LOCK)
    assert LOCK_SCHEMA_SHA.read_text(encoding="utf-8").strip() == _sha(LOCK_SCHEMA)
    assert APPROVED_MD_SHA.read_text(encoding="utf-8").strip() == _sha(APPROVED_MD)
    assert CANDIDATES_SHA.read_text(encoding="utf-8").strip() == _sha(CANDIDATES)
    lock = _load(LOCK)
    assert lock["sourceCandidateRegistrySha256"] == _sha(CANDIDATES)
    assert lock["productApprovedShortlistSha256"] == _sha(APPROVED_MD)


def test_15_m210b_preflight_gate6_met_only_when_valid():
    assert LOCK.is_file() and APPROVED_MD.is_file()
    text = PREFLIGHT_M210B.read_text(encoding="utf-8")
    assert "READY FOR M2.10b PHASE 0" in text
    gate6_lines = [
        line
        for line in text.splitlines()
        if ("| 6 |" in line or line.strip().startswith("| 6 "))
        and "shortlist" in line.lower()
    ]
    assert gate6_lines, "Gate 6 shortlist row missing from m2.10b-preflight.md"
    assert "NOT MET" not in gate6_lines[0]
    assert "MET" in gate6_lines[0]


def test_16_no_install_runtime_or_sandbox_evidence():
    registry = _load(CANDIDATES)
    assert registry["safety"]["noInstall"] is True
    assert registry["safety"]["noExecution"] is True
    assert registry["safety"]["noWeightDownload"] is True
    for c in registry["candidates"]:
        assert c["sandboxStatus"] == "not_installed"
        assert c["validationStatus"] == "not_run"
        assert c.get("noInstall", True) is True
        assert c.get("noExecution", True) is True
        assert c.get("noWeightDownload", True) is True
    for rel in (
        "sandboxes",
        "sandbox-output",
        "model-weights",
        "candidate-installs",
    ):
        assert not (ROOT / rel).exists()
    lock = _load(LOCK)
    assert lock["installationAuthorized"] is False
    assert lock["executionAuthorized"] is False
    assert lock["weightDownloadAuthorized"] is False
    assert PROPOSED.is_file()
