"""MAGI sequence persistence repairs — m1 (GET-write fix, PUT validation) +
m2 (asset ownership) + m8 (structured error envelope)."""

from __future__ import annotations

import uuid

from app.db import Asset, SessionLocal, init_db
from app.magi.sequence.store import get_sequence, save_sequence


def _create_project(client, name: str = "MAGI Persistence") -> str:
    res = client.post("/api/projects", json={"name": name, "global_prompt": "Test."})
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _seed_asset(project_id: str, *, tag: str = "asset", kind: str = "image") -> str:
    init_db()
    db = SessionLocal()
    try:
        asset_id = str(uuid.uuid4())
        db.add(
            Asset(
                id=asset_id,
                project_id=project_id,
                tag=tag,
                kind=kind,
                filename=f"{tag}.png",
                path="",
            )
        )
        db.commit()
        return asset_id
    finally:
        db.close()


def _seq_body(project_id: str, asset_id: str | None = None) -> dict:
    """A structurally valid sequence with a clip (or empty clips when None)."""
    seq = get_sequence(project_id)
    seq["tracks"] = [
        {"id": "trk_v1_000001", "kind": "video", "label": "V1", "order": 0},
        {"id": "trk_v1_000002", "kind": "video", "label": "V2", "order": 1},
    ]
    seq["clips"] = (
        [
            {
                "id": "clip_000001",
                "trackId": "trk_v1_000001",
                "assetId": asset_id,
                "name": "Clip",
                "startFrame": 0,
                "durationFrames": 24,
                "inPoint": 0,
                "outPoint": 24,
            }
        ]
        if asset_id
        else []
    )
    seq["markers"] = []
    return seq


def test_get_sequence_does_not_persist_on_read():
    """m1 P2 fix: GET on a missing project must not create a file."""
    from pathlib import Path

    from app.config import settings

    project_id = "no-such-project"
    seq = get_sequence(project_id)
    assert seq["projectId"] == project_id
    assert seq["clips"] == []
    path = Path(settings.data_dir) / "magi" / "sequences" / project_id / "sequence.json"
    assert not path.exists(), "GET must not persist an empty sequence on read"


def test_save_sequence_validates_schema_and_persists(client):
    project_id = _create_project(client)
    asset_id = _seed_asset(project_id)
    saved = save_sequence(project_id, _seq_body(project_id, asset_id))
    assert saved["projectId"] == project_id
    assert saved["clips"][0]["assetId"] == asset_id
    assert saved["clips"][0]["id"] == "clip_000001"
    # Persisted on disk, reloadable byte-for-byte.
    reloaded = get_sequence(project_id)
    assert reloaded["clips"][0]["id"] == "clip_000001"
    assert reloaded["revision"] == saved["revision"]


def test_save_sequence_rejects_invalid_schema(client):
    project_id = _create_project(client)
    bad = _seq_body(project_id)
    bad["clips"] = [
        {
            "id": "clip_bad",
            "trackId": "trk_does_not_exist",
            "assetId": "anything",
            "startFrame": 0,
            "durationFrames": 24,
            "inPoint": 0,
            "outPoint": 24,
        }
    ]
    try:
        save_sequence(project_id, bad)
        raise AssertionError("expected ValueError for unknown trackId")
    except ValueError as exc:
        assert "trackId" in str(exc)


def test_save_sequence_rejects_negative_playhead(client):
    project_id = _create_project(client)
    bad = _seq_body(project_id)
    bad["playheadFrame"] = -5
    try:
        save_sequence(project_id, bad)
        raise AssertionError("expected ValueError for negative playhead")
    except ValueError as exc:
        assert "playheadFrame" in str(exc)


