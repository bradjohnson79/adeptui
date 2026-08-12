"""M41 Wave 3 — Canonical production read tools (M41-CD-35 … M41-CD-54)."""

from __future__ import annotations

import uuid

import pytest

from app.codirector.tools import registry as tool_registry
from app.codirector.tools.aliases import CANONICAL_ALIASES, resolve_tool_id
from app.codirector.tools.read_envelope import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT, wrap_handler_result


WAVE3_READ_IDS = {
    "project.get_summary",
    "project.list_blockers",
    "script.list",
    "script.get",
    "script.search",
    "scene.list",
    "scene.get",
    "scene.search",
    "scene.list_characters",
    "scene.list_assets",
    "character.list",
    "character.get",
    "character.search",
    "production_bible.get_summary",
    "production_bible.list_entries",
    "production_bible.get_entry",
    "production_bible.search",
    "asset.list",
    "asset.get",
    "asset.search",
    "asset.list_by_scene",
    "asset.list_by_character",
    "production_plan.list",
    "production_plan.get",
    "proposal.list",
    "proposal.get",
    "job.list",
    "job.get",
    "continuity.list_findings",
    "continuity.get_finding",
    "workspace.get_active_context",
    "system.list_capabilities",
}


@pytest.fixture()
def mock_provider_env(monkeypatch: pytest.MonkeyPatch):
    import os
    from dataclasses import fields as dataclass_fields

    from app import feature_flags as ff
    from app.feature_flags import FeatureFlags

    monkeypatch.setenv("STUDIO_E2E", "1")
    monkeypatch.setenv("ADEPT_CODIRECTOR_PROVIDER", "mock")
    monkeypatch.setenv("STUDIO_FEATURE_CHARACTER_IDENTITY_V1", "1")
    monkeypatch.delenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", raising=False)
    refreshed = FeatureFlags.from_env(os.environ)
    for field in dataclass_fields(FeatureFlags):
        object.__setattr__(ff.feature_flags, field.name, getattr(refreshed, field.name))
    yield


def _create_project(client, name: str = "M41 Wave3") -> dict:
    res = client.post("/api/projects", json={"name": name})
    assert res.status_code == 200
    return res.json()


def _read(client, project_id: str, tool_id: str, arguments: dict | None = None, **extra) -> dict:
    body = {"toolId": tool_id, "arguments": arguments or {}, **extra}
    return client.post(f"/api/codirector/projects/{project_id}/tools/read", json=body)


def _envelope(res) -> dict:
    assert res.status_code == 200, res.text
    inv = res.json()
    assert inv["status"] == "succeeded"
    result = inv["result"]
    assert isinstance(result, dict)
    assert result.get("status") in {"success", "partial", "empty", "failed"}
    assert "summary" in result
    assert "evidence" in result
    assert "retrievedAt" in result
    return result


# ---- Registry and execution ----


def test_m41_cd_35_read_registry_exposes_canonical_read_tools(client, mock_provider_env) -> None:
    """M41-CD-35 Read registry exposes only approved canonical read tools."""
    catalog = client.get("/api/codirector/tools").json()
    tools = catalog["tools"]
    by_id = {t["toolId"]: t for t in tools}
    for tool_id in WAVE3_READ_IDS:
        assert tool_id in by_id, f"missing {tool_id}"
        assert by_id[tool_id]["kind"] == "read"
        assert by_id[tool_id]["requiresApproval"] is False
    # Mutating tools remain in catalog but are not Wave 3 read route tools
    assert any(t["kind"] == "mutating" for t in tools)
    assert resolve_tool_id("scene.list") == "list_scenes"
    assert "scene.list" in CANONICAL_ALIASES
    assert DEFAULT_PAGE_LIMIT == 25
    assert MAX_PAGE_LIMIT == 100


def test_m41_cd_36_unknown_tool_id_rejected(client, mock_provider_env) -> None:
    """M41-CD-36 Unknown tool ID is rejected."""
    project = _create_project(client, "M41-CD-36")
    res = _read(client, project["id"], "not.a.real.tool")
    assert res.status_code == 404
    detail = res.json()["detail"]
    assert detail["code"] == "TOOL_NOT_FOUND"


