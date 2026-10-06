"""Display / Full Size / Library must not select leftover restitch when a newer full-sheet visual exists."""

from __future__ import annotations

from types import SimpleNamespace

from app.spatial_map.ers_display import select_ers_display_asset_id
from app.scene_creator.service import build_production_context


def test_display_does_not_select_restitch_when_newer_full_sheet_visual_exists() -> None:
    visual = "4fe330b6-a6d7-4205-a17d-4210df347429"
    restitch = "19ec1b83-1ed4-4cd5-b69f-65f3527803f8"
    sheet = SimpleNamespace(
        ers_composite_asset_id=visual,
        provenance=SimpleNamespace(
            details={
                "visualSheetAssetId": visual,
                "restitchCompositeAssetId": restitch,
                "generationMode": "full_sheet_api",
            }
        ),
    )
    package = SimpleNamespace(
        ers_composite_asset_id=visual,
        metadata={
            "collageAssetId": visual,
            "restitchCompositeAssetId": restitch,
            "generationMode": "full_sheet_api",
        },
    )
    selected = select_ers_display_asset_id(
        sheet=sheet,
        package=package,
        claimed_asset_id=restitch,
        resolved_composite_asset_id=visual,
    )
    assert selected == visual
    assert selected != restitch


def test_display_falls_back_to_restitch_only_without_newer_visual() -> None:
    restitch = "19ec1b83-1ed4-4cd5-b69f-65f3527803f8"
    sheet = SimpleNamespace(
        ers_composite_asset_id="",
        provenance=SimpleNamespace(details={"restitchCompositeAssetId": restitch}),
    )
    assert select_ers_display_asset_id(sheet=sheet, claimed_asset_id=restitch) == restitch


def test_production_context_library_uses_live_visual_not_leftover_restitch() -> None:
    visual = "4fe330b6-a6d7-4205-a17d-4210df347429"
    restitch = "19ec1b83-1ed4-4cd5-b69f-65f3527803f8"
    sheet = SimpleNamespace(
        ers_composite_asset_id=visual,
        provenance=SimpleNamespace(
            details={
                "visualSheetAssetId": visual,
                "restitchCompositeAssetId": restitch,
                "generationMode": "full_sheet_api",
            }
        ),
    )
    profile = SimpleNamespace(
        handoffId="h1",
        sceneId="scene-1",
        spatialMapId="map-1",
        ersPackageId="pkg-1",
        ersLibraryAssetId=restitch,
        revision=2,
        fingerprint="fp",
        aspectRatio="16:9",
    )
    resolved = {
        "package_id": "pkg-1",
        "ers_composite_asset_id": visual,
    }
    ctx = build_production_context(
        selected_profile=profile,
        resolved=resolved,
        scene_id="scene-1",
        sheet=sheet,
    )
    assert ctx is not None
    assert ctx["ersLibraryAssetId"] == visual
    assert ctx["ersLibraryAssetId"] != restitch
    assert ctx["loaded"] is True
