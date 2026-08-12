"""c5-cross-system: cross-system workflow + operational lineage certification.

Executable certification for milestone phases 10 (CROSS-SYSTEM WORKFLOWS),
11 (OPERATIONAL LINEAGE), and 12 (UI SYNCHRONIZATION - API-side lineage half;
the UI half is the companion Playwright spec
``tests/e2e/codirector/cross-system-uIsync.spec.ts``).

Every chain drives the REAL pathway through the public HTTP API:

    registry lookup -> sanitize_arguments -> propose -> human approve
        -> execute_approved_proposal (apply handler) -> independent read-back.

No handler or service is mocked. Only the shared test DB fixtures (``client``)
are reused from ``conftest.py``. Generation boundaries (voice/image/video) are
exercised up to the planning boundary; capability-blocked or honest
non-generation outcomes are the expected result in the test environment
(Build Law #26 / #20).

Lineage invariant (Phase 11): every write result and independent read must
show immutable IDs (``projectId``, ``sceneId``, ``batchBlockId``,
``characterId``, ``assetId``). Array index and display name are never accepted
as lineage. The ``batchBlockId`` of the modified batch must match the intended
batch, and other batches must be untouched.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import fields as dataclass_fields
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
def _enable_cross_system_features(monkeypatch: pytest.MonkeyPatch, client):
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
# HTTP helpers (real pathway: read / propose / approve)
# ---------------------------------------------------------------------------


def _create_project(client, name: str = "c5 Cross-System Project") -> str:
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
    """Clear the project's Co-Director read cache so PERSIST/VERIFY sees post-mutation state."""
    from app.codirector.tools.read_cache import clear_project

    clear_project(project_id)


def _master(client, project_id: str, scene_id: str) -> dict[str, Any]:
    """Independent authoritative read of the full w46 timeline master (read-only REST)."""
    res = client.get(f"/api/director-timeline/projects/{project_id}/scenes/{scene_id}/master")
    assert res.status_code == 200, res.text
    return res.json()["master"]


def _batches_summary(client, project_id: str, scene_id: str) -> dict[str, Any]:
    _bust_read_cache(project_id)
    return _result_data(_read(client, project_id, "timeline.inspect_batches", sceneId=scene_id))


def _batch_ids(client, project_id: str, scene_id: str) -> list[str]:
    data = _batches_summary(client, project_id, scene_id)
    return [b["id"] for b in data["batches"]]


# ===========================================================================
# Chain A - Character -> Asset -> Timeline (specific batch, not batches[0])
# ===========================================================================


