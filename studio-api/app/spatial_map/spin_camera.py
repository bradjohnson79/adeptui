from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..asset_graph import add_edge
from ..db import Asset, Job, ProjectTraitRow
from ..hosted_providers.service import provider_card
from ..production_control.model_registry import get_model
from ..storyboard_jobs import enqueue_imagegen_job
from .ers_component_pipeline import recompose_ers_package
from .ers_contracts import EnvironmentReferencePackage
from .ers_persistence import (
    _list_trait_values,
    _load_trait_value,
    _model_dump_json,
    _upsert_trait,
)
from .schemas import SpatialMapDocument, SpinCameraPlacement
from .service import _parse_document, _row_or_404, get_document

SPIN_CATEGORY = "spatial_spin_package"
DIRECTIONS: tuple[str, ...] = ("center", "north", "east", "south", "west")
DIRECTION_YAW: dict[str, int] = {"north": 0, "east": 90, "south": 180, "west": 270}


class _SpinView(BaseModel):
    """Mutable view slot stored inside the spin package manifest."""

    assetId: str | None = None
    status: str = "queued"
    jobId: str = ""
    error: str = ""
    provider: str = ""
    edgeAdded: bool = False


class _SpinPackageManifest(BaseModel):
    """Internal manifest shape persisted in a ProjectTraitRow."""

    spinPackageId: str = Field(default_factory=lambda: str(uuid.uuid4()))
    version: int = 1
    sceneId: str | None = None
    mapId: str = ""
    provider: str = ""
    origin: dict[str, float] = Field(default_factory=lambda: {"x": 0.0, "z": 0.0})
    cameraHeight: float = 1.6
    fov: float = 75.0
    lensMm: float = 35.0
    spatialMapAssetId: str | None = None
    views: dict[str, _SpinView] = Field(default_factory=dict)
    ersStale: bool = False
    ersCompositeAssetId: str | None = None
    createdAt: str = ""
    completedAt: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def center_status(document: SpatialMapDocument, placement: SpinCameraPlacement) -> dict[str, Any]:
    """Return center validation against the map's half-extent tolerance."""
    half_extent = min(document.widthMeters or 10.0, document.depthMeters or 10.0) / 2.0
    tolerance = half_extent * 0.15
    x = float(getattr(placement, "x", 0.0) or 0.0)
    z = float(getattr(placement, "z", 0.0) or 0.0)
    distance = math.hypot(x, z)
    return {
        "centered": distance <= tolerance,
        "distanceMeters": round(distance, 2),
        "toleranceMeters": round(tolerance, 2),
    }


def compile_spin_prompt(document: SpatialMapDocument, placement: SpinCameraPlacement, direction: str) -> str:
    """Generator-neutral semantic prompt template from the frozen contract §5."""
    direction_word = str(direction or "center").upper()
    height = float(getattr(placement, "cameraHeight", 1.6) or 1.6)
    prompt = (
        f"First-person environment view from the Spin Camera origin "
        f"({placement.x:.2f}, {placement.z:.2f}) at camera height {height:.2f}m. "
        f"Direction: {direction_word}. "
    )
    if str(direction or "").lower() == "center":
        prompt += (
            "This is the canonical establishing perspective toward the room's default forward "
            "(North), showing the full environment in a slightly wider framing. "
        )
    prompt += (
        "The Spatial Map reference image is the spatial authority — preserve exact environment identity: "
        "architecture, room proportions, materials, decor, lighting, doors, windows, furniture placement, floor layout. "
        "Do not redesign the room. Do not add people. Do not move architectural elements."
    )
    return prompt


