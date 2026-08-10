"""M2.3 Production Bible domain tool handlers."""

from __future__ import annotations

from typing import Any

from ...bible.context_retrieval import ContextRetrievalService
from ...bible.domain_service import BibleDomainService
from ...bible.domain.schemas import CanonRecordData, CharacterData, VisualLanguageData
from ...bible import operations as ops
from ...bible.schemas import BibleMutationSet, EntityMutation, FactMutation
from ....db import Asset
from ...errors import (
    CAPABILITY_NOT_CONFIGURED,
    CoDirectorError,
    REFERENCE_ASSET_MISSING,
    REFERENCE_LINK_EXISTS,
    REFERENCE_TARGET_MISSING,
    SUPERSEDED_NOT_CURRENT,
)
from ..definitions import ToolContext, ToolPreview


def _require_bible(ctx: ToolContext):
    bible = ops.get_bible(ctx.db, ctx.project_id)
    version = ops.get_current_version(ctx.db, bible) if bible else None
    if not bible or not version:
        raise CoDirectorError(
            CAPABILITY_NOT_CONFIGURED,
            "This project doesn't have a Production Bible yet.",
            details={"projectId": ctx.project_id, "capability": "bible"},
            recoverable=True,
            recommended_action="configure_capability",
        )
    return bible, version


