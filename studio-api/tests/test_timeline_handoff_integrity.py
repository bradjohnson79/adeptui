"""Timeline handoff integrity — CDX-044 + CDX-045.

CDX-044: Scene Creator-owned exports (invented scene_shot_* clipIds) must not
fail CLIP_NOT_FOUND when a saved MAGI sequence exists whose clips list lacks
those clipIds — the m8 membership guard applies only to real MAGI sequence
clip references.

CDX-045: approving a scene-shot take must group the approved asset into a
scene_shots Library collection and persist collection_id on the shot's take
state; unapproved assets never enter the collection.
"""

from __future__ import annotations

import uuid

from app.spatial_map.ers_contracts import SceneShot, SceneShotCandidate


def _session():
    from app.db import SessionLocal, init_db

    init_db()
    return SessionLocal()


def _create_project(name: str = "Timeline Handoff Integrity") -> str:
    from app.db import Project, SessionLocal, init_db

    init_db()
    db = SessionLocal()
    try:
        project_id = str(uuid.uuid4())
        db.add(Project(id=project_id, name=name))
        db.commit()
        return project_id
    finally:
        db.close()


def _create_scene(db, project_id: str) -> str:
    from app.db import Scene

    scene_id = f"scene_{uuid.uuid4().hex[:10]}"
    db.add(Scene(id=scene_id, project_id=project_id, name="Handoff Scene"))
    db.commit()
    return scene_id


def _create_asset(db, project_id: str, *, tag: str = "scene_shot") -> str:
    from app.db import Asset

    asset_id = str(uuid.uuid4())
    db.add(
        Asset(
            id=asset_id,
            project_id=project_id,
            tag=tag,
            kind="image",
            filename=f"{tag}.png",
            path=f"{tag}.png",
            production_approval="none",
        )
    )
    db.commit()
    return asset_id


def _make_shot(db, project_id: str, scene_id: str, *, candidates: list[SceneShotCandidate] | None = None) -> SceneShot:
    from app.spatial_map.ers_persistence import save_scene_shot

    shot = SceneShot(
        project_id=project_id,
        scene_id=scene_id,
        sheet_id="sheet-handoff",
        ers_package_id="ers-handoff",
        intent="Korri walks the atrium",
    )
    shot.candidates = list(candidates or [])
    for c in shot.candidates:
        c.shot_id = shot.id
    save_scene_shot(db, project_id, shot)
    return shot


def _candidate(asset_id: str, *, take_label: str = "Take") -> SceneShotCandidate:
    return SceneShotCandidate(
        id=str(uuid.uuid4()),
        status="complete",
        asset_id=asset_id,
        take_label=take_label,
    )


def _seed_saved_sequence_with_clip(project_id: str, asset_id: str) -> None:
    """Persist a MAGI sequence document that contains one real NLE clip."""
    from app.magi.sequence.store import get_sequence, save_sequence

    seq = get_sequence(project_id)
    seq["tracks"] = [
        {"id": "trk_v1_000001", "kind": "video", "label": "V1", "order": 0},
    ]
    seq["clips"] = [
        {
            "id": "clip_000001",
            "trackId": "trk_v1_000001",
            "assetId": asset_id,
            "name": "NLE Clip",
            "startFrame": 0,
            "durationFrames": 24,
            "inPoint": 0,
            "outPoint": 24,
        }
    ]
    seq["markers"] = []
    save_sequence(project_id, seq)


def _scene_shots_collections(project_id: str) -> list[dict]:
    from app.image_product.collections import list_collections

    return [
        c
        for c in list_collections(project_id)
        if (c.get("metadata") or {}).get("collection_type") == "scene_shots"
    ]


# ---------------------------------------------------------------------------
# CDX-044 — Scene Creator export vs saved-sequence CLIP_NOT_FOUND guard
# ---------------------------------------------------------------------------


def test_send_approved_shot_to_timeline_ok_with_saved_sequence(monkeypatch) -> None:
    """CDX-044: with a saved NLE sequence that has clips, the Scene Creator
    approved-take export must succeed (its scene_shot_* clipId is invented W46
    provenance, never a MAGI sequence clip reference). The m8 guard must not
    reject it."""
    from app.scene_creator.service import send_approved_to_timeline

    project_id = _create_project("CDX-044 Saved Sequence")
    db = _session()
    try:
        scene_id = _create_scene(db, project_id)
        asset_id = _create_asset(db, project_id)
        _seed_saved_sequence_with_clip(project_id, asset_id)

        cand = _candidate(asset_id, take_label="Take 1")
        shot = _make_shot(db, project_id, scene_id, candidates=[cand])
        shot.approved_candidate_id = cand.id
        from app.spatial_map.ers_persistence import save_scene_shot

        save_scene_shot(db, project_id, shot)

        captured: dict = {}

        def _fake_add_batch(session, pid, sid, *, label, planned_duration, **kw):
            return {"ok": True, "batch": {"id": f"bb_{uuid.uuid4().hex[:8]}"}}

        def _fake_add_clip(session, pid, sid, batch_id, body):
            captured["legacyClipId"] = body.get("legacyClipId")
            captured["assetId"] = body.get("assetId")
            return {"ok": True, "clip": {"id": f"bbclip_{uuid.uuid4().hex[:8]}"}}

        monkeypatch.setattr(
            "app.director_timeline_w46.service.add_batch", _fake_add_batch
        )
        monkeypatch.setattr(
            "app.director_timeline_w46.orchestrator.add_clip_to_batch", _fake_add_clip
        )

        result = send_approved_to_timeline(db, project_id, shot.id)

        # The m8 guard must NOT reject the invented scene_shot_* clipId.
        assert result.get("ok") is True, result
        assert result.get("error") is None
        assert result.get("batchBlockId", "").startswith("bb_")
        assert result.get("clips_sent") == 1
        assert str(captured.get("legacyClipId") or "").startswith("scene_shot_")
        assert captured.get("assetId") == asset_id
    finally:
        db.close()