def _validate_provider(provider_id: str) -> tuple[str, str]:
    """Return (backend, provider_id) or raise a 400 with an honest message."""
    pid = str(provider_id or "").strip()
    if not pid:
        raise HTTPException(400, detail="provider is required")
    descriptor = get_model(pid)
    if descriptor is None or str(descriptor.modality or "").lower() != "image":
        raise HTTPException(400, detail=f"Unknown image provider: {pid}")
    if not descriptor.executable:
        raise HTTPException(400, detail=f"Provider {pid} is not currently executable in Adept UI.")
    backend = str(getattr(descriptor, "providerId", "") or "").strip().lower()
    if not backend:
        raise HTTPException(400, detail=f"Provider {pid} has no configured backend.")
    card = provider_card(backend)
    if not card.get("apiKeyStatus", {}).get("configured"):
        raise HTTPException(
            400,
            detail=(
                f"Provider {backend} is not connected. "
                "Add the API key in Settings → AI Providers before generating."
            ),
        )
    caps = set(card.get("executableCapabilities") or [])
    if "image_to_image" not in caps and "image_editing" not in caps and "edit" not in descriptor.supports:
        raise HTTPException(
            400,
            detail=f"Provider {pid} does not support image-to-image edits for Spin Camera.",
        )
    return backend, pid


def _build_manifest(
    document: SpatialMapDocument,
    placement: SpinCameraPlacement,
    provider: str,
) -> _SpinPackageManifest:
    now = _now()
    package_id = str(uuid.uuid4())
    atlas_id = str(document.backgroundAssetId or "") or None
    views: dict[str, _SpinView] = {}
    for direction in DIRECTIONS:
        views[direction] = _SpinView(status="queued")
    return _SpinPackageManifest(
        spinPackageId=package_id,
        version=1,
        sceneId=placement.sceneId or document.sceneId,
        mapId=document.id,
        provider=provider,
        origin={"x": float(placement.x or 0.0), "z": float(placement.z or 0.0)},
        cameraHeight=float(placement.cameraHeight or 1.6),
        fov=float(placement.fov or 75.0),
        lensMm=float(placement.lensMm or 35.0),
        spatialMapAssetId=atlas_id,
        views=views,
        ersStale=False,
        createdAt=now,
        completedAt=None,
    )


def _save_manifest(db: Session, project_id: str, manifest: _SpinPackageManifest, provenance: str = "spin_camera") -> None:
    _upsert_trait(
        db,
        project_id=project_id,
        category=SPIN_CATEGORY,
        key=manifest.spinPackageId,
        value=_model_dump_json(manifest),
        provenance=provenance,
    )


def _load_manifest(db: Session, project_id: str, package_id: str) -> _SpinPackageManifest | None:
    raw = _load_trait_value(db, project_id=project_id, category=SPIN_CATEGORY, key=package_id)
    if not raw:
        return None
    try:
        return _SpinPackageManifest.model_validate_json(raw)
    except Exception as exc:
        raise HTTPException(500, detail=f"Stored spin package {package_id} is corrupt: {exc}") from exc


def _next_version(manifests: list[_SpinPackageManifest]) -> int:
    versions = [m.version for m in manifests if getattr(m, "version", None) is not None]
    return max(versions or [0]) + 1


def _manifests_for_map(db: Session, project_id: str, map_id: str) -> list[_SpinPackageManifest]:
    out: list[_SpinPackageManifest] = []
    for raw in _list_trait_values(db, project_id=project_id, category=SPIN_CATEGORY):
        try:
            m = _SpinPackageManifest.model_validate_json(raw)
        except Exception:
            continue
        if m.mapId == map_id:
            out.append(m)
    return sorted(out, key=lambda m: m.createdAt or "", reverse=False)


def _job_payload(
    document: SpatialMapDocument,
    placement: SpinCameraPlacement,
    provider: str,
    direction: str,
    package_id: str,
) -> dict[str, Any]:
    atlas_id = str(document.backgroundAssetId or "")
    prompt = compile_spin_prompt(document, placement, direction)
    # Atlas-conditioned generate — not image.edit. openai/gpt-image-2 has no
    # /edit official id; the capability layer refuses silent T2I-as-edit.
    # Same continuity path as Spatial Map atlas shots (sourceAssetId + generate).
    return {
        "prompt": prompt,
        "sourceAssetId": atlas_id,
        "hostedModelId": provider,
        "width": 1920,
        "height": 1080,
        "aspectRatio": "16:9",
        "resolution": "1080p",
        "tag": f"spin-{direction}-{package_id[:8]}",
        "purpose": "environment_reference_sheet",
        "operation": "image.generate",
        "commitToLibrary": True,
        "creativeContext": {
            "objective": "spin_camera",
            "spinPackageId": package_id,
            "direction": direction,
            "mapId": document.id,
            "provider": provider,
            "cameraHeight": float(placement.cameraHeight or 1.6),
            "lensMm": float(placement.lensMm or 35.0),
        },
    }


