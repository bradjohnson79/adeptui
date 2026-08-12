"""M42 Wave 5 — Identity and Visual Continuity unit/integration tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.continuity import SCHEMA_VERSIONS
from app.continuity.evaluator import evaluate_packet, evaluator_capability
from app.continuity.packet_compiler import select_references
from app.continuity.production_gate import evaluate_m42_wave5_gate
from app.db import Asset, Base, Project
from app.continuity import models as continuity_models  # noqa: F401
from app.continuity import service


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    project = Project(id="proj-w5", name="W5 Test")
    session.add(project)
    session.add(
        Asset(
            id="asset-1",
            project_id="proj-w5",
            tag="ref",
            kind="image",
            filename="a.png",
            path="a.png",
        )
    )
    session.add(
        Asset(
            id="asset-2",
            project_id="proj-w5",
            tag="out",
            kind="image",
            filename="b.png",
            path="b.png",
        )
    )
    session.add(Project(id="proj-other", name="Other"))
    session.add(
        Asset(
            id="asset-other",
            project_id="proj-other",
            tag="x",
            kind="image",
            filename="x.png",
            path="x.png",
        )
    )
    session.commit()
    yield session
    session.close()


def test_schema_versions_present():
    assert SCHEMA_VERSIONS["visualIdentitySchemaVersion"] == 1
    assert SCHEMA_VERSIONS["continuityPacketSchemaVersion"] == 1


def test_identity_create_version_immutability(db):
    ident = service.create_identity(
        db, "proj-w5", {"identityType": "character", "canonicalName": "Anadriya"}
    )
    assert ident["visualIdentitySchemaVersion"] == 1
    versions = service.list_versions(db, "proj-w5", ident["id"])
    v1 = versions[0]
    approved = service.approve_version(db, "proj-w5", v1["id"])
    assert approved["status"] == "approved"
    child = service.update_version_or_spawn_draft(
        db, "proj-w5", v1["id"], {"traits": {"eyes": {"mode": "locked", "value": "aqua"}}}
    )
    assert child["versionNumber"] == 2
    assert child["status"] == "draft"
    still = service.list_versions(db, "proj-w5", ident["id"])
    v1_again = next(v for v in still if v["versionNumber"] == 1)
    assert v1_again["traits"] == {}  # approved unchanged


def test_reference_roles_approval_rejection_revocation(db):
    ident = service.create_identity(db, "proj-w5", {"canonicalName": "Korri", "identityType": "character"})
    ver = service.list_versions(db, "proj-w5", ident["id"])[0]
    service.approve_version(db, "proj-w5", ver["id"])
    ref = service.create_reference(
        db,
        "proj-w5",
        {
            "identityId": ident["id"],
            "identityVersionId": ver["id"],
            "assetId": "asset-1",
            "roles": ["canonical_front", "full_body"],
        },
    )
    assert ref["approvalStatus"] == "candidate"
    approved = service.approve_reference(db, "proj-w5", ref["id"])
    assert approved["approvalStatus"] == "approved"
    # Rejected cannot enter selection
    ref2 = service.create_reference(
        db,
        "proj-w5",
        {
            "identityId": ident["id"],
            "identityVersionId": ver["id"],
            "assetId": "asset-2",
            "roles": ["canonical_profile"],
        },
    )
    service.reject_reference(db, "proj-w5", ref2["id"])
    selection = select_references(
        candidates=[
            {
                "id": approved["id"],
                "asset_id": "asset-1",
                "roles": ["canonical_front"],
                "approval_status": "approved",
                "archived": False,
            },
            {
                "id": ref2["id"],
                "asset_id": "asset-2",
                "roles": ["canonical_profile"],
                "approval_status": "rejected",
                "archived": False,
            },
        ],
        preferred_roles=["canonical_front", "canonical_profile"],
        max_references=4,
    )
    assert approved["id"] in [s["id"] for s in selection["selected"]]
    assert ref2["id"] not in [s["id"] for s in selection["selected"]]

    # Revocation does not mutate packets
    service.update_policy(db, "proj-w5", {"enabled": True, "preflightMode": "warn"})
    pf = service.preflight(
        db,
        "proj-w5",
        {
            "bindings": [{"identityId": ident["id"], "requiredRoles": ["canonical_front"]}],
            "workflowSupportsReferences": True,
        },
    )
    assert pf["packetId"]
    packet_before = service.get_packet(db, "proj-w5", pf["packetId"])
    frozen_status = packet_before["bindings"][0]["reference_approval_states"]
    service.revoke_reference(db, "proj-w5", approved["id"], reason="wrong")
    packet_after = service.get_packet(db, "proj-w5", pf["packetId"])
    assert packet_after["bindings"][0]["reference_approval_states"] == frozen_status
    issues = service.list_issues(db, "proj-w5")
    assert any(i["issueType"] == "reference_revoked" for i in issues)


def test_cross_project_reference_denied(db):
    ident = service.create_identity(db, "proj-w5", {"canonicalName": "X"})
    ver = service.list_versions(db, "proj-w5", ident["id"])[0]
    with pytest.raises(Exception) as ei:
        service.create_reference(
            db,
            "proj-w5",
            {
                "identityId": ident["id"],
                "identityVersionId": ver["id"],
                "assetId": "asset-other",
                "roles": ["canonical_front"],
            },
        )
    assert "CROSS_PROJECT" in str(ei.value) or "403" in str(ei.value) or "denied" in str(ei.value).lower()


def test_external_url_rejected(db):
    ident = service.create_identity(db, "proj-w5", {"canonicalName": "Y"})
    ver = service.list_versions(db, "proj-w5", ident["id"])[0]
    with pytest.raises(Exception):
        service.create_reference(
            db,
            "proj-w5",
            {
                "identityId": ident["id"],
                "identityVersionId": ver["id"],
                "assetId": "https://evil.example/ref.png",
                "roles": ["canonical_front"],
            },
        )


def test_multi_identity_packet_and_visibility(db):
    a = service.create_identity(db, "proj-w5", {"canonicalName": "A", "identityType": "character"})
    b = service.create_identity(db, "proj-w5", {"canonicalName": "Env", "identityType": "environment"})
    for ident in (a, b):
        ver = service.list_versions(db, "proj-w5", ident["id"])[0]
        service.approve_version(db, "proj-w5", ver["id"])
    service.update_policy(db, "proj-w5", {"enabled": True, "preflightMode": "warn"})
    pf = service.preflight(
        db,
        "proj-w5",
        {
            "bindings": [
                {
                    "identityId": a["id"],
                    "expectedVisibility": "fully_visible",
                    "expectedView": {"angle": "rear"},
                },
                {
                    "identityId": b["id"],
                    "expectedVisibility": "background",
                    "expectedScreenRole": "environment",
                },
            ]
        },
    )
    assert pf["bindingCount"] == 2
    packet = service.get_packet(db, "proj-w5", pf["packetId"])
    assert len(packet["bindings"]) == 2
    assert packet["frozen"] is True

    result = evaluate_packet(
        packet={"id": packet["id"], "bindings": packet["bindings"]},
        asset_id="asset-2",
        project_id="proj-w5",
    )
    eye_dims = [d for d in result["dimensions"] if d["dimension"] == "eyes"]
    assert eye_dims
    assert eye_dims[0]["status"] == "not_assessable"
    assert eye_dims[0]["score"] is None


def test_evaluator_capability_and_readiness(db):
    cap = evaluator_capability()
    assert cap["deterministic"] is True
    assert "face_structure" in cap["supported_dimensions"]
    ident = service.create_identity(db, "proj-w5", {"canonicalName": "Ready"})
    ready = service.identity_readiness(db, "proj-w5", ident["id"])
    assert ready["kind"] == "identity_readiness"
    assert ready["notContinuityScore"] is True
    assert "Continuity Score" not in ready["label"]


def test_human_review_appends(db):
    ident = service.create_identity(db, "proj-w5", {"canonicalName": "Rev"})
    ver = service.list_versions(db, "proj-w5", ident["id"])[0]
    service.approve_version(db, "proj-w5", ver["id"])
    service.update_policy(db, "proj-w5", {"enabled": True})
    pf = service.preflight(db, "proj-w5", {"bindings": [{"identityId": ident["id"]}]})
    ev = service.evaluate(db, "proj-w5", "asset-2", pf["packetId"])
    assert ev["overallStatus"] in ("review", "not_assessable", "pass", "drift", "error")
    reviewed = service.add_review(
        db,
        "proj-w5",
        ev["id"],
        {"decision": "override_warning", "reason": "Intentional lighting variant", "reviewer": "tester"},
    )
    assert len(reviewed["reviews"]) == 1
    assert reviewed["reviews"][0]["decision"] == "override_warning"
    # Automated result still present
    assert reviewed["overallStatus"] == ev["overallStatus"]


def test_archival_of_approved_identity(db):
    ident = service.create_identity(db, "proj-w5", {"canonicalName": "Keep"})
    ver = service.list_versions(db, "proj-w5", ident["id"])[0]
    service.approve_version(db, "proj-w5", ver["id"])
    result = service.delete_or_archive_identity(db, "proj-w5", ident["id"])
    assert result["action"] == "archived"


def test_wave5_gate_structure():
    g = evaluate_m42_wave5_gate()
    assert g["phase"] == "M42-W5"
    assert "wave5Go" in g
    assert "wave4cPrerequisitePassed" in g
    assert "multiIdentityPacketsOperational" in g
    assert "referenceReadinessHonest" in g


def test_codirector_tools_bound():
    from app.codirector.tools.registry import TOOL_DEFINITIONS, read_handler

    ids = {t.tool_id for t in TOOL_DEFINITIONS}
    assert "continuity.search_identities" in ids
    assert "continuity.propose_correction" in ids
    assert read_handler("continuity.search_identities") is not None
