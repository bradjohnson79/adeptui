"""Production Bible read handlers, plus the `record_director_decision` preview/apply pair.

Reads go through `bible.operations` (the same accessors the Bible workspace and context
injection use), so a tool can never see a Bible state the rest of the app doesn't agree with.
`record_director_decision` writes through `operations.apply_mutation_set`, which means a
recorded decision is a normal, immutable, copy-on-write Bible version — auditable in the
version history like any other change, not a side-channel store.
"""

from __future__ import annotations

from typing import Any

from ...bible import operations as ops
from ...bible.context import DEFAULT_TOKEN_BUDGET, ProjectContextService
from ...bible.schemas import BibleMutationSet, FactMutation
from ...errors import CAPABILITY_NOT_CONFIGURED, TOOL_TARGET_NOT_FOUND, CoDirectorError
from ..definitions import ToolContext, ToolPreview

DECISION_FACT_TYPE = "director_decision"
DEFAULT_ENTITY_LIMIT = 60


def _require_current_version(ctx: ToolContext):
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


# --------------------------------------------------------------------------
# Read
# --------------------------------------------------------------------------


async def get_current_bible_version(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _, version = _require_current_version(ctx)
    entities = ops.entities_for_version(ctx.db, version.id)
    facts = ops.facts_for_version(ctx.db, version.id)
    return {
        "projectId": ctx.project_id,
        "versionNumber": version.version_number,
        "versionId": version.id,
        "summary": version.summary or "",
        "changeReason": version.change_reason or "",
        "createdBy": version.created_by,
        "createdAt": version.created_at.isoformat() if version.created_at else None,
        "entityCount": len(entities),
        "factCount": len(facts),
        "entityTypes": sorted({e.entity_type for e in entities}),
    }


def _canonical_status_from_row(row: Any) -> str:
    status = str(getattr(row, "lifecycle_status", None) or getattr(row, "lifecycleStatus", None) or "").lower()
    if status in {"approved", "locked", "canonical", "active"}:
        return "canonical"
    if status in {"draft", "proposed", "pending"}:
        return "draft"
    return status or "unknown"


async def get_bible_entity(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _, version = _require_current_version(ctx)
    entity_key = str(args["entityKey"])
    for row in ops.entities_for_version(ctx.db, version.id):
        if row.entity_key == entity_key:
            entity = ops.entity_row_to_schema(row)
            related = [
                ops.fact_row_to_schema(f).statement
                for f in ops.facts_for_version(ctx.db, version.id)
                if f.entity_key == entity_key
            ]
            payload = entity.model_dump(mode="json")
            canonical_status = _canonical_status_from_row(row)
            if isinstance(payload, dict) and "canonical_status" not in payload:
                payload["canonical_status"] = canonical_status
            return {
                "versionNumber": version.version_number,
                "entity": payload,
                "facts": related[:20],
                "canonical_status": canonical_status,
                "_summary": f"Bible entity '{entity_key}' ({canonical_status}).",
                "_evidence": [
                    {
                        "sourceType": "production_bible",
                        "sourceId": entity_key,
                        "sourceName": getattr(row, "display_name", None),
                        "repository": "bible.operations",
                    }
                ],
            }
    raise CoDirectorError(
        TOOL_TARGET_NOT_FOUND,
        f"No Bible entity with key '{entity_key}' exists in the current version.",
        details={"projectId": ctx.project_id, "entityKey": entity_key},
        recoverable=True,
        recommended_action="none",
    )


async def list_bible_entities(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ..read_envelope import clamp_limit

    _, version = _require_current_version(ctx)
    entity_type = args.get("entityType")
    limit = clamp_limit(args.get("limit"), default=DEFAULT_ENTITY_LIMIT)
    rows = ops.entities_for_version(ctx.db, version.id)
    if entity_type:
        rows = [r for r in rows if r.entity_type == entity_type]
    entities = [
        {
            "entityType": r.entity_type,
            "entityKey": r.entity_key,
            "displayName": r.display_name or "",
            "canonical_status": _canonical_status_from_row(r),
        }
        for r in rows[:limit]
    ]
    return {
        "versionNumber": version.version_number,
        "entityType": entity_type,
        "total": len(rows),
        "entities": entities,
        "_summary": f"{len(entities)} Bible entit(y/ies).",
        "_pagination": {
            "limit": limit,
            "total": len(rows),
            "hasMore": len(rows) > limit,
            "returnedCount": len(entities),
            "appliedFilters": {"entityType": entity_type} if entity_type else {},
        },
        "_evidence": [
            {
                "sourceType": "production_bible",
                "sourceId": e["entityKey"],
                "sourceName": e["displayName"],
                "repository": "bible.operations",
            }
            for e in entities
        ],
    }


async def get_relevant_bible_context(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _require_current_version(ctx)
    budget = int(args.get("tokenBudget") or DEFAULT_TOKEN_BUDGET)
    excerpt, manifest = ProjectContextService.build(ctx.db, ctx.project_id, token_budget=budget)
    return {"excerpt": excerpt, "manifest": manifest.model_dump(mode="json")}


# --------------------------------------------------------------------------
# Mutating: record_director_decision
# --------------------------------------------------------------------------


def _decision_statement(args: dict[str, Any]) -> str:
    decision = str(args["decision"]).strip()
    rationale = str(args.get("rationale") or "").strip()
    return f"{decision} (Rationale: {rationale})" if rationale else decision


def preview_record_director_decision(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    _, version = _require_current_version(ctx)
    entity_key = args.get("entityKey")
    lines = [_decision_statement(args)]
    warnings: list[str] = []
    if entity_key:
        known = {r.entity_key for r in ops.entities_for_version(ctx.db, version.id)}
        lines.append(f"Attached to: {entity_key}")
        if entity_key not in known:
            warnings.append(f"'{entity_key}' isn't an entity in the current Bible version yet.")
    return ToolPreview(
        summary=f"Record a director decision as a continuity fact in Bible v{version.version_number + 1}.",
        lines=lines,
        resourceKind="bible",
        resourceId=version.id,
        warnings=warnings,
    )


def apply_record_director_decision(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    bible, version = _require_current_version(ctx)
    statement = _decision_statement(args)
    mutations = BibleMutationSet(
        factMutations=[
            FactMutation(
                entityKey=args.get("entityKey"),
                factType=DECISION_FACT_TYPE,
                statement=statement,
                data={"recordedVia": "codirector_tool"},
            )
        ],
        summary=version.summary or "",
        changeReason="director_decision_recorded",
    )
    new_version = ops.apply_mutation_set(
        ctx.db,
        bible=bible,
        base_version=version,
        mutations=mutations,
        created_by="tool:record_director_decision",
    )
    return {
        "recorded": "director_decision",
        "statement": statement,
        "bibleVersionNumber": new_version.version_number,
        "bibleVersionId": new_version.id,
    }
