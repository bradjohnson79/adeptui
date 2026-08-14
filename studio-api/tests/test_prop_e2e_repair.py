"""Targeted Prop Creator E2E wiring repairs: ledger prop_ids + delete_prop shot unlink."""

from __future__ import annotations

import uuid


def _session():
    from app.db import SessionLocal, init_db

    init_db()
    return SessionLocal()


def _create_project(name: str = "Prop E2E Repair") -> str:
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


def test_record_ledger_keeps_prop_ids(monkeypatch) -> None:
    captured: dict = {}

    def fake_record(project_id, batch_block_id, entries, **kwargs):
        captured["project_id"] = project_id
        captured["batch_block_id"] = batch_block_id
        captured["entries"] = entries
        captured["kwargs"] = kwargs
        return {}

    monkeypatch.setattr("app.magi.sequence.store.record_export_ledger", fake_record)
    from app.magi.timeline_handoff import _record_ledger

    _record_ledger(
        "proj-1",
        "bb_1",
        [{"clipId": "c1", "assetId": "a1", "prop_ids": ["prop-aaa", "prop-bbb"]}],
        [{"clip": {"id": "w46_1"}}],
        scene_id="s1",
        label="Scene Creator batch",
    )
    entry = captured["entries"][0]
    assert entry["clipId"] == "c1"
    assert entry["w46ClipId"] == "w46_1"
    assert entry["assetId"] == "a1"
    assert entry["prop_ids"] == ["prop-aaa", "prop-bbb"]

    _record_ledger(
        "proj-1",
        "bb_2",
        [{"clipId": "c2", "assetId": "a2"}],
        [{"clip": {"id": "w46_2"}}],
        scene_id="s1",
        label="MAGI export",
    )
    assert captured["entries"][0]["prop_ids"] == []


def test_delete_prop_clears_shot_prop_entity_ids() -> None:
    from app.prop_creator.service import create_or_update_prop, delete_prop
    from app.spatial_map.ers_contracts import SceneShot, SceneShotTakeMemory
    from app.spatial_map.ers_persistence import load_scene_shot, save_scene_shot

    project_id = _create_project("Delete Shot Unlink")
    db = _session()
    try:
        prop = create_or_update_prop(db, project_id, name="Mug")
        other_id = "keep-other-prop"
        shot = SceneShot(
            project_id=project_id,
            scene_id="scene-1",
            sheet_id="sheet-1",
            prop_entity_ids=[prop.id, other_id],
            take_memory=SceneShotTakeMemory(blocking={"prop_entity_ids": [prop.id, other_id]}),
        )
        save_scene_shot(db, project_id, shot)
        result = delete_prop(db, project_id, prop.id)
        assert result["ok"] is True
        assert result["library_assets_kept"] is True
        assert result["shots_unlinked"] == 1
        reloaded = load_scene_shot(db, project_id, shot.id)
        assert reloaded is not None
        assert prop.id not in reloaded.prop_entity_ids
        assert other_id in reloaded.prop_entity_ids
        assert prop.id not in (reloaded.take_memory.blocking.get("prop_entity_ids") or [])
        assert other_id in (reloaded.take_memory.blocking.get("prop_entity_ids") or [])
    finally:
        db.close()