def _set_document_placement(
    db: Session,
    row,
    document: SpatialMapDocument,
    placement: SpinCameraPlacement,
) -> None:
    """Minimal save that keeps the Spin Camera field on the Spatial Map document."""
    document.updatedAt = _now()
    if not document.createdAt:
        document.createdAt = document.updatedAt
    try:
        version = int(document.version or "0")
    except (TypeError, ValueError):
        version = 0
    document.version = str(max(1, version + 1))
    document.projectId = row.project_id
    document.sceneId = row.scene_id
    document.locationId = row.location_id
    row.document_json = document.model_dump_json()
    row.updated_at = _now_dt()
    db.commit()
    db.refresh(row)


def create_package(
    db: Session,
    project_id: str,
    document: SpatialMapDocument,
    provider: str,
    *,
    confirm_paid: bool,
) -> dict[str, Any]:
    """Create a new Spin Package and enqueue 5 directional atlas-conditioned jobs."""
    placement = document.spinCamera
    if placement is None:
        raise HTTPException(400, detail="Place a Spin Camera on this map before creating a package.")
    atlas_id = str(document.backgroundAssetId or "").strip()
    if not atlas_id:
        raise HTTPException(400, detail="The Spatial Map needs a background atlas asset before Spin views can be generated.")
    _validate_provider(provider)
    if not confirm_paid:
        raise HTTPException(
            402,
            detail="Paid cloud generation requires confirmPaidCloud=true. No credits will be spent without explicit confirmation.",
        )

    manifests = _manifests_for_map(db, project_id, document.id)
    manifest = _build_manifest(document, placement, provider)
    manifest.version = _next_version(manifests)
    manifest.spinPackageId = str(uuid.uuid4())

    # Enqueue 5 sequential jobs (one per direction). Each carries the map atlas
    # as its single reference image and the direction-specific semantic prompt.
    for direction in DIRECTIONS:
        body = _job_payload(document, placement, provider, direction, manifest.spinPackageId)
        job = enqueue_imagegen_job(
            db,
            project_id=project_id,
            body=body,
            scene_id=placement.sceneId or document.sceneId,
        )
        manifest.views[direction] = _SpinView(status="queued", jobId=job.id, provider=provider)

    _save_manifest(db, project_id, manifest, provenance="spin_camera.create_package")
    return manifest.model_dump(mode="json")


def reconcile_package(
    db: Session,
    project_id: str,
    package_id: str,
) -> dict[str, Any]:
    """Lazy reconciliation: read job rows and update view statuses."""
    manifest = _load_manifest(db, project_id, package_id)
    if manifest is None:
        raise HTTPException(404, detail="Spin package not found.")
    changed = False
    for direction, view in manifest.views.items():
        job_id = view.jobId
        if not job_id:
            continue
        job = db.get(Job, job_id)
        if job is None:
            if view.status not in ("failed", "done"):
                view.status = "failed"
                view.error = "Job record was removed."
                changed = True
            continue
        new_status = str(job.status or "queued").lower()
        if new_status == view.status:
            # Already terminal — still try to capture asset id if missing.
            if new_status == "done" and not view.assetId:
                asset_id = _extract_output_asset_id(job)
                if asset_id:
                    view.assetId = asset_id
                    changed = True
            continue
        view.status = new_status
        changed = True
        if new_status == "done":
            asset_id = _extract_output_asset_id(job)
            view.assetId = asset_id
            view.error = ""
        elif new_status in ("failed", "cancelled", "canceled", "timed_out"):
            view.assetId = None
            view.error = str(job.message or "Generation failed.").strip() or "Generation failed."
        else:
            view.assetId = None
            view.error = ""
    if changed:
        manifest.ersStale = True
        manifest.completedAt = None
        _save_manifest(db, project_id, manifest, provenance="spin_camera.reconcile_package")
    changed = _ensure_lineage_edges(db, manifest)
    if changed:
        _save_manifest(db, project_id, manifest, provenance="spin_camera.lineage")
    return manifest.model_dump(mode="json")