def test_put_sequence_rejects_cross_project_asset(client):
    """m2/m1 A4: an asset owned by another project must be rejected with a
    structured ASSET_PROJECT_MISMATCH envelope (not silently persisted)."""
    project_a = _create_project(client, "Project A")
    project_b = _create_project(client, "Project B")
    asset_in_b = _seed_asset(project_b)

    body = _seq_body(project_a, asset_in_b)
    res = client.put(f"/api/magi/projects/{project_a}/sequence", json={"sequence": body})
    assert res.status_code == 400
    data = res.json()
    assert data["detail"]["error"]["code"] == "ASSET_PROJECT_MISMATCH"
    assert "another project" in data["detail"]["error"]["message"]
    assert data["detail"]["error"]["fields"]["assetIds"] == [asset_in_b]


def test_put_sequence_rejects_unknown_asset(client):
    project_id = _create_project(client)
    body = _seq_body(project_id, asset_id="clip_unknown_asset_zzz")
    res = client.put(f"/api/magi/projects/{project_id}/sequence", json={"sequence": body})
    assert res.status_code == 400
    data = res.json()
    assert data["detail"]["error"]["code"] == "ASSET_NOT_FOUND"
    assert data["detail"]["error"]["fields"]["assetIds"] == ["clip_unknown_asset_zzz"]


def test_put_sequence_rejects_clip_without_asset(client):
    """m1 A4: a clip with no asset reference is an INVALID_CLIP_ASSET (422)."""
    project_id = _create_project(client)
    body = _seq_body(project_id)
    body["clips"] = [
        {
            "id": "clip_no_asset",
            "trackId": "trk_v1_000001",
            "assetId": "",
            "name": "No asset",
            "startFrame": 0,
            "durationFrames": 24,
            "inPoint": 0,
            "outPoint": 24,
        }
    ]
    res = client.put(f"/api/magi/projects/{project_id}/sequence", json={"sequence": body})
    assert res.status_code == 422
    data = res.json()
    assert data["detail"]["error"]["code"] == "INVALID_CLIP_ASSET"
    assert data["detail"]["error"]["fields"]["clipIds"] == ["clip_no_asset"]


def test_put_sequence_accepts_owned_asset(client):
    project_id = _create_project(client)
    asset_id = _seed_asset(project_id)
    body = _seq_body(project_id, asset_id)
    res = client.put(f"/api/magi/projects/{project_id}/sequence", json={"sequence": body})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["sequence"]["clips"][0]["assetId"] == asset_id
    assert data["sequence"]["clips"][0]["id"] == "clip_000001"


def test_put_sequence_rejects_malformed_document(client):
    project_id = _create_project(client)
    body = _seq_body(project_id)
    body["frameRate"] = "not-a-number"
    res = client.put(f"/api/magi/projects/{project_id}/sequence", json={"sequence": body})
    assert res.status_code == 400
    data = res.json()
    assert data["detail"]["error"]["code"] == "INVALID_SEQUENCE"
    assert data["detail"]["error"]["fields"]["errors"]


def test_lineage_fields_preserved_on_save(client):
    """m2: optional lineage fields survive persistence."""
    project_id = _create_project(client)
    asset_id = _seed_asset(project_id)
    body = _seq_body(project_id, asset_id)
    body["clips"][0]["batchBlockId"] = "bb_1234"
    body["clips"][0]["sceneId"] = "scene_99"
    saved = save_sequence(project_id, body)
    assert saved["clips"][0]["batchBlockId"] == "bb_1234"
    assert saved["clips"][0]["sceneId"] == "scene_99"


def test_get_sequence_returns_empty_for_missing_file_without_side_effect(client):
    project_id = _create_project(client)
    res = client.get(f"/api/magi/projects/{project_id}/sequence")
    assert res.status_code == 200
    assert res.json()["sequence"]["clips"] == []
    # A second GET returns the same empty shape (nothing written between).
    res2 = client.get(f"/api/magi/projects/{project_id}/sequence")
    assert res2.status_code == 200
    assert res2.json()["sequence"]["clips"] == []


