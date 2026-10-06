"""Co-Director Prop Creator tools — same PropEntity store as the creator UI."""

from __future__ import annotations

from typing import Any

from ..definitions import ToolContext, ToolPreview
from ....prop_creator.readiness import (
    OPTIONAL_VIEWS,
    readiness_payload,
    valid_primary_candidate,
)

PROP_VIEWS = ("primary",) + OPTIONAL_VIEWS
ADVANCED_ANGLES = OPTIONAL_VIEWS


def _require_project(ctx: ToolContext) -> None:
    if not ctx.project_id:
        raise ValueError("projectId is required")


def _normalize_view(raw: Any) -> str:
    value = str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "identity": "primary",
        "hero_shot": "hero",
        "top_down": "top",
        "underside": "bottom",
    }
    value = aliases.get(value, value)
    if value not in PROP_VIEWS:
        raise ValueError(f"Unknown prop view: {raw}")
    return value


def _resolve_prop(ctx: ToolContext, args: dict[str, Any]):
    from ....prop_creator.service import get_prop, list_props

    _require_project(ctx)
    prop_id = str(args.get("propId") or args.get("prop_id") or "").strip()
    if prop_id:
        return get_prop(ctx.db, ctx.project_id, prop_id)
    name = str(args.get("propName") or args.get("name") or "").strip().lower()
    if name:
        for prop in list_props(ctx.db, ctx.project_id, approved_only=False):
            label = (prop.display_label or "").strip().lower()
            tag = (prop.tag or "").strip().lower()
            if name in {label, tag} or name in label or name in tag:
                return prop
    raise ValueError("propId is required")


def _angle_payload(prop) -> dict[str, Any]:
    angles = {}
    raw = prop.angles or {}
    for key in ADVANCED_ANGLES:
        slot = raw.get(key)
        if slot is None:
            angles[key] = {"assetId": None, "approved": False, "source": None, "status": "idle"}
            continue
        angles[key] = {
            "assetId": getattr(slot, "asset_id", None),
            "approved": bool(getattr(slot, "approved", False)),
            "source": getattr(slot, "source", None),
            "status": getattr(slot, "status", None),
        }
    ready = readiness_payload(prop)
    return {
        "angles": angles,
        "requiredApproved": ready["identityReady"],
        "sheetReady": ready["sheetReady"],
        "propReady": ready["propReady"],
        "missingOptionalViews": ready["missingOptionalViews"],
        "missingViewsBlockReadiness": False,
        "readyReason": ready["readyReason"],
    }