def _extract_output_asset_id(job: Job) -> str | None:
    try:
        params = json.loads(job.params_json or "{}")
    except Exception:
        params = {}
    asset_id = str(params.get("output_asset_id") or "").strip()
    if asset_id:
        return asset_id
    # Fallback: output_path filename may have an asset id if the worker stamped it.
    path = str(job.output_path or "").strip()
    if not path:
        return None
    return None


def _ensure_lineage_edges(db: Session, manifest: _SpinPackageManifest) -> bool:
    """Add atlas -> view asset lineage edges. Returns True if the manifest changed."""
    atlas_id = str(manifest.spatialMapAssetId or "").strip()
    changed = False
    if not atlas_id:
        return changed
    for direction, view in manifest.views.items():
        asset_id = view.assetId
        if not asset_id or view.edgeAdded:
            continue
        try:
            add_edge(db, atlas_id, asset_id, "derived_from", {"spinDirection": direction, "spinPackageId": manifest.spinPackageId})
            view.edgeAdded = True
            changed = True
        except Exception:
            continue
    if changed:
        db.commit()
    return changed


def regenerate_direction(
    db: Session,
    project_id: str,
    package_id: str,
    direction: str,
    *,
    confirm_paid: bool,
) -> dict[str, Any]:
    """Re-enqueue a single direction for an existing Spin Package."""
    direction = str(direction or "").strip().lower()
    if direction not in DIRECTIONS:
        raise HTTPException(400, detail=f"Invalid direction: {direction}. Use one of {DIRECTIONS}.")
    manifest = _load_manifest(db, project_id, package_id)
    if manifest is None:
        raise HTTPException(404, detail="Spin package not found.")
    provider = str(manifest.provider or "").strip()
    if not provider:
        raise HTTPException(400, detail="Spin package has no provider recorded.")
    _validate_provider(provider)
    if not confirm_paid:
        raise HTTPException(
            402,
            detail="Paid cloud regeneration requires confirmPaidCloud=true.",
        )
    document = get_document(db, project_id, manifest.mapId)
    placement = document.spinCamera
    if placement is None:
        raise HTTPException(400, detail="The Spin Camera placement is missing from this map.")
    atlas_id = str(document.backgroundAssetId or "").strip()
    if not atlas_id:
        raise HTTPException(400, detail="The Spatial Map atlas is missing.")

    body = _job_payload(document, placement, provider, direction, manifest.spinPackageId)
    job = enqueue_imagegen_job(
        db,
        project_id=project_id,
        body=body,
        scene_id=placement.sceneId or document.sceneId,
    )
    manifest.views[direction] = _SpinView(status="queued", jobId=job.id, provider=provider)
    manifest.ersStale = True
    manifest.completedAt = None
    _save_manifest(db, project_id, manifest, provenance="spin_camera.regenerate_direction")
    return manifest.model_dump(mode="json")


