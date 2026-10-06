"""ERS production pipeline: one-pass full sheet (GPT API default) + targeted component repair.

Normal GPT Image 2 API generation is ``ers_pipeline=full_sheet`` (one paid job).
The sequential Master → N → E → S → W → 3D → Occupied path is targeted repair
and historical ``generationMode=components`` packages only.

Local / non-GPT empty pipeline remains ``collage``.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

COMPONENT_SEQUENCE: tuple[str, ...] = ("master", "north", "east", "south", "west", "three_d", "occupied")
COMPONENT_LABELS: dict[str, str] = {
    "master": "Master",
    "north": "North",
    "east": "East",
    "south": "South",
    "west": "West",
    "three_d": "3D Environment Representation",
    "occupied": "Occupied scale",
    "compose": "Composing sheet",
}

_DIRECTIONS: tuple[str, ...] = ("north", "east", "south", "west")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_pipeline_mode(
    ers_pipeline: str = "",
    gpt_selected: bool = False,
    retry_component: str = "",
) -> str:
    """Resolve ERS execution mode.

    Targeted retry always uses the component repair path. GPT API defaults to
    one-pass ``full_sheet``. Local / non-GPT empty pipeline stays ``collage``.
    """
    if str(retry_component or "").strip():
        return "components"
    mode = str(ers_pipeline or "").strip().lower()
    if mode in {"full_sheet_api", "full_sheet"}:
        return "full_sheet"
    if mode in {"components", "collage", "recompose"}:
        return mode
    if gpt_selected:
        return "full_sheet"
    return "collage"


def next_component(
    accepted: dict[str, str],
    *,
    skip_three_d: bool = False,
    include_occupied: bool = False,
) -> str | None:
    for name in COMPONENT_SEQUENCE:
        if name == "three_d" and skip_three_d:
            continue
        if name == "occupied" and not include_occupied:
            continue
        if not str(accepted.get(name) or "").strip():
            return name
    return None


def collage_source_asset_id(package: Any) -> str:
    meta = dict(getattr(package, "metadata", None) or {})
    return str(
        meta.get("collageAssetId")
        or getattr(package, "ers_composite_asset_id", None)
        or meta.get("sheetCompositeAssetId")
        or ""
    ).strip()


def package_uses_collage_occupied(package: Any) -> bool:
    """True when the accepted sheet is a one-shot collage, not component tiles."""
    meta = dict(getattr(package, "metadata", None) or {})
    if str(meta.get("collageAssetId") or "").strip():
        return True
    accepted = accepted_from_package(package)
    has_env_tiles = bool(accepted.get("master")) and all(accepted.get(d) for d in _DIRECTIONS)
    return bool(collage_source_asset_id(package)) and not has_env_tiles


def accepted_from_package(package: Any) -> dict[str, str]:
    meta = dict(getattr(package, "metadata", None) or {})
    components = dict(meta.get("components") or {})
    out = {
        "master": str(getattr(package, "master_environment_asset_id", None) or components.get("master") or ""),
        "north": str((getattr(package, "directional_assets", None) or {}).get("north") or components.get("north") or ""),
        "east": str((getattr(package, "directional_assets", None) or {}).get("east") or components.get("east") or ""),
        "south": str((getattr(package, "directional_assets", None) or {}).get("south") or components.get("south") or ""),
        "west": str((getattr(package, "directional_assets", None) or {}).get("west") or components.get("west") or ""),
        "three_d": str(meta.get("threeDRepresentationAssetId") or components.get("three_d") or ""),
        "occupied": str(meta.get("occupiedScaleAssetId") or components.get("occupied") or ""),
    }
    return {k: v for k, v in out.items() if v}


def bind_component_asset(package: Any, component: str, asset_id: str) -> Any:
    asset_id = str(asset_id or "").strip()
    meta = dict(package.metadata or {})
    components = dict(meta.get("components") or {})
    components[component] = asset_id
    meta["components"] = components
    if component == "master":
        package.master_environment_asset_id = asset_id
        meta["masterRevision"] = int(meta.get("masterRevision") or 0) + 1
        meta["directionalAppearanceStale"] = True
    elif component in _DIRECTIONS:
        dirs = dict(package.directional_assets or {})
        dirs[component] = asset_id
        package.directional_assets = dirs
        if component == "north":
            meta["directionalAppearanceStale"] = False
    elif component == "three_d":
        meta["threeDRepresentationAssetId"] = asset_id
        meta["threeDKind"] = "representation"
        meta["threeDTruthLabel"] = "illustrative"
    elif component == "occupied":
        meta["occupiedScaleAssetId"] = asset_id
        meta["identityRequired"] = True
        for item in (meta.get("packet") or {}).get("characters") or []:
            if str(item.get("characterId") or "").strip():
                meta["characterId"] = item.get("characterId")
                meta["characterRevision"] = item.get("approvedRevision")
                meta["characterReferenceAssetId"] = item.get("referenceAssetId")
                meta["characterSheetAssetId"] = item.get("characterSheetAssetId")
                break
    package.metadata = meta
    return package


def _child_payload(job_id: str, component: str, index: int, *, status: str = "queued", **meta: Any) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "label": COMPONENT_LABELS.get(component, component),
        "status": status,
        "child_index": index,
        "stage": "queued" if status == "queued" else status,
        "metadata": {
            "ersComponent": component,
            "ers_pipeline": "components",
            **meta,
        },
    }


def force_full_requested(body: dict[str, Any] | None = None, *, force_full: bool = False) -> bool:
    """True when the creator clicked Regenerate (not a targeted Retry)."""
    if force_full:
        return True
    blob = body if isinstance(body, dict) else {}
    ctx = blob.get("creativeContext") if isinstance(blob.get("creativeContext"), dict) else {}
    for src in (blob, ctx):
        for key in ("forceFull", "force_full", "ers_force_full"):
            value = src.get(key)
            if value is True or str(value or "").strip().lower() in {"1", "true", "yes"}:
                return True
    return False


def start_ers_component_pipeline(
    db: Any,
    project_id: str,
    *,
    execution_id: str,
    body: dict[str, Any],
    package: Any,
    sheet: Any,
    spatial_document: Any,
    scene_id: str = "",
    retry_component: str = "",
    force_full: bool = False,
) -> dict[str, Any]:
    from .ers_packet import compile_ers_packet, hydrate_ers_character_canon, packet_needs_occupied, placement_fingerprint
    from .ers_persistence import save_ers_package
    from ..codirector.capabilities.handlers.ers_generate import (
        _enqueue_ers_image_product,
        _stamp_ers_job_on_sheet,
    )
    from ..environment_reference_sheet.store import save_sheet

    packet = hydrate_ers_character_canon(
        db, compile_ers_packet(spatial_document, project_id=project_id), project_id=project_id
    )
    meta = dict(package.metadata or {})
    previous_fp = str(meta.get("lineageFingerprint") or "")
    previous_place = str(meta.get("placementFingerprint") or "")
    lineage = str((package.metadata or {}).get("grounding_fingerprint") or meta.get("grounding_fingerprint") or "")
    place_fp = placement_fingerprint(packet)
    accepted = accepted_from_package(package)
    if not accepted and db is not None:
        from .ers_persistence import list_ers_packages

        map_id = str(getattr(spatial_document, "id", "") or getattr(package, "scene_layout_id", "") or "")
        try:
            priors = [
                p
                for p in list_ers_packages(db, project_id)
                if str(getattr(p, "scene_layout_id", "") or "") == map_id
                and str(p.id) != str(package.id)
                and not str(p.id).startswith("runtime-")
            ]
        except Exception:
            priors = []
        priors.sort(
            key=lambda p: (len(accepted_from_package(p)), p.updated_at or p.created_at or ""),
            reverse=True,
        )
        if priors and accepted_from_package(priors[0]):
            package = priors[0]
            meta = dict(package.metadata or {})
            previous_fp = str(meta.get("lineageFingerprint") or previous_fp)
            previous_place = str(meta.get("placementFingerprint") or previous_place)
            lineage = str(meta.get("grounding_fingerprint") or lineage)
            accepted = accepted_from_package(package)

    retry = str(retry_component or "").strip().lower()
    if retry and retry not in COMPONENT_SEQUENCE:
        raise RuntimeError(f"Cannot retry unknown ERS component: {retry_component}")

    if retry == "occupied":
        meta["occupiedOnly"] = True
        meta["retryComponent"] = "occupied"
    else:
        meta.pop("occupiedOnly", None)
        if str(meta.get("retryComponent") or "") == "occupied":
            meta.pop("retryComponent", None)
    package.metadata = meta

    force_full = force_full_requested(body, force_full=force_full) and not retry
    recompose_only = (
        not force_full
        and not retry
        and bool(accepted.get("master"))
        and all(accepted.get(d) for d in _DIRECTIONS)
        and previous_fp
        and previous_fp == lineage
        and previous_place != place_fp
    )
    if recompose_only:
        return recompose_ers_package(
            db,
            project_id,
            execution_id=execution_id,
            package=package,
            sheet=sheet,
            spatial_document=spatial_document,
            scene_id=scene_id,
        )

    if not retry:
        # Full generation: keep accepted siblings only when retrying a child.
        if force_full or (previous_fp and previous_fp != lineage):
            accepted = {}
            package.master_environment_asset_id = None
            package.directional_assets = {d: None for d in _DIRECTIONS}
            meta["components"] = {}
            meta["threeDRepresentationAssetId"] = None
            meta["occupiedScaleAssetId"] = None
            meta["directionalAppearanceStale"] = False

    include_occupied = packet_needs_occupied(packet)
    if include_occupied and accepted.get("occupied"):
        stored_rev = int(meta.get("characterRevision") or 0)
        live_rev = 0
        for item in packet.get("characters") or []:
            if item.get("approvedRevision") is not None:
                live_rev = int(item.get("approvedRevision") or 0)
                break
        if live_rev and stored_rev and live_rev != stored_rev:
            accepted.pop("occupied", None)
            meta["occupiedScaleAssetId"] = None
            components = dict(meta.get("components") or {})
            components.pop("occupied", None)
            meta["components"] = components
    first = retry or next_component(accepted, include_occupied=include_occupied)
    if package_uses_collage_occupied(package):
        meta["occupiedCompose"] = "collage_panel_9"
        package.metadata = meta
    if first is None:
        return recompose_ers_package(
            db,
            project_id,
            execution_id=execution_id,
            package=package,
            sheet=sheet,
            spatial_document=spatial_document,
            scene_id=scene_id,
        )

    meta.update(
        {
            "ers_pipeline": "components",
            "pipeline_status": "running",
            "packet": packet,
            "job_template": _strip_prompt(body),
            "lineageFingerprint": lineage,
            "placementFingerprint": place_fp,
            "environmentRevision": int(getattr(spatial_document, "version", 0) or meta.get("environmentRevision") or 1),
            "spatialMapRevision": str(getattr(spatial_document, "savedVersion", "") or getattr(spatial_document, "version", "") or ""),
            "ersRevision": int(meta.get("ersRevision") or 0),
            "sheet_id": getattr(sheet, "sheetId", "") or meta.get("sheet_id"),
            "execution_id": execution_id,
        }
    )
    package.metadata = meta
    save_ers_package(db, project_id, package)

    job_body = _component_body(body, packet, first, execution_id=execution_id, package_id=package.id, sheet_id=sheet.sheetId)
    queued = _enqueue_ers_image_product(db, project_id, job_body, scene_id=scene_id or None)
    job_id = _job_id_from_queued(queued)
    _stamp_ers_job_on_sheet(sheet, job_id=job_id, package_id=package.id)
    save_sheet(sheet)

    child_jobs = [_child_payload(job_id, first, 0, sheet_id=sheet.sheetId, spatial_map_id=str(getattr(spatial_document, "id", "")), ers_package_id=package.id)]
    return {
        "job_ids": [job_id],
        "child_jobs": child_jobs,
        "surface_type": "ers_generation",
        "ers_package_id": package.id,
        "sheet_id": sheet.sheetId,
        "spatial_map_id": str(getattr(spatial_document, "id", "") or ""),
        "plan_data": {
            "ersStage": f"Generating {COMPONENT_LABELS[first]}",
            "ers_pipeline": "components",
            "ers_package_id": package.id,
            "sheet_id": sheet.sheetId,
        },
    }


def advance_ers_component(
    db: Any,
    project_id: str,
    *,
    asset_id: str,
    sheet_id: str = "",
    package_id: str = "",
    component: str = "",
    execution_id: str = "",
    scene_id: str = "",
) -> dict[str, Any]:
    from .ers_persistence import list_ers_packages, load_ers_package, save_ers_package
    from ..codirector.capabilities.handlers.ers_generate import persist_ers_composite_asset
    from ..environment_reference_sheet.store import load_sheet

    package = None
    if package_id:
        try:
            package = load_ers_package(db, project_id, package_id)
        except Exception:
            package = None
    if package is None and sheet_id:
        packages = [
            p
            for p in list_ers_packages(db, project_id)
            if str((p.metadata or {}).get("sheet_id") or "") == sheet_id
            and not str(p.id).startswith("runtime-")
        ]
        if packages:
            package = sorted(packages, key=lambda p: p.updated_at or p.created_at or "", reverse=True)[0]
    if package is None:
        return persist_ers_composite_asset(db, project_id, sheet_id=sheet_id, asset_id=asset_id, package_id=package_id)

    component = str(component or "").strip() or "master"
    meta = dict(package.metadata or {})
    packet = dict(meta.get("packet") or {})
    if component == "occupied":
        from .ers_character_identity_gate import apply_occupied_identity_gate

        gate = apply_occupied_identity_gate(db, project_id, asset_id=asset_id, packet=packet)
        meta["identityGateResult"] = gate
        package.metadata = meta
        if str(gate.get("verdict") or "") == "FAIL_CHARACTER_IDENTITY":
            from .ers_persistence import save_ers_package

            save_ers_package(db, project_id, package)
            return {
                "advanced": None,
                "identityGateResult": gate,
                "package_id": package.id,
                "retry_component": "occupied",
            }
    bind_component_asset(package, component, asset_id)
    meta = dict(package.metadata or {})
    accepted = accepted_from_package(package)
    skip_3d = bool(meta.get("threeDSkipped"))
    from .ers_packet import packet_needs_occupied

    include_occupied = packet_needs_occupied(packet)
    nxt = next_component(accepted, skip_three_d=skip_3d, include_occupied=include_occupied)
    if component == "occupied" and (
        meta.get("occupiedOnly") or str(meta.get("retryComponent") or "") == "occupied"
    ):
        nxt = None
    template = dict(meta.get("job_template") or {})
    exec_id = str(execution_id or meta.get("execution_id") or "")
    sheet = load_sheet(project_id, str(sheet_id or meta.get("sheet_id") or "")) if (sheet_id or meta.get("sheet_id")) else None

    if nxt == "three_d":
        try:
            job_body = _component_body(
                template,
                packet,
                nxt,
                execution_id=exec_id,
                package_id=package.id,
                sheet_id=str(getattr(sheet, "sheetId", "") or sheet_id),
            )
            from ..codirector.capabilities.handlers.ers_generate import _enqueue_ers_image_product

            queued = _enqueue_ers_image_product(db, project_id, job_body, scene_id=scene_id or None)
            job_id = _job_id_from_queued(queued)
            save_ers_package(db, project_id, package)
            _append_execution_child(db, project_id, exec_id, job_id, nxt, len(accepted))
            return {"advanced": nxt, "job_id": job_id, "package_id": package.id}
        except Exception as exc:
            logger.warning("3D Environment Representation skipped: %s", exc)
            meta["threeDSkipped"] = True
            meta["threeDUnavailableReason"] = str(exc)[:400]
            package.metadata = meta
            nxt = None

    if nxt:
        from ..codirector.capabilities.handlers.ers_generate import _enqueue_ers_image_product

        job_body = _component_body(
            template,
            packet,
            nxt,
            execution_id=exec_id,
            package_id=package.id,
            sheet_id=str(getattr(sheet, "sheetId", "") or sheet_id),
        )
        queued = _enqueue_ers_image_product(db, project_id, job_body, scene_id=scene_id or None)
        job_id = _job_id_from_queued(queued)
        save_ers_package(db, project_id, package)
        _append_execution_child(db, project_id, exec_id, job_id, nxt, len(accepted))
        return {"advanced": nxt, "job_id": job_id, "package_id": package.id}

    composed = persist_composed_ers(
        db,
        project_id,
        package=package,
        sheet=sheet,
        spatial_document_id=str(package.scene_layout_id or ""),
    )
    save_ers_package(db, project_id, package)
    if exec_id:
        _stamp_execution_complete(db, project_id, exec_id, composed.get("ers_composite_asset_id") or "")
    return composed


def skip_three_d_and_compose(
    db: Any,
    project_id: str,
    *,
    sheet_id: str = "",
    package_id: str = "",
    execution_id: str = "",
    reason: str = "",
) -> dict[str, Any]:
    from .ers_persistence import load_ers_package, save_ers_package
    from ..environment_reference_sheet.store import load_sheet

    package = load_ers_package(db, project_id, package_id) if package_id else None
    if package is None:
        return {}
    meta = dict(package.metadata or {})
    meta["threeDSkipped"] = True
    meta["threeDUnavailableReason"] = (reason or "3D Environment Representation is unavailable")[:400]
    package.metadata = meta
    sheet = load_sheet(project_id, sheet_id) if sheet_id else None
    composed = persist_composed_ers(db, project_id, package=package, sheet=sheet, spatial_document_id=str(package.scene_layout_id or ""))
    save_ers_package(db, project_id, package)
    if execution_id:
        _stamp_execution_complete(db, project_id, execution_id, composed.get("ers_composite_asset_id") or "")
    return composed


def recompose_ers_package(
    db: Any,
    project_id: str,
    *,
    execution_id: str,
    package: Any,
    sheet: Any,
    spatial_document: Any,
    scene_id: str = "",
) -> dict[str, Any]:
    from .ers_packet import compile_ers_packet, placement_fingerprint
    from .ers_persistence import save_ers_package

    packet = compile_ers_packet(spatial_document, project_id=project_id)
    meta = dict(package.metadata or {})
    meta["packet"] = packet
    meta["placementFingerprint"] = placement_fingerprint(packet)
    meta["ers_pipeline"] = "components"
    package.metadata = meta
    composed = persist_composed_ers(
        db,
        project_id,
        package=package,
        sheet=sheet,
        spatial_document_id=str(getattr(spatial_document, "id", "") or package.scene_layout_id or ""),
    )
    save_ers_package(db, project_id, package)
    composite_id = str(composed.get("ers_composite_asset_id") or "")
    return {
        "job_ids": [],
        "child_jobs": [
            {
                "job_id": f"ers-recompose-{package.id[:8]}",
                "label": "Composing sheet",
                "status": "completed",
                "child_index": 0,
                "asset_id": composite_id,
                "metadata": {"ersComponent": "compose", "ers_pipeline": "recompose"},
            }
        ],
        "result_asset_ids": [composite_id] if composite_id else [],
        "status": "completed",
        "surface_type": "ers_generation",
        "ers_package_id": package.id,
        "sheet_id": getattr(sheet, "sheetId", ""),
        "spatial_map_id": str(getattr(spatial_document, "id", "") or ""),
    }


def persist_composed_ers(
    db: Any,
    project_id: str,
    *,
    package: Any,
    sheet: Any,
    spatial_document_id: str = "",
) -> dict[str, Any]:
    from .ers_compose_2k import choose_aspect, compose_ers_png
    from .ers_packet import human_readable_summary
    from ..codirector.capabilities.handlers.ers_generate import ers_2k_pixels, persist_ers_composite_asset
    from ..config import settings
    from ..db import Asset

    packet = dict((package.metadata or {}).get("packet") or {})
    accepted = accepted_from_package(package)
    images: dict[str, bytes] = {}
    for key in ("master", "north", "east", "south", "west", "three_d", "occupied"):
        aid = accepted.get(key)
        if not aid:
            continue
        raw = _asset_bytes(db, aid)
        if raw:
            images[key] = raw
    atlas_id = str(packet.get("spatialMapAssetId") or "").strip()
    if atlas_id:
        atlas_raw = _asset_bytes(db, atlas_id)
        if atlas_raw:
            images["atlas"] = atlas_raw
    json_lines = human_readable_summary(packet)
    aspect = choose_aspect(map_cells=10, json_lines=len(json_lines))
    width, height = ers_2k_pixels(aspect)
    collage_id = collage_source_asset_id(package)
    collage_bytes = _asset_bytes(db, collage_id) if collage_id else b""
    occupied_bytes = images.get("occupied") or b""
    compose_mode = "components_2k"
    if package_uses_collage_occupied(package):
        from .ers_compose_2k import compose_occupied_into_collage
        from .ers_collage_templates import (
            ErsCollageTemplateError,
            lookup_collage_template,
            stamp_template_on_package,
        )

        if not collage_bytes:
            raise ErsCollageTemplateError(
                "Original Environment Reference Sheet collage is missing. Occupied cannot be composed."
            )
        if not occupied_bytes:
            raise ErsCollageTemplateError(
                "Occupied still is missing. Panel 9 cannot be composed onto the original collage."
            )
        collage_id = collage_source_asset_id(package)
        contract = lookup_collage_template(
            collage_asset_id=collage_id,
            template_id=str((package.metadata or {}).get("ersCollageTemplateId") or ""),
        )
        if contract is not None:
            stamp_template_on_package(package, contract)
        png = compose_occupied_into_collage(
            collage_bytes,
            occupied_bytes,
            collage_asset_id=collage_id,
            template_id=str((package.metadata or {}).get("ersCollageTemplateId") or ""),
        )
        compose_mode = "collage_panel_9"
    else:
        png = compose_ers_png(packet, images, width=width, height=height)
    identity_rows = []
    for item in packet.get("characters") or []:
        cid = str(item.get("characterId") or item.get("character_id") or "").strip()
        if not cid:
            continue
        identity_rows.append(
            {
                "placementId": item.get("id"),
                "characterId": cid,
                "displayName": item.get("displayName") or item.get("label"),
                "approvedRevision": item.get("approvedRevision"),
                "referenceAssetId": item.get("referenceAssetId"),
                "characterSheetAssetId": item.get("characterSheetAssetId"),
                "occupiedComponent": "occupied",
                "identityRequired": True,
            }
        )
    machine = {
        **packet,
        "masterAssetId": accepted.get("master"),
        "directional_assets": {d: accepted.get(d) for d in _DIRECTIONS},
        "threeDRepresentationAssetId": accepted.get("three_d") or None,
        "occupiedScaleAssetId": accepted.get("occupied") or None,
        "threeDKind": "representation",
        "threeDTruthLabel": "illustrative",
        "labels": ["SPATIAL MAP", "MASTER", "NORTH", "EAST", "SOUTH", "WEST", "3D ENVIRONMENT", "OCCUPIED SCALE"],
        "summary": json_lines,
        "composeMode": compose_mode,
        "characterIdentity": identity_rows,
        "identityRequired": bool(identity_rows),
        "ersRevision": int((package.metadata or {}).get("ersRevision") or 0) + 1,
        "composedAt": _now(),
    }
    dest_dir = Path(settings.data_dir) / "projects" / project_id / "assets"
    dest_dir.mkdir(parents=True, exist_ok=True)
    png_name = f"ers-composite-{package.id[:8]}.png"
    json_name = f"ers-machine-{package.id[:8]}.json"
    png_path = dest_dir / png_name
    json_path = dest_dir / json_name
    png_path.write_bytes(png)
    json_path.write_text(json.dumps(machine, indent=2), encoding="utf-8")

    png_asset = Asset(
        id=str(uuid.uuid4()),
        project_id=project_id,
        tag="environment_reference_sheet",
        kind="image",
        filename=png_name,
        path=str(png_path),
        comfy_name="",
        scope="project",
        labels_json=json.dumps(["ERS", "composite"]),
        prompt_meta_json=json.dumps(
            {
                "libraryVisible": True,
                "sourceFeature": "ers_component_pipeline",
                "role": "ers_composite",
                "ersPackageId": package.id,
                "asset_type": "image",
            }
        ),
    )
    json_asset = Asset(
        id=str(uuid.uuid4()),
        project_id=project_id,
        tag="ers_machine_json",
        kind="json",
        filename=json_name,
        path=str(json_path),
        comfy_name="",
        scope="project",
        labels_json=json.dumps(["ERS", "machine-json"]),
        prompt_meta_json=json.dumps(
            {
                "libraryVisible": True,
                "sourceFeature": "ers_component_pipeline",
                "role": "ers_machine_json",
                "ersPackageId": package.id,
                "asset_type": "json",
            }
        ),
    )
    db.add(png_asset)
    db.add(json_asset)
    db.flush()

    meta = dict(package.metadata or {})
    meta["machineJsonAssetId"] = json_asset.id
    meta["ersRevision"] = int(meta.get("ersRevision") or 0) + 1
    meta["pipeline_status"] = "complete"
    meta["composedAt"] = _now()
    meta["occupiedCompose"] = compose_mode
    if accepted.get("occupied"):
        meta["occupiedScaleAssetId"] = accepted.get("occupied")
        meta["identityRequired"] = bool(identity_rows)
    package.metadata = meta
    package.ers_composite_asset_id = png_asset.id

    _stamp_sheet_grounding_fingerprint(db, project_id, sheet, spatial_document_id)
    persist_ers_composite_asset(
        db,
        project_id,
        sheet_id=str(getattr(sheet, "sheetId", "") or meta.get("sheet_id") or ""),
        asset_id=png_asset.id,
        package_id=package.id,
        sheet=sheet,
        package=package,
    )
    if compose_mode == "collage_panel_9":
        from .ers_full_sheet import persist_repair_lineage, stamp_repair_on_sheet
        from .ers_persistence import save_ers_package
        from ..environment_reference_sheet.store import save_sheet

        persist_repair_lineage(
            package,
            original_full_sheet_asset_id=str(collage_id or ""),
            replacement_component="occupied",
            replacement_asset_id=str(accepted.get("occupied") or ""),
            restitch_composite_asset_id=png_asset.id,
        )
        meta = dict(package.metadata or {})
        gate = dict(meta.get("identityGateResult") or {})
        if str(gate.get("verdict") or ""):
            meta["identityGate"] = gate
            package.metadata = meta
        stamp_repair_on_sheet(
            sheet,
            identity=gate or None,
            original_full_sheet_asset_id=str(collage_id or ""),
            replacement_component="occupied",
            replacement_asset_id=str(accepted.get("occupied") or ""),
            restitch_composite_asset_id=png_asset.id,
            repair_revision=int((package.metadata or {}).get("repairRevision") or 1),
        )
        if sheet is not None:
            save_sheet(sheet)
        save_ers_package(db, project_id, package, provenance="ers_occupied_restitch")
    return {
        "ers_composite_asset_id": png_asset.id,
        "machineJsonAssetId": json_asset.id,
        "package_id": package.id,
        "has_reference": True,
    }


def _stamp_sheet_grounding_fingerprint(
    db: Any,
    project_id: str,
    sheet: Any,
    spatial_document_id: str,
) -> None:
    """Write the live map lineage onto the sheet so stale clears when they match."""
    if sheet is None:
        return
    fingerprint = ""
    map_id = str(spatial_document_id or "").strip()
    if db is not None and map_id:
        try:
            from .service import get_document

            doc = get_document(db, project_id, map_id)
            fingerprint = str(getattr(doc, "groundingFingerprint", "") or "")
        except Exception:
            fingerprint = ""
    if not fingerprint:
        return
    provenance = getattr(sheet, "provenance", None)
    if provenance is None:
        return
    details = dict(getattr(provenance, "details", None) or {})
    details["groundingFingerprint"] = fingerprint
    provenance.details = details


def _strip_prompt(body: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(body, default=str))
    out.pop("prompt", None)
    return out


def _component_body(
    template: dict[str, Any],
    packet: dict[str, Any],
    component: str,
    *,
    execution_id: str,
    package_id: str,
    sheet_id: str,
) -> dict[str, Any]:
    from .ers_packet import compile_component_prompt
    from ..codirector.capabilities.handlers.ers_generate import ers_2k_pixels

    body = json.loads(json.dumps(template, default=str))
    prompt = compile_component_prompt(packet, component)
    body["prompt"] = prompt
    body["tag"] = f"codirector_ers_{execution_id[:8]}_{component}"
    w, h = ers_2k_pixels("16:9")
    body["width"] = w
    body["height"] = h
    ctx = body.setdefault("creativeContext", {})
    if not isinstance(ctx, dict):
        ctx = {}
        body["creativeContext"] = ctx
    ctx["ersComponent"] = component
    ctx["ers_pipeline"] = "components"
    ctx["ersPackageId"] = package_id
    ctx["environmentReferenceSheetId"] = sheet_id
    ctx["direction"] = "master" if component == "master" else component
    ctx["objective"] = "environment_reference_sheet"
    if component == "occupied":
        ctx["identityRequired"] = True
        refs = [
            str(item.get("referenceAssetId") or "").strip()
            for item in packet.get("characters") or []
            if str(item.get("referenceAssetId") or "").strip()
        ]
        ctx["approvedCharacterAssetIds"] = refs
        ctx["characterIds"] = [
            str(item.get("characterId") or "").strip()
            for item in packet.get("characters") or []
            if str(item.get("characterId") or "").strip()
        ]
        missing = [
            str(item.get("displayName") or item.get("label") or item.get("characterId") or "this character")
            for item in packet.get("characters") or []
            if item.get("visible") is not False
            and str(item.get("characterId") or "").strip()
            and not item.get("hasApprovedReference")
        ]
        if missing:
            raise RuntimeError(
                f"CHARACTER_REFERENCE_UNAVAILABLE: I couldn't resolve the approved "
                f"Character Creator reference for {missing[0]}, so I did not substitute another person."
            )
        for item in packet.get("characters") or []:
            if str(item.get("characterId") or "").strip():
                ctx["characterRevision"] = item.get("approvedRevision")
                ctx["characterReferenceAssetId"] = item.get("referenceAssetId")
                ctx["characterSheetAssetId"] = item.get("characterSheetAssetId")
                break
        from ..codirector.capabilities.handlers.ers_generate import (
            _gpt_i2i_official_id,
            _public_asset_url,
            order_occupied_reference_assets,
        )

        env_id = str(
            ctx.get("authoritativeSourceAssetId")
            or body.get("sourceAssetId")
            or body.get("source_asset_id")
            or ""
        ).strip()
        grounding_ids = [
            str(aid).strip()
            for aid in (ctx.get("groundingAssetIds") or [])
            if str(aid or "").strip()
        ]
        ordered = order_occupied_reference_assets(refs, env_id, grounding_ids)
        urls = [url for url in (_public_asset_url(aid) for aid in ordered) if url]
        if not refs or not urls:
            who = (ctx.get("characterIds") or ["this character"])[0]
            raise RuntimeError(
                f"CHARACTER_REFERENCE_UNAVAILABLE: approved character pixels could not be published for {who}."
            )
        body["input_urls"] = urls[:2]
        body["sourceAssetId"] = refs[0]
        body["kieImageModelId"] = _gpt_i2i_official_id()
        ctx["referenceGrounding"] = {
            "mode": "pixel",
            "assetIds": ordered[:2],
            "roles": ["character_identity", "environment"][: len(urls[:2])],
            "authoritativeSourceAssetId": refs[0],
            "urlCount": len(urls[:2]),
            "workflow": _gpt_i2i_official_id(),
        }
        ctx["operationIntent"] = "image.generate"
    return body


def _job_id_from_queued(queued: Any) -> str:
    if isinstance(queued, dict):
        return str(queued.get("jobId") or (queued.get("jobs") or [{}])[0].get("jobId") or "")
    return str(getattr(queued, "id", None) or "")


def _asset_bytes(db: Any, asset_id: str) -> bytes:
    from ..db import Asset

    row = db.get(Asset, asset_id)
    if row is None:
        return b""
    path = Path(str(getattr(row, "path", "") or ""))
    if not path.is_file():
        return b""
    return path.read_bytes()


def _append_execution_child(
    db: Any,
    project_id: str,
    execution_id: str,
    job_id: str,
    component: str,
    index: int,
) -> None:
    if not execution_id or not job_id:
        return
    try:
        from ..codirector.execution.contracts import ChildJobStatus, ChildJobView, ExecutionStatus
        from ..codirector.execution.pack_store import load_pack, save_pack

        plan = load_pack(db, project_id, execution_id)
        if plan is None:
            return
        if any(c.job_id == job_id for c in plan.child_jobs):
            return
        plan.child_jobs.append(
            ChildJobView(
                job_id=job_id,
                label=COMPONENT_LABELS.get(component, component),
                status=ChildJobStatus.QUEUED,
                child_index=index,
                stage="queued",
                metadata={
                    "ersComponent": component,
                    "ers_pipeline": "components",
                    "ers_package_id": str((plan.plan_data or {}).get("ers_package_id") or ""),
                    "sheet_id": str((plan.plan_data or {}).get("sheet_id") or ""),
                },
            )
        )
        plan.status = ExecutionStatus.RUNNING
        plan.plan_data = {**dict(plan.plan_data or {}), "ersStage": f"Generating {COMPONENT_LABELS.get(component, component)}"}
        save_pack(db, project_id, plan)
    except Exception:
        logger.exception("Failed to append ERS child job to execution pack")


def _stamp_execution_complete(db: Any, project_id: str, execution_id: str, composite_id: str) -> None:
    if not execution_id:
        return
    try:
        from ..codirector.execution.pack_store import load_pack, save_pack

        plan = load_pack(db, project_id, execution_id)
        if plan is None:
            return
        if composite_id and composite_id not in (plan.result_asset_ids or []):
            plan.result_asset_ids = [*(plan.result_asset_ids or []), composite_id]
        plan.plan_data = {**dict(plan.plan_data or {}), "ersStage": "Complete", "ers_pipeline": "components"}
        save_pack(db, project_id, plan)
    except Exception:
        logger.exception("Failed to stamp ERS execution complete")
