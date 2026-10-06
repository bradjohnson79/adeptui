"""ERS instant snapshot capture — editable master + SS-N versioning (no image gen)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PIL import Image

from app.environment_reference_sheet import snapshots as snap
from app.environment_reference_sheet.contracts import (
    EnvironmentProfile,
    EnvironmentReferenceSheet,
    ERSCompositionRecord,
    ERSCreationPlan,
    ContinuityValidationReport,
)


def _sheet(
    *,
    sheet_id: str = "master-1",
    project_id: str = "proj-1",
    name: str = "Schnick Coffee Shop",
    composite: str = "asset-base-1",
    high_water: int = 0,
    **extra,
) -> EnvironmentReferenceSheet:
    payload = {
        "sheetId": sheet_id,
        "projectId": project_id,
        "name": name,
        "description": "test",
        "profile": EnvironmentProfile(environmentName=name, description="test").model_dump(),
        "creationPlan": ERSCreationPlan(summary="s", creatorPreview="p").model_dump(),
        "composition": ERSCompositionRecord(sheetTitle=name, renderedAssetIds={"composite": composite}).model_dump(),
        "continuity": ContinuityValidationReport().model_dump(),
        "ers_composite_asset_id": composite,
        "recordKind": "original",
        "isEditableMaster": True,
        "snapshotSequenceHighWater": high_water,
        "rootSheetId": sheet_id,
        **extra,
    }
    return EnvironmentReferenceSheet.model_validate(payload)


@pytest.fixture()
def snap_harness(tmp_path, monkeypatch):
    master = _sheet()
    sheets: dict[str, EnvironmentReferenceSheet] = {master.sheetId: master}

    base_png = tmp_path / "base.png"
    Image.new("RGB", (64, 48), color=(40, 80, 120)).save(base_png)

    source = SimpleNamespace(
        id="asset-base-1",
        project_id="proj-1",
        path=str(base_png),
        prompt_meta_json="{}",
    )

    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()

    def _load(pid, sid):
        return sheets.get(sid)

    def _save(sheet):
        sheets[sheet.sheetId] = sheet
        return tmp_path / f"{sheet.sheetId}.json"

    def _list(pid):
        return list(sheets.values())

    monkeypatch.setattr(snap, "load_sheet", _load)
    monkeypatch.setattr(snap, "save_sheet", _save)
    monkeypatch.setattr(snap, "list_sheets", _list)

    def _remove(pid, sid):
        sheets.pop(sid, None)

    monkeypatch.setattr(snap, "_remove_sheet_record", _remove)

    # Avoid real settings/db asset registration — stub register path.
    registered = {}

    def _fake_register(db, **kwargs):
        asset_id = f"baked-{len(registered)+1}"
        dest = assets_dir / f"{asset_id}.png"
        from shutil import copy2
        copy2(kwargs["source_path"], dest)
        asset = SimpleNamespace(id=asset_id, path=str(dest), project_id=kwargs["project_id"])
        registered[asset_id] = asset
        return asset

    monkeypatch.setattr(
        "app.generation_tools.lineage.register_derived_asset",
        _fake_register,
        raising=False,
    )
    # Patch inside module function import path used by _register_baked_asset
    import app.generation_tools.lineage as lineage

    monkeypatch.setattr(lineage, "register_derived_asset", _fake_register)

    from app.config import settings as app_settings

    monkeypatch.setattr(app_settings, "data_dir", tmp_path, raising=False)

    # edit helpers used by capture
    import app.environment_reference_sheet.edit as ers_edit

    monkeypatch.setattr(ers_edit, "resolve_source_asset_id", lambda sheet, sid: sid or "asset-base-1")

    db = MagicMock()
    db.get.side_effect = lambda model, key: source if str(key) == "asset-base-1" else None

    return SimpleNamespace(
        db=db,
        master=master,
        sheets=sheets,
        registered=registered,
        base_png=base_png,
        source=source,
    )


def test_next_snapshot_number_monotonic_and_no_recycle(snap_harness):
    h = snap_harness
    assert snap.next_snapshot_number(h.master) == 1
    h.master.snapshotSequenceHighWater = 3
    # existing SS-2 still listed but high water 3 => next 4
    child = _sheet(sheet_id="snap-2", name="Schnick Coffee Shop SS-2", composite="baked-x")
    child.recordKind = "snapshot"
    child.isEditableMaster = False
    child.snapshotNumber = 2
    child.snapshotOfSheetId = "master-1"
    child.parentSheetId = "master-1"
    h.sheets[child.sheetId] = child
    assert snap.next_snapshot_number(h.master) == 4


def test_capture_creates_snapshot_without_image_gen(snap_harness):
    h = snap_harness
    out = snap.capture_ers_snapshot(
        h.db,
        "proj-1",
        "master-1",
        source_asset_id="asset-base-1",
        legend={
            "position": {"left": 0.42, "top": 0.28, "width": 0.16, "height": 0.42},
            "characters": [{"color": "#ef4444", "label": "Hero"}],
            "props": [{"color": "#22c55e", "label": "Cup"}],
            "userMoved": True,
        },
        drawing_overlay=None,
        text_labels=[{"id": "t1", "text": "Bar", "x": 0.2, "y": 0.3, "fontSize": 14, "color": "#ffffff"}],
        numbered_markers=[{"id": "m1", "number": 1, "x": 0.5, "y": 0.5}],
    )
    assert out["ok"] is True
    assert out["imageGenInvoked"] is False
    assert out["providersInvoked"] == []
    assert out["snapshotNumber"] == 1
    assert out["snapshotName"] == "Schnick Coffee Shop SS-1"
    assert out["bakedAssetId"]
    assert out["masterSheetId"] == "master-1"
    master = h.sheets["master-1"]
    assert master.ers_composite_asset_id == "asset-base-1"  # master never replaced
    assert master.overlayState is not None
    assert master.snapshotSequenceHighWater == 1
    assert master.isEditableMaster is True
    child = h.sheets[out["snapshotSheetId"]]
    assert child.recordKind == "snapshot"
    assert child.isEditableMaster is False
    assert child.snapshotOfSheetId == "master-1"
    assert Path(h.registered[out["bakedAssetId"]].path).is_file()


def test_delete_snapshot_preserves_master_and_numbering(snap_harness):
    h = snap_harness
    first = snap.capture_ers_snapshot(
        h.db, "proj-1", "master-1", source_asset_id="asset-base-1",
        legend={"position": {"left": 0.4, "top": 0.3, "width": 0.16, "height": 0.4}, "characters": [], "props": [], "userMoved": False},
    )
    snap_id = first["snapshotSheetId"]
    deleted = snap.delete_ers_snapshot("proj-1", snap_id)
    assert deleted["ok"] is True
    assert deleted["masterPreserved"] is True
    assert deleted["numberRecycled"] is False
    assert snap_id not in h.sheets
    assert "master-1" in h.sheets
    assert h.sheets["master-1"].snapshotSequenceHighWater == 1
    second = snap.capture_ers_snapshot(
        h.db, "proj-1", "master-1", source_asset_id="asset-base-1",
        legend={"position": {"left": 0.4, "top": 0.3, "width": 0.16, "height": 0.4}, "characters": [], "props": [], "userMoved": False},
    )
    assert second["snapshotNumber"] == 2
    assert second["snapshotName"].endswith("SS-2")


def test_delete_refuses_master(snap_harness):
    with pytest.raises(ValueError, match="Only snapshots"):
        snap.delete_ers_snapshot("proj-1", "master-1")


def test_resolve_editable_master_redirects_snapshot(snap_harness):
    h = snap_harness
    child = _sheet(sheet_id="snap-1", name="X SS-1", composite="baked")
    child.recordKind = "snapshot"
    child.isEditableMaster = False
    child.snapshotNumber = 1
    child.snapshotOfSheetId = "master-1"
    child.parentSheetId = "master-1"
    h.sheets[child.sheetId] = child
    master = snap.resolve_editable_master("proj-1", "snap-1")
    assert master.sheetId == "master-1"



def test_direction_movement_independent_notes(snap_harness):
    h = snap_harness
    a = snap.capture_ers_snapshot(
        h.db,
        "proj-1",
        "master-1",
        source_asset_id="asset-base-1",
        legend={
            "position": {"left": 0.4, "top": 0.3, "width": 0.16, "height": 0.4},
            "characters": [],
            "props": [],
            "userMoved": False,
            "directionMovement": "Walk from door to counter",
        },
    )
    assert a["directionMovement"] == "Walk from door to counter"
    assert a["movementSequenceIndex"] == 1
    ss1 = h.sheets[a["snapshotSheetId"]]
    assert ss1.directionMovement == "Walk from door to counter"
    assert h.sheets["master-1"].directionMovement == "Walk from door to counter"

    b = snap.capture_ers_snapshot(
        h.db,
        "proj-1",
        "master-1",
        source_asset_id="asset-base-1",
        legend={
            "position": {"left": 0.4, "top": 0.3, "width": 0.16, "height": 0.4},
            "characters": [],
            "props": [],
            "userMoved": False,
            "directionMovement": "Sprint through the alley toward the neon sign",
        },
    )
    assert b["snapshotNumber"] == 2
    ss2 = h.sheets[b["snapshotSheetId"]]
    assert ss2.directionMovement == "Sprint through the alley toward the neon sign"
    # Earlier SS note preserved
    assert h.sheets[a["snapshotSheetId"]].directionMovement == "Walk from door to counter"
    assert h.sheets["master-1"].directionMovement == "Sprint through the alley toward the neon sign"
    assert snap.list_display_label(h.sheets["master-1"]) == "Schnick Coffee Shop"
    assert snap.list_display_label(ss1).endswith("SS-1")
    assert snap.list_display_label(ss2).endswith("SS-2")


def test_direction_movement_word_cap():
    words = " ".join(f"w{i}" for i in range(60))
    out = snap.normalize_direction_movement(words)
    assert len(out.split()) == 50