def build_ers(
    db: Session,
    project_id: str,
    package_id: str,
) -> dict[str, Any]:
    """Assemble an EnvironmentReferencePackage from completed Spin views and compose."""
    manifest = _load_manifest(db, project_id, package_id)
    if manifest is None:
        raise HTTPException(404, detail="Spin package not found.")
    manifest_dict = reconcile_package(db, project_id, package_id)
    manifest = _SpinPackageManifest.model_validate(manifest_dict)

    missing = [d for d in DIRECTIONS if manifest.views[d].status != "done" or not manifest.views[d].assetId]
    if missing:
        raise HTTPException(
            400,
            detail={
                "message": "Cannot build ERS until all Spin views are complete.",
                "missing": missing,
                "statuses": {d: manifest.views[d].model_dump(mode="json") for d in DIRECTIONS},
            },
        )

    document = get_document(db, project_id, manifest.mapId)
    center_asset = manifest.views["center"].assetId
    directional = {
        "north": manifest.views["north"].assetId,
        "east": manifest.views["east"].assetId,
        "south": manifest.views["south"].assetId,
        "west": manifest.views["west"].assetId,
    }

    pkg = EnvironmentReferencePackage(
        id=manifest.spinPackageId,
        project_id=project_id,
        scene_layout_id=document.id,
        atlas_asset_id=manifest.spatialMapAssetId,
        master_environment_asset_id=center_asset,
        placements=[c.model_dump(mode="json") for c in document.characters]
        + [p.model_dump(mode="json") for p in document.props]
        + [c.model_dump(mode="json") for c in document.cameras],
        orientation="atlas-north-up",
        directional_assets=directional,
        metadata={"source": "spin_camera", "spinPackageId": manifest.spinPackageId},
        created_at=manifest.createdAt,
        updated_at=_now(),
    )

    composed = recompose_ers_package(
        db,
        project_id,
        execution_id="",
        package=pkg,
        sheet=None,
        spatial_document=document,
        scene_id=manifest.sceneId or document.sceneId or "",
    )

    manifest.ersStale = False
    manifest.ersCompositeAssetId = str(composed.get("ers_composite_asset_id") or "") or None
    manifest.completedAt = _now()
    _save_manifest(db, project_id, manifest, provenance="spin_camera.build_ers")

    return {
        "ers_composite_asset_id": composed.get("ers_composite_asset_id"),
        "machineJsonAssetId": composed.get("machineJsonAssetId"),
        "package_id": manifest.spinPackageId,
        "directional_assets": directional,
        "master_environment_asset_id": center_asset,
        "ersStale": False,
    }


def list_packages(
    db: Session,
    project_id: str,
    map_id: str,
) -> list[dict[str, Any]]:
    """Return reconciled manifests for a Spatial Map, newest last."""
    manifests = _manifests_for_map(db, project_id, map_id)
    return [reconcile_package(db, project_id, m.spinPackageId) for m in manifests]


def get_package(db: Session, project_id: str, map_id: str, package_id: str) -> dict[str, Any]:
    manifest = _load_manifest(db, project_id, package_id)
    if manifest is None or manifest.mapId != map_id:
        raise HTTPException(404, detail="Spin package not found on this map.")
    return reconcile_package(db, project_id, package_id)


def set_placement(
    db: Session,
    project_id: str,
    map_id: str,
    x: float,
    z: float,
    scene_id: str | None = None,
) -> dict[str, Any]:
    row = _row_or_404(db, project_id, map_id)
    document = _parse_document(row)
    now = _now()
    placement = document.spinCamera
    if placement is None:
        placement = SpinCameraPlacement(
            x=float(x),
            z=float(z),
            sceneId=scene_id,
            mapId=map_id,
            createdAt=now,
            updatedAt=now,
        )
    else:
        placement.x = float(x)
        placement.z = float(z)
        if scene_id is not None:
            placement.sceneId = scene_id
        placement.updatedAt = now
    document.spinCamera = placement
    _set_document_placement(db, row, document, placement)
    return {"placement": placement.model_dump(mode="json"), "centerStatus": center_status(document, placement)}


def delete_placement(db: Session, project_id: str, map_id: str) -> dict[str, Any]:
    row = _row_or_404(db, project_id, map_id)
    document = _parse_document(row)
    document.spinCamera = None
    _set_document_placement(db, row, document, SpinCameraPlacement())
    return {"deleted": True, "mapId": map_id}


def get_placement(db: Session, project_id: str, map_id: str) -> dict[str, Any]:
    row = _row_or_404(db, project_id, map_id)
    document = _parse_document(row)
    placement = document.spinCamera
    if placement is None:
        return {"exists": False}
    return {
        "exists": True,
        "placement": placement.model_dump(mode="json"),
        "centerStatus": center_status(document, placement),
    }