def test_character_to_timeline_chain(client):
    project_id = _create_project(client, "Cross Character->Timeline")
    scene = _first_scene(client, project_id)
    scene_id = scene["id"]

    # 1. Create a character through the real propose->approve path.
    char_prop = _propose(
        client, project_id, "character_creator.create_from_brief",
        name="Korri", brief="A resourceful engineer.", role="lead",
    )
    assert char_prop.status_code == 200, char_prop.text
    _approve_result(client, project_id, char_prop.json()["id"])
    _bust_read_cache(project_id)
    listed = _result_data(_read(client, project_id, "list_character_profiles"))
    assert listed["count"] >= 1
    character_id = listed["items"][0]["id"]
    assert character_id, "characterId must be a real immutable id, not array index or display name"

    # 2. Create an approved character reference asset (seeded Asset row, then attached
    #    to the scene as an approved character reference through propose->approve).
    asset_id = _create_asset(project_id, tag="Korri reference", filename="korri.png")
    ref_prop = _propose(
        client, project_id, "references.attach",
        assetId=asset_id, scopeType="scene", scopeId=scene_id, referenceType="character",
        usageModes=["identity", "appearance"], referenceRoles=["hero"],
    )
    assert ref_prop.status_code == 200, ref_prop.text
    ref_result = _approve_result(client, project_id, ref_prop.json()["id"])
    assert ref_result.get("_evidence", {}).get("persisted") is True

    # 3. Capture the pre-mutation timeline revision. The migrated batch ids are only
    #    stable once a persisting write lands (NO_AUTO_PERSIST_ON_READ), so we capture
    #    only the revision here and resolve batch ids after the first persist below.
    summary_before = _batches_summary(client, project_id, scene_id)
    revision_before = int(summary_before["timelineRevision"])
    assert summary_before["batchCount"] >= 1, "a fresh scene must migrate with at least one batch block"

    # 4. Add a SECOND batch (not batches[0]) with a specific generatorId set at creation.
    add_prop = _propose(
        client, project_id, "timeline.propose_add_batch",
        sceneId=scene_id, label="Rooftop Standoff Batch", plannedDuration=4.0,
        generatorId="gen-cinematic-enhanced", timelineRevision=revision_before,
    )
    assert add_prop.status_code == 200, add_prop.text
    add_result = _approve_result(client, project_id, add_prop.json()["id"])
    assert add_result.get("ok") is True

    # 5. Capture the immutable batchBlockIds via independent read AFTER the first persist.
    #    Both batches[0] and the new batch now have stable ids (save_master persisted them).
    summary_after_add = _batches_summary(client, project_id, scene_id)
    revision_after_add = int(summary_after_add["timelineRevision"])
    assert revision_after_add == revision_before + 1, "add_batch must bump the timeline revision exactly once"
    assert summary_after_add["batchCount"] >= 2, "add_batch must produce a second batch block"
    ids_after_add = [b["id"] for b in summary_after_add["batches"]]
    first_batch_id = ids_after_add[0]
    new_batch_id = ids_after_add[-1]
    assert new_batch_id != first_batch_id, "the added batch must be a distinct batch block, not batches[0]"
    first_batch_summary_before_attach = next(b for b in summary_after_add["batches"] if b["id"] == first_batch_id)
    first_batch_ref_count_before = first_batch_summary_before_attach["referenceCount"]
    first_batch_generator_before = first_batch_summary_before_attach["generatorId"]

    # 6. Attach the approved character reference asset to the SPECIFIC new batch.
    attach_prop = _propose(
        client, project_id, "timeline.attach_optional_reference",
        sceneId=scene_id, batchBlockId=new_batch_id, assetId=asset_id,
        role="character", label="Korri reference", timelineRevision=revision_after_add,
    )
    assert attach_prop.status_code == 200, attach_prop.text
    attach_result = _approve_result(client, project_id, attach_prop.json()["id"])
    assert attach_result.get("ok") is True
    assert attach_result.get("batchBlockId") == new_batch_id, (
        "the attach result must echo the exact immutable batchBlockId, not an array index"
    )
    assert attach_result.get("reference", {}).get("assetId") == asset_id, (
        "the attach result must echo the exact immutable assetId"
    )
    revision_after_attach = int(attach_result.get("timelineRevision") or revision_after_add + 1)
    assert revision_after_attach == revision_after_add + 1, "attach must bump the timeline revision exactly once"

    # 7. INDEPENDENT READ-BACK of the full master (REST) to verify every native state + lineage id.
    master = _master(client, project_id, scene_id)
    batches = master["batchBlocks"]
    new_batch = next((b for b in batches if b["id"] == new_batch_id), None)
    assert new_batch is not None, "the new batch block must persist with its immutable batchBlockId"
    first_batch = next((b for b in batches if b["id"] == first_batch_id), None)
    assert first_batch is not None, "batches[0] must still persist with its immutable batchBlockId"

    # 7a. Batch clip binding: the reference is on the NEW batch only.
    new_refs = new_batch.get("references") or []
    bound = next((r for r in new_refs if r.get("assetId") == asset_id), None)
    assert bound is not None, "the asset must be bound to the specific new batch by immutable assetId"
    assert bound.get("role") == "character"

    # 7b. Batch generator config: the generatorId set at creation persists.
    assert new_batch.get("generatorId") == "gen-cinematic-enhanced", (
        "the generatorId set at add_batch creation must persist on the new batch"
    )

    # 7c. Other batches untouched: batches[0] has no new reference and its generator unchanged.
    first_refs = first_batch.get("references") or []
    assert not any(r.get("assetId") == asset_id for r in first_refs), (
        "batches[0] must NOT receive the reference - only the specific new batch mutates"
    )
    assert first_batch.get("generatorId") == first_batch_generator_before, (
        "batches[0] generatorId must be untouched by the new batch's creation/attach"
    )
    summary_final = _batches_summary(client, project_id, scene_id)
    first_batch_summary_after = next(b for b in summary_final["batches"] if b["id"] == first_batch_id)
    assert first_batch_summary_after["referenceCount"] == first_batch_ref_count_before, (
        "batches[0] referenceCount must be unchanged - no partial write to other batches"
    )

    # 7d. Lineage consistency: all ids are real immutable strings, never array index or display name.
    for _id in (project_id, scene_id, new_batch_id, character_id, asset_id):
        assert isinstance(_id, str) and _id
    assert new_batch_id != first_batch_id
    assert new_batch_id != character_id
    assert new_batch_id != asset_id

    # 8. The character record is independently verifiable with the same characterId.
    _bust_read_cache(project_id)
    listed_again = _result_data(_read(client, project_id, "list_character_profiles"))
    items = listed_again.get("items") or []
    assert any(it.get("id") == character_id for it in items), (
        "the character record must round-trip the same immutable characterId via independent list"
    )

    # 9. The approved character reference asset is independently verifiable.
    _bust_read_cache(project_id)
    ref_list = _result_data(_read(client, project_id, "references.list", scopeType="scene", scopeId=scene_id))
    items = ref_list.get("items") or []
    binding = next((b for b in items if b.get("asset_id") == asset_id), None)
    assert binding is not None, "the approved character reference must appear in the independent reference list"
    assert binding.get("reference_roles") == ["hero"], "referenceRoles must round-trip (c1 repair)"