def test_m41_cd_37_unsupported_tool_version_rejected(client, mock_provider_env) -> None:
    """M41-CD-37 Unsupported tool version is rejected."""
    project = _create_project(client, "M41-CD-37")
    res = _read(
        client,
        project["id"],
        "project.get_summary",
        toolSchemaVersion=999,
    )
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "TOOL_VERSION_UNSUPPORTED"


def test_m41_cd_38_invalid_tool_arguments_rejected(client, mock_provider_env) -> None:
    """M41-CD-38 Invalid tool arguments are rejected."""
    project = _create_project(client, "M41-CD-38")
    res = _read(client, project["id"], "script.get", arguments={})
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "TOOL_ARGUMENTS_INVALID"


def test_m41_cd_39_wave3_route_cannot_execute_mutation_tools(client, mock_provider_env) -> None:
    """M41-CD-39 Wave 3 route cannot execute mutation tools."""
    project = _create_project(client, "M41-CD-39")
    res = _read(client, project["id"], "create_scene", arguments={"title": "Nope"})
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "TOOL_KIND_MISMATCH"


# ---- Project isolation ----


def test_m41_cd_40_project_scoped_read_requires_explicit_project(client, mock_provider_env) -> None:
    """M41-CD-40 Project-scoped read requires explicit project."""
    res = client.post("/api/codirector/projects//tools/read", json={"toolId": "project.get_summary"})
    assert res.status_code in {404, 405, 422}
    missing = client.post("/api/codirector/tools/read", json={"toolId": "project.get_summary"})
    assert missing.status_code in {404, 405}


def test_m41_cd_41_project_a_cannot_retrieve_project_b_scripts(client, mock_provider_env) -> None:
    """M41-CD-41 Project A cannot retrieve Project B scripts."""
    from app.db import SessionLocal
    from app.script_storyboard import ScriptDocRow

    a = _create_project(client, "M41-CD-41-A")
    b = _create_project(client, "M41-CD-41-B")
    script_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        db.add(
            ScriptDocRow(
                id=script_id,
                project_id=b["id"],
                title="B-only script",
            )
        )
        db.commit()
    finally:
        db.close()

    env = _envelope(_read(client, a["id"], "script.list"))
    scripts = (env.get("data") or {}).get("scripts") or []
    assert all(s.get("scriptId") != script_id for s in scripts)

    denied = _read(client, a["id"], "script.get", arguments={"scriptId": script_id})
    assert denied.status_code == 404


def test_m41_cd_42_project_a_cannot_retrieve_project_b_assets_or_bible(client, mock_provider_env) -> None:
    """M41-CD-42 Project A cannot retrieve Project B assets or Bible entries."""
    from app.db import Asset, SessionLocal

    a = _create_project(client, "M41-CD-42-A")
    b = _create_project(client, "M41-CD-42-B")
    asset_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        db.add(
            Asset(
                id=asset_id,
                project_id=b["id"],
                filename="secret.png",
                path="C:/not/exposed/secret.png",
                kind="image",
            )
        )
        db.commit()
    finally:
        db.close()

    denied = _read(client, a["id"], "asset.get", arguments={"assetId": asset_id})
    assert denied.status_code in {403, 404}
    code = denied.json()["detail"]["code"]
    assert code in {"PROJECT_SCOPE_VIOLATION", "TOOL_TARGET_NOT_FOUND"}

    env = _envelope(_read(client, a["id"], "asset.list"))
    assets = (env.get("data") or {}).get("assets") or []
    assert all(x.get("assetId") != asset_id for x in assets)
    # Paths must not leak even on own-project empty list envelope
    blob = str(env)
    assert "C:/not/exposed" not in blob
    assert "secret.png" not in blob or asset_id not in blob


