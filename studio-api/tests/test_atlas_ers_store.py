"""Phase 5 remediation: Atlas request body + ERS store ordering (Subagent 5B).

Covers:
- CDX-031: atlas width/height derive from the requested aspect ratio instead of
  a hardcoded 1280x1280 (default 1:1 stays 1280x1280; wide/tall are non-square).
- CDX-032: when creator reference images are attached, the atlas job payload
  carries source_asset_id (the worker-facing lineage field read by
  queue_worker._imagegen_commit_asset) so the committed atlas asset records
  parent_asset_id / derived_from edges; all refs ride
  creativeContext.originalEnvironmentReferenceAssetIds.
- CDX-042: list_sheets orders newest-first by parsed updatedAt (not filename),
  and the production_handoff fallback picks the newest sheet.
"""

from __future__ import annotations

import uuid

from app.codirector.capabilities.handlers import atlas_generate
from app.environment_reference_sheet import orchestrator, store


def _patch_enqueue(monkeypatch, captured: list[dict]) -> None:
    class _Job:
        def __init__(self) -> None:
            self.id = "job-atlas-cdx"

    def _fake(db, project_id, body, scene_id=None):
        captured.append(dict(body))
        return _Job()

    monkeypatch.setattr("app.storyboard_jobs.enqueue_imagegen_job", _fake)


def _run_atlas(monkeypatch, captured: list[dict], **kwargs) -> dict:
    _patch_enqueue(monkeypatch, captured)
    base = {
        "db": None,
        "project_id": f"proj-{uuid.uuid4()}",
        "execution_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "prompt": "Top-down environment atlas.",
        "scene_description": "A neighborhood environment.",
        "scene_intent": {"sceneTitle": "Cafe", "summary": "A neighborhood environment."},
    }
    base.update(kwargs)
    atlas_generate.handle(**base)
    assert captured, "enqueue_imagegen_job was never called"
    return captured[0]


# ── CDX-031: body dimensions honor the requested aspect ratio ──────────


def test_atlas_default_1_1_keeps_1280_square(monkeypatch) -> None:
    captured: list[dict] = []
    body = _run_atlas(monkeypatch, captured)
    assert body["width"] == 1280
    assert body["height"] == 1280
    assert body["aspectRatio"] == "1:1"


def test_atlas_16_9_body_is_wide(monkeypatch) -> None:
    captured: list[dict] = []
    body = _run_atlas(monkeypatch, captured, aspect_ratio="16:9")
    assert body["width"] == 2400
    assert body["height"] == 1344
    assert body["width"] > body["height"]
    assert body["width"] % 8 == 0 and body["height"] % 8 == 0
    assert body["aspectRatio"] == "16:9"


def test_atlas_9_16_body_is_tall(monkeypatch) -> None:
    captured: list[dict] = []
    body = _run_atlas(monkeypatch, captured, aspect_ratio="9:16")
    assert body["height"] > body["width"]
    assert body["width"] % 8 == 0 and body["height"] % 8 == 0
    assert body["aspectRatio"] == "9:16"


def test_atlas_unknown_aspect_falls_back_to_square_default(monkeypatch) -> None:
    captured: list[dict] = []
    body = _run_atlas(monkeypatch, captured, aspect_ratio="7:5")
    assert (body["width"], body["height"]) == (1280, 1280)


# ── CDX-032: source_asset_id lineage when reference images exist ────────


def test_atlas_body_carries_source_asset_id_with_reference_images(monkeypatch) -> None:
    source_a = "4d3062e8-8c30-4230-8376-bc25d1d4f735"
    source_b = "9b3062e8-8c30-4230-8376-bc25d1d4f7aa"
    captured: list[dict] = []
    body = _run_atlas(monkeypatch, captured, attachment_asset_ids=[source_a, source_b])
    # Worker-facing lineage field: queue_worker._imagegen_commit_asset reads
    # params["source_asset_id"] → parent_asset_id + derived_from/reference_of edge.
    assert body["source_asset_id"] == source_a
    assert body["sourceAssetId"] == source_a
    assert body["referenceImage"] == source_a
    assert body["creativeContext"]["authoritativeSourceAssetId"] == source_a
    # Full lineage chain (all refs) rides creativeContext → prompt_meta.
    assert body["creativeContext"]["originalEnvironmentReferenceAssetIds"] == [source_a, source_b]
    # I2I, never T2I, once a source exists.
    assert body["creativeContext"]["operationIntent"] == "image_to_image_reference"
    assert body["forceWorkflowKey"] == "qwen2512.ref"


