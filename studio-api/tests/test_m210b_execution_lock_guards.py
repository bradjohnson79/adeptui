"""M2.10b execution-lock guards (sandbox install/execute authorized; production false)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXEC_LOCK = ROOT / "config/capabilities/adept-ui-v1.1-m2.10b-execution-lock.json"
EXEC_SCHEMA = ROOT / "config/capabilities/adept-ui-v1.1-m2.10b-execution-lock.schema.json"
PRODUCT_LOCK = ROOT / "config/capabilities/adept-ui-v1.1-product-approved-sandbox-lock.json"
MANIFEST = ROOT / "config/capabilities/adept-ui-v1.0-provider-manifest.json"
MANIFEST_SHA = ROOT / "config/capabilities/adept-ui-v1.0-provider-manifest.sha256"

EXPECTED_MANIFEST_SHA = "cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc"
CAPABILITIES = (
    "audio.dialogue.generate",
    "audio.sfx.generate",
    "audio.music.generate",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _all_candidates(lock: dict) -> list[dict]:
    out: list[dict] = []
    for cap in CAPABILITIES:
        out.extend(lock["candidatesByCapability"][cap])
    return out


def test_01_execution_lock_exists_and_schema():
    assert EXEC_LOCK.is_file()
    assert EXEC_SCHEMA.is_file()
    lock = _load(EXEC_LOCK)
    schema = _load(EXEC_SCHEMA)
    assert lock["schemaVersion"] == schema["properties"]["schemaVersion"]["const"]
    assert lock["lockId"] == schema["properties"]["lockId"]["const"]
    for key in schema["required"]:
        assert key in lock
    assert lock["approvalScope"] == "sandbox_evaluation_only"
    assert lock["productionAuthorized"] is False
    assert lock["installationAuthorized"] is True
    assert lock["executionAuthorized"] is True
    assert lock["weightDownloadAuthorized"] is True


def test_02_exactly_nine_candidates():
    lock = _load(EXEC_LOCK)
    assert lock.get("authorizedCandidateCount", len(_all_candidates(lock))) == 9
    assert len(_all_candidates(lock)) == 9
    for cap in CAPABILITIES:
        assert len(lock["candidatesByCapability"][cap]) == 3


def test_03_subset_of_product_lock():
    from app.codirector.m210b.execution_lock import (
        assert_subset_of_product_lock,
        clear_lock_caches,
    )

    clear_lock_caches()
    assert_subset_of_product_lock()
    exe = _load(EXEC_LOCK)
    product = _load(PRODUCT_LOCK)
    product_ids = {c["registryId"] for c in _all_candidates(product)}
    product_keys = {c["sourceKey"] for c in _all_candidates(product)}
    for c in _all_candidates(exe):
        assert c["registryId"] in product_ids
        assert c["sourceKey"] in product_keys


def test_04_execution_lock_flags_authorize_sandbox():
    lock = _load(EXEC_LOCK)
    for c in _all_candidates(lock):
        assert c.get("productionAuthorized", c.get("productionApproved")) is False
        assert c["installationAuthorized"] is True
        assert c["executionAuthorized"] is True
        assert c["weightDownloadAuthorized"] is True
        assert c["sandboxOnly"] is True


def test_05_product_lock_still_blocks_install_execute():
    lock = _load(PRODUCT_LOCK)
    assert lock["installationAuthorized"] is False
    assert lock["executionAuthorized"] is False
    assert lock["weightDownloadAuthorized"] is False
    assert lock["productionApproved"] is False
    for c in _all_candidates(lock):
        assert c["installationAuthorized"] is False
        assert c["executionAuthorized"] is False
        assert c["weightDownloadAuthorized"] is False
        assert c["productionApproved"] is False


def test_06_provider_manifest_sha_unchanged():
    digest = _sha(MANIFEST)
    assert digest == EXPECTED_MANIFEST_SHA
    assert MANIFEST_SHA.read_text(encoding="utf-8").strip() == digest
    lock = _load(EXEC_LOCK)
    assert lock["providerManifestSha256"] == digest


def test_07_unapproved_registry_id_cannot_execute():
    from app.codirector.m210b.execution_lock import clear_lock_caches, is_execution_authorized
    from app.codirector.m210b.registry import get_adapter

    clear_lock_caches()
    assert is_execution_authorized("m2101-dialogue-001") is True
    assert is_execution_authorized("not-a-real-candidate") is False
    assert is_execution_authorized("m2101-unapproved-999") is False
    assert get_adapter("not-a-real-candidate") is None
