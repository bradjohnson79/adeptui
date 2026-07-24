"""ProjectContextService: bounded Production Bible excerpt for chat context injection.

Deliberately separate from `assistant.build_context_block` (project/scene/asset context) and
`learning_context_block` (learning preferences) — this only ever contributes a Bible excerpt,
so projects without a Bible see byte-for-byte the same context as before M2.1.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from ...db import ProductionBibleEntity, ProductionBibleFact
from . import operations as ops
from .schemas import ENTITY_TYPE_PRIORITY, ContextManifest

DEFAULT_TOKEN_BUDGET = 1200


def _estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token) — good enough for a soft prompt-size budget."""

    return max(1, len(text) // 4)


def _format_entity(row: ProductionBibleEntity) -> str:
    entity = ops.entity_row_to_schema(row)
    detail_bits = []
    for key in ("description", "appearance", "personality", "notes"):
        val = entity.data.get(key)
        if val:
            detail_bits.append(str(val))
    detail = " — " + "; ".join(detail_bits) if detail_bits else ""
    return f"[{entity.entityType}] {entity.displayName or entity.entityKey}{detail}"


def _format_fact(row: ProductionBibleFact) -> str:
    fact = ops.fact_row_to_schema(row)
    prefix = f"({fact.entityKey}) " if fact.entityKey else ""
    return f"- {prefix}{fact.statement}".strip()


class ProjectContextService:
    """Builds the Bible excerpt block injected into Co-Director's system context."""

    @staticmethod
    def build(db: Session, project_id: Optional[str], *, token_budget: int = DEFAULT_TOKEN_BUDGET) -> tuple[str, ContextManifest]:
        manifest = ContextManifest(projectId=project_id or "", tokenBudget=token_budget)
        if not project_id:
            return "", manifest

        bible = ops.get_bible(db, project_id)
        if not bible:
            return "", manifest

        version = ops.get_current_version(db, bible)
        if not version:
            return "", manifest

        manifest.bibleVersionId = version.id
        manifest.bibleVersionNumber = version.version_number

        entity_rows = ops.entities_for_version(db, version.id)
        fact_rows = ops.facts_for_version(db, version.id)

        priority_index = {t: i for i, t in enumerate(ENTITY_TYPE_PRIORITY)}
        entity_rows.sort(key=lambda r: (priority_index.get(r.entity_type, len(ENTITY_TYPE_PRIORITY)), r.entity_key))

        lines: list[str] = ["Production Bible (v" + str(version.version_number) + "):"]
        budget = token_budget
        used_any = False
        truncated = False

        for row in entity_rows:
            text = _format_entity(row)
            cost = _estimate_tokens(text)
            if used_any and cost > budget:
                truncated = True
                continue
            lines.append(text)
            manifest.includedEntityKeys.append(row.entity_key)
            budget -= cost
            used_any = True

        if fact_rows:
            lines.append("Continuity / narrative facts:")
        for row in fact_rows:
            text = _format_fact(row)
            cost = _estimate_tokens(text)
            if used_any and cost > budget:
                truncated = True
                continue
            lines.append(text)
            manifest.includedFactIds.append(row.id)
            budget -= cost
            used_any = True

        manifest.truncated = truncated
        excerpt = "\n".join(lines) if (manifest.includedEntityKeys or manifest.includedFactIds) else ""
        manifest.estimatedTokens = _estimate_tokens(excerpt)
        return excerpt, manifest