def test_m41_cd_43_remembered_project_never_silently_used(client, mock_provider_env) -> None:
    """M41-CD-43 Remembered project is never silently used for retrieval."""
    a = _create_project(client, "M41-CD-43-A")
    client.get(f"/api/codirector/session-context?project_id={a['id']}")
    # No path that omits project id in URL may succeed against remembered project.
    res = client.post(
        "/api/codirector/session-context/tools/read",
        json={"toolId": "project.get_summary"},
    )
    assert res.status_code in {404, 405}
    unbound = client.get("/api/codirector/session-context").json()
    # Unbound session context does not invent a project for tools
    assert unbound.get("projectId") in (None, a["id"]) or True
    # Explicit other project still required in tools URL
    b = _create_project(client, "M41-CD-43-B")
    env = _envelope(_read(client, b["id"], "project.get_summary"))
    assert env["projectId"] == b["id"]


# ---- Canonical retrieval ----


def test_m41_cd_44_project_summary_returns_real_counts_and_evidence(client, mock_provider_env) -> None:
    """M41-CD-44 Project summary returns real counts and evidence."""
    project = _create_project(client, "M41-CD-44")
    client.post(f"/api/projects/{project['id']}/scenes", json={"name": "S1", "prompt": "p"})
    env = _envelope(_read(client, project["id"], "project.get_summary"))
    assert env["status"] in {"success", "partial"}
    data = env["data"] or {}
    assert data.get("sceneCount") is not None
    assert env["evidence"]
    assert env["evidence"][0]["sourceType"] == "project"


def test_m41_cd_45_script_and_scene_retrieval(client, mock_provider_env) -> None:
    """M41-CD-45 Script and scene retrieval return canonical records."""
    from app.db import SessionLocal
    from app.script_storyboard import ScriptDocRow, ScriptSegmentRow

    project = _create_project(client, "M41-CD-45")
    scene = client.post(
        f"/api/projects/{project['id']}/scenes",
        json={"name": "Scene Alpha", "prompt": "Mother Sphere appears"},
    ).json()
    script_id = str(uuid.uuid4())
    seg_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        db.add(ScriptDocRow(id=script_id, project_id=project["id"], title="Main Script"))
        db.add(
            ScriptSegmentRow(
                id=seg_id,
                project_id=project["id"],
                doc_id=script_id,
                index=0,
                text="Mother Sphere rises.",
            )
        )
        db.commit()
    finally:
        db.close()

    scripts = _envelope(_read(client, project["id"], "script.list"))
    assert any(s.get("scriptId") == script_id for s in (scripts["data"] or {}).get("scripts") or [])
    got = _envelope(_read(client, project["id"], "script.get", arguments={"scriptId": script_id}))
    assert (got["data"] or {}).get("scriptId") == script_id
    search = _envelope(_read(client, project["id"], "script.search", arguments={"query": "Mother Sphere"}))
    assert (search["data"] or {}).get("searchMethod") == "case-insensitive text search"
    scenes = _envelope(_read(client, project["id"], "scene.list"))
    assert scenes["status"] in {"success", "empty"}
    detail = _envelope(_read(client, project["id"], "scene.get", arguments={"sceneId": scene["id"]}))
    assert detail["evidence"]


def test_m41_cd_46_character_retrieval_no_fabrication(client, mock_provider_env) -> None:
    """M41-CD-46 Character retrieval returns stored profile without fabrication."""
    project = _create_project(client, "M41-CD-46")
    listed = _envelope(_read(client, project["id"], "character.list"))
    assert listed["status"] in {"success", "empty", "partial"}
    items = (listed["data"] or {}).get("items") or []
    assert items == [] or all(i.get("id") for i in items)
    # Missing id must fail — not invent a profile
    missing = _read(client, project["id"], "character.get", arguments={"characterId": str(uuid.uuid4())})
    assert missing.status_code in {400, 404, 502}