# ===========================================================================
# Chain B - Bible -> Canon/Continuity -> Scene (real entityStableId + sceneId)
# ===========================================================================


def test_bible_canon_scene_chain(client):
    project_id = _create_project(client, "Cross Bible->Canon->Scene")
    _create_bible(client, project_id)

    # 1. Discover the real entityKey from list_bible_entities, then read its stableId via
    #    get_bible_entity (list_bible_entities omits stableId; get_bible_entity returns it).
    _bust_read_cache(project_id)
    entities_list = _result_data(_read(client, project_id, "list_bible_entities"))
    assert entities_list["total"] >= 1, "bible import must create at least one entity"
    entity_key = entities_list["entities"][0]["entityKey"]
    _bust_read_cache(project_id)
    entity = _result_data(_read(client, project_id, "get_bible_entity", entityKey=entity_key))["entity"]
    entity_stable_id = entity["stableId"]
    assert entity_stable_id, "entityStableId must be a real immutable id, not the display name or entityKey"

    # 2. Create a real scene and capture its immutable sceneId.
    scene_prop = _propose(client, project_id, "create_scene", name="Rooftop Standoff", durationSec=6.0)
    assert scene_prop.status_code == 200, scene_prop.text
    scene_result = _approve_result(client, project_id, scene_prop.json()["id"])
    scene_id = scene_result.get("scene", {}).get("sceneId")
    if not scene_id:
        _bust_read_cache(project_id)
        scenes_list = _result_data(_read(client, project_id, "list_scenes"))["scenes"]
        scene_id = next(s["sceneId"] for s in scenes_list if s["name"] == "Rooftop Standoff")
    assert scene_id, "sceneId must be a real immutable id"

    # 3. Propose a canon record binding the EXACT entityStableId + sceneId, then approve.
    canon_prop = _propose(
        client, project_id, "propose_canon_record",
        claim="Korri carries a multitool on the rooftop",
        entityStableId=entity_stable_id, sceneId=scene_id,
    )
    assert canon_prop.status_code == 200, canon_prop.text
    canon_result = _approve_result(client, project_id, canon_prop.json()["id"])
    canon_record = canon_result.get("canonRecord") or {}
    canon_data = canon_record.get("data") or canon_record
    assert canon_data.get("entityStableId") == entity_stable_id, (
        "the canon record must reference the EXACT immutable entityStableId"
    )
    assert canon_data.get("sceneId") == scene_id, (
        "the canon record must reference the EXACT immutable sceneId"
    )

    # 4. INDEPENDENT READ-BACK via list_canon_records confirms the bindings persisted.
    _bust_read_cache(project_id)
    canon_list = _result_data(_read(client, project_id, "list_canon_records"))
    records = canon_list.get("canonRecords") or []
    matched = next(
        (
            r
            for r in records
            if (r.get("data", {}) or {}).get("entityStableId") == entity_stable_id
            and (r.get("data", {}) or {}).get("sceneId") == scene_id
        ),
        None,
    )
    assert matched is not None, (
        "the canon record must persist with the exact entity/scene bindings via independent read"
    )

    # 5. Lineage: the entity and scene referenced by the canon record are independently verifiable.
    _bust_read_cache(project_id)
    reloaded_entity = _result_data(_read(client, project_id, "get_bible_entity", entityKey=entity_key))["entity"]
    assert reloaded_entity["stableId"] == entity_stable_id, (
        "the canon record's entityStableId must resolve to the same bible entity"
    )
    _bust_read_cache(project_id)
    reloaded_scene = _result_data(_read(client, project_id, "get_scene", sceneId=scene_id))
    assert reloaded_scene["sceneId"] == scene_id, (
        "the canon record's sceneId must resolve to the same scene"
    )


