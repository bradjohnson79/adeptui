"""Budgeted, provenance-tagged context compilation for specialists."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from ..bible.context_retrieval import ContextRetrievalService
from ..errors import redact_secrets
from ..tools.capabilities import CapabilityAdapter
from .schemas import CONTEXT_PACKAGE_VERSION, ContextFact, ContextPackage
from .specialist_registry import SpecialistDefinition

USER_MESSAGE_BEGIN = "<<<USER_MESSAGE>>>"
USER_MESSAGE_END = "<<<END_USER_MESSAGE>>>"
DEFAULT_CHAR_BUDGET = 12_000


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _hash_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _wrap_user_message(message: str) -> str:
    sanitized = redact_secrets(message.strip())
    sanitized = sanitized.replace(USER_MESSAGE_BEGIN, "[user_delimiter]").replace(USER_MESSAGE_END, "[end_user_delimiter]")
    return f"{USER_MESSAGE_BEGIN}\n{sanitized}\n{USER_MESSAGE_END}"


def _fact(
    key: str,
    value: Any,
    *,
    category: str,
    authority: str = "approved",
    source_type: str = "production_bible",
    source_id: str | None = None,
) -> ContextFact:
    return ContextFact(
        key=key,
        value=value,
        category=category,
        authority=authority,  # type: ignore[arg-type]
        sourceType=source_type,  # type: ignore[arg-type]
        sourceId=source_id,
    )


class ContextCompiler:
    CATEGORY_PRIORITY: tuple[str, ...] = (
        "project_overview",
        "scene",
        "shot",
        "characters",
        "locations",
        "continuity",
        "references",
        "visual_language",
        "canon",
        "capabilities",
        "story",
        "production_decisions",
        "wardrobe",
        "previous_shot",
        "next_shot",
        "objects",
        "audio",
        "vfx",
    )

    def __init__(self, *, char_budget: int = DEFAULT_CHAR_BUDGET) -> None:
        self.char_budget = char_budget

    async def compile(
        self,
        db: Session,
        *,
        project_id: str,
        user_message: str,
        scene_id: Optional[str] = None,
        specialists: Iterable[SpecialistDefinition] = (),
    ) -> ContextPackage:
        allowed: set[str] = set()
        for specialist in specialists:
            allowed.update(specialist.allowed_context)
        if not allowed:
            allowed.update(self.CATEGORY_PRIORITY)

        facts: list[ContextFact] = []
        omitted: list[str] = []

        summary = ContextRetrievalService.project_summary(db, project_id)
        if "project_overview" in allowed:
            facts.append(_fact("project.summary", summary, category="project_overview"))

        if scene_id and "scene" in allowed:
            scene_ctx = ContextRetrievalService.scene_context(db, project_id, scene_id)
            facts.append(_fact("scene.context", scene_ctx, category="scene", source_id=scene_id))
            if scene_ctx.get("characters") and "characters" in allowed:
                facts.append(_fact("scene.characters", scene_ctx["characters"], category="characters"))
            if scene_ctx.get("visualLanguage") and "visual_language" in allowed:
                facts.append(
                    _fact("scene.visualLanguage", scene_ctx["visualLanguage"], category="visual_language")
                )
            if scene_ctx.get("continuityStates") and "continuity" in allowed:
                facts.append(
                    _fact("scene.continuity", scene_ctx["continuityStates"], category="continuity")
                )

        if "references" in allowed or "shot" in allowed:
            generation = ContextRetrievalService.generation_package(db, project_id, scene_id=scene_id)
            if "references" in allowed:
                facts.append(_fact("generation.references", generation, category="references"))
            if "continuity" in allowed and generation.get("continuityConstraints"):
                facts.append(
                    _fact(
                        "generation.continuityConstraints",
                        generation["continuityConstraints"],
                        category="continuity",
                    )
                )

        adapter = CapabilityAdapter(db, project_id)
        capability_states = await adapter.snapshot()
        if "capabilities" in allowed:
            facts.append(
                _fact(
                    "capabilities.snapshot",
                    {key: state.to_dict() for key, state in capability_states.items()},
                    category="capabilities",
                    authority="approved",
                    source_type="asset_metadata",
                )
            )

        facts.append(
            _fact(
                "user.message",
                user_message,
                category="project_overview",
                authority="unverified",
                source_type="user_message",
            )
        )

        selected, omitted_categories = self._apply_budget(facts, allowed)
        payload = {
            "projectId": project_id,
            "activeScope": {"sceneId": scene_id},
            "facts": [fact.model_dump(mode="json") for fact in selected],
        }
        capabilities = {
            key: state.to_dict() for key, state in capability_states.items() if state.available
        }
        return ContextPackage(
            schemaVersion=CONTEXT_PACKAGE_VERSION,
            projectId=project_id,
            activeScope={"sceneId": scene_id},
            facts=selected,
            omittedCategories=omitted + omitted_categories,
            tokenEstimate=_estimate_tokens(json.dumps(payload, default=str)),
            contextHash=_hash_payload(payload),
            userMessageDelimited=_wrap_user_message(user_message),
            capabilities=capabilities,
            diagnostics={"allowedCategories": sorted(allowed), "charBudget": self.char_budget},
        )

    def _apply_budget(
        self, facts: list[ContextFact], allowed: set[str]
    ) -> tuple[list[ContextFact], list[str]]:
        by_category: dict[str, list[ContextFact]] = {}
        for fact in facts:
            if fact.category not in allowed and fact.key != "user.message":
                continue
            by_category.setdefault(fact.category, []).append(fact)

        selected: list[ContextFact] = []
        used = 0
        omitted: list[str] = []
        for category in self.CATEGORY_PRIORITY:
            bucket = by_category.get(category)
            if not bucket:
                continue
            block = json.dumps([f.model_dump(mode="json") for f in bucket], default=str)
            if used + len(block) > self.char_budget and category not in ("project_overview", "scene", "user"):
                omitted.append(category)
                continue
            selected.extend(bucket)
            used += len(block)
        # Always keep delimited user message as a dedicated fact entry.
        user_facts = [f for f in facts if f.key == "user.message"]
        for fact in user_facts:
            if fact not in selected:
                selected.append(fact)
        return selected, omitted

    @staticmethod
    def filter_for_specialist(
        package: ContextPackage, specialist: SpecialistDefinition
    ) -> ContextPackage:
        allowed = set(specialist.allowed_context)
        filtered = [fact for fact in package.facts if fact.category in allowed or fact.key == "user.message"]
        return package.model_copy(update={"facts": filtered})