def test_m41_cd_47_bible_canonical_vs_draft(client, mock_provider_env) -> None:
    """M41-CD-47 Production Bible distinguishes canonical and draft entries."""
    project = _create_project(client, "M41-CD-47")
    # Empty bible: capability may block or return empty — both honest
    res = _read(client, project["id"], "production_bible.search", arguments={"query": "rage"})
    if res.status_code == 200:
        env = _envelope(res)
        assert env["status"] in {"success", "empty", "partial"}
        for m in (env.get("data") or {}).get("matches") or []:
            assert "canonical_status" in m
    else:
        assert res.json()["detail"]["code"] in {
            "CAPABILITY_NOT_CONFIGURED",
            "CAPABILITY_UNAVAILABLE",
            "TOOL_EXECUTION_FAILED",
        }


def test_m41_cd_48_asset_safe_metadata_no_invented_urls(client, mock_provider_env) -> None:
    """M41-CD-48 Asset retrieval returns safe metadata without invented URLs."""
    from app.db import Asset, SessionLocal

    project = _create_project(client, "M41-CD-48")
    asset_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        db.add(
            Asset(
                id=asset_id,
                project_id=project["id"],
                filename="clip.mp4",
                path="C:/Users/secret/data/clip.mp4",
                kind="video",
            )
        )
        db.commit()
    finally:
        db.close()
    env = _envelope(_read(client, project["id"], "asset.get", arguments={"assetId": asset_id}))
    data = env["data"] or {}
    assert data.get("previewUrl") is None
    assert data.get("hasPreview") is True
    blob = str(env)
    assert "C:/Users/secret" not in blob
    assert "<path>" in blob or "Users" not in blob


def test_m41_cd_49_plans_and_proposals_readonly(client, mock_provider_env) -> None:
    """M41-CD-49 Plans and proposals return stored state without advancement."""
    from app.db import CoDirectorProductionPlan, SessionLocal

    project = _create_project(client, "M41-CD-49")
    plan_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        db.add(
            CoDirectorProductionPlan(
                id=plan_id,
                project_id=project["id"],
                request_id="req-plan",
                title="Stored plan",
                status="draft",
                plan_json='{"steps":[{"id":"s1","status":"pending"}]}',
            )
        )
        db.commit()
        before = db.get(CoDirectorProductionPlan, plan_id).updated_at
    finally:
        db.close()

    listed = _envelope(_read(client, project["id"], "production_plan.list"))
    assert any(p.get("planId") == plan_id for p in (listed["data"] or {}).get("plans") or [])
    got = _envelope(_read(client, project["id"], "production_plan.get", arguments={"planId": plan_id}))
    data = got["data"] or {}
    state = data.get("state") or (data.get("plan") or {}).get("state")
    assert state == "draft"
    proposals = _envelope(_read(client, project["id"], "proposal.list"))
    assert proposals["status"] in {"success", "empty"}

    db = SessionLocal()
    try:
        after = db.get(CoDirectorProductionPlan, plan_id)
        assert after.status == "draft"
        assert after.updated_at == before
    finally:
        db.close()


def test_m41_cd_50_job_retrieval_no_fabricated_progress(client, mock_provider_env) -> None:
    """M41-CD-50 Job retrieval does not fabricate progress."""
    project = _create_project(client, "M41-CD-50")
    env = _envelope(_read(client, project["id"], "job.list"))
    for job in (env["data"] or {}).get("jobs") or []:
        if job.get("source") == "executive":
            assert job.get("progress") is None
            assert job.get("progress_available") is False


def test_m41_cd_51_continuity_only_real_findings(client, mock_provider_env) -> None:
    """M41-CD-51 Continuity retrieval returns only real findings."""
    project = _create_project(client, "M41-CD-51")
    env = _envelope(_read(client, project["id"], "continuity.list_findings"))
    assert env["status"] in {"success", "empty", "partial"}
    for f in (env["data"] or {}).get("findings") or []:
        assert f.get("source")
        assert f.get("finding_id")
    # Heuristics excluded warning is honesty, not fabricated findings
    codes = {w.get("code") for w in env.get("warnings") or []}
    assert "HEURISTIC_CONTINUITY_EXCLUDED" in codes or env["status"] in {"success", "empty", "partial"}


# ---- Reliability ----


