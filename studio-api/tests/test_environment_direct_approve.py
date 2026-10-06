"""Environment Creator Path A — Approve as Environment (direct reference approval).

Covers: approve uploaded/library image as the official environment visual,
persistence across reload, replace-then-reapprove semantics, clear-approval,
Global ownership rules, Co-Director resolver convergence, Timeline binding
identity. Both paths (direct approval / generated ERS) share one contract:
ers_composite_asset_id + status=approved + canonical pointer + scope sync.
"""

from __future__ import annotations

import base64

from app.db import SessionLocal
from app.environment_reference_sheet.store import (
    get_canonical_sheet_id,
    load_sheet,
)

_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _create_project(client, name: str) -> str:
    response = client.post("/api/projects", json={"name": name})
    assert response.status_code == 200
    return response.json()["id"]


def _upload_png(client, project_id: str, tag: str) -> str:
    res = client.post(
        f"/api/projects/{project_id}/assets",
        files={"file": (f"{tag}.png", _ONE_PIXEL_PNG, "image/png")},
        data={"tag": tag, "kind": "image"},
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _save_environment(client, project_id: str, name: str, **extra) -> str:
    res = client.post(
        f"/api/environment-reference-sheets/projects/{project_id}/save",
        json={"name": name, "environmentPrompt": "corridor", **extra},
    )
    assert res.status_code == 200, res.text
    return res.json()["sheet"]["sheetId"]


def _approve(client, project_id: str, sheet_id: str, asset_id: str):
    return client.post(
        f"/api/environment-reference-sheets/projects/{project_id}/{sheet_id}/approve-reference",
        json={"assetId": asset_id},
    )


def test_approve_reference_as_environment_happy_path(client) -> None:
    project_id = _create_project(client, "Env Direct Approve")
    asset_id = _upload_png(client, project_id, "venture_corridor")
    sheet_id = _save_environment(
        client, project_id, "Venture Corridor Scene", referenceImageAssetId=asset_id
    )

    res = _approve(client, project_id, sheet_id, asset_id)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["approved"] is True
    assert body["assetId"] == asset_id
    assert body["mock"] is False
    assert body["canonicalSheetId"] == sheet_id

    sheet = body["sheet"]
    assert sheet["sheetId"] == sheet_id
    assert sheet["name"] == "Venture Corridor Scene"
    assert sheet["status"] == "approved"
    assert sheet["ers_composite_asset_id"] == asset_id
    # reference_asset_id (plan) remains the uploaded image; the official
    # environment asset field points at that same asset.
    plan = sheet["provenance"]["details"]["environmentCreatorPlan"]
    assert plan["referenceImageAssetId"] == asset_id
    # Canonical tag unchanged by approval.
    assert sheet["canonicalTag"].lstrip("#").lower() == "venturecorridorscene"

    # Canonical pointer flipped through the sole writer.
    assert get_canonical_sheet_id(project_id) == sheet_id


def test_approve_reference_persists_across_reload(client) -> None:
    project_id = _create_project(client, "Env Direct Approve Reload")
    asset_id = _upload_png(client, project_id, "reload_ref")
    sheet_id = _save_environment(client, project_id, "Reload Corridor", referenceImageAssetId=asset_id)
    assert _approve(client, project_id, sheet_id, asset_id).status_code == 200

    # Reload from the file-backed store (no process state).
    reloaded = load_sheet(project_id, sheet_id)
    assert reloaded is not None
    assert reloaded.status == "approved"
    assert reloaded.ers_composite_asset_id == asset_id

    # And through the read API the lower panel consumes.
    got = client.get(f"/api/environment-reference-sheets/projects/{project_id}/{sheet_id}")
    assert got.status_code == 200
    assert got.json()["sheet"]["ers_composite_asset_id"] == asset_id
    assert got.json()["sheet"]["status"] == "approved"

    listed = client.get(f"/api/environment-reference-sheets/projects/{project_id}")
    row = next(s for s in listed.json()["sheets"] if s["sheetId"] == sheet_id)
    assert row["status"] == "approved"
    assert row["ers_composite_asset_id"] == asset_id
    assert row["has_reference"] is True


def test_approve_reference_requires_existing_sheet(client) -> None:
    project_id = _create_project(client, "Env Direct Approve 404")
    asset_id = _upload_png(client, project_id, "orphan_ref")
    res = _approve(client, project_id, "sheet-does-not-exist", asset_id)
    assert res.status_code == 404


def test_approve_reference_rejects_non_image(client) -> None:
    project_id = _create_project(client, "Env Direct Approve Audio")
    res = client.post(
        f"/api/projects/{project_id}/assets",
        files={"file": ("steps.wav", b"RIFF\x00\x00\x00\x00WAVE", "audio/wav")},
        data={"tag": "steps", "kind": "audio"},
    )
    assert res.status_code == 200, res.text
    audio_id = res.json()["id"]
    sheet_id = _save_environment(client, project_id, "Audio Corridor")
    res = _approve(client, project_id, sheet_id, audio_id)
    assert res.status_code == 400
    assert "picture" in res.json()["detail"].lower()


def test_approve_reference_cross_project_asset_denied(client) -> None:
    project_a = _create_project(client, "Env Approve Owner")
    project_b = _create_project(client, "Env Approve Other")
    foreign_asset = _upload_png(client, project_b, "foreign_ref")
    sheet_id = _save_environment(client, project_a, "Owner Corridor")
    res = _approve(client, project_a, sheet_id, foreign_asset)
    assert res.status_code == 403


def test_replace_reference_keeps_old_approval_until_explicit_reapprove(client) -> None:
    project_id = _create_project(client, "Env Direct Approve Replace")
    asset_a = _upload_png(client, project_id, "corridor_a")
    asset_b = _upload_png(client, project_id, "corridor_b")
    sheet_id = _save_environment(client, project_id, "Replace Corridor", referenceImageAssetId=asset_a)
    assert _approve(client, project_id, sheet_id, asset_a).status_code == 200

    # Creator swaps the attached reference image and saves — the approved
    # official visual must remain asset A (no silent replacement).
    swapped = client.post(
        f"/api/environment-reference-sheets/projects/{project_id}/save",
        json={
            "sheetId": sheet_id,
            "name": "Replace Corridor",
            "environmentPrompt": "corridor",
            "referenceImageAssetId": asset_b,
        },
    )
    assert swapped.status_code == 200, swapped.text
    assert swapped.json()["sheet"]["ers_composite_asset_id"] == asset_a
    assert swapped.json()["sheet"]["status"] == "approved"

    # Explicit re-approval of the new reference converges on asset B.
    reapproved = _approve(client, project_id, sheet_id, asset_b)
    assert reapproved.status_code == 200, reapproved.text
    assert reapproved.json()["sheet"]["ers_composite_asset_id"] == asset_b
    assert reapproved.json()["sheet"]["status"] == "approved"
    assert load_sheet(project_id, sheet_id).ers_composite_asset_id == asset_b


def test_clear_approval_releases_visual_and_canonical_but_keeps_library(client) -> None:
    project_id = _create_project(client, "Env Direct Approve Clear")
    asset_id = _upload_png(client, project_id, "clear_ref")
    sheet_id = _save_environment(client, project_id, "Clear Corridor", referenceImageAssetId=asset_id)
    assert _approve(client, project_id, sheet_id, asset_id).status_code == 200
    assert get_canonical_sheet_id(project_id) == sheet_id

    cleared = client.post(f"/api/environment-reference-sheets/projects/{project_id}/{sheet_id}/clear-approval")
    assert cleared.status_code == 200, cleared.text
    body = cleared.json()
    assert body["approved"] is False
    assert body["clearedAssetId"] == asset_id
    assert body["canonicalCleared"] is True
    assert body["sheet"]["status"] == "draft"
    assert body["sheet"]["ers_composite_asset_id"] is None

    assert get_canonical_sheet_id(project_id) is None
    reloaded = load_sheet(project_id, sheet_id)
    assert reloaded is not None
    assert reloaded.status == "draft"
    assert reloaded.ers_composite_asset_id is None

    # Library bytes are never deleted by approval clearing.
    from app.db import Asset

    db = SessionLocal()
    try:
        assert db.get(Asset, asset_id) is not None
    finally:
        db.close()


def test_approve_global_environment_visible_from_other_project_and_owner_only(client) -> None:
    project_a = _create_project(client, "Env Global Owner")
    project_b = _create_project(client, "Env Global Reader")
    asset_id = _upload_png(client, project_a, "global_corridor")
    sheet_id = _save_environment(
        client, project_a, "Global Corridor", isGlobal=True, referenceImageAssetId=asset_id
    )
    assert _approve(client, project_a, sheet_id, asset_id).status_code == 200

    # Visible + approved from another project (same identity, same asset).
    visible = client.get(f"/api/environment-reference-sheets/projects/{project_b}")
    assert visible.status_code == 200
    row = next((s for s in visible.json()["sheets"] if s["sheetId"] == sheet_id), None)
    assert row is not None
    assert row["status"] == "approved"
    assert row["ers_composite_asset_id"] == asset_id

    # Owner/mutation rules unchanged: only the owning project may approve.
    other_asset = _upload_png(client, project_b, "reader_ref")
    forbidden = _approve(client, project_b, sheet_id, other_asset)
    assert forbidden.status_code == 403


def test_codirector_resolves_directly_approved_environment_like_generated_ers(client) -> None:
    from app.codirector.production.reference_resolver import resolve_production_reference

    project_id = _create_project(client, "Env Direct Approve Resolve")
    asset_id = _upload_png(client, project_id, "resolve_ref")
    sheet_id = _save_environment(
        client, project_id, "Venture Corridor Scene", referenceImageAssetId=asset_id
    )
    assert _approve(client, project_id, sheet_id, asset_id).status_code == 200

    db = SessionLocal()
    try:
        resolved = resolve_production_reference(
            db,
            project_id=project_id,
            query="Venture Corridor Scene",
            expected_type="environment",
        )
    finally:
        db.close()
    assert resolved.status == "found"
    assert resolved.entity_id == sheet_id
    assert resolved.bindable_asset_id == asset_id
    assert resolved.approved_sheet is True
    assert resolved.canonical_tag.lstrip("#").lower() == "venturecorridorscene"


def test_timeline_binding_resolves_same_identity_and_approved_asset(client) -> None:
    """A scene binding on the environment identity resolves to the approved
    asset and the sheet's canonical #tag — identical to a generated ERS."""
    from app.scene_references import service as ref_service
    from app.director_timeline_w46.generation.reference_compile import resolve_binding_id

    project_id = _create_project(client, "Env Direct Approve Binding")
    asset_id = _upload_png(client, project_id, "binding_ref")
    sheet_id = _save_environment(client, project_id, "Binding Corridor", referenceImageAssetId=asset_id)
    assert _approve(client, project_id, sheet_id, asset_id).status_code == 200

    db = SessionLocal()
    try:
        binding = ref_service.attach(
            db,
            project_id,
            {
                "asset_id": asset_id,
                "scope_type": "project",
                "scope_id": project_id,
                "reference_type": "environment",
                "media_kind": "image",
                "alias": "Binding Corridor",
                "usage_modes": ["environment"],
                "reference_roles": ["environment"],
                "identity_id": sheet_id,
            },
            actor="user",
        )
        resolved = resolve_binding_id(db, project_id, binding["id"])
    finally:
        db.close()
    assert resolved["broken"] is False
    assert resolved["assetId"] == asset_id
    assert resolved["identityId"] == sheet_id
    assert resolved["referenceType"] == "environment"
    assert str(resolved["canonicalTag"]).lstrip("#").lower() == "bindingcorridor"