# ===========================================================================
# Chain C - Voice -> Asset lineage (non-persisted plan; no real voice generation)
# ===========================================================================


def test_voice_performance_plan_lineage(client):
    project_id = _create_project(client, "Cross Voice->Asset Lineage")

    # 1. Create a character to anchor the voice performance plan.
    char_prop = _propose(
        client, project_id, "character_creator.create_from_brief",
        name="Korri", brief="A resourceful engineer with a dry wit.", role="lead",
    )
    assert char_prop.status_code == 200, char_prop.text
    _approve_result(client, project_id, char_prop.json()["id"])
    _bust_read_cache(project_id)
    listed = _result_data(_read(client, project_id, "list_character_profiles"))
    assert listed["count"] >= 1
    character_id = listed["items"][0]["id"]
    assert character_id, "characterId must be a real immutable id"

    # 2. Create a non-persisted voice performance plan for the character (READ tool).
    #    This does NOT trigger real voice generation - compile_performance only plans.
    plan_res = _read(
        client, project_id, "voice_performance.preview_plan",
        characterId=character_id,
        sourceText="KORRI: We don't have time for this. (dry) Let's move.",
    )
    # Acceptable outcomes: 200 (plan produced) or an honest capability-blocked /
    # not-ready outcome. A real provider job would be a defect (Build Law #26 / #20).
    if plan_res.status_code != 200:
        assert plan_res.status_code in (404, 409, 400, 502), plan_res.text
        # Capability-blocked is an honest non-generation outcome; lineage of the
        # character itself is still independently verifiable below.
        plan_data = {}
    else:
        plan_data = _result_data(plan_res)

    # 3. If a plan was produced, assert it carries the character lineage id.
    #    compile_performance returns characterId (and voiceVersionId when available);
    #    projectId lineage is verified via the independent character read-back below
    #    (the character belongs to this project, so the plan's characterId transitively
    #    binds the plan to this project).
    if plan_data:
        plan_character_id = plan_data.get("characterId")
        assert plan_character_id == character_id, (
            "the voice performance plan must carry the exact immutable characterId"
        )

    # 4. INDEPENDENT READ-BACK: the character record exists with the same characterId,
    #    proving the plan's character lineage resolves to a real entity in THIS project.
    _bust_read_cache(project_id)
    listed_again = _result_data(_read(client, project_id, "list_character_profiles"))
    items = listed_again.get("items") or []
    assert any(it.get("id") == character_id for it in items), (
        "the plan's characterId must resolve to a real character record in this project via independent list"
    )

    # 5. The project itself is independently verifiable (projectId lineage).
    project = client.get(f"/api/projects/{project_id}").json()
    assert project["id"] == project_id