def test_atlas_body_without_reference_images_has_no_source_asset_id(monkeypatch) -> None:
    captured: list[dict] = []
    body = _run_atlas(monkeypatch, captured)
    assert not body.get("source_asset_id")
    assert not body.get("sourceAssetId")
    assert not body.get("referenceImage")
    assert "originalEnvironmentReferenceAssetIds" not in body["creativeContext"]
    assert body["creativeContext"]["operationIntent"] == "text_to_image"


# ── CDX-042: list_sheets newest-first by updatedAt; fallback picks newest ─


def _make_sheet(project_id: str, sheet_id: str, updated_at: str):
    sheet = orchestrator.create_sheet(
        project_id=project_id,
        name=f"Sheet {sheet_id[-4:]}",
        description="Environment reference sheet for ordering test.",
    )
    sheet.sheetId = sheet_id
    sheet.updatedAt = updated_at
    store.save_sheet(sheet)
    return sheet


def test_list_sheets_orders_by_updated_at_not_filename() -> None:
    project_id = f"proj-{uuid.uuid4()}"
    # UUID filenames deliberately OUT of updatedAt order: filename order
    # (lexicographic desc) would be ffff > 1111 > 0000, but the newest by
    # updatedAt is 0000… (2026-08-14), then 1111… (2026-08-12), then ffff…
    # (2026-08-10).
    newest = "00000000-0000-4000-8000-00000000000a"
    middle = "11111111-1111-4111-8111-111111111111"
    oldest = "ffffffff-ffff-4fff-8fff-ffffffffffff"
    _make_sheet(project_id, newest, "2026-08-14T18:07:10Z")
    _make_sheet(project_id, oldest, "2026-08-10T09:00:00Z")
    _make_sheet(project_id, middle, "2026-08-12T12:30:00Z")
    ids = [s.sheetId for s in store.list_sheets(project_id)]
    assert ids == [newest, middle, oldest]


def test_list_sheets_malformed_updated_at_sorts_oldest() -> None:
    project_id = f"proj-{uuid.uuid4()}"
    dated = "00000000-0000-4000-8000-000000000001"
    undated = "00000000-0000-4000-8000-000000000002"
    _make_sheet(project_id, dated, "2026-08-14T18:07:10Z")
    bad = orchestrator.create_sheet(
        project_id=project_id,
        name="Undated sheet",
        description="Sheet with an unparseable updatedAt.",
    )
    bad.sheetId = undated
    bad.updatedAt = "not-a-timestamp"
    store.save_sheet(bad)
    ids = [s.sheetId for s in store.list_sheets(project_id)]
    assert ids[0] == dated, f"undated sheet must never be newest, got {ids}"


def test_production_handoff_fallback_picks_newest_sheet() -> None:
    from app.scene_creator.production_handoff import _pick_sheet

    project_id = f"proj-{uuid.uuid4()}"
    newest = _make_sheet(project_id, "00000000-0000-4000-8000-00000000000a", "2026-08-14T18:07:10Z")
    _make_sheet(project_id, "ffffffff-ffff-4fff-8fff-ffffffffffff", "2026-08-10T09:00:00Z")
    picked = _pick_sheet(project_id)
    assert picked.sheetId == newest.sheetId


def test_production_handoff_fallback_picks_newest_composite_sheet() -> None:
    from app.scene_creator.production_handoff import _pick_sheet

    project_id = f"proj-{uuid.uuid4()}"
    newest = _make_sheet(project_id, "00000000-0000-4000-8000-00000000000a", "2026-08-14T18:07:10Z")
    newest.ers_composite_asset_id = "asset-composite-newest"
    store.save_sheet(newest)
    older = _make_sheet(project_id, "ffffffff-ffff-4fff-8fff-ffffffffffff", "2026-08-10T09:00:00Z")
    older.ers_composite_asset_id = "asset-composite-older"
    store.save_sheet(older)
    picked = _pick_sheet(project_id)
    assert picked.sheetId == newest.sheetId