def test_export_non_scene_shot_clip_id_still_rejected_when_sequence_has_clips() -> None:
    """CDX-044 negative control: a genuinely stale MAGI clipId with a saved
    sequence still yields CLIP_NOT_FOUND — the exemption is scoped to the
    Scene Creator scene_shot_* namespace only."""
    from app.magi.timeline_handoff import export_to_timeline

    project_id = _create_project("CDX-044 Stale Guard")
    db = _session()
    try:
        scene_id = _create_scene(db, project_id)
        asset_id = _create_asset(db, project_id)
        _seed_saved_sequence_with_clip(project_id, asset_id)

        result = export_to_timeline(
            db,
            project_id,
            scene_id,
            [{"clipId": "stale_clip", "assetId": asset_id}],
        )
        assert result.get("ok") is False
        assert result.get("error") == "CLIP_NOT_FOUND"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# CDX-045 — approved scene-shot takes enter a scene_shots Library collection
# ---------------------------------------------------------------------------


def test_approved_scene_shot_creates_and_updates_scene_shots_collection() -> None:
    """CDX-045: approving a take creates a scene_shots collection containing
    the approved asset, persists collection_id on the take state, and later
    approvals append to the same collection."""
    from app.scene_creator.service import approve_candidate
    from app.spatial_map.ers_persistence import load_scene_shot

    project_id = _create_project("CDX-045 Collection")
    db = _session()
    try:
        scene_id = _create_scene(db, project_id)
        asset_a = _create_asset(db, project_id, tag="take-a")
        asset_b = _create_asset(db, project_id, tag="take-b")
        cand_a = _candidate(asset_a, take_label="Take A")
        cand_b = _candidate(asset_b, take_label="Take B")
        shot = _make_shot(db, project_id, scene_id, candidates=[cand_a, cand_b])

        approved = approve_candidate(db, project_id, shot.id, cand_a.id)
        col_id = str(approved.take_memory.takeState.get("collection_id") or "")
        assert col_id, "collection_id must be persisted on take state"

        scene_shots = _scene_shots_collections(project_id)
        assert len(scene_shots) == 1
        assert scene_shots[0]["collectionId"] == col_id
        assert asset_a in scene_shots[0]["assetIds"]
        assert (scene_shots[0]["metadata"] or {}).get("shot_id") == shot.id
        assert (scene_shots[0]["metadata"] or {}).get("ers_package_id") == "ers-handoff"

        # Second approval appends to the SAME collection (idempotent grouping).
        approved2 = approve_candidate(db, project_id, shot.id, cand_b.id)
        assert approved2.take_memory.takeState.get("collection_id") == col_id
        scene_shots = _scene_shots_collections(project_id)
        assert len(scene_shots) == 1
        assert asset_a in scene_shots[0]["assetIds"]
        assert asset_b in scene_shots[0]["assetIds"]

        # Persisted on the shot (survives reload).
        reloaded = load_scene_shot(db, project_id, shot.id)
        assert reloaded is not None
        assert reloaded.take_memory.takeState.get("collection_id") == col_id
    finally:
        db.close()


def test_unapproved_shot_asset_not_added_to_collection() -> None:
    """CDX-045: unapproved / non-complete takes are never grouped into the
    scene_shots collection — no collection is created and no asset is added."""
    from app.scene_creator.service import _sync_scene_shots_collection

    project_id = _create_project("CDX-045 No Approval")
    db = _session()
    try:
        scene_id = _create_scene(db, project_id)
        asset_id = _create_asset(db, project_id)
        cand = _candidate(asset_id, take_label="Take")
        shot = _make_shot(db, project_id, scene_id, candidates=[cand])

        # Not the approved candidate -> no-op.
        assert _sync_scene_shots_collection(db, project_id, shot, cand) == ""
        # Approved but not complete -> no-op.
        shot.approved_candidate_id = cand.id
        cand.status = "queued"
        assert _sync_scene_shots_collection(db, project_id, shot, cand) == ""

        assert _scene_shots_collections(project_id) == []
        assert not (shot.take_memory.takeState or {}).get("collection_id")
    finally:
        db.close()


def test_approve_endpoint_still_rejects_ineligible_candidate() -> None:
    """CDX-045: the approval gate itself is unchanged — a non-complete take
    cannot be approved, and approval never creates a collection for it."""
    from app.scene_creator.service import SceneCreatorError, approve_candidate

    project_id = _create_project("CDX-045 Reject")
    db = _session()
    try:
        scene_id = _create_scene(db, project_id)
        asset_id = _create_asset(db, project_id)
        cand = SceneShotCandidate(
            id=str(uuid.uuid4()),
            status="queued",
            asset_id=asset_id,
            take_label="Take",
        )
        shot = _make_shot(db, project_id, scene_id, candidates=[cand])

        try:
            approve_candidate(db, project_id, shot.id, cand.id)
            raise AssertionError("approving a queued take must fail")
        except SceneCreatorError as exc:
            assert "still generating" in str(exc)

        assert _scene_shots_collections(project_id) == []
    finally:
        db.close()