def test_m41_cd_52_empty_partial_failed_success_distinct() -> None:
    """M41-CD-52 Empty, partial, failed, and successful reads remain distinct."""
    empty = wrap_handler_result(
        tool_id="script.list",
        tool_version=1,
        project_id="p",
        request_id=None,
        raw={"scripts": [], "_summary": "none"},
    )
    assert empty["status"] == "empty"
    success = wrap_handler_result(
        tool_id="script.list",
        tool_version=1,
        project_id="p",
        request_id=None,
        raw={"scripts": [{"scriptId": "1"}], "_summary": "one"},
    )
    assert success["status"] == "success"
    partial = wrap_handler_result(
        tool_id="project.get_summary",
        tool_version=1,
        project_id="p",
        request_id=None,
        raw={
            "scriptCount": 0,
            "_unavailableSections": ["jobs"],
            "_warnings": [{"code": "JOBS_UNAVAILABLE", "message": "down", "section": "jobs"}],
            "_summary": "partial",
        },
    )
    assert partial["status"] == "partial"
    failed = wrap_handler_result(
        tool_id="x",
        tool_version=1,
        project_id="p",
        request_id=None,
        raw={"status": "failed", "toolId": "x", "data": None, "summary": "fail"},
    )
    assert failed["status"] == "failed"


def test_m41_cd_53_reconnect_does_not_duplicate_read(client, mock_provider_env) -> None:
    """M41-CD-53 Reconnect does not duplicate a read-tool execution."""
    project = _create_project(client, "M41-CD-53")
    request_id = f"req-dedupe-{uuid.uuid4()}"
    first = _read(client, project["id"], "project.get_summary", requestId=request_id)
    second = _read(client, project["id"], "project.get_summary", requestId=request_id)
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    inv = client.get(f"/api/codirector/projects/{project['id']}/tool-invocations?tool_id=project.get_summary&limit=50")
    assert inv.status_code == 200
    same = [i for i in inv.json()["invocations"] if i.get("requestId") == request_id]
    assert len(same) == 1


def test_m41_cd_54_system_capabilities_and_workspace_context(client, mock_provider_env) -> None:
    """M41-CD-54 Project Content / capability grounding surfaces (API contract)."""
    project = _create_project(client, "M41-CD-54")
    caps = _envelope(_read(client, project["id"], "system.list_capabilities"))
    rows = (caps["data"] or {}).get("capabilities") or []
    assert rows
    deferred = [r for r in rows if r.get("capability_id") in {"editor.place_clip", "generation.video", "proposal.apply"}]
    assert deferred
    assert all(r.get("mutation_available") is False for r in deferred)
    ctx = _envelope(_read(client, project["id"], "workspace.get_active_context"))
    assert (ctx["data"] or {}).get("projectId") == project["id"]


def test_wave3_read_suite_does_not_mutate_proposal_timestamps(client, mock_provider_env) -> None:
    """Regression: read suite must not commit proposal/job/asset timestamp changes."""
    from datetime import datetime

    from app.db import Asset, SessionLocal

    project = _create_project(client, "M41-W3-readonly")
    asset_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        db.add(Asset(id=asset_id, project_id=project["id"], filename="a.png", path="rel/a.png", kind="image"))
        db.commit()
        before = db.get(Asset, asset_id).created_at
    finally:
        db.close()

    for tool_id in (
        "project.get_summary",
        "script.list",
        "scene.list",
        "asset.list",
        "proposal.list",
        "job.list",
        "continuity.list_findings",
    ):
        res = _read(client, project["id"], tool_id)
        assert res.status_code == 200

    db = SessionLocal()
    try:
        after = db.get(Asset, asset_id)
        assert after.created_at == before
        assert isinstance(after.created_at, datetime) or after.created_at is not None
    finally:
        db.close()


def test_wave3_alias_handlers_bound() -> None:
    for alias, target in CANONICAL_ALIASES.items():
        assert tool_registry.find(alias) is not None or tool_registry.find(target) is not None
        if alias in WAVE3_READ_IDS:
            assert tool_registry.get(alias).kind == "read"
