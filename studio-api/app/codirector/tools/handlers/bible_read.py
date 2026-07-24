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
            return {
                "versionNumber": version.version_number,
                "entity": entity.model_dump(mode="json"),
                "facts": related[:20],
            }
    raise CoDirectorError(
        TOOL_TARGET_NOT_FOUND,
        f"No Bible entity with key '{entity_key}' exists in the current version.",
        details={"projectId": ctx.project_id, "entityKey": entity_key},
        recoverable=True,
        recommended_action="none",
    )


async def list_bible_entities(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _, version = _require_current_version(ctx)
    entity_type = args.get("entityType")
    limit = int(args.get("limit") or DEFAULT_ENTITY_LIMIT)
    rows = ops.entities_for_version(ctx.db, version.id)
    if entity_type:
        rows = [r for r in rows if r.entity_type == entity_type]
    return {
        "versionNumber": version.version_number,
        "entityType": entity_type,
        "total": len(rows),
        "entities": [
            {"entityType": r.entity_type, "entityKey": r.entity_key, "displayName": r.display_name or ""}
            for r in rows[:limit]
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