def test_get_sequence_returns_identical_document_on_repeated_read(client):
    """m1 A2: GET must be read-only — repeated reads return byte-identical
    documents (same revision and updatedAt), proving no write side-effect."""
    project_id = _create_project(client)
    asset_id = _seed_asset(project_id)
    body = _seq_body(project_id, asset_id)
    saved = save_sequence(project_id, body)
    first = client.get(f"/api/magi/projects/{project_id}/sequence").json()["sequence"]
    second = client.get(f"/api/magi/projects/{project_id}/sequence").json()["sequence"]
    assert first["revision"] == saved["revision"]
    assert first["updatedAt"] == saved["updatedAt"]
    assert first == second


def test_put_sequence_expected_revision_mismatch_is_409(client):
    """m1 A3: optimistic concurrency — a stale expectedRevision is refused with
    409 and the server document is left untouched (no last-writer-wins)."""
    project_id = _create_project(client)
    asset_id = _seed_asset(project_id)
    body = _seq_body(project_id, asset_id)
    first = client.put(f"/api/magi/projects/{project_id}/sequence", json={"sequence": body})
    assert first.status_code == 200, first.text
    revision_after_first = first.json()["sequence"]["revision"]

    # A stale expectedRevision (the value the client would have observed before
    # the first PUT) must conflict.
    stale_body = _seq_body(project_id, asset_id)
    stale_body["clips"][0]["name"] = "stale overwrite"
    res = client.put(
        f"/api/magi/projects/{project_id}/sequence",
        json={"sequence": stale_body, "expectedRevision": revision_after_first - 1},
    )
    assert res.status_code == 409
    data = res.json()
    assert data["detail"]["error"]["code"] == "REVISION_CONFLICT"
    assert data["detail"]["error"]["fields"]["currentRevision"] == revision_after_first

    # The server document must be unchanged (the stale overwrite never landed).
    reloaded = client.get(f"/api/magi/projects/{project_id}/sequence").json()["sequence"]
    assert reloaded["revision"] == revision_after_first
    assert reloaded["clips"][0]["name"] == "Clip"


def test_put_sequence_expected_revision_match_succeeds(client):
    """m1 A3: a matching expectedRevision succeeds and bumps the revision."""
    project_id = _create_project(client)
    asset_id = _seed_asset(project_id)
    body = _seq_body(project_id, asset_id)
    first = client.put(f"/api/magi/projects/{project_id}/sequence", json={"sequence": body})
    rev = first.json()["sequence"]["revision"]
    body["clips"][0]["name"] = "bumped"
    res = client.put(
        f"/api/magi/projects/{project_id}/sequence",
        json={"sequence": body, "expectedRevision": rev},
    )
    assert res.status_code == 200, res.text
    assert res.json()["sequence"]["revision"] == rev + 1


def test_put_sequence_expected_revision_omitted_is_backward_compatible(client):
    """m1 A3: clients that omit expectedRevision keep last-writer-wins."""
    project_id = _create_project(client)
    asset_id = _seed_asset(project_id)
    body = _seq_body(project_id, asset_id)
    first = client.put(f"/api/magi/projects/{project_id}/sequence", json={"sequence": body})
    rev = first.json()["sequence"]["revision"]
    body["clips"][0]["name"] = "no expected revision"
    res = client.put(f"/api/magi/projects/{project_id}/sequence", json={"sequence": body})
    assert res.status_code == 200, res.text
    assert res.json()["sequence"]["revision"] == rev + 1


def test_put_sequence_expected_revision_malformed_is_422(client):
    project_id = _create_project(client)
    body = _seq_body(project_id)
    res = client.put(
        f"/api/magi/projects/{project_id}/sequence",
        json={"sequence": body, "expectedRevision": "not-a-number"},
    )
    assert res.status_code == 422
    assert res.json()["detail"]["error"]["code"] == "INVALID_REVISION"