# ===========================================================================
# Chain D - Negative cross-project: attach Project A's asset to Project B's batch
#           must be rejected (404/scope violation), no partial writes in either project.
# ===========================================================================


def test_negative_cross_project_attach_rejected(client):
    project_a = _create_project(client, "Cross Negative Project A")
    project_b = _create_project(client, "Cross Negative Project B")

    # 1. Project B: capture the pre-attempt state in a SINGLE read. The migrated batch
    #    ids are unstable until a persisting write lands (NO_AUTO_PERSIST_ON_READ), and
    #    Project B never receives a persisting write (its only mutation attempt is
    #    rejected below), so we compare batch COUNT / revision / reference presence
    #    across reads rather than specific unstable batch ids.
    scene_b = _first_scene(client, project_b)
    scene_b_id = scene_b["id"]
    b_summary_before = _batches_summary(client, project_b, scene_b_id)
    b_batch_count_before = b_summary_before["batchCount"]
    b_revision_before = int(b_summary_before["timelineRevision"])
    b_total_refs_before = sum(b["referenceCount"] for b in b_summary_before["batches"])
    # Capture one batch id to target in the attach attempt (the apply handler 404s at
    # _require_bundle before the batch id is ever validated, so any of B's batch ids
    # suffices to exercise the cross-project scope violation).
    b_target_batch_id = b_summary_before["batches"][0]["id"]

    # 2. Project A: seed an asset (A's asset) and capture A's pre-attempt state.
    asset_a_id = _create_asset(project_a, tag="A only asset", filename="a.png")
    scene_a = _first_scene(client, project_a)
    scene_a_id = scene_a["id"]
    a_summary_before = _batches_summary(client, project_a, scene_a_id)
    a_batch_count_before = a_summary_before["batchCount"]
    a_revision_before = int(a_summary_before["timelineRevision"])

    # 3. Under Project A's Co-Director context, attempt to attach A's asset to
    #    Project B's batch (B's sceneId + B's batchBlockId). The propose step creates
    #    a proposal (preview does not load the bundle); the APPROVE step runs the apply
    #    handler, which calls _require_bundle(ctx.project_id=A, sceneId=B) -> 404
    #    SCENE_NOT_FOUND because B's scene is not owned by A.
    prop = _propose(
        client, project_a, "timeline.attach_optional_reference",
        sceneId=scene_b_id, batchBlockId=b_target_batch_id, assetId=asset_a_id,
        role="character", label="cross-project attempt", timelineRevision=b_revision_before,
    )
    # Propose creates the proposal (preview does not validate scene ownership).
    assert prop.status_code == 200, prop.text
    proposal_id = prop.json()["id"]

    approve_res = _approve(client, project_a, proposal_id)
    # The apply handler raises TOOL_TARGET_NOT_FOUND -> HTTP 404 (scope violation).
    assert approve_res.status_code == 404, (
        f"cross-project attach must be rejected with 404, got {approve_res.status_code}: {approve_res.text}"
    )
    try:
        detail = approve_res.json().get("detail", {})
        code = detail.get("code") if isinstance(detail, dict) else None
    except Exception:
        code = None
    assert code == "TOOL_TARGET_NOT_FOUND", (
        f"cross-project rejection must be a TOOL_TARGET_NOT_FOUND scope violation, got {code}"
    )

    # 4. NO PARTIAL WRITES in Project B: batch count, revision, and total references unchanged,
    #    and no foreign assetId leaked onto any batch. (We compare counts rather than
    #    specific batch ids because B's migrated ids are unstable without a persisting write.)
    b_summary_after = _batches_summary(client, project_b, scene_b_id)
    assert b_summary_after["batchCount"] == b_batch_count_before, (
        "Project B's batch count must be unchanged by A's rejected attempt"
    )
    assert int(b_summary_after["timelineRevision"]) == b_revision_before, (
        "Project B's timeline revision must NOT bump from A's rejected attempt"
    )
    b_total_refs_after = sum(b["referenceCount"] for b in b_summary_after["batches"])
    assert b_total_refs_after == b_total_refs_before, (
        "Project B's total reference count must be unchanged - no partial write"
    )
    # And the full master confirms no foreign assetId leaked onto any of B's batches.
    b_master = _master(client, project_b, scene_b_id)
    for batch in b_master["batchBlocks"]:
        assert not any((r.get("assetId") == asset_a_id) for r in (batch.get("references") or [])), (
            "Project B's batches must not contain Project A's assetId reference"
        )

    # 5. NO PARTIAL WRITES in Project A: A's timeline is unchanged (the proposal never applied).
    a_summary_after = _batches_summary(client, project_a, scene_a_id)
    assert a_summary_after["batchCount"] == a_batch_count_before, "Project A's batch count must be unchanged"
    assert int(a_summary_after["timelineRevision"]) == a_revision_before, (
        "Project A's timeline revision must NOT bump from its own rejected attempt"
    )

    # 6. The failed proposal reached a terminal state (durable evidence, not silently retryable).
    refetched = client.get(f"/api/codirector/projects/{project_a}/proposals/{proposal_id}").json()
    assert refetched["status"] in ("failed", "rejected", "completed"), (
        f"the rejected cross-project proposal must reach a terminal state, got {refetched['status']}"
    )


