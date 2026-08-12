"""M42 Wave 6P — Scene Reference Binding domain tests."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Asset, Base, Project
from app.scene_references import models as _sr_models  # noqa: F401
from app.scene_references import service
from app.scene_references.capability import get_capability, support_status_for
from app.scene_references.inheritance import ancestor_chain, merge_inherited
from app.scene_references.production_gate import evaluate_m42_w6p_scene_reference_gate


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
    session.add(Project(id="proj-w6p", name="W6P Test"))
    session.add(
        Asset(
            id="asset-1",
            project_id="proj-w6p",
            tag="hero",
            kind="image",
            filename="a.png",
            path="a.png",
        )
    )
    session.add(
        Asset(
            id="asset-2",
            project_id="proj-w6p",
            tag="env",
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


def test_capability_honesty_txt2vid_prompt_guided():
    cap = get_capability("text_to_video")
    assert cap is not None
    assert cap.support_class == "prompt_guided"
    assert cap.image_conditioning is False
    assert support_status_for("text_to_video") == "prompt_guided"
    assert support_status_for("one_frame") == "reference_conditioned"


def test_attach_list_enable_remove(db):
    b = service.attach(
        db,
        "proj-w6p",
        {
            "asset_id": "asset-1",
            "scope_type": "scene",
            "scope_id": "scene-1",
            "reference_type": "character",
            "usage_modes": ["appearance"],
            "reference_roles": ["character"],
        },
    )
    assert b["id"]
    assert b["asset_id"] == "asset-1"
    items = service.list_for_scope(db, "proj-w6p", "scene", "scene-1")
    assert len(items) == 1
    updated = service.update(db, "proj-w6p", b["id"], {"enabled": False})
    assert updated["enabled"] is False
    removed = service.remove(db, "proj-w6p", b["id"])
    assert removed["ok"] is True
    assert removed["assetDeleted"] is False
    assert service.list_for_scope(db, "proj-w6p", "scene", "scene-1") == []


def test_cross_project_denied(db):
    with pytest.raises(HTTPException) as ei:
        service.attach(
            db,
            "proj-w6p",
            {
                "asset_id": "asset-other",
                "scope_type": "scene",
                "scope_id": "scene-1",
                "reference_type": "character",
                "usage_modes": ["appearance"],
            },
        )
    assert ei.value.status_code == 403


def test_inheritance_override(db):
    service.attach(
        db,
        "proj-w6p",
        {
            "asset_id": "asset-1",
            "scope_type": "scene",
            "scope_id": "scene-1",
            "reference_type": "character",
            "usage_modes": ["appearance"],
        },
    )
    service.attach(
        db,
        "proj-w6p",
        {
            "asset_id": "asset-2",
            "scope_type": "shot",
            "scope_id": "shot-1",
            "reference_type": "environment",
            "usage_modes": ["environment"],
        },
    )
    merged = service.list_for_scope(
        db,
        "proj-w6p",
        "shot",
        "shot-1",
        include_inherited=True,
        scene_id="scene-1",
    )
    types = {m["reference_type"] for m in merged}
    assert "character" in types
    assert "environment" in types


def test_preflight_limit_explainability(db):
    # Attach more than max for text_to_video (6)
    for i in range(8):
        aid = f"asset-bulk-{i}"
        db.add(
            Asset(
                id=aid,
                project_id="proj-w6p",
                tag=f"t{i}",
                kind="image",
                filename=f"{i}.png",
                path=f"{i}.png",
            )
        )
    db.commit()
    for i in range(8):
        service.attach(
            db,
            "proj-w6p",
            {
                "asset_id": f"asset-bulk-{i}",
                "scope_type": "scene",
                "scope_id": "scene-lim",
                "reference_type": "style" if i % 2 == 0 else "prop",
                "usage_modes": ["style"] if i % 2 == 0 else ["prop"],
            },
        )
    pf = service.preflight(
        db,
        "proj-w6p",
        scope_type="scene",
        scope_id="scene-lim",
        workflow_key="text_to_video",
    )
    assert pf["ok"] is True
    assert pf["supportClass"] == "prompt_guided"
    assert pf["imageConditioning"] is False
    assert len(pf["selected"]) == 6
    assert len(pf["excluded"]) == 2
    prov = pf["provenance"]
    for eid in prov["excludedReferenceIds"]:
        assert prov["exclusionReasons"][eid] == "excluded_by_limit"
    assert "bindingIds" in prov


def test_merge_inherited_marks_override():
    chain = ancestor_chain("shot", "shot-1", project_id="p1", scene_id="scene-1")
    by = {
        ("project", "p1"): [
            {"id": "a", "asset_id": "x", "reference_type": "character", "enabled": True, "order_index": 0}
        ],
        ("scene", "scene-1"): [
            {"id": "b", "asset_id": "x", "reference_type": "character", "enabled": True, "order_index": 0}
        ],
        ("shot", "shot-1"): [],
    }
    merged = merge_inherited(by, chain)
    assert len(merged) == 1
    assert merged[0]["id"] == "b"
    assert merged[0]["is_override"] is True


def test_asset_usage_blocks_delete_signal(db):
    service.attach(
        db,
        "proj-w6p",
        {
            "asset_id": "asset-1",
            "scope_type": "scene",
            "scope_id": "s1",
            "reference_type": "character",
            "usage_modes": ["appearance"],
        },
    )
    usage = service.asset_usage(db, "proj-w6p", "asset-1")
    assert usage["activeBindingCount"] == 1
    assert usage["deleteBlocked"] is True


def test_copy_scope(db):
    service.attach(
        db,
        "proj-w6p",
        {
            "asset_id": "asset-1",
            "scope_type": "scene",
            "scope_id": "prev",
            "reference_type": "character",
            "usage_modes": ["appearance"],
        },
    )
    created = service.copy_scope(
        db,
        "proj-w6p",
        source_scope_type="scene",
        source_scope_id="prev",
        target_scope_type="scene",
        target_scope_id="next",
    )
    assert len(created) == 1
    assert created[0]["scope_id"] == "next"


def test_scene_reference_gate_structure():
    g = evaluate_m42_w6p_scene_reference_gate()
    assert "sceneReferenceAddendumGo" in g
    assert g.get("binaryOnly") is True
    assert g.get("conditionalGoForbidden") is True