def test_save_reload_roundtrip_preserves_full_document(client):
    """m1 A7: PUT -> GET roundtrip reconstructs an identical document for real
    clip data including lineage, playhead, markers, and track blueprint."""
    project_id = _create_project(client)
    asset_id = _seed_asset(project_id)
    body = _seq_body(project_id, asset_id)
    body["clips"][0].update(
        {
            "name": "Roundtrip shot",
            "startFrame": 48,
            "durationFrames": 120,
            "inPoint": 10,
            "outPoint": 130,
            "batchBlockId": "bb_roundtrip",
            "generationId": "gen_roundtrip",
            "takeId": "tk_roundtrip",
            "sourceClipId": "src_roundtrip",
            "sceneId": "scene_roundtrip",
        }
    )
    body["playheadFrame"] = 60
    body["markers"] = [{"id": "mk_1", "frame": 30, "label": "beat"}]
    res = client.put(f"/api/magi/projects/{project_id}/sequence", json={"sequence": body})
    assert res.status_code == 200, res.text
    saved = res.json()["sequence"]

    reloaded = client.get(f"/api/magi/projects/{project_id}/sequence").json()["sequence"]
    assert reloaded["id"] == saved["id"]
    assert reloaded["projectId"] == project_id
    assert reloaded["playheadFrame"] == 60
    assert reloaded["tracks"] == saved["tracks"]
    assert reloaded["markers"] == saved["markers"]
    assert len(reloaded["clips"]) == 1
    clip = reloaded["clips"][0]
    assert clip["id"] == "clip_000001"
    assert clip["batchBlockId"] == "bb_roundtrip"
    assert clip["generationId"] == "gen_roundtrip"
    assert clip["takeId"] == "tk_roundtrip"
    assert clip["sourceClipId"] == "src_roundtrip"
    assert clip["sceneId"] == "scene_roundtrip"


# ---------------------------------------------------------------------------
# m5 — Timeline handoff via the certified W46 surface
# ---------------------------------------------------------------------------


def _first_scene(client, project_id: str) -> dict:
    scenes = client.get(f"/api/projects/{project_id}").json()["scenes"]
    assert scenes, "a new project should have a default scene"
    return scenes[0]


def test_timeline_import_rejects_foreign_asset(client):
    project_a = _create_project(client, "Import A")
    project_b = _create_project(client, "Import B")
    asset_in_b = _seed_asset(project_b)
    res = client.post(
        f"/api/magi/projects/{project_a}/timeline/import",
        json={"assetId": asset_in_b},
    )
    assert res.status_code == 400
    data = res.json()
    assert data["detail"]["error"]["code"] == "ASSET_OWNERSHIP"


def test_timeline_import_accepts_owned_asset(client):
    project_id = _create_project(client)
    asset_id = _seed_asset(project_id)
    res = client.post(
        f"/api/magi/projects/{project_id}/timeline/import",
        json={
            "assetId": asset_id,
            "sceneId": "scene_x",
            "batchBlockId": "bb_1234",
            "generationId": "gen_1",
            "takeId": "tk_1",
            "sourceClipId": "clip_orig",
        },
    )
    assert res.status_code == 200, res.text
    clip = res.json()["clip"]
    assert clip["assetId"] == asset_id
    # m5 B2: lineage is FLAT (matches MagiClipModel/MagiClip), never nested.
    assert "lineage" not in clip
    assert clip["batchBlockId"] == "bb_1234"
    assert clip["sceneId"] == "scene_x"
    assert clip["generationId"] == "gen_1"
    assert clip["takeId"] == "tk_1"
    assert clip["sourceClipId"] == "clip_orig"


def test_timeline_import_missing_asset_id(client):
    project_id = _create_project(client)
    res = client.post(f"/api/magi/projects/{project_id}/timeline/import", json={})
    assert res.status_code == 400
    assert res.json()["detail"]["error"]["code"] == "ASSET_ID_REQUIRED"


