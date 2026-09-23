"""Scene production API/persistence laws — prepared state survives reload.

Covers the persistence half of the Universal Scene Intelligence mission:

- prepared DirectorSceneIntent persists (active production store)
- compiled Timeline prompt persists on the scene + batch prompt segments
- canonical tags survive reload (no suffix drift)
- reference bindings persist; retry does NOT duplicate them
- scene addressing ("For Scene 3") targets the right scene
- multi-batch scenes create N batch blocks and one scene-level Timed Prompt
- missing references fail closed (no fabricated bindings, no fake success)
"""

from __future__ import annotations

import base64
import uuid

import pytest

from app.db import Asset, Project, Scene, SessionLocal
from app.character_identity.crs_service import persist_crs_in_session
from app.character_identity.models import CharacterProfileRow
from app.character_identity.schemas import CharacterProfileCreate
from app.character_identity.service import create_profile

_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_project(client, name: str) -> str:
    response = client.post("/api/projects", json={"name": f"{name} {uuid.uuid4().hex[:8]}"})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _upload_png(client, project_id: str, tag: str) -> str:
    res = client.post(
        f"/api/projects/{project_id}/assets",
        files={"file": (f"{tag}.png", _ONE_PIXEL_PNG, "image/png")},
        data={"tag": tag, "kind": "image"},
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _approve_environment(client, project_id: str, name: str, tag: str) -> tuple[str, str]:
    asset_id = _upload_png(client, project_id, tag)
    res = client.post(
        f"/api/environment-reference-sheets/projects/{project_id}/save",
        json={"name": name, "environmentPrompt": "test environment", "referenceImageAssetId": asset_id},
    )
    assert res.status_code == 200, res.text
    sheet_id = res.json()["sheet"]["sheetId"]
    approve = client.post(
        f"/api/environment-reference-sheets/projects/{project_id}/{sheet_id}/approve-reference",
        json={"assetId": asset_id},
    )
    assert approve.status_code == 200, approve.text
    return sheet_id, asset_id


def _seed_character(db, project_id: str, name: str, slug: str) -> tuple[str, str]:
    profile = create_profile(db, project_id, CharacterProfileCreate(name=name, slug=slug, role="lead"))
    asset_id = str(uuid.uuid4())
    db.add(
        Asset(
            id=asset_id,
            project_id=project_id,
            tag=f"{slug}-crs",
            kind="image",
            filename=f"{slug}-crs.png",
            path=f"/tmp/{slug}-crs.png",
        )
    )
    db.commit()
    persist_crs_in_session(db, db.get(CharacterProfileRow, profile.id), asset_id=asset_id)
    db.commit()
    return profile.id, asset_id


def _seed_prop(db, project_id: str, name: str, tag: str) -> tuple[str, str]:
    from app.prop_creator.service import create_or_update_prop, use_as_prop_identity

    prop = create_or_update_prop(db, project_id, name=name)
    asset_id = str(uuid.uuid4())
    db.add(
        Asset(
            id=asset_id,
            project_id=project_id,
            tag=tag,
            kind="image",
            filename=f"{tag}.png",
            path=f"/tmp/{tag}.png",
        )
    )
    db.commit()
    use_as_prop_identity(db, project_id, prop.id, asset_id=asset_id)
    db.commit()
    return prop.id, asset_id


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _prepare(db, project_id: str, message: str, scene_id: str = ""):
    from app.codirector.production.orchestrator import prepare_production_request

    return prepare_production_request(
        db,
        project_id=project_id,
        message=message,
        scene_id=scene_id,
        allow_llm=False,  # deterministic Layer B for persistence assertions
    )


def _load_master(db, project_id: str, scene_id: str):
    from app.director_timeline_w46 import store
    from app.director_timeline_w46.contracts import SceneTimelineMaster

    loaded = store.load_master(db, project_id, scene_id)
    assert loaded.get("ok"), loaded
    return SceneTimelineMaster.model_validate(loaded["master"])


# ---------------------------------------------------------------------------
# 1. Full prepare persists intent + prompt + tags across reload
# ---------------------------------------------------------------------------

def test_prepare_persists_intent_prompt_and_tags_across_reload(client, db_session) -> None:
    project_id = _create_project(client, "Persist Scene")
    _approve_environment(client, project_id, "Venture Corridor Scene", "venture_corridor")
    _seed_character(db_session, project_id, "Cade O'Connor", "cade-oconnor")
    _seed_prop(db_session, project_id, "Cade's Starfighter", "cades-starfighter")

    message = (
        "Create a Timeline scene using the Venture Corridor Scene environment reference sheet as the setting, "
        "with the Character reference of Cade O'Connor and the Cade's Starfighter prop reference sheet. "
        "The starfighter drifts into the corridor and docks. Cade climbs out and walks toward camera. "
        "Do not reveal Cade before the docking clamps lock. "
        "CADE: \"Docking confirmed.\" "
        "10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP."
    )
    prepared = _prepare(db_session, project_id, message)
    assert prepared.ok, prepared.error
    spec = prepared.spec

    # References verified with canonical tags.
    by_tag = {r.canonical_tag: r for r in spec.references}
    assert "#VentureCorridorScene" in by_tag
    assert "@CadeOConnor" in by_tag
    assert "%CadeSStarfighter" in by_tag
    assert all(r.status == "found" for r in spec.references)

    # Grounded milestones emitted.
    event_types = [e.type for e in prepared.events]
    assert "environment_identified" in event_types
    assert "references_verified" in event_types
    assert "scene_structure_analyzed" in event_types
    assert "dialogue_detected" in event_types
    assert "reveals_identified" in event_types
    assert "action_synthesized" in event_types
    assert "prompt_compiled" in event_types

    # Compiled prompt carries canonical identity, no drift, no runtime dump in ACTION.
    from app.codirector.production.prompt_compiler import extract_prompt_section

    prompt = prepared.compiled_prompt
    assert "@CadeOConnor" in prompt
    assert "#VentureCorridorScene" in prompt
    assert "%CadeSStarfighter" in prompt
    assert "@CadeOConnor2" not in prompt and "#VentureCorridorScene2" not in prompt
    action = extract_prompt_section(prompt, "ACTION")
    assert "10 seconds" not in action and "21:9" not in action and "MiniMax" not in action
    assert '"Docking confirmed."' in action

    # Active production store persists spec + intent.
    from app.codirector.production.orchestrator import load_active_production

    active = load_active_production(db_session, project_id)
    assert active["sceneId"] == prepared.scene_id
    assert active["shotId"] == prepared.shot_id
    persisted_spec = active["spec"]
    assert persisted_spec["director_intent"]["action_text"] == spec.director_intent.action_text
    assert persisted_spec["director_intent"]["dialogue"][0]["line"] == "Docking confirmed."
    assert active["compiledPrompt"] == prepared.compiled_prompt

    # Scene row persists the compiled prompt.
    scene = db_session.get(Scene, prepared.scene_id)
    assert scene is not None
    assert scene.prompt == prepared.compiled_prompt

    # Timeline master persists batch prompt segments with tags — survives reload.
    master = _load_master(db_session, project_id, prepared.scene_id)
    batches = [
        b for b in master.batchBlocks
        if (b.migrationMetadata or {}).get("sourceProductionRequestId") == spec.production_request_id
    ]
    assert len(batches) == 1
    # No leftover fresh-scene seed block: the prepared scene has exactly its
    # production batches, not a duplicate default batch carrying the prompt.
    assert len(master.batchBlocks) == 1
    segment_text = batches[0].promptSegments[0].text
    assert "@CadeOConnor" in segment_text
    assert "#VentureCorridorScene" in segment_text
    assert batches[0].duration.plannedDuration == pytest.approx(10.0)

    # Reference bindings persisted on the scene.
    from app.scene_references import repository as ref_repo

    bindings = ref_repo.list_bindings(db_session, project_id, scope_type="scene", scope_id=prepared.scene_id)
    assert len(bindings) == 3


# ---------------------------------------------------------------------------
# 2. Retry: follow-up re-synthesizes without duplicating bindings
# ---------------------------------------------------------------------------

def test_retry_followup_reuses_scene_and_does_not_duplicate_bindings(client, db_session) -> None:
    project_id = _create_project(client, "Retry Scene")
    _approve_environment(client, project_id, "Neon Harbor", "neon_harbor")
    _seed_character(db_session, project_id, "Mara Voss", "mara-voss")

    first = _prepare(
        db_session,
        project_id,
        "Build a Timeline scene with the Character reference of Mara Voss inside the Neon Harbor "
        "environment reference sheet. Mara walks along the dock. 10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP.",
    )
    assert first.ok, first.error

    from app.scene_references import repository as ref_repo

    before = ref_repo.list_bindings(db_session, project_id, scope_type="scene", scope_id=first.scene_id)
    assert len(before) == 2

    follow = _prepare(
        db_session,
        project_id,
        "Actually make her walk more slowly and add light rain.",
    )
    assert follow.ok, follow.error
    # Same scene + shot identity (no blank restart).
    assert follow.scene_id == first.scene_id
    assert follow.shot_id == first.shot_id
    # Prompt was re-synthesized from original + revision context.
    assert follow.compiled_prompt != first.compiled_prompt
    assert "rain" in follow.compiled_prompt.lower()
    # No duplicate bindings after retry.
    after = ref_repo.list_bindings(db_session, project_id, scope_type="scene", scope_id=first.scene_id)
    assert len(after) == 2
    assert {b.id for b in after} == {b.id for b in before}
    # Tags still canonical after retry.
    assert "@MaraVoss" in follow.compiled_prompt
    assert "#NeonHarbor" in follow.compiled_prompt


# ---------------------------------------------------------------------------
# 3. Scene addressing by number
# ---------------------------------------------------------------------------

def test_scene_addressing_by_number_targets_named_scene(client, db_session) -> None:
    project_id = _create_project(client, "Address Scene")
    _approve_environment(client, project_id, "Salt Flats", "salt_flats")
    for index in range(3):
        db_session.add(
            Scene(
                id=str(uuid.uuid4()),
                project_id=project_id,
                name=f"Scene {index + 1}",
                index=index,
            )
        )
    db_session.commit()
    target = next(
        row for row in db_session.query(Scene).filter(Scene.project_id == project_id).all()
        if row.name == "Scene 3"
    )

    prepared = _prepare(
        db_session,
        project_id,
        "For Scene 3, create a Timeline prompt using the Salt Flats environment reference sheet as the "
        "setting. Slow aerial drift over the flats at dawn. 10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP.",
    )
    assert prepared.ok, prepared.error
    assert prepared.scene_id == target.id


# ---------------------------------------------------------------------------
# 4. Multi-batch Timeline blocks
# ---------------------------------------------------------------------------

def test_multi_batch_scene_creates_windowed_batch_blocks(client, db_session) -> None:
    project_id = _create_project(client, "Multi Batch")
    _approve_environment(client, project_id, "Flooded Arcade", "flooded_arcade")
    _seed_character(db_session, project_id, "Jun Park", "jun-park")

    prepared = _prepare(
        db_session,
        project_id,
        "Build a Timeline scene in the Flooded Arcade environment with the Character reference of Jun Park. "
        "Jun wades in from the left. He stops and listens. A sign crashes down behind him. "
        "He turns toward the sound, then keeps moving and exits frame right. "
        "20 seconds, 2 batches, MiniMax H3, 21:9, 1.0 MP.",
    )
    assert prepared.ok, prepared.error
    spec = prepared.spec
    assert spec.batch_count == 2

    master = _load_master(db_session, project_id, prepared.scene_id)
    batches = sorted(
        (
            b for b in master.batchBlocks
            if (b.migrationMetadata or {}).get("sourceProductionRequestId") == spec.production_request_id
        ),
        key=lambda b: int((b.migrationMetadata or {}).get("sourceProductionBatchIndex") or 0),
    )
    assert len(batches) == 2
    # No leftover fresh-scene seed block alongside the two production batches.
    assert len(master.batchBlocks) == 2
    # Capability-driven windows (full windows, partial final): MiniMax H3
    # certified single-pass window is 15s, so a 20s scene plans 0-15 + 15-20.
    assert batches[0].duration.plannedDuration == pytest.approx(15.0)
    assert batches[1].duration.plannedDuration == pytest.approx(5.0)
    from app.director_timeline_w46.migration_reconcile import project_prompts_to_legacy

    # 12B working-Timeline shape: EVERY batch owns a window-scoped segment and
    # projects its own Timed Prompt entry (0-15 and 15-20 visible entries).
    timed = project_prompts_to_legacy(master)
    assert len(timed) == 2, "each batch must project its own window prompt"
    timed_sorted = sorted(timed, key=lambda t: t["start"])
    assert timed_sorted[0]["start"] == pytest.approx(0.0)
    assert timed_sorted[0]["length"] == pytest.approx(15.0)
    assert timed_sorted[1]["start"] == pytest.approx(15.0)
    assert timed_sorted[1]["length"] == pytest.approx(5.0)
    scene_prompt = " ".join(t["text"] for t in timed_sorted)
    assert "wades" in scene_prompt.lower()
    assert "exits" in scene_prompt.lower() or "exit" in scene_prompt.lower()
    assert "@JunPark" in scene_prompt
    # Both batches own prompt text — later batches are NOT empty render windows.
    assert any((seg.text or "").strip() for seg in batches[0].promptSegments)
    assert any((seg.text or "").strip() for seg in batches[1].promptSegments)
    # Batch segments are batch-local (start 0.0) — the 12B convention.
    assert all(seg.start == pytest.approx(0.0) for b in batches for seg in b.promptSegments)


def _production_batches(master, request_id: str = ""):
    rows = [
        b
        for b in master.batchBlocks
        if (b.migrationMetadata or {}).get("codirectorSceneProduction")
    ]
    if request_id:
        rows = [
            b
            for b in rows
            if (b.migrationMetadata or {}).get("sourceProductionRequestId") == request_id
        ]
    return sorted(
        rows,
        key=lambda b: int((b.migrationMetadata or {}).get("sourceProductionBatchIndex") or 0),
    )


def test_retry_followup_multibatch_reuses_all_batches(client, db_session) -> None:
    """A non-structural follow-up on a 2-batch scene must re-synthesize in
    place: same request id, same batch ids, no duplicated batch blocks, and
    inherited aspect ratio (never a silent reset to 16:9)."""
    project_id = _create_project(client, "Retry Multi")
    _approve_environment(client, project_id, "Flooded Arcade", "flooded_arcade")
    _seed_character(db_session, project_id, "Jun Park", "jun-park")

    first = _prepare(
        db_session,
        project_id,
        "Build a Timeline scene in the Flooded Arcade environment with the Character reference of Jun Park. "
        "Jun wades in from the left. He stops and listens. A sign crashes down behind him. "
        "He turns toward the sound, then keeps moving and exits frame right. "
        "20 seconds, 2 batches, MiniMax H3, 21:9, 1.0 MP.",
    )
    assert first.ok, first.error
    master_before = _load_master(db_session, project_id, first.scene_id)
    ids_before = [b.id for b in _production_batches(master_before)]
    assert len(ids_before) == 2
    assert len(master_before.batchBlocks) == 2

    follow = _prepare(
        db_session,
        project_id,
        "Actually make the sign crash louder and add flickering lights.",
    )
    assert follow.ok, follow.error
    assert follow.scene_id == first.scene_id
    # Effective spec unchanged structurally → same idempotency key.
    assert follow.spec.production_request_id == first.spec.production_request_id
    # Aspect ratio inherited from the validated prior spec, not reset.
    assert follow.spec.aspect_ratio == "21:9"

    master_after = _load_master(db_session, project_id, first.scene_id)
    ids_after = [b.id for b in _production_batches(master_after)]
    assert ids_after == ids_before, "retry must reuse both batch blocks, not duplicate them"
    assert len(master_after.batchBlocks) == 2
    # Prompt was re-synthesized with the revision.
    scene_text = " ".join(
        (seg.text or "")
        for batch in master_after.batchBlocks
        for seg in (batch.promptSegments or [])
    )
    assert "flickering" in scene_text.lower() or "flickering" in (follow.compiled_prompt or "").lower()


def test_retry_followup_structural_change_adopts_prior_batches(client, db_session) -> None:
    """A structural follow-up (duration/batch count changes) mints a new
    request id — the builder must ADOPT the scene's prior CD batches and
    re-stamp them, never leave orphans alongside duplicates."""
    project_id = _create_project(client, "Retry Structural")
    _approve_environment(client, project_id, "Flooded Arcade", "flooded_arcade")
    _seed_character(db_session, project_id, "Jun Park", "jun-park")

    first = _prepare(
        db_session,
        project_id,
        "Build a Timeline scene in the Flooded Arcade environment with the Character reference of Jun Park. "
        "Jun wades in from the left. He stops and listens. A sign crashes down behind him. "
        "He turns toward the sound, then keeps moving and exits frame right. "
        "20 seconds, 2 batches, MiniMax H3, 21:9, 1.0 MP.",
    )
    assert first.ok, first.error
    ids_before = [b.id for b in _production_batches(_load_master(db_session, project_id, first.scene_id))]
    assert len(ids_before) == 2

    follow = _prepare(
        db_session,
        project_id,
        "Actually make it 30 seconds with 3 batches.",
    )
    assert follow.ok, follow.error
    assert follow.spec.batch_count == 3
    assert follow.spec.production_request_id != first.spec.production_request_id

    master_after = _load_master(db_session, project_id, first.scene_id)
    # Exactly three batch blocks total — two adopted, one created, zero orphans.
    assert len(master_after.batchBlocks) == 3
    current = _production_batches(master_after, follow.spec.production_request_id)
    assert len(current) == 3
    stale = [
        b
        for b in master_after.batchBlocks
        if (b.migrationMetadata or {}).get("sourceProductionRequestId") == first.spec.production_request_id
    ]
    assert not stale, "prior request id must be fully superseded"
    adopted = [b for b in current if b.id in ids_before]
    assert len(adopted) == 2, "both prior batches adopted into the new request"
    assert all(
        b.duration.plannedDuration == pytest.approx(10.0) for b in current
    )


def test_retry_followup_batch_reduction_prunes_surplus(client, db_session) -> None:
    """An explicit "1 batch" follow-up on a 2-batch scene is an intentional
    structural reduction: the count must be honored (not overwritten by the
    prior spec) and the surplus batch block must be removed, not left stale."""
    project_id = _create_project(client, "Retry Reduce")
    _approve_environment(client, project_id, "Flooded Arcade", "flooded_arcade")
    _seed_character(db_session, project_id, "Jun Park", "jun-park")

    first = _prepare(
        db_session,
        project_id,
        "Build a Timeline scene in the Flooded Arcade environment with the Character reference of Jun Park. "
        "Jun wades in from the left. He stops and listens. A sign crashes down behind him. "
        "He turns toward the sound, then keeps moving and exits frame right. "
        "20 seconds, 2 batches, MiniMax H3, 21:9, 1.0 MP.",
    )
    assert first.ok, first.error
    assert len(_load_master(db_session, project_id, first.scene_id).batchBlocks) == 2

    follow = _prepare(
        db_session,
        project_id,
        "Actually make it 10 seconds with 1 batch.",
    )
    assert follow.ok, follow.error
    assert follow.spec.batch_count == 1, "explicit '1 batch' must survive the prior-spec restore"
    master_after = _load_master(db_session, project_id, first.scene_id)
    assert len(master_after.batchBlocks) == 1, "surplus batch must be pruned, not left stale"
    only = master_after.batchBlocks[0]
    assert only.duration.plannedDuration == pytest.approx(10.0)
    assert (only.migrationMetadata or {}).get("sourceProductionRequestId") == follow.spec.production_request_id


def test_batch_reduction_preserves_history_bearing_surplus(client, db_session) -> None:
    """Pruning must never delete a batch that carries execution provenance:
    ExecutionSnapshots are immutable audit records keyed by snapshot id and
    linked via batchBlockId — a surplus batch with a referencing snapshot
    stays, and no snapshot is removed."""
    from app.director_timeline_w46.contracts import ExecutionSnapshot

    project_id = _create_project(client, "Retry Reduce History")
    _approve_environment(client, project_id, "Flooded Arcade", "flooded_arcade")
    _seed_character(db_session, project_id, "Jun Park", "jun-park")

    first = _prepare(
        db_session,
        project_id,
        "Build a Timeline scene in the Flooded Arcade environment with the Character reference of Jun Park. "
        "Jun wades in from the left. He stops and listens. A sign crashes down behind him. "
        "He turns toward the sound, then keeps moving and exits frame right. "
        "20 seconds, 2 batches, MiniMax H3, 21:9, 1.0 MP.",
    )
    assert first.ok, first.error
    master = _load_master(db_session, project_id, first.scene_id)
    assert len(master.batchBlocks) == 2
    # Simulate execution provenance on the surplus batch (index 1).
    history_batch = master.batchBlocks[1]
    snap = ExecutionSnapshot(batchBlockId=history_batch.id)
    master.executionSnapshots[snap.id] = snap
    from app.director_timeline_w46 import store

    store.save_master(db_session, project_id, first.scene_id, master)

    follow = _prepare(
        db_session,
        project_id,
        "Actually make it 10 seconds with 1 batch.",
    )
    assert follow.ok, follow.error
    master_after = _load_master(db_session, project_id, first.scene_id)
    remaining = {b.id for b in master_after.batchBlocks}
    assert history_batch.id in remaining, "history-bearing batch must survive pruning"
    assert snap.id in master_after.executionSnapshots, "immutable snapshot must never be removed"
    assert len(master_after.batchBlocks) == 2  # 1 rewritten + 1 preserved history


# ---------------------------------------------------------------------------
# 5. Missing references fail closed
# ---------------------------------------------------------------------------

def test_missing_reference_fails_closed_without_fabrication(client, db_session) -> None:
    project_id = _create_project(client, "Fail Closed")
    _approve_environment(client, project_id, "Derelict Station", "derelict_station")

    prepared = _prepare(
        db_session,
        project_id,
        "Build a Timeline scene with the Character reference of Nonexistent Person inside the "
        "Derelict Station environment reference sheet. 10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP.",
    )
    assert not prepared.ok
    assert prepared.error_code == "REFERENCE_RESOLUTION_FAILED"
    event_types = [e.type for e in prepared.events]
    assert "reference_missing" in event_types
    # No scene was prepared and no active production was saved.
    from app.codirector.production.orchestrator import load_active_production

    assert load_active_production(db_session, project_id) == {}
