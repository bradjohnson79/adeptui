from __future__ import annotations

from sqlalchemy.orm import Session

from ..db import Asset
from .collage import build_directional_prompts
from .errors import SpatialMapErrorCode, raise_http_error
from .schemas import SpatialCamera, SpatialMapDocument, SpatialReferenceAsset, SpatialReferenceBundle


def _is_unplaced(placement: object) -> bool:
    """True when no explicit grid placement coords were ever provided (CDX-025).

    Unplaced characters keep the SpatialPlacement defaults x=0/z=0 with no
    normalized grid coords; unplaced props store x/z as None. Both read as
    'not on the grid yet' instead of a placement at the world origin (0,0).
    """
    nx = getattr(placement, "normalizedX", None)
    ny = getattr(placement, "normalizedY", None)
    if nx is not None or ny is not None:
        return False
    x = getattr(placement, "x", None)
    z = getattr(placement, "z", None)
    if x is None or z is None:
        return True
    try:
        return float(x) == 0.0 and float(z) == 0.0
    except (TypeError, ValueError):
        return True


def creative_position_labels(*, x: float, y: float, z: float) -> dict[str, str]:
    lateral = "center"
    if x <= -1.5:
        lateral = "left"
    elif x >= 1.5:
        lateral = "right"
    depth = "midground"
    if z <= -1.5:
        depth = "foreground"
    elif z >= 1.5:
        depth = "background"
    height = "eye level"
    if y >= 2.2:
        height = "high"
    elif y <= 0.6:
        height = "low"
    summary = f"{depth} {lateral}".strip()
    return {
        "lateral": lateral,
        "depth": depth,
        "height": height,
        "summary": summary,
    }


def _select_camera(document: SpatialMapDocument, camera_id: str | None = None) -> SpatialCamera | None:
    if camera_id:
        return next((camera for camera in document.cameras if camera.id == camera_id), None)
    hero = next((camera for camera in document.cameras if camera.hero), None)
    return hero or (document.cameras[0] if document.cameras else None)


def compile_reference_bundle(
    db: Session,
    *,
    document: SpatialMapDocument,
    target: str = "image",
    camera_id: str | None = None,
    warnings: list[str] | None = None,
) -> SpatialReferenceBundle:
    if target not in {"image", "video"}:
        raise raise_http_error(SpatialMapErrorCode.REFERENCE_BUNDLE_TARGET_INVALID, target=target)

    asset_ids = {
        asset_id
        for asset_id in [
            document.backgroundAssetId,
            *[item.assetId for item in document.characters],
            *[item.assetId for item in document.props],
            *([view.assetId for view in document.collage.views] if document.collage else []),
        ]
        if asset_id
    }
    assets: list[SpatialReferenceAsset] = []
    if asset_ids:
        rows = db.query(Asset).filter(Asset.project_id == document.projectId, Asset.id.in_(list(asset_ids))).all()
        assets = [
            SpatialReferenceAsset(assetId=row.id, kind=row.kind, filename=row.filename, path=row.path)
            for row in rows
        ]

    # CDX-025: only placements with an explicit grid position get a creative
    # label. Unplaced characters default to x=0/z=0 and must not read as
    # standing at the world origin; unplaced props keep x/z=None.
    creator_labels = {
        placement.id: creative_position_labels(x=placement.x, y=placement.y, z=placement.z)["summary"]
        for placement in [*document.characters, *document.props]
        if getattr(placement, "placementMode", None) != "attached" and not _is_unplaced(placement)
    }
    available_directions = [view.direction for view in document.collage.views] if document.collage else []
    directional_prompts = (
        build_directional_prompts(
            master_environment_prompt=document.collage.masterEnvironmentPrompt or document.masterEnvironmentPrompt,
            include_characters=bool(document.collage and document.collage.captureMode == "include_characters"),
            camera_height_meters=document.collage.cameraHeightMeters if document.collage else 1.6,
            lens_mm=document.collage.lensMm if document.collage else 24.0,
        )
        if document.collage
        else {}
    )
    return SpatialReferenceBundle(
        documentId=document.id,
        documentVersion=document.updatedAt or None,
        projectId=document.projectId,
        sceneId=document.sceneId,
        locationId=document.locationId,
        target=target,  # type: ignore[arg-type]
        providerHonesty=document.providerHonesty,
        environmentPrompt=(
            document.masterEnvironmentPrompt
            or (document.collage.masterEnvironmentPrompt if document.collage else "")
        ),
        backgroundAssetId=document.backgroundAssetId,
        referenceAssetIds=sorted(asset_ids),
        assetReferences=assets,
        characters=document.characters,
        props=document.props,
        primaryCamera=_select_camera(document, camera_id),
        movementPaths=document.paths if target == "video" else [],
        availableCollageDirections=available_directions,
        creatorPositionLabels=creator_labels,
        directionalPrompts=directional_prompts,
        warnings=list(warnings or []),
    )