def test_timeline_export_places_clips_on_w46_batch(client):
    project_id = _create_project(client, "Export Project")
    scene = _first_scene(client, project_id)
    asset_id = _seed_asset(project_id)
    res = client.post(
        f"/api/magi/projects/{project_id}/scenes/{scene['id']}/timeline/export",
        json={
            "label": "MAGI export cert",
            "clips": [
                {
                    "clipId": "magi_clip_1",
                    "assetId": asset_id,
                    "name": "Exported shot",
                    "startFrame": 0,
                    "durationFrames": 120,
                }
            ],
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["ok"] is True
    assert data["batchBlockId"].startswith("bb_")
    assert all(c.get("ok") for c in data["clips"])


def test_timeline_export_requires_clips(client):
    project_id = _create_project(client, "Export Empty")
    scene = _first_scene(client, project_id)
    res = client.post(
        f"/api/magi/projects/{project_id}/scenes/{scene['id']}/timeline/export",
        json={"clips": []},
    )
    assert res.status_code == 400
    assert res.json()["detail"]["error"]["code"] == "CLIPS_REQUIRED"


def test_timeline_export_rejects_unknown_clip_id(client):
    """m8: once a sequence is saved, exporting a clipId absent from it is a
    structured 404 CLIP_NOT_FOUND — never a silent placement."""
    project_id = _create_project(client, "Export Stale Clip")
    scene = _first_scene(client, project_id)
    asset_id = _seed_asset(project_id)
    save_sequence(project_id, _seq_body(project_id, asset_id))
    res = client.post(
        f"/api/magi/projects/{project_id}/scenes/{scene['id']}/timeline/export",
        json={"clips": [{"clipId": "stale_clip", "assetId": asset_id}]},
    )
    assert res.status_code == 404
    data = res.json()
    assert data["detail"]["error"]["code"] == "CLIP_NOT_FOUND"
    assert "stale_clip" in data["detail"]["error"]["message"]


def test_timeline_export_rejects_foreign_asset(client):
    project_a = _create_project(client, "Export A")
    project_b = _create_project(client, "Export B")
    scene_a = _first_scene(client, project_a)
    asset_in_b = _seed_asset(project_b)
    res = client.post(
        f"/api/magi/projects/{project_a}/scenes/{scene_a['id']}/timeline/export",
        json={"clips": [{"clipId": "c1", "assetId": asset_in_b}]},
    )
    assert res.status_code == 400
    assert res.json()["detail"]["error"]["code"] == "ASSET_OWNERSHIP"


def test_timeline_export_to_existing_batch_requires_explicit_batch_block_id(client):
    """m5 B3: existing-batch export requires an explicit batchBlockId — the
    export must not silently pick a default batch."""
    project_id = _create_project(client, "Export Existing")
    scene = _first_scene(client, project_id)
    asset_id = _seed_asset(project_id)
    res = client.post(
        f"/api/magi/projects/{project_id}/scenes/{scene['id']}/timeline/export",
        json={
            "label": "MAGI export cert",
            "batchBlockId": "bb_no_such_batch",
            "clips": [{"clipId": "magi_clip_1", "assetId": asset_id}],
        },
    )
    assert res.status_code == 404
    data = res.json()
    assert data["detail"]["error"]["code"] == "BATCH_NOT_FOUND"


def test_timeline_export_new_batch_records_ledger_and_survives_reload(client):
    """m5 B3/B6: new-batch export places clips on W46, records MAGI-side export
    provenance in sequence.json.exportLedger, and the ledger survives reload."""
    project_id = _create_project(client, "Export Ledger")
    scene = _first_scene(client, project_id)
    asset_id = _seed_asset(project_id)
    res = client.post(
        f"/api/magi/projects/{project_id}/scenes/{scene['id']}/timeline/export",
        json={
            "label": "MAGI export cert",
            "clips": [
                {
                    "clipId": "magi_clip_1",
                    "assetId": asset_id,
                    "name": "Exported shot",
                    "startFrame": 0,
                    "durationFrames": 120,
                }
            ],
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["ok"] is True
    batch_block_id = data["batchBlockId"]
    assert batch_block_id.startswith("bb_")
    assert all(c.get("ok") for c in data["clips"])

    # Ledger was recorded in the canonical sequence document.
    seq = get_sequence(project_id)
    assert batch_block_id in (seq.get("exportLedger") or {})
    entry = seq["exportLedger"][batch_block_id]
    assert entry["sceneId"] == scene["id"]
    assert entry["clips"][0]["clipId"] == "magi_clip_1"
    assert entry["clips"][0]["assetId"] == asset_id
    assert entry["clips"][0]["w46ClipId"]

    # Reload path returns the same ledger (no write side effect on read).
    reloaded = client.get(f"/api/magi/projects/{project_id}/sequence").json()["sequence"]
    assert batch_block_id in (reloaded.get("exportLedger") or {})
    assert reloaded["exportLedger"][batch_block_id]["clips"][0]["clipId"] == "magi_clip_1"


def test_timeline_export_to_existing_batch_places_and_ledgers(client):
    """m5 B3: exporting to an existing real batch appends clips and ledgers the
    batch without creating a new batch."""
    project_id = _create_project(client, "Export Existing Real")
    scene = _first_scene(client, project_id)
    asset_id = _seed_asset(project_id)
    first = client.post(
        f"/api/magi/projects/{project_id}/scenes/{scene['id']}/timeline/export",
        json={"label": "Seed batch", "clips": [{"clipId": "seed_1", "assetId": asset_id}]},
    )
    assert first.status_code == 200, first.text
    batch_block_id = first.json()["batchBlockId"]

    second = client.post(
        f"/api/magi/projects/{project_id}/scenes/{scene['id']}/timeline/export",
        json={
            "label": "Append",
            "batchBlockId": batch_block_id,
            "clips": [{"clipId": "append_1", "assetId": asset_id}],
        },
    )
    assert second.status_code == 200, second.text
    assert second.json()["batchBlockId"] == batch_block_id

    # Both clips now live on the same batch, and the ledger has both entries.
    master = client.get(
        f"/api/director-timeline/projects/{project_id}/scenes/{scene['id']}/master"
    )
    assert master.status_code == 200
    blocks = master.json()["master"]["batchBlocks"]
    batch = next(b for b in blocks if b["id"] == batch_block_id)
    placed_legacy = [
        c.get("legacyClipId") for c in batch.get("visualClips", []) + batch.get("audioClips", []) + batch.get("sfxClips", [])
    ]
    assert "seed_1" in placed_legacy
    assert "append_1" in placed_legacy

    ledger = get_sequence(project_id)["exportLedger"][batch_block_id]
    assert {e["clipId"] for e in ledger["clips"]} == {"seed_1", "append_1"}


def test_timeline_export_does_not_mutate_generation_history(client):
    """m5 B4: exporting MAGI clips never touches generation/source history —
    X stays X; Y is a derived output with provenance."""
    project_id = _create_project(client, "Export History")
    scene = _first_scene(client, project_id)
    asset_id = _seed_asset(project_id)
    body = _seq_body(project_id, asset_id)
    body["clips"][0].update(
        {
            "batchBlockId": "bb_src",
            "generationId": "gen_src",
            "takeId": "tk_src",
            "sourceClipId": "clip_src",
            "sceneId": "scene_src",
        }
    )
    saved = save_sequence(project_id, body)
    generation_snapshot = saved["clips"][0]["generationId"]

    res = client.post(
        f"/api/magi/projects/{project_id}/scenes/{scene['id']}/timeline/export",
        json={"clips": [{"clipId": "clip_000001", "assetId": asset_id}]},
    )
    assert res.status_code == 200, res.text

    # Source clip lineage is untouched by the export.
    after = get_sequence(project_id)
    assert after["clips"][0]["generationId"] == generation_snapshot
    assert after["clips"][0]["sourceClipId"] == "clip_src"
    assert after["clips"][0]["sceneId"] == "scene_src"
    assert after["clips"][0]["batchBlockId"] == "bb_src"