async def get_production_bible_summary(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    summary = BibleDomainService.get_summary(ctx.db, ctx.project_id)
    if not isinstance(summary, dict):
        summary = {"value": summary}
    summary["_summary"] = "Production Bible summary from domain service."
    summary["_evidence"] = [
        {"sourceType": "production_bible", "sourceId": ctx.project_id, "repository": "bible.domain"}
    ]
    return summary


async def get_scene_bible_context(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene_id = args.get("sceneId") or ctx.scene_id
    if not scene_id:
        raise CoDirectorError("TOOL_ARGUMENTS_INVALID", "sceneId is required.", recoverable=True)
    return ContextRetrievalService.scene_context(ctx.db, ctx.project_id, str(scene_id))


async def get_character_bible_context(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return ContextRetrievalService.character_context(ctx.db, ctx.project_id, str(args["stableId"]))


async def get_location_bible_context(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return ContextRetrievalService.location_context(ctx.db, ctx.project_id, str(args["stableId"]))


async def list_canon_records(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    items = BibleDomainService.list_canon(ctx.db, ctx.project_id)
    return {"canonRecords": items}


async def list_continuity_warnings(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    conflicts = BibleDomainService.sync_conflicts(ctx.db, ctx.project_id)
    return {"warnings": conflicts}


async def get_generation_reference_package(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return ContextRetrievalService.generation_package(ctx.db, ctx.project_id, scene_id=args.get("sceneId"))


# --------------------------------------------------------------------------
# Mutating proposal previews/applies
# --------------------------------------------------------------------------


def preview_propose_character_update(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    _, version = _require_bible(ctx)
    stable_id = args.get("stableId")
    entity_key = args.get("entityKey", stable_id or "character")
    lines = [f"Update character fields for {entity_key}"]
    if args.get("data"):
        lines.append(f"Fields: {', '.join(args['data'].keys())}")
    return ToolPreview(
        summary=f"Propose character update in Bible v{version.version_number + 1}.",
        lines=lines,
        resourceKind="bible",
        resourceId=version.id,
    )


def apply_propose_character_update(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bible, version = _require_bible(ctx)
    stable_id = args.get("stableId")
    entity_key = args.get("entityKey")
    entities = [ops.entity_row_to_schema(r) for r in ops.entities_for_version(ctx.db, version.id)]
    existing = next((e for e in entities if (stable_id and e.stableId == stable_id) or (entity_key and e.entityKey == entity_key)), None)
    if not existing:
        data = CharacterData.model_validate(args.get("data") or {}).model_dump(mode="json")
        mutation = EntityMutation(
            entityType="character",
            entityKey=entity_key or f"char-{stable_id[:8] if stable_id else 'new'}",
            displayName=args.get("displayName", "Character"),
            data=data,
        )
    else:
        merged = {**existing.data, **(args.get("data") or {})}
        CharacterData.model_validate(merged)
        mutation = EntityMutation(
            entityType="character",
            entityKey=existing.entityKey,
            displayName=args.get("displayName") or existing.displayName,
            data=merged,
            stableId=existing.stableId,
            contentRevision=existing.contentRevision + 1,
        )
    new_version = ops.apply_mutation_set(
        ctx.db,
        bible=bible,
        base_version=version,
        mutations=BibleMutationSet(entityMutations=[mutation], changeReason="tool_propose_character_update"),
        created_by="tool:propose_character_update",
    )
    return {"bibleVersionNumber": new_version.version_number}


def preview_propose_canon_record(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    _, version = _require_bible(ctx)
    claim = str(args.get("claim", ""))[:120]
    return ToolPreview(
        summary=f"Propose canon record in Bible v{version.version_number + 1}.",
        lines=[claim],
        resourceKind="bible",
        resourceId=version.id,
    )


def apply_propose_canon_record(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    result = BibleDomainService.create_canon_record(
        ctx.db,
        ctx.project_id,
        claim=str(args["claim"]),
        entity_stable_id=args.get("entityStableId"),
        scene_id=args.get("sceneId"),
    )
    return {"canonRecord": result}


def preview_propose_canon_supersession(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    _, version = _require_bible(ctx)
    return ToolPreview(
        summary=f"Supersede canon record {args.get('supersedesStableId')} in Bible v{version.version_number + 1}.",
        lines=[str(args.get("claim", ""))],
        resourceKind="bible",
        resourceId=version.id,
    )


def apply_propose_canon_supersession(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # D4: authoritative read-before-write — verify the superseded record exists
    # and is the current version (not already superseded) before delegating to
    # the service. The service applies the supersession, but the tool boundary
    # must reject a supersession against a stale or missing record.
    bible, version = _require_bible(ctx)
    supersedes_stable_id = str(args.get("supersedesStableId") or "")
    if not supersedes_stable_id:
        raise CoDirectorError(
            "TOOL_ARGUMENTS_INVALID",
            "supersedesStableId is required for a canon supersession.",
            recoverable=True,
            recommended_action="revise_arguments",
        )
    entities = [ops.entity_row_to_schema(r) for r in ops.entities_for_version(ctx.db, version.id)]
    superseded = next((e for e in entities if e.stableId == supersedes_stable_id and e.entityType == "canon_record"), None)
    if superseded is None:
        raise CoDirectorError(
            SUPERSEDED_NOT_CURRENT,
            "The canon record being superseded does not exist in the current Bible version.",
            details={"supersedesStableId": supersedes_stable_id},
            recoverable=False,
            recommended_action="none",
        )
    if str(superseded.data.get("status") or "").lower() in {"superseded", "retired"}:
        raise CoDirectorError(
            SUPERSEDED_NOT_CURRENT,
            "The canon record being superseded is already superseded — supersede the current record instead.",
            details={"supersedesStableId": supersedes_stable_id, "currentStatus": superseded.data.get("status")},
            recoverable=True,
            recommended_action="reload_and_retry",
        )
    result = BibleDomainService.create_canon_record(
        ctx.db,
        ctx.project_id,
        claim=str(args["claim"]),
        entity_stable_id=args.get("entityStableId"),
        supersedes_stable_id=supersedes_stable_id,
    )
    return {"canonRecord": result}


def preview_propose_continuity_update(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    _, version = _require_bible(ctx)
    return ToolPreview(
        summary=f"Propose continuity update in Bible v{version.version_number + 1}.",
        lines=[f"Aspect: {args.get('aspect', 'other')}"],
        resourceKind="bible",
        resourceId=version.id,
    )


def apply_propose_continuity_update(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    import uuid

    # D5: authoritative read-before-write — query existing continuity entities
    # for the same subject before generating a new entity_key. When an existing
    # continuity_state entity for the same subject+scene exists, update it in
    # place via the domain service instead of creating a duplicate.
    bible, version = _require_bible(ctx)
    aspect = str(args.get("aspect", "other"))
    scene_id = args.get("sceneId")
    subject_stable_id = args.get("entityStableId")
    entities = [ops.entity_row_to_schema(r) for r in ops.entities_for_version(ctx.db, version.id)]
    existing = next(
        (
            e
            for e in entities
            if e.entityType == "continuity_state"
            and (e.data.get("aspect") or "other") == aspect
            and (e.data.get("sceneId") or None) == (scene_id or None)
            and (
                # Match either by explicit subject stable id, or by aspect+scene when no subject.
                (subject_stable_id and e.data.get("entityStableId") == subject_stable_id)
                or (not subject_stable_id)
            )
        ),
        None,
    )
    data = {
        "aspect": aspect,
        "entityStableId": subject_stable_id,
        "sceneId": scene_id,
        "expectedValue": args.get("expectedValue", ""),
        "actualValue": args.get("actualValue", ""),
        "resolved": args.get("resolved", False),
    }
    if existing is not None:
        updated = BibleDomainService.update_entity(
            ctx.db,
            ctx.project_id,
            existing.stableId,
            display_name=f"Continuity {aspect}",
            data=data,
        )
        return {"continuityState": updated}
    result = BibleDomainService.create_entity(
        ctx.db,
        ctx.project_id,
        entity_type="continuity_state",
        entity_key=f"cont-{uuid.uuid4().hex[:8]}",
        display_name=f"Continuity {aspect}",
        data=data,
    )
    return {"continuityState": result}


def preview_propose_reference_link(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    _, version = _require_bible(ctx)
    return ToolPreview(
        summary=f"Propose reference link in Bible v{version.version_number + 1}.",
        lines=[f"Asset {args.get('assetId')} → {args.get('targetStableId')}"],
        resourceKind="bible",
        resourceId=version.id,
    )


def apply_propose_reference_link(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # D6: authoritative read-before-write — verify the asset and target exist
    # and that an identical reference link is not already present before
    # delegating to the service. The service checks the target entity, but the
    # tool boundary must also verify the asset (an Asset row) and reject a
    # duplicate link with explicit codes.
    bible, version = _require_bible(ctx)
    asset_id = str(args["assetId"])
    target_stable_id = str(args["targetStableId"])
    purpose = str(args.get("purpose", "identity"))
    primary = bool(args.get("primary", False))

    asset = ctx.db.query(Asset).filter(Asset.id == asset_id, Asset.project_id == ctx.project_id).first()
    if asset is None:
        raise CoDirectorError(
            REFERENCE_ASSET_MISSING,
            "The asset being linked does not exist in this project.",
            details={"assetId": asset_id, "projectId": ctx.project_id},
            recoverable=False,
            recommended_action="none",
        )
    entities = [ops.entity_row_to_schema(r) for r in ops.entities_for_version(ctx.db, version.id)]
    target = next((e for e in entities if e.stableId == target_stable_id), None)
    if target is None:
        raise CoDirectorError(
            REFERENCE_TARGET_MISSING,
            "The link target does not exist in the current Bible version.",
            details={"targetStableId": target_stable_id},
            recoverable=False,
            recommended_action="none",
        )
    existing_link = next(
        (
            e
            for e in entities
            if e.entityType == "reference_link"
            and e.data.get("assetId") == asset_id
            and e.data.get("targetStableId") == target_stable_id
            and (e.data.get("purpose") or "identity") == purpose
        ),
        None,
    )
    if existing_link is not None:
        raise CoDirectorError(
            REFERENCE_LINK_EXISTS,
            "An identical reference link already exists in the current Bible version.",
            details={
                "assetId": asset_id,
                "targetStableId": target_stable_id,
                "purpose": purpose,
                "existingStableId": existing_link.stableId,
            },
            recoverable=True,
            recommended_action="none",
        )
    result = BibleDomainService.link_reference(
        ctx.db,
        ctx.project_id,
        asset_id=asset_id,
        target_stable_id=target_stable_id,
        purpose=purpose,
        primary=primary,
    )
    return {"referenceLink": result}


def preview_propose_production_decision(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    _, version = _require_bible(ctx)
    return ToolPreview(
        summary=f"Propose production decision in Bible v{version.version_number + 1}.",
        lines=[str(args.get("decision", ""))],
        resourceKind="bible",
        resourceId=version.id,
    )


def apply_propose_production_decision(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    import uuid

    result = BibleDomainService.create_entity(
        ctx.db,
        ctx.project_id,
        entity_type="production_decision",
        entity_key=f"dec-{uuid.uuid4().hex[:8]}",
        display_name=str(args.get("decision", "Decision"))[:80],
        data={
            "decision": str(args.get("decision", "")),
            "rationale": str(args.get("rationale", "")),
            "entityStableId": args.get("entityStableId"),
            "sceneId": args.get("sceneId"),
        },
    )
    return {"decision": result}


def preview_propose_visual_language_update(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    _, version = _require_bible(ctx)
    return ToolPreview(
        summary=f"Propose visual language update in Bible v{version.version_number + 1}.",
        lines=[str(args.get("description", ""))[:120]],
        resourceKind="bible",
        resourceId=version.id,
    )


def apply_propose_visual_language_update(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bible, version = _require_bible(ctx)
    entities = [ops.entity_row_to_schema(r) for r in ops.entities_for_version(ctx.db, version.id)]
    existing = next((e for e in entities if e.entityType in ("visual_language", "visual_style")), None)
    data = VisualLanguageData.model_validate(args.get("data") or {"description": args.get("description", "")}).model_dump(mode="json")
    if existing:
        merged = {**existing.data, **data}
        mutation = EntityMutation(
            entityType="visual_language",
            entityKey=existing.entityKey,
            displayName=existing.displayName,
            data=merged,
            stableId=existing.stableId,
            contentRevision=existing.contentRevision + 1,
        )
    else:
        mutation = EntityMutation(
            entityType="visual_language",
            entityKey="visual-language",
            displayName="Visual Language",
            data=data,
        )
    new_version = ops.apply_mutation_set(
        ctx.db,
        bible=bible,
        base_version=version,
        mutations=BibleMutationSet(entityMutations=[mutation], changeReason="tool_propose_visual_language_update"),
        created_by="tool:propose_visual_language_update",
    )
    return {"bibleVersionNumber": new_version.version_number}