# ---------------------------------------------------------------------------
# Streaming fence regression (U-2 repair)
# ---------------------------------------------------------------------------


def test_streaming_chat_interprets_tool_fence_for_proposal(client, monkeypatch) -> None:
    """Regression: the streaming chat path must route a fenced mutation through _interpret_reply
    and emit a tool_proposal_created event, even when the reply is produced by the deterministic
    foundation/conversation-core path (Build Law #31 / Phase 12 UI-sync prerequisite).
    """
    import json

    from app.codirector.providers.mock import clear_scripted_steps, set_scripted_steps

    monkeypatch.setenv("STUDIO_E2E", "1")
    monkeypatch.setenv("ADEPT_CODIRECTOR_PROVIDER", "mock")
    monkeypatch.setenv("ADEPT_CODIRECTOR_MOCK_SCENARIO", "scripted")

    project_id = _create_project(client, "Stream Fence Regression")
    scene_id = _first_scene(client, project_id)["id"]

    set_scripted_steps([
        {
            "match": "set the scene prompt",
            "reply": "I'll update the scene prompt for you.",
            "tool": {
                "toolId": "set_scene_prompt",
                "responseType": "mutation_proposal",
                "arguments": {
                    "sceneId": scene_id,
                    "prompt": "Regression prompt from streaming fence.",
                },
            },
        }
    ])

    try:
        events: list[dict] = []
        with client.stream(
            "POST",
            "/api/codirector/chat/stream",
            json={"messages": [{"role": "user", "content": "set the scene prompt"}], "project_id": project_id},
        ) as res:
            assert res.status_code == 200, res.text
            for line in res.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                events.append(json.loads(line[len("data:") :].strip()))

        types = [e["type"] for e in events]
        assert "tool_proposal_created" in types, (
            f"expected tool_proposal_created in stream events, got {types}"
        )
        proposal_event = next(e for e in events if e["type"] == "tool_proposal_created")
        assert proposal_event["toolId"] == "set_scene_prompt"

        completed = next(e for e in events if e["type"] == "completed")
        content = completed.get("content", "")
        assert "```tool" not in content, "completed event must not contain the raw tool fence"
        assert "Regression prompt from streaming fence" not in content, (
            "completed event should show the display text, not the tool argument payload"
        )
    finally:
        clear_scripted_steps()