def summarize_reference_bundle(
    bundle: SpatialReferenceBundle,
    *,
    start_camera_id: str | None = None,
    end_camera_id: str | None = None,
) -> dict[str, object]:
    """Creator-first plain-language conditioning for image/video generation."""

    background_summary = _background_summary(bundle)
    camera_summary = _camera_summary(bundle.primaryCamera)
    character_summaries = [_character_summary(bundle, item) for item in bundle.characters[:4]]
    prop_summaries = [_prop_summary(bundle, item) for item in bundle.props[:4]]
    prompt_hints: list[str] = []

    if background_summary:
        prompt_hints.append(background_summary)
    if camera_summary:
        prompt_hints.append(camera_summary)
    if character_summaries:
        prompt_hints.append("Characters: " + "; ".join(character_summaries))
    if prop_summaries:
        prompt_hints.append("Props: " + "; ".join(prop_summaries))
    if bundle.availableCollageDirections:
        directions = ", ".join(direction.replace("_", " ") for direction in bundle.availableCollageDirections[:8])
        prompt_hints.append(f"360 references available from {directions}.")
    movement_summary = _movement_summary(
        bundle,
        start_camera_id=start_camera_id,
        end_camera_id=end_camera_id,
    )
    if movement_summary:
        prompt_hints.append(movement_summary)

    return {
        "mapId": bundle.documentId,
        "mapVersion": bundle.documentVersion,
        "providerHonesty": bundle.providerHonesty,
        "background": background_summary,
        "camera": camera_summary,
        "characters": character_summaries,
        "props": prop_summaries,
        "warnings": list(bundle.warnings or []),
        "promptHints": prompt_hints,
        "summary": " ".join(prompt_hints).strip(),
    }


def preferred_reference_assets(bundle: SpatialReferenceBundle, *, limit: int = 4) -> list[SpatialReferenceAsset]:
    """Best-effort reference ordering for providers that accept visual inputs."""

    by_id = {item.assetId: item for item in bundle.assetReferences}
    ordered_ids: list[str] = []
    if bundle.backgroundAssetId:
        ordered_ids.append(bundle.backgroundAssetId)
    ordered_ids.extend(bundle.referenceAssetIds)

    seen: set[str] = set()
    assets: list[SpatialReferenceAsset] = []
    for asset_id in ordered_ids:
        if asset_id in seen:
            continue
        seen.add(asset_id)
        item = by_id.get(asset_id)
        if item is None:
            continue
        if item.kind and item.kind not in {"image", "environment"}:
            continue
        assets.append(item)
        if len(assets) >= limit:
            break
    return assets


def _background_summary(bundle: SpatialReferenceBundle) -> str:
    parts: list[str] = []
    if bundle.environmentPrompt:
        parts.append(f"Environment: {bundle.environmentPrompt.strip()}")
    if bundle.backgroundAssetId:
        parts.append("Keep the established background plate and geography consistent.")
    return " ".join(parts).strip()


def _camera_summary(camera: SpatialCamera | None) -> str:
    if camera is None:
        return ""
    parts = [f"Camera: {camera.label or 'Hero camera'}"]
    if camera.shotType:
        parts.append(camera.shotType.replace("_", " "))
    if camera.lensMm:
        parts.append(f"{int(round(camera.lensMm))}mm lens")
    if camera.targetCharacterIds:
        parts.append(f"favoring {len(camera.targetCharacterIds)} performer(s)")
    return ", ".join(part for part in parts if part).strip()


def _character_summary(bundle: SpatialReferenceBundle, item) -> str:
    label = item.label or item.characterId or "Character"
    if _is_unplaced(item):
        # CDX-025: no explicit grid placement - do not claim world origin.
        details = [f"{label} on the map but not placed on the grid yet"]
    else:
        position = bundle.creatorPositionLabels.get(item.id) or creative_position_labels(
            x=item.x,
            y=item.y,
            z=item.z,
        )["summary"]
        details = [f"{label} at {position}"]
    if item.pose:
        details.append(item.pose)
    if item.expression:
        details.append(item.expression)
    if item.eyeLine:
        details.append(f"eyeline {item.eyeLine}")
    return ", ".join(part for part in details if part).strip()


def _prop_summary(bundle: SpatialReferenceBundle, item) -> str:
    label = item.label or item.propId or "Prop"
    if getattr(item, "placementMode", None) == "attached":
        details = [f"{label} attached"]
        if item.relationship:
            details.append(str(item.relationship).replace("_", " "))
        if item.attachmentPoint and item.attachmentPoint != "unspecified":
            details.append(str(item.attachmentPoint).replace("_", " "))
        return ", ".join(part for part in details if part).strip()
    if _is_unplaced(item):
        # CDX-025: unplaced independent prop - no world origin claim.
        details = [f"{label} saved to the map but not placed in the scene yet"]
    else:
        position = bundle.creatorPositionLabels.get(item.id) or creative_position_labels(
            x=item.x,
            y=item.y,
            z=item.z,
        )["summary"]
        details = [f"{label} at {position}"]
    if item.category:
        details.append(item.category)
    if item.state:
        details.append(item.state)
    return ", ".join(part for part in details if part).strip()


def _movement_summary(
    bundle: SpatialReferenceBundle,
    *,
    start_camera_id: str | None = None,
    end_camera_id: str | None = None,
) -> str:
    if bundle.target != "video":
        return ""
    moves: list[str] = []
    if start_camera_id and end_camera_id and start_camera_id != end_camera_id:
        moves.append("Move from the chosen start camera framing into the selected end camera framing.")
    if bundle.movementPaths:
        moves.append(
            "Honor the staged movement paths for performers, props, and camera motion."
        )
    return " ".join(moves).strip()