async def get_views(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    prop = _resolve_prop(ctx, args)
    snap = _angle_payload(prop)
    identity = {
        "assetId": prop.approved_asset_id,
        "approved": bool((prop.approved_asset_id or "").strip()),
        "source": None,
    }
    uploaded = next(
        (c for c in (prop.candidates or []) if c.asset_id == prop.approved_asset_id and getattr(c, "origin", None)),
        None,
    )
    if uploaded is not None:
        identity["source"] = uploaded.origin
    elif (prop.primary_approved_asset_id or "") == (prop.approved_asset_id or "") and prop.primary_approved_asset_id:
        identity["source"] = "generated"
    from ....prop_creator.readiness import (
        approved_primary_asset_id,
        valid_primary_candidate_asset_id,
        visible_primary_preview_asset_id,
    )

    approved_primary = approved_primary_asset_id(prop)
    pending_primary = valid_primary_candidate_asset_id(prop)
    preview_primary = visible_primary_preview_asset_id(prop)
    pending_is_replacement = bool(pending_primary and approved_primary and pending_primary != approved_primary)
    return {
        "ok": True,
        "propId": prop.id,
        "propName": prop.display_label,
        "tag": prop.tag,
        "mode": prop.mode,
        "sameStore": True,
        "mock": False,
        "primary": {
            "assetId": approved_primary or None,
            "approved": bool(approved_primary),
            "phase": prop.primary_phase,
            "pendingAssetId": pending_primary if pending_is_replacement else None,
            "previewAssetId": preview_primary or None,
        },
        "identity": identity,
        "angles": snap["angles"],
        "sheetReady": snap["sheetReady"],
        "propReady": snap["propReady"],
        "missingOptionalViews": snap["missingOptionalViews"],
        "missingViewsBlockReadiness": False,
        "readyReason": snap["readyReason"],
        "advancedSheetAssetId": prop.advanced_sheet_asset_id,
        "advancedSheetStatus": prop.advanced_sheet_status,
    }


def preview_adopt_view(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    prop = _resolve_prop(ctx, args)
    view = _normalize_view(args.get("view") or args.get("angle"))
    return ToolPreview(
        summary=f"Use this picture as {prop.display_label}'s {view} view.",
        lines=[
            "Saves it to the Library and binds it to this Prop.",
            "Does not approve the view. The creator still clicks Approve.",
            "Does not create a new Prop.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_adopt_view(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    prop = _resolve_prop(ctx, args)
    view = _normalize_view(args.get("view") or args.get("angle"))
    asset_id = str(args.get("assetId") or args.get("imageAssetId") or args.get("asset_id") or "").strip()
    if not asset_id:
        raise ValueError("assetId is required")
    if view == "primary":
        if prop.mode == "advanced":
            from ....prop_creator.advanced_service import adopt_primary_from_asset

            prop = adopt_primary_from_asset(
                ctx.db, ctx.project_id, prop.id, asset_id, source_type="uploaded"
            )
        else:
            from ....prop_creator.service import adopt_identity_from_asset

            prop = adopt_identity_from_asset(
                ctx.db, ctx.project_id, prop.id, asset_id, source_type="uploaded"
            )
    else:
        from ....prop_creator.advanced_service import adopt_angle_from_asset

        prop = adopt_angle_from_asset(
            ctx.db, ctx.project_id, prop.id, view, asset_id, source_type="uploaded"
        )
    return {
        "ok": True,
        "propId": prop.id,
        "view": view,
        "approved": False,
        "source": "uploaded",
        "sameStore": True,
    }


def preview_approve_view(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    prop = _resolve_prop(ctx, args)
    view = _normalize_view(args.get("view") or args.get("angle"))
    return ToolPreview(
        summary=f"Approve {prop.display_label}'s {view} view.",
        lines=["Makes this the approved Prop view.", "Works the same for uploaded and generated pictures."],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_approve_view(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    prop = _resolve_prop(ctx, args)
    view = _normalize_view(args.get("view") or args.get("angle"))
    if view == "primary":
        if prop.mode == "advanced":
            from ....prop_creator.advanced_service import approve_primary

            ready = valid_primary_candidate(prop)
            if ready is None:
                raise ValueError("Upload or generate a Primary look before approving.")
            prop = approve_primary(
                ctx.db,
                ctx.project_id,
                prop.id,
                candidate_id=ready.id,
                asset_id=ready.asset_id or "",
            )
        else:
            from ....prop_creator.service import approve_candidate

            ready = valid_primary_candidate(prop)
            if ready is None:
                raise ValueError("Upload or generate a Primary look before approving.")
            prop = approve_candidate(ctx.db, ctx.project_id, prop.id, ready.id)
    else:
        from ....prop_creator.advanced_service import approve_angle

        prop = approve_angle(ctx.db, ctx.project_id, prop.id, view, approved=True)
    snap = _angle_payload(prop)
    return {
        "ok": True,
        "propId": prop.id,
        "view": view,
        "sheetReady": snap["sheetReady"],
        "sameStore": True,
    }


def preview_generate_view(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    name = str(args.get("name") or args.get("propName") or "").strip()
    try:
        prop = _resolve_prop(ctx, args)
        label = prop.display_label or name or "this prop"
    except ValueError:
        label = name or "this prop"
    view = str(args.get("view") or args.get("angle") or "primary").strip()
    return ToolPreview(
        summary=f"Generate {label}'s {view} look in Prop Creator.",
        lines=[
            "Uses the Prop Creator generator on this project.",
            "Does not start a separate image provider.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def _button_generator_args(args: dict[str, Any]) -> dict[str, Any]:
    """Forward the Prop Creator button payload. Do not pick a provider here."""

    from ....codirector.durable.bind import PROP_CREATOR_BUTTON_SOURCES

    sources = args.get("generatorSources")
    if not isinstance(sources, dict):
        sources = dict(PROP_CREATOR_BUTTON_SOURCES)
    return {
        "local_enabled": bool(args.get("local_enabled", True)),
        "api_enabled": bool(args.get("api_enabled", False)),
        "local_family": str(args.get("local_family") or "auto"),
        "api_model": str(args.get("api_model") or ""),
        "candidate_count": int(args.get("candidate_count") or 1),
        "generator_sources": sources,
    }


def _ensure_prop(ctx: ToolContext, args: dict[str, Any]):
    from ....prop_creator.service import create_or_update_prop

    try:
        prop = _resolve_prop(ctx, args)
    except ValueError:
        name = str(args.get("name") or args.get("propName") or "").strip()
        if not name:
            raise
        prop = create_or_update_prop(
            ctx.db,
            ctx.project_id,
            name=name,
            description=str(args.get("description") or "") or None,
            visual_style="live_action",
        )
        return prop
    description = str(args.get("description") or "").strip()
    if description and not str(prop.description or "").strip():
        prop = create_or_update_prop(
            ctx.db,
            ctx.project_id,
            prop_id=prop.id,
            name=prop.display_label,
            description=description,
        )
    return prop


def _queued_prop_job(job_id: str) -> dict[str, Any]:
    """Read the request that was just handed to the existing image worker."""

    import json

    from ....db import Job, SessionLocal

    with SessionLocal() as db:
        job = db.get(Job, job_id)
        params: dict[str, Any] = {}
        if job is not None:
            try:
                params = json.loads(job.params_json or "{}")
            except Exception:
                params = {}
        runtime = params.get("imageRuntime") if isinstance(params.get("imageRuntime"), dict) else {}
    return {
        "jobId": job_id,
        "assetId": "",
        "status": "queued",
        "provider": str(params.get("providerPreference") or runtime.get("provider") or ""),
        "model": str(runtime.get("modelFamily") or params.get("model") or ""),
        "workflowKey": str(runtime.get("workflowKey") or ""),
        "endpoint": str(runtime.get("workflowKey") or ""),
    }


def apply_generate_view(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    prop = _ensure_prop(ctx, args)
    raw = str(args.get("view") or args.get("angle") or "").strip()
    plan = _button_generator_args(args)
    if not raw or raw.lower() == "primary":
        from ....prop_creator.advanced_service import generate_primary
        from ....prop_creator.service import generate_candidates

        if prop.mode == "advanced":
            prop = generate_primary(ctx.db, ctx.project_id, prop.id, **plan)
        else:
            prop = generate_candidates(ctx.db, ctx.project_id, prop.id, **plan)
        view = "primary"
        ctx.db.commit()
        job_id = ""
        for candidate in prop.candidates:
            if candidate.job_id and not str(candidate.job_id).startswith("failed_"):
                job_id = candidate.job_id
                break
        if not job_id:
            error = next((candidate.error for candidate in prop.candidates if candidate.error), "")
            raise ValueError(error or "Prop Creator did not start an image job.")
        return {
            "ok": True,
            "propId": prop.id,
            "view": view,
            "sameStore": True,
            "message": "The prop image is generating. It is not in the Library yet.",
            **_queued_prop_job(job_id),
        }
    else:
        from ....prop_creator.advanced_service import generate_angle

        view = _normalize_view(raw)
        if view == "primary":
            return apply_generate_view(ctx, {**args, "view": "primary"})
        prop = generate_angle(ctx.db, ctx.project_id, prop.id, view, regenerate=False)
    return {"ok": True, "propId": prop.id, "view": view, "sameStore": True}


def preview_generate_reference_sheet(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    prop = _resolve_prop(ctx, args)
    return ToolPreview(
        summary=f"Create the Prop Reference Sheet for {prop.display_label}.",
        lines=["Uses approved views only.", "Uploaded and generated views count the same."],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def preview_create_profile(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    _require_project(ctx)
    name = str(args.get("name") or args.get("propName") or "").strip() or "Untitled prop"
    from ....creator_scope.contract import ENTITY_PROP
    from ....creator_scope.service import reuse_existing_profile

    reused = reuse_existing_profile(ctx.db, entity_type=ENTITY_PROP, project_id=ctx.project_id, name=name)
    if reused:
        return ToolPreview(
            summary=f"{name} already exists. I'll use the existing Prop profile.",
            lines=[
                "Does not create a second Prop.",
                f"Existing id: {reused['existingId']}",
                "Global" if reused.get("isGlobal") else "Local to this project",
            ],
            resourceKind="project",
            resourceId=ctx.project_id,
        )
    return ToolPreview(
        summary=f"Create Prop profile “{name}”.",
        lines=["Creates one Prop with this name.", "Does not generate images."],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_create_profile(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _require_project(ctx)
    name = str(args.get("name") or args.get("propName") or "").strip()
    if not name:
        raise ValueError("name is required")
    from ....creator_scope.contract import ENTITY_PROP
    from ....creator_scope.service import reuse_existing_profile
    from ....prop_creator.service import create_or_update_prop, get_prop

    reused = reuse_existing_profile(ctx.db, entity_type=ENTITY_PROP, project_id=ctx.project_id, name=name)
    if reused:
        prop = get_prop(ctx.db, ctx.project_id, reused["entityId"])
        reused["propId"] = prop.id
        reused["prop"] = prop.model_dump()
        return reused
    is_global = bool(args.get("isGlobal") or args.get("is_global"))
    prop = create_or_update_prop(
        ctx.db,
        ctx.project_id,
        name=name,
        description=str(args.get("description") or ""),
        is_global=is_global,
    )
    return {
        "ok": True,
        "created": True,
        "reused": False,
        "propId": prop.id,
        "prop": prop.model_dump(),
        "message": f"Created Prop {prop.display_label}.",
    }


def apply_generate_reference_sheet(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    prop = _resolve_prop(ctx, args)
    if prop.mode == "advanced":
        from ....prop_creator.advanced_service import generate_advanced_reference_sheet

        prop = generate_advanced_reference_sheet(ctx.db, ctx.project_id, prop.id)
    else:
        from ....prop_creator.service import _compose_prs_after_approval

        _compose_prs_after_approval(ctx.db, ctx.project_id, prop)
        from ....prop_creator.service import get_prop

        prop = get_prop(ctx.db, ctx.project_id, prop.id)
    return {
        "ok": True,
        "propId": prop.id,
        "advancedSheetAssetId": prop.advanced_sheet_asset_id,
        "advancedSheetStatus": prop.advanced_sheet_status,
        "sameStore": True,
    }


def preview_delete_profile(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    prop = _resolve_prop(ctx, args)
    from ....creator_scope.contract import ENTITY_PROP
    from ....creator_scope.service import delete_preview_payload
    preview = delete_preview_payload(
        ctx.db,
        entity_type=ENTITY_PROP,
        entity_id=prop.id,
        name=prop.display_label or prop.tag or "Prop",
        is_global=getattr(prop, "is_global", False) or getattr(prop, "isGlobal", False),
        owning_project_id=prop.project_id,
    )
    scope_label = "Global" if preview["isGlobal"] else "Local"
    lines = [
        f"This is a {scope_label} Prop profile.",
        f"Referenced by {preview['usageCount']} scene(s) across {preview['projectCount']} project(s).",
        "Library images and the Prop Reference Sheet are kept — only the canonical prop profile is removed.",
        "This action cannot be undone.",
    ]
    if preview["isGlobal"]:
        lines.insert(1, "Deleting it will remove the canonical profile from every project using it.")
    return ToolPreview(
        summary=f'Delete Prop profile "{prop.display_label or prop.tag or "Prop"}".',
        lines=lines,
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_delete_profile(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    prop = _resolve_prop(ctx, args)
    from ....prop_creator.service import delete_prop
    confirm = bool(args.get("confirmCrossProject") or args.get("confirm_cross_project"))
    result = delete_prop(ctx.db, ctx.project_id, prop.id, confirm_cross_project=confirm)
    return {"ok": True, "deleted": result.get("ok"), "propId": prop.id, "name": prop.display_label or prop.tag}
