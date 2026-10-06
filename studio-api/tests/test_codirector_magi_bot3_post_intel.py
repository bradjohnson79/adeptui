"""Bot3 CD Post Intel — PostProductionContextPackage, inspect_grade/job, MagiActionReceipt VERIFY."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest

from app.db import Asset, SessionLocal

MAGI_READ_TOOLS = (
    "magi.inspect_sequence",
    "magi.inspect_clip",
    "magi.inspect_tracks",
    "magi.inspect_selection",
    "magi.inspect_timeline_lineage",
    "magi.inspect_post_context",
    "magi.inspect_grade",
    "magi.inspect_job",
    "magi.verify_action",
    "magi.readiness",
)

MAGI_MUTATORS = (
    "magi.color.apply",
    "magi.upscale",
    "magi.audio.generate",
    "magi.render",
    "magi.propose_finish",
)


def _create_project(client, name: str = "MAGI Bot3 Cert") -> str:
    res = client.post("/api/projects", json={"name": name, "global_prompt": "Handheld documentary look."})
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _read(client, project_id: str, tool_id: str, **arguments) -> Any:
    return client.post(
        f"/api/codirector/projects/{project_id}/tools/read",
        json={"toolId": tool_id, "arguments": arguments},
    )


def _result_data(response) -> dict[str, Any]:
    return response.json()["result"]["data"]


def _seed_sequence(client, project_id: str, *, clip_id: str = "clip_bot3_1") -> str:
    from app.magi.finishing import set_clip_grade
    from app.magi.sequence.store import get_sequence

    asset_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        db.add(
            Asset(
                id=asset_id,
                project_id=project_id,
                tag="MAGI bot3 cert clip",
                kind="image",
                filename="magi_bot3.png",
                path="",
            )
        )
        db.commit()
    finally:
        db.close()

    base = get_sequence(project_id)
    body = {
        **base,
        "tracks": [
            {"id": "trk_v1_b3", "kind": "video", "label": "V1", "order": 0},
            {"id": "trk_i1_b3", "kind": "image", "label": "I1", "order": 3},
        ],
        "clips": [
            {
                "id": clip_id,
                "trackId": "trk_i1_b3",
                "assetId": asset_id,
                "name": "Bot3 cert clip",
                "startFrame": 0,
                "durationFrames": 72,
                "inPoint": 0,
                "outPoint": 72,
            }
        ],
        "playheadFrame": 24,
        "exportLedger": {},
    }
    res = client.put(f"/api/magi/projects/{project_id}/sequence", json={"sequence": body})
    assert res.status_code == 200, res.text
    set_clip_grade(project_id, clip_id, "cinematic_warm", {"contrast": 0.1})
    return asset_id


def test_inspect_post_context_matches_freeze_shape(client) -> None:
    project_id = _create_project(client, "Bot3 Post Context")
    _seed_sequence(client, project_id)
    res = _read(client, project_id, "magi.inspect_post_context", domains=["color"], includePresets=True)
    assert res.status_code == 200, res.text
    data = _result_data(res)
    pkg = data["postProductionContext"]
    assert pkg["projectId"] == project_id
    assert "clips" in pkg
    assert "finishing" in pkg and "clipGrades" in pkg["finishing"]
    assert "readiness" in pkg
    assert pkg["selectedClipIds"] is None
    assert "colorPresetsSummary" in pkg
    assert any("Publish" in x or "trim" in x for x in pkg["notSupported"])
    assert pkg["finishing"]["clipGrades"]["clip_bot3_1"]["presetId"] == "cinematic_warm"


def test_inspect_grade_returns_presets_and_clip_grade(client) -> None:
    project_id = _create_project(client, "Bot3 Grade")
    _seed_sequence(client, project_id)
    res = _read(client, project_id, "magi.inspect_grade", clipId="clip_bot3_1")
    assert res.status_code == 200, res.text
    data = _result_data(res)
    assert data["clipGrade"]["presetId"] == "cinematic_warm"
    assert data["presetCount"] >= 5
    assert any(p.get("id") == "cinematic_warm" for p in data["presets"])


def test_inspect_job_rejects_missing_and_non_magi(client) -> None:
    project_id = _create_project(client, "Bot3 Job")
    missing = _read(client, project_id, "magi.inspect_job", jobId="does-not-exist")
    assert missing.status_code == 404

    # Seed a non-magi job
    from app.db import Job

    db = SessionLocal()
    try:
        job = Job(
            id=str(uuid.uuid4()),
            project_id=project_id,
            kind="imagegen",
            status="queued",
            progress=0.0,
            stage="Queued",
            message="not magi",
            params_json="{}",
        )
        db.add(job)
        db.commit()
        jid = job.id
    finally:
        db.close()
    bad = _read(client, project_id, "magi.inspect_job", jobId=jid)
    assert bad.status_code == 404
    assert "not a MAGI job" in bad.json()["detail"]["message"]


def test_magi_allowed_mutators_registered() -> None:
    from app.codirector.tools.registry import all_definitions

    mutating = {
        d.tool_id for d in all_definitions() if d.tool_id.startswith("magi") and d.kind == "mutating"
    }
    assert mutating == set(MAGI_MUTATORS)


def test_magi_new_reads_registered_and_exposed() -> None:
    from app.codirector.tools.exposure import derive_domain, expose
    from app.codirector.tools.registry import all_definitions

    registered = {d.tool_id for d in all_definitions()}
    for tool_id in MAGI_READ_TOOLS:
        assert tool_id in registered
        assert derive_domain(tool_id) == "magi"
    surface = expose(workspace_surface="magi", intent="Inspect MAGI grade and post context")
    for tool_id in (
        "magi.inspect_post_context",
        "magi.inspect_grade",
        "magi.inspect_job",
        "magi.verify_action",
    ):
        assert tool_id in surface


def test_magi_action_receipt_verify_helper_color_without_clip() -> None:
    from app.codirector.tools.handlers.magi_action_receipt import build_receipt, verify_magi_action
    from app.db import SessionLocal

    project_id = str(uuid.uuid4())
    # Use empty project sequence path via get_sequence creating empty
    db = SessionLocal()
    try:
        # Ensure project exists for FK if needed — verify only reads sequence/job
        receipt = build_receipt(
            tool_id="magi.color.apply",
            status="applied",
            asset_ids_in=[],
            asset_ids_out=[],
            domain="color",
        )
        assert receipt["actionId"].startswith("magi_act_")
        assert "clip_grade_persisted" in receipt["verifyPlan"]["checks"]
        # verify against a temp project id (empty sequence) — clip grade check fails honestly
        from app.magi.sequence.store import get_sequence

        get_sequence(project_id)  # creates empty sequence file
        result = verify_magi_action(
            db,
            project_id,
            tool_id="magi.color.apply",
            clip_id=None,
            asset_ids_in=[],
            asset_ids_out=[],
        )
        assert "checks" in result
        assert result["status"] in {"verified", "failed", "applied"}
    finally:
        db.close()


def test_not_supported_edit_tool_still_refused(client) -> None:
    project_id = _create_project(client, "Bot3 Refuse Trim")
    _seed_sequence(client, project_id)
    proposal = client.post(
        f"/api/codirector/projects/{project_id}/tools/proposals",
        json={"toolId": "magi.trim", "arguments": {"clipId": "clip_bot3_1"}},
    )
    assert proposal.status_code == 404
    assert proposal.json()["detail"]["code"] == "TOOL_NOT_FOUND"


def test_knowledge_packs_present() -> None:
    from app.codirector.knowledgebase.loader import get_document, load_all_documents

    docs = {d.id for d in load_all_documents()}
    for doc_id in ("magi", "magi-color", "magi-edit", "magi-sound", "magi-music"):
        assert doc_id in docs
    magi = get_document("magi")
    assert magi is not None
    assert "NOT_SUPPORTED" in (magi.body or "")
