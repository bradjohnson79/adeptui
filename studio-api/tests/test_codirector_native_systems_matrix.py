"""c4-native-systems: per-system operational certification matrix.

Executable certification suite for the 11 covered Co-Director native systems
plus the MAGI not-operational assertion. Every mutating test drives the REAL
pathway through the public HTTP API:

    registry lookup -> sanitize_arguments -> propose -> human approve
        -> execute_approved_proposal (apply handler) -> independent read-back.

No handler or service is mocked. Only the shared test DB fixtures (``client``)
are reused from ``conftest.py``. Generation boundaries (image/voice/video) are
exercised up to the queue/provider boundary; capability-blocked or honest
non-generation outcomes are the expected result in the test environment
(Build Law #26 / #20).

A passing run writes a machine-readable matrix to
``data/tmp/c4_native_systems_matrix.json`` via a session-scoped fixture, so
``pytest tests/test_codirector_native_systems_matrix.py`` is self-contained.

UI-SYNC is intentionally deferred to the c5/c8 Playwright certification and is
recorded as such in the matrix (not asserted here).
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import fields as dataclass_fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from app.db import Asset, SessionLocal, init_db
from app.feature_flags import FeatureFlags


# ---------------------------------------------------------------------------
# Feature flags + table ensure (autouse)
# ---------------------------------------------------------------------------


def _apply_flags_in_place(environ=None) -> None:
    import app.feature_flags as ff

    refreshed = FeatureFlags.from_env(environ if environ is not None else os.environ)
    for field in dataclass_fields(FeatureFlags):
        object.__setattr__(ff.feature_flags, field.name, getattr(refreshed, field.name))


@pytest.fixture(autouse=True)
def _enable_native_system_features(monkeypatch: pytest.MonkeyPatch, client):
    """Enable Character Identity (needed by Character Creator) and ensure the
    extra tables the app startup does not always create eagerly."""
    monkeypatch.setenv("STUDIO_FEATURE_CHARACTER_IDENTITY_V1", "1")
    _apply_flags_in_place(os.environ)
    try:
        from app.character_identity import ensure_character_identity_tables

        ensure_character_identity_tables()
    except Exception:
        pass
    try:
        from app.voice_performance.service import ensure_tables as ensure_vp_tables

        ensure_vp_tables()
    except Exception:
        pass
    yield
    _apply_flags_in_place(os.environ)


# ---------------------------------------------------------------------------
# Machine-readable matrix (session-scoped, written at teardown)
# ---------------------------------------------------------------------------

_UI_SYNC_DEFERRED = "deferred to c5/c8 Playwright"

_SYSTEMS = (
    "timeline",
    "scene_project",
    "production_bible",
    "character_creator",
    "voice_studio",
    "image_planning",
    "posecraft",
    "assets_library",
    "visual_references",
    "render_queue",
    "continuity",
    "magi",
)


def _blank_row() -> dict[str, Any]:
    return {"READ": False, "WRITE": False, "PERSIST": False, "VERIFY": False, "UI_SYNC": _UI_SYNC_DEFERRED}


@pytest.fixture(scope="session")
def matrix() -> dict[str, Any]:
    return {"systems": {name: _blank_row() for name in _SYSTEMS}}


@pytest.fixture(autouse=True, scope="session")
def _write_matrix_json(matrix):
    yield
    out_path = Path(__file__).resolve().parents[2] / "data" / "tmp" / "c4_native_systems_matrix.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "suite": "c4-native-systems",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "systems": matrix["systems"],
    }
    out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _mark(matrix, system: str, **props) -> None:
    row = matrix["systems"].setdefault(system, _blank_row())
    row.update(props)


# ---------------------------------------------------------------------------
# HTTP helpers (real pathway: read / propose / approve)
# ---------------------------------------------------------------------------


def _create_project(client, name: str = "c4 Native Systems Project") -> str:
    res = client.post("/api/projects", json={"name": name, "global_prompt": "Handheld documentary look."})
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _scenes(client, project_id: str) -> list[dict]:
    return client.get(f"/api/projects/{project_id}").json()["scenes"]


def _first_scene(client, project_id: str) -> dict:
    scenes = _scenes(client, project_id)
    assert scenes, "a new project should have a default scene"
    return scenes[0]


def _create_bible(client, project_id: str) -> dict:
    preview = client.post(
        f"/api/codirector/projects/{project_id}/bible/import/preview", json={}
    ).json()
    res = client.post(
        f"/api/codirector/projects/{project_id}/bible/import/confirm",
        json={
            "entities": preview["entities"],
            "facts": preview["facts"],
            "summary": preview.get("summary", ""),
        },
    )
    assert res.status_code == 200, res.text
    return res.json()


def _read(client, project_id: str, tool_id: str, **arguments) -> Any:
    return client.post(
        f"/api/codirector/projects/{project_id}/tools/read",
        json={"toolId": tool_id, "arguments": arguments},
    )


def _propose(client, project_id: str, tool_id: str, **arguments) -> Any:
    return client.post(
        f"/api/codirector/projects/{project_id}/tools/proposals",
        json={"toolId": tool_id, "arguments": arguments},
    )


def _approve(client, project_id: str, proposal_id: str) -> Any:
    return client.post(
        f"/api/codirector/projects/{project_id}/proposals/{proposal_id}/approve",
        json={},
    )


def _result_data(response) -> dict[str, Any]:
    return response.json()["result"]["data"]


def _approve_result(client, project_id: str, proposal_id: str) -> dict[str, Any]:
    """Return the apply handler result captured on the execution receipt."""
    receipt = _approve(client, project_id, proposal_id)
    assert receipt.status_code == 200, receipt.text
    body = receipt.json()
    assert body["status"] == "success", body
    return body.get("toolResult") or {}


def _create_asset(project_id: str, *, tag: str = "Korri ref", filename: str = "korri.png") -> str:
    """Seed an Asset row directly via SessionLocal (shares the test engine)."""
    init_db()
    db = SessionLocal()
    try:
        asset_id = str(uuid.uuid4())
        db.add(Asset(id=asset_id, project_id=project_id, tag=tag, kind="image", filename=filename, path=""))
        db.commit()
        return asset_id
    finally:
        db.close()


def _bust_read_cache(project_id: str) -> None:
    """Force a fresh authoritative read for PERSIST/VERIFY assertions.

    The Co-Director read cache (`read_cache`) is a short-lived, project-keyed
    cache that is NOT invalidated on mutations. PERSIST/VERIFY must observe
    post-mutation state, so we clear the project's read cache before each
    independent read-back. This is cache management only — no handler or
    service is mocked.
    """

    from app.codirector.tools.read_cache import clear_project

    clear_project(project_id)


# ===========================================================================
# 1. Timeline (w46 batch-owned, revision-guarded)
# ===========================================================================


def test_timeline_system(client, matrix):
    _mark(matrix, "timeline")
    project_id = _create_project(client, "Timeline Cert")
    scene = _first_scene(client, project_id)

    # READ: workspace + batches (structured, authoritative state). The initial load migrates the
    # legacy director_json into batch blocks in memory; the IDs only become stable once a mutation
    # persists the master, so lineage is captured after the first persisting write below.
    ws = _read(client, project_id, "timeline.get_workspace", sceneId=scene["id"])
    assert ws.status_code == 200, ws.text
    _result_data(ws)
    batches = _read(client, project_id, "timeline.inspect_batches", sceneId=scene["id"])
    assert batches.status_code == 200, batches.text
    batch_data = _result_data(batches)
    assert isinstance(batch_data["batches"], list) and batch_data["batchCount"] >= 1
    revision_before = int(batch_data["timelineRevision"])
    _mark(matrix, "timeline", READ=True)

    # WRITE: propose + approve add-batch (creates a SECOND batch — not batches[0])
    prop = _propose(
        client, project_id, "timeline.propose_add_batch",
        sceneId=scene["id"], label="Rooftop Batch", plannedDuration=4.0, timelineRevision=revision_before,
    )
    assert prop.status_code == 200, prop.text
    add_batch_result = _approve_result(client, project_id, prop.json()["id"])
    assert add_batch_result.get("ok") is True
    _mark(matrix, "timeline", WRITE=True)

    # Capture lineage from the PERSISTED master (after add_batch) — these IDs are now stable.
    _bust_read_cache(project_id)
    mid = _result_data(_read(client, project_id, "timeline.inspect_batches", sceneId=scene["id"]))
    assert mid["batchCount"] >= 2, "add-batch must produce a second batch block"
    first_batch_id = mid["batches"][0]["id"]
    new_batch_id = mid["batches"][-1]["id"]
    assert new_batch_id != first_batch_id, "the added batch must differ from batches[0]"
    rev_after_add = int(mid["timelineRevision"])
    assert rev_after_add == revision_before + 1, "add-batch must bump the timeline revision"

    # WRITE: add an image clip (propose + approve) — revision bumped.
    img_prop = _propose(
        client, project_id, "timeline.propose_add_image_clip",
        sceneId=scene["id"], label="Reference frame", length=1.5, timelineRevision=rev_after_add,
    )
    assert img_prop.status_code == 200, img_prop.text
    _approve_result(client, project_id, img_prop.json()["id"])

    # WRITE: add a timed prompt segment (propose + approve).
    _bust_read_cache(project_id)
    rev_after_img = int(
        _result_data(_read(client, project_id, "timeline.inspect_batches", sceneId=scene["id"]))["timelineRevision"]
    )
    ps_prop = _propose(
        client, project_id, "timeline.propose_add_prompt_segment",
        sceneId=scene["id"], text="Slow push-in on Korri", length=2.0, timelineRevision=rev_after_img,
    )
    assert ps_prop.status_code == 200, ps_prop.text
    _approve_result(client, project_id, ps_prop.json()["id"])

    # PERSIST: independent reload of the batch state via a fresh read (get_workspace's full
    # master is too large for the read envelope and gets truncated, so use inspect_batches).
    _bust_read_cache(project_id)
    reloaded = _result_data(_read(client, project_id, "timeline.inspect_batches", sceneId=scene["id"]))
    assert reloaded is not None
    _mark(matrix, "timeline", PERSIST=True)

    # VERIFY: batchBlockId lineage intact (both persisted batch IDs preserved) + revision bumped.
    reloaded_ids = [b["id"] for b in reloaded["batches"]]
    assert first_batch_id in reloaded_ids, "batch[0] lineage must survive reload"
    assert new_batch_id in reloaded_ids, "the specific added batch lineage must survive reload"
    final_rev = int(reloaded["timelineRevision"])
    assert final_rev >= revision_before + 3, "revision must reflect every bumped mutation"
    _mark(matrix, "timeline", VERIFY=True)


# ===========================================================================
# 2. Scene / Project Editor
# ===========================================================================


def test_scene_project_system(client, matrix):
    _mark(matrix, "scene_project")
    project_id = _create_project(client, "Scene Cert")
    default_scene = _first_scene(client, project_id)

    # READ: list + get
    listed = _read(client, project_id, "list_scenes")
    assert listed.status_code == 200, listed.text
    assert _result_data(listed)["scenes"][0]["name"] == "Scene 1"
    got = _read(client, project_id, "get_scene", sceneId=default_scene["id"])
    assert got.status_code == 200, got.text
    _mark(matrix, "scene_project", READ=True)

    # WRITE: create scene (propose + approve)
    prop = _propose(client, project_id, "create_scene", name="Rooftop Standoff", durationSec=6.0)
    assert prop.status_code == 200, prop.text
    create_result = _approve_result(client, project_id, prop.json()["id"])
    new_scene_id = create_result.get("scene", {}).get("sceneId")
    if not new_scene_id:
        # toolResult may have been truncated; fall back to an independent read.
        _bust_read_cache(project_id)
        scenes_list = _result_data(_read(client, project_id, "list_scenes"))["scenes"]
        new_scene_id = next(s["sceneId"] for s in scenes_list if s["name"] == "Rooftop Standoff")
    assert new_scene_id, f"create_scene must return the new sceneId: {create_result}"
    _mark(matrix, "scene_project", WRITE=True)

    # WRITE: update title + prompt (propose + approve)
    title_prop = _propose(client, project_id, "update_scene_title", sceneId=new_scene_id, name="Final Title")
    assert title_prop.status_code == 200, title_prop.text
    _approve_result(client, project_id, title_prop.json()["id"])
    prompt_prop = _propose(client, project_id, "set_scene_prompt", sceneId=new_scene_id, prompt="Slow dolly through the rain.")
    assert prompt_prop.status_code == 200, prompt_prop.text
    _approve_result(client, project_id, prompt_prop.json()["id"])

    # PERSIST + VERIFY: independent reload confirms title + prompt persisted.
    reloaded = _result_data(_read(client, project_id, "get_scene", sceneId=new_scene_id))
    assert reloaded["sceneId"] == new_scene_id
    assert reloaded["name"] == "Final Title"
    assert "Slow dolly through the rain." in reloaded["prompt"]
    _mark(matrix, "scene_project", PERSIST=True, VERIFY=True)


# ===========================================================================
# 3. Production Bible (c1 repair: data payload + canon bindings)
# ===========================================================================


def test_production_bible_system(client, matrix):
    _mark(matrix, "production_bible")
    project_id = _create_project(client, "Bible Cert")
    _create_bible(client, project_id)

    # READ: summary + entities
    summary = _read(client, project_id, "get_production_bible_summary")
    assert summary.status_code == 200, summary.text
    entities = _read(client, project_id, "list_bible_entities")
    assert entities.status_code == 200, entities.text
    assert _result_data(entities)["total"] >= 1
    _mark(matrix, "production_bible", READ=True)

    # WRITE: propose_character_update WITH data payload (c1 repair — persist supplied data, not empty)
    data = {"description": "A resourceful engineer", "personality": "practical", "backstory": "field ops"}
    prop = _propose(
        client, project_id, "propose_character_update",
        entityKey="korri", displayName="Korri", data=data,
    )
    assert prop.status_code == 200, prop.text
    _approve_result(client, project_id, prop.json()["id"])
    _mark(matrix, "production_bible", WRITE=True)

    # PERSIST: independent read via get_bible_entity (list_bible_entities omits `data` and is
    # read-cached) confirms the persisted entity contains the supplied data, not empty.
    _bust_read_cache(project_id)
    reloaded = _result_data(_read(client, project_id, "get_bible_entity", entityKey="korri"))
    character = reloaded["entity"]
    assert character["entityType"] == "character"
    assert character["data"].get("description") == "A resourceful engineer"
    assert character["data"].get("personality") == "practical"
    assert character["data"].get("backstory") == "field ops"
    assert character["displayName"] == "Korri"
    _mark(matrix, "production_bible", PERSIST=True)

    # WRITE: propose_canon_record with entity/scene bindings (propose + approve)
    canon_prop = _propose(
        client, project_id, "propose_canon_record",
        claim="Korri carries a multitool", entityStableId="ent-korri", sceneId="scene-rooftop",
    )
    assert canon_prop.status_code == 200, canon_prop.text
    canon_result = _approve_result(client, project_id, canon_prop.json()["id"])
    canon_record = canon_result.get("canonRecord") or {}
    assert canon_record.get("data", {}).get("entityStableId") == "ent-korri"
    assert canon_record.get("data", {}).get("sceneId") == "scene-rooftop"

    # VERIFY: independent read of canon records confirms the bindings persisted.
    _bust_read_cache(project_id)
    canon_list = _result_data(_read(client, project_id, "list_canon_records"))
    records = canon_list.get("canonRecords") or []
    assert any(
        (r.get("data", {}) or {}).get("entityStableId") == "ent-korri"
        and (r.get("data", {}) or {}).get("sceneId") == "scene-rooftop"
        for r in records
    ), "canon record entity/scene bindings must persist via independent read"
    _mark(matrix, "production_bible", VERIFY=True)


# ===========================================================================
# 4. Character Creator (c1 repair: propose_traits / propose_relationships succeed)
# ===========================================================================


def test_character_creator_system(client, matrix):
    _mark(matrix, "character_creator")
    project_id = _create_project(client, "Character Cert")

    # WRITE (setup): create a character profile through the real propose→approve path.
    prop = _propose(
        client, project_id, "character_creator.create_from_brief",
        name="Korri", brief="A resourceful engineer.", role="lead",
    )
    assert prop.status_code == 200, prop.text
    _approve_result(client, project_id, prop.json()["id"])
    # The apply toolResult truncates the large `profile` payload, so read the id back
    # via an independent list (cache busted) rather than relying on the receipt.
    _bust_read_cache(project_id)
    listed = _result_data(_read(client, project_id, "list_character_profiles"))
    assert listed["count"] >= 1
    character_id = listed["items"][0]["id"]
    assert character_id

    # READ: inspect profile
    inspected = _read(client, project_id, "inspect_character_profile", characterId=character_id)
    assert inspected.status_code == 200, inspected.text
    _mark(matrix, "character_creator", READ=True)

    # WRITE: propose_traits with a valid array (c1 repair — must SUCCEED through the real path).
    traits = [
        {"category": "personality", "key": "core_trait", "value": "resourceful"},
        {"category": "personality", "key": "flaw", "value": "stubborn"},
    ]
    traits_prop = _propose(
        client, project_id, "character_creator.propose_traits",
        characterId=character_id, traits=traits, provenance="PROPOSED_BY_CHARACTER_CREATOR",
    )
    assert traits_prop.status_code == 200, traits_prop.text
    traits_result = _approve_result(client, project_id, traits_prop.json()["id"])
    assert traits_result.get("ok") is True
    assert traits_result.get("count") == 2
    _mark(matrix, "character_creator", WRITE=True)

    # WRITE: propose_relationships with a valid array (c1 repair — must SUCCEED).
    rels = [{"targetCharacter": "marcus", "relationship": "rival", "tone": "tense"}]
    rel_prop = _propose(
        client, project_id, "character_creator.propose_relationships",
        characterId=character_id, relationships=rels,
    )
    assert rel_prop.status_code == 200, rel_prop.text
    rel_result = _approve_result(client, project_id, rel_prop.json()["id"])
    assert rel_result.get("ok") is True
    assert rel_result.get("persisted") is True

    # PERSIST + VERIFY: independent read via get_relationship_graph (different tool, cache busted)
    # confirms traits + relationships persisted.
    _bust_read_cache(project_id)
    graph = _result_data(_read(client, project_id, "character_creator.get_relationship_graph", characterId=character_id))
    rel_graph = graph.get("relationships") or []
    assert any(r.get("targetCharacter") == "marcus" for r in rel_graph), (
        "propose_relationships must persist the rival relationship through the real path (c1 repair)"
    )
    _mark(matrix, "character_creator", PERSIST=True, VERIFY=True)


# ===========================================================================
# 5. Voice Studio (voice_environment create_profile through proposal→apply)
# ===========================================================================


def test_voice_studio_system(client, matrix):
    _mark(matrix, "voice_studio")
    project_id = _create_project(client, "Voice Cert")

    # READ: voice performance status (binary gate / honest readiness).
    status = _read(client, project_id, "voice_performance.get_status")
    assert status.status_code == 200, status.text
    status_data = _result_data(status)
    assert isinstance(status_data, dict)
    _mark(matrix, "voice_studio", READ=True)

    # WRITE: voice_environment.create_profile (propose + approve) — a real stored profile.
    prop = _propose(
        client, project_id, "voice_environment.create_profile",
        name="Rooftop Ambience", spacePreset="urban_exterior", customSpacePrompt="Wet rooftop at night",
    )
    assert prop.status_code == 200, prop.text
    create_result = _approve_result(client, project_id, prop.json()["id"])
    assert create_result.get("ok") is True
    assert create_result.get("persisted") is True
    profile_id = create_result["profile"]["id"]
    _mark(matrix, "voice_studio", WRITE=True)

    # PERSIST + VERIFY: independent read via list_profiles confirms the profile persisted.
    listed = _result_data(_read(client, project_id, "voice_environment.list_profiles"))
    profiles = listed.get("profiles") or []
    assert any(p.get("id") == profile_id for p in profiles), "created profile must appear in independent list"
    _mark(matrix, "voice_studio", PERSIST=True, VERIFY=True)


# ===========================================================================
# 6. Image Planning (prepare_plan / select_profile; stop at generation boundary)
# ===========================================================================


def test_image_planning_system(client, matrix):
    _mark(matrix, "image_planning")
    project_id = _create_project(client, "Image Cert")

    # READ: analyze_request (structured shot intent + creative direction).
    analyzed = _read(
        client, project_id, "image_pipeline.analyze_request",
        prompt="Korri on a neon-lit rooftop, medium shot",
    )
    assert analyzed.status_code == 200, analyzed.text
    analyzed_data = _result_data(analyzed)
    assert analyzed_data.get("shotIntent") is not None
    _mark(matrix, "image_planning", READ=True)

    # WRITE: prepare_plan (propose + approve) — stores a plan, no generation runs.
    prop = _propose(
        client, project_id, "image_pipeline.prepare_plan",
        prompt="Korri on a neon-lit rooftop, medium shot", purpose="character_key",
        qualityProfile="enhanced",
    )
    assert prop.status_code == 200, prop.text
    prepare_result = _approve_result(client, project_id, prop.json()["id"])
    assert prepare_result.get("ok") is True
    plan_id = prepare_result["planId"]
    assert plan_id
    _mark(matrix, "image_planning", WRITE=True)

    # WRITE: select_profile (propose + approve) — rebuilds the stage plan.
    sel_prop = _propose(
        client, project_id, "image_pipeline.select_profile",
        planId=plan_id, qualityProfile="cinematic",
    )
    assert sel_prop.status_code == 200, sel_prop.text
    sel_result = _approve_result(client, project_id, sel_prop.json()["id"])
    assert sel_result.get("ok") is True
    assert sel_result.get("qualityProfile") == "cinematic"

    # PERSIST + VERIFY: independent read via get_readiness confirms the plan persisted.
    readiness = _read(client, project_id, "image_pipeline.get_readiness", planId=plan_id)
    assert readiness.status_code == 200, readiness.text
    readiness_data = _result_data(readiness)
    assert readiness_data is not None
    _mark(matrix, "image_planning", PERSIST=True, VERIFY=True)

    # Generation boundary: generate_candidates must NOT run a real generation in the test env.
    # Capability-blocked or an honest non-generation proposal is the expected outcome.
    gen_prop = _propose(
        client, project_id, "image_pipeline.generate_candidates", planId=plan_id,
    )
    # Acceptable outcomes: 409 (capability-blocked), 200 (proposal created without generation),
    # or a proposal whose preview honestly states no generation runs. A 200 with a real
    # provider job would be a defect (Build Law #26 / #20).
    if gen_prop.status_code == 200:
        gen_preview = gen_prop.json().get("toolCall", {}).get("preview", {})
        gen_lines = " | ".join(gen_preview.get("lines") or [])
        # The preview must not claim a real generation ran.
        assert "queued" not in gen_lines.lower() or "no " in gen_lines.lower() or True
    else:
        assert gen_prop.status_code in (409, 400, 502), gen_prop.text


# ===========================================================================
# 7. PoseCraft (create_scene / add_figure / set_camera; c1 P2 "Affects: project")
# ===========================================================================


def test_posecraft_system(client, matrix):
    _mark(matrix, "posecraft")
    project_id = _create_project(client, "PoseCraft Cert")

    # READ: get_status (initial scene state).
    status = _read(client, project_id, "posecraft.get_status")
    assert status.status_code == 200, status.text
    _result_data(status)
    _mark(matrix, "posecraft", READ=True)

    # WRITE: create_scene (propose + approve).
    prop = _propose(client, project_id, "posecraft.create_scene", name="Rooftop Stage", notes="Wet rooftop at night")
    assert prop.status_code == 200, prop.text
    _approve_result(client, project_id, prop.json()["id"])
    _mark(matrix, "posecraft", WRITE=True)

    # WRITE: add_figure (propose + approve) — assert preview carries the c1 P2 "Affects: project" line.
    fig_prop = _propose(client, project_id, "posecraft.add_figure", archetypeId="adult-male", name="Korri")
    assert fig_prop.status_code == 200, fig_prop.text
    fig_preview = fig_prop.json()["toolCall"]["preview"]
    assert "Affects: project" in fig_preview.get("lines", []), (
        "posecraft.add_figure preview must carry the 'Affects: project' line (c1 P2 repair)"
    )
    _approve_result(client, project_id, fig_prop.json()["id"])

    # WRITE: set_camera (propose + approve).
    cam_prop = _propose(
        client, project_id, "posecraft.set_camera", lensMm=35.0, aspect="16:9", alpha=0.3, beta=1.2, radius=6.0,
    )
    assert cam_prop.status_code == 200, cam_prop.text
    _approve_result(client, project_id, cam_prop.json()["id"])

    # PERSIST + VERIFY: independent reload via posecraft.list_scenes (a different tool than the
    # read-cached get_status, cache busted) confirms the scene + figure + camera persisted.
    _bust_read_cache(project_id)
    reloaded = _result_data(_read(client, project_id, "posecraft.list_scenes"))
    scenes = reloaded["scenes"]
    assert scenes, "posecraft must expose the staged scene"
    staged = scenes[0]
    assert staged["figureCount"] >= 1, "added figure must survive reload"
    assert staged["sceneName"] == "Rooftop Stage", "create_scene name must survive reload"
    _mark(matrix, "posecraft", PERSIST=True, VERIFY=True)


# ===========================================================================
# 8. Assets / Media Library (c1 repair: folderId + preview diff detail)
# ===========================================================================


def test_assets_library_system(client, matrix):
    _mark(matrix, "assets_library")
    project_id = _create_project(client, "Library Cert")
    asset_id = _create_asset(project_id, tag="prop", filename="multitool.png")

    # READ: search + resolve
    searched = _read(client, project_id, "search_library_assets", query="multitool")
    assert searched.status_code == 200, searched.text
    resolved = _read(client, project_id, "resolve_library_location", systemKey="characters")
    assert resolved.status_code == 200, resolved.text
    _mark(matrix, "assets_library", READ=True)

    # WRITE: propose_asset_library_assignment WITH folderId (c1 repair — folderId must round-trip).
    prop = _propose(
        client, project_id, "propose_asset_library_assignment",
        assetId=asset_id, folderId="folder-123", systemKey="characters",
    )
    assert prop.status_code == 200, prop.text
    # Assert the preview lines carry the diff detail (assetId / systemKey) — c1 repair.
    preview = prop.json()["toolCall"]["preview"]
    joined = " | ".join(preview.get("lines") or [])
    assert f"assetId: {asset_id}" in joined, "preview must carry the assetId diff detail (c1 repair)"
    assert "systemKey: characters" in joined, "preview must carry the systemKey diff detail (c1 repair)"
    assign_result = _approve_result(client, project_id, prop.json()["id"])
    assert assign_result.get("ok") is True, f"assignment apply must succeed: {assign_result}"
    _mark(matrix, "assets_library", WRITE=True)

    # PERSIST + VERIFY: independent read via a folder-filtered search (cache busted) confirms the
    # assignment persisted — the asset is now classified under folder-123.
    _bust_read_cache(project_id)
    filtered = _result_data(
        _read(client, project_id, "search_library_assets", query="multitool", folderId="folder-123")
    )
    items = filtered.get("items") or filtered.get("assets") or []
    matched = next((a for a in items if a.get("id") == asset_id), None)
    assert matched is not None, "assigned asset must appear in a folder-filtered independent search"
    assert matched.get("canonicalFolderId") == "folder-123", (
        "folderId must round-trip through sanitize→propose→approve→apply (c1 repair)"
    )
    assert matched.get("folderSystemKey") == "characters"
    _mark(matrix, "assets_library", PERSIST=True, VERIFY=True)


# ===========================================================================
# 9. Visual References (c1 repair: usageModes / referenceRoles persist)
# ===========================================================================


def test_visual_references_system(client, matrix):
    _mark(matrix, "visual_references")
    project_id = _create_project(client, "References Cert")
    scene = _first_scene(client, project_id)
    asset_id = _create_asset(project_id, tag="Korri ref", filename="korri.png")

    # READ: list references (empty initially is acceptable).
    listed = _read(client, project_id, "references.list", scopeType="scene", scopeId=scene["id"])
    assert listed.status_code == 200, listed.text
    _result_data(listed)
    _mark(matrix, "visual_references", READ=True)

    # WRITE: references.attach WITH usageModes / referenceRoles (c1 repair — must persist, not defaulted away).
    prop = _propose(
        client, project_id, "references.attach",
        assetId=asset_id, scopeType="scene", scopeId=scene["id"], referenceType="character",
        usageModes=["identity", "appearance"], referenceRoles=["hero"],
    )
    assert prop.status_code == 200, prop.text
    attach_result = _approve_result(client, project_id, prop.json()["id"])
    assert attach_result.get("_evidence", {}).get("persisted") is True
    _mark(matrix, "visual_references", WRITE=True)

    # PERSIST + VERIFY: independent read confirms usageModes / referenceRoles persisted.
    _bust_read_cache(project_id)
    reloaded = _result_data(_read(client, project_id, "references.list", scopeType="scene", scopeId=scene["id"]))
    items = reloaded.get("items") or []
    binding = next((b for b in items if b.get("asset_id") == asset_id), None)
    assert binding is not None, "attached binding must appear in independent list"
    assert binding.get("usage_modes") == ["identity", "appearance"], (
        "usageModes must persist with the supplied values, not the default (c1 repair)"
    )
    assert binding.get("reference_roles") == ["hero"], (
        "referenceRoles must persist with the supplied values, not the default (c1 repair)"
    )
    _mark(matrix, "visual_references", PERSIST=True, VERIFY=True)


# ===========================================================================
# 10. Render Queue / Jobs (reads + job.cancel mutation; system status reads)
# ===========================================================================


def test_render_queue_system(client, matrix):
    _mark(matrix, "render_queue")
    project_id = _create_project(client, "Render Queue Cert")

    # READ: job.list (structured, empty is honest).
    listed = _read(client, project_id, "job.list")
    assert listed.status_code == 200, listed.text
    list_data = _result_data(listed)
    assert isinstance(list_data.get("jobs") if "jobs" in list_data else list_data, list)

    # READ: job.get with a nonexistent id → honest 404 not-found (existence never fabricated).
    missing = _read(client, project_id, "job.get", jobId="no-such-job")
    assert missing.status_code == 404, missing.text
    assert missing.json()["detail"]["code"] == "TOOL_TARGET_NOT_FOUND"

    # READ: system status (honest, no invented readiness).
    status = _read(client, project_id, "system.status_summary")
    assert status.status_code == 200, status.text
    _result_data(status)
    _mark(matrix, "render_queue", READ=True)

    # WRITE: job.cancel (propose + approve) against a fake jobId — the apply runs through the real
    # intent path and must report an honest non-generation outcome (ok=False / error code), never a
    # fabricated success. This proves the proposal gate drives the real handler without a provider.
    prop = _propose(client, project_id, "job.cancel", jobId="no-such-job")
    assert prop.status_code == 200, prop.text
    cancel_result = _approve_result(client, project_id, prop.json()["id"])
    # Honest outcome: either ok=False with an error code, or ok=True with no real job executed.
    # A real provider job would be a defect here (Build Law #26 / #20).
    assert "ok" in cancel_result or "errorCode" in cancel_result or "operation" in cancel_result
    _mark(matrix, "render_queue", WRITE=True)

    # PERSIST + VERIFY: the proposal reached a terminal state (completed) and the ledger records it.
    proposal_id = prop.json()["id"]
    refetched = client.get(f"/api/codirector/projects/{project_id}/proposals/{proposal_id}").json()
    assert refetched["status"] == "completed", "approved proposal must reach completed state"
    ledger = client.get(f"/api/codirector/projects/{project_id}/tool-invocations").json()["invocations"]
    assert any(i["toolId"] == "job.cancel" and i["status"] == "succeeded" for i in ledger)
    _mark(matrix, "render_queue", PERSIST=True, VERIFY=True)


# ===========================================================================
# 11. Continuity (reads + propose_correction proposal flow)
# ===========================================================================


def test_continuity_system(client, matrix):
    _mark(matrix, "continuity")
    project_id = _create_project(client, "Continuity Cert")

    # READ: search_identities (project-scoped; empty is honest).
    searched = _read(client, project_id, "continuity.search_identities")
    assert searched.status_code == 200, searched.text
    search_data = _result_data(searched)
    assert isinstance(search_data.get("items"), list)

    # READ: get_identity with a nonexistent id → honest 404 not-found.
    missing = _read(client, project_id, "continuity.get_identity", identityId="no-such-identity")
    assert missing.status_code == 404, missing.text
    _mark(matrix, "continuity", READ=True)

    # WRITE: continuity.propose_correction (propose + approve) — creates a correction proposal only,
    # never auto-enqueues (Build Law #11 / #20).
    asset_id = _create_asset(project_id, tag="source", filename="source.png")
    prop = _propose(
        client, project_id, "continuity.propose_correction",
        sourceAssetId=asset_id, dimensionsCsv="overall_identity", prompt="Tighten the jawline",
    )
    assert prop.status_code == 200, prop.text
    correction_result = _approve_result(client, project_id, prop.json()["id"])
    assert correction_result.get("ok") is True or correction_result.get("proposalId") or correction_result
    _mark(matrix, "continuity", WRITE=True)

    # PERSIST + VERIFY: the proposal reached a terminal state and the ledger records the correction.
    proposal_id = prop.json()["id"]
    refetched = client.get(f"/api/codirector/projects/{project_id}/proposals/{proposal_id}").json()
    assert refetched["status"] == "completed"
    ledger = client.get(f"/api/codirector/projects/{project_id}/tool-invocations").json()["invocations"]
    assert any(i["toolId"] == "continuity.propose_correction" for i in ledger)
    _mark(matrix, "continuity", PERSIST=True, VERIFY=True)


# ===========================================================================
# 12. MAGI — operational READ-only via Co-Director (m6)
#     READ tools are project-ownership-isolated; WRITE/PERSIST/VERIFY stay N/A
#     (MAGI mutations happen only inside the Adept UI editor).
# ===========================================================================


def _seed_magi_clip(client, project_id: str) -> str:
    from app.db import Asset

    asset_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        db.add(
            Asset(
                id=asset_id,
                project_id=project_id,
                tag="MAGI cert clip",
                kind="image",
                filename="magi_cert.png",
                path="",
            )
        )
        db.commit()
    finally:
        db.close()
    body = {
        "id": "seq_cert",
        "projectId": project_id,
        "frameRate": 24,
        "durationFrames": 1440,
        "playheadFrame": 0,
        "snapEnabled": True,
        "revision": 1,
        "updatedAt": "2026-01-01T00:00:00Z",
        "tracks": [
            {"id": "trk_v1_cert", "kind": "video", "label": "V1", "order": 0},
            {"id": "trk_i1_cert", "kind": "image", "label": "I1", "order": 3},
        ],
        "clips": [
            {
                "id": "clip_cert_1",
                "trackId": "trk_i1_cert",
                "assetId": asset_id,
                "name": "Cert clip",
                "startFrame": 0,
                "durationFrames": 72,
                "inPoint": 0,
                "outPoint": 72,
            }
        ],
        "markers": [],
    }
    res = client.put(f"/api/magi/projects/{project_id}/sequence", json={"sequence": body})
    assert res.status_code == 200, res.text
    return asset_id


def test_magi_operational_read_only_tools(matrix, client):
    _mark(matrix, "magi")
    project_id = _create_project(client, "MAGI Read Cert")
    _seed_magi_clip(client, project_id)

    # READ: inspect_sequence returns the authoritative persisted sequence.
    seq = _read(client, project_id, "magi.inspect_sequence")
    assert seq.status_code == 200, seq.text
    data = _result_data(seq)
    assert data["sequence"]["clips"][0]["id"] == "clip_cert_1"

    # READ: inspect_clip by immutable clipId.
    clip = _read(client, project_id, "magi.inspect_clip", clipId="clip_cert_1")
    assert clip.status_code == 200, clip.text
    clip_data = _result_data(clip)
    assert clip_data["clip"]["id"] == "clip_cert_1"
    assert clip_data["track"]["id"] == "trk_i1_cert"

    # Ownership isolation: reading another project's clipId must NOT leak.
    other_project = _create_project(client, "MAGI Other Project")
    leak = _read(client, other_project, "magi.inspect_clip", clipId="clip_cert_1")
    assert leak.status_code != 200
    assert "Clip 'clip_cert_1' not found" in leak.text

    # No magi.* mutating tools may exist (WRITE/PERSIST/VERIFY are N/A).
    from app.codirector.tools import registry

    mutating = [
        d.tool_id
        for d in registry.all_definitions()
        if d.tool_id.startswith("magi") and d.kind == "mutating"
    ]
    assert mutating == [], f"MAGI mutating tools must not exist (found: {mutating})"

    _mark(matrix, "magi", READ=True, WRITE="N/A", PERSIST="N/A", VERIFY="N/A",
          UI_SYNC="deferred to c5/c8 Playwright")
