"""Budgeted, provenance-tagged context compilation for specialists."""



from __future__ import annotations



import hashlib

import json

from typing import Any, Iterable, Optional



from sqlalchemy.orm import Session



from ..bible.context_retrieval import ContextRetrievalService

from ..errors import redact_secrets

from ..tools.capabilities import CapabilityAdapter

from ..tools.handlers.timeline_references import extract_timeline_image_mentions
from .schemas import CONTEXT_PACKAGE_VERSION, ContextFact, ContextPackage

from .specialist_registry import SpecialistDefinition



USER_MESSAGE_BEGIN = "<<<USER_MESSAGE>>>"

USER_MESSAGE_END = "<<<END_USER_MESSAGE>>>"

DEFAULT_CHAR_BUDGET = 12_000

# Categories that may never enter a compiled context package, even when a
# specialist explicitly declares them in `allowed_context`. Kept as a frozen
# set (module-level) so the runtime allowlist is the single source of truth.
FORBIDDEN_CONTEXT_CATEGORIES: frozenset[str] = frozenset(
    {
        "full_tool_registry",
        "full_marketing_plan",
    }
)





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

        attachment_ids: Optional[list[str]] = None,

        recent_messages: Optional[list[dict[str, Any]]] = None,

        conversation_plan: Optional[dict[str, Any]] = None,

    ) -> ContextPackage:

        requested_by_specialists: set[str] = set()

        for specialist in specialists:

            requested_by_specialists.update(specialist.allowed_context)

        forbidden_applied: frozenset[str] = (
            FORBIDDEN_CONTEXT_CATEGORIES & requested_by_specialists
        )

        allowed: set[str] = requested_by_specialists - forbidden_applied

        if not allowed and not requested_by_specialists:

            # Backward-compatible fallback: no selected specialists means the
            # union of all known categories, still filtered by the forbidden
            # set. If a specialist set was provided but every declared
            # category was forbidden, keep the empty allowlist and assemble
            # only the always-on user message.
            allowed = set(self.CATEGORY_PRIORITY) - set(FORBIDDEN_CONTEXT_CATEGORIES)



        facts: list[ContextFact] = []

        omitted: list[str] = []

        denied_categories: list[str] = []



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




        if scene_id and ("references" in allowed or "shot" in allowed or "scene" in allowed):
            try:
                from ....feature_flags import feature_flags
                from ....director_references.service import TimelineReferenceService
                from ....director_references.tags import ensure_tags
                from ....director_timeline import parse_director_timeline
                from ....db import Scene as _Scene

                if feature_flags.timeline_references_v1:
                    scene_row = db.get(_Scene, scene_id)
                    if scene_row and scene_row.project_id == project_id:
                        tl = ensure_tags(
                            parse_director_timeline(
                                scene_row.director_json,
                                fallback_duration=scene_row.duration_sec or 5.0,
                                fallback_prompt=scene_row.prompt or "",
                            )
                        )
                        svc = TimelineReferenceService(db)
                        images = []
                        for clip in tl.image_clips:
                            ref = svc.store.load_active_set(project_id, scene_id, clip.id)
                            images.append(
                                {
                                    "timelineItemId": clip.id,
                                    "displayTag": clip.display_tag,
                                    "assetId": clip.asset_id,
                                    "referenceCount": len(ref.version.bindings) if ref and ref.version else 0,
                                    "activeVersion": ref.active_version if ref else 0,
                                }
                            )
                        mentions = extract_timeline_image_mentions(user_message)
                        resolved = []
                        for tag in mentions:
                            try:
                                resolved.append(svc.resolve_tag(project_id, scene_id, tag))
                            except Exception:
                                resolved.append({"displayTag": tag, "error": "unresolved"})
                        facts.append(
                            _fact(
                                "timeline.images",
                                {
                                    "images": images,
                                    "mentions": mentions,
                                    "resolvedMentions": resolved,
                                },
                                category="references",
                                source_id=scene_id,
                            )
                        )
            except Exception:
                omitted.append("timelineImage")

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

        if recent_messages and "project_overview" in allowed:
            recent_window: list[dict[str, str]] = []
            for item in recent_messages[-12:]:
                if not isinstance(item, dict):
                    continue
                role = str(item.get("role") or "user")
                content = str(item.get("content") or "").strip()
                if not content:
                    continue
                if len(content) > 280:
                    content = content[:277].rstrip() + "..."
                recent_window.append({"role": role, "content": content})
            if recent_window:
                facts.append(
                    _fact(
                        "conversation.recent",
                        recent_window,
                        category="project_overview",
                        authority="unverified",
                        source_type="conversation",
                    )
                )

        if conversation_plan and "project_overview" in allowed:
            facts.append(
                _fact(
                    "conversation.plan",
                    {
                        "primaryIntent": conversation_plan.get("primaryIntent"),
                        "responseMode": conversation_plan.get("responseMode"),
                        "creativeStage": conversation_plan.get("creativeStage"),
                        "creativeSubstate": conversation_plan.get("creativeSubstate"),
                        "shouldAskQuestion": conversation_plan.get("shouldAskQuestion"),
                        "selectedQuestion": conversation_plan.get("selectedQuestion"),
                        "recommendedNextStep": conversation_plan.get("recommendedNextStep"),
                    },
                    category="project_overview",
                    authority="proposed",
                    source_type="conversation_plan",
                )
            )

        # Project Wiki snapshot + honest attachment metadata (no invented perception).
        # Import helpers lazily from a leaf module path to avoid service↔intelligence cycles.
        try:
            from ..context_enrichment import attachment_context_block, compact_wiki_context

            if "project_overview" in allowed:
                wiki_block = compact_wiki_context(db, project_id)
                if wiki_block:
                    facts.append(
                        _fact(
                            "project.wiki_snapshot",
                            wiki_block,
                            category="project_overview",
                            authority="proposed",
                            source_type="project_wiki",
                        )
                    )
            if attachment_ids and ("references" in allowed or "project_overview" in allowed):
                attachment_block = attachment_context_block(
                    db, project_id=project_id, attachment_ids=attachment_ids
                )
                if attachment_block:
                    facts.append(
                        _fact(
                            "turn.attachments",
                            attachment_block,
                            category="references" if "references" in allowed else "project_overview",
                            authority="unverified",
                            source_type="asset_metadata",
                        )
                    )
        except Exception:
            pass

        # Hard allowlist: strip any fact whose category is forbidden regardless
        # of the assembled facts, then dedupe omitted categories before the
        # budget pass records them in diagnostics.
        facts = [
            fact
            for fact in facts
            if fact.key == "user.message" or fact.category not in FORBIDDEN_CONTEXT_CATEGORIES
        ]

        reconciled_omitted: list[str] = []
        for entry in omitted:
            if entry not in reconciled_omitted:
                reconciled_omitted.append(entry)
        omitted = reconciled_omitted

        selected, omitted_categories = self._apply_budget(facts, allowed)

        payload = {

            "projectId": project_id,

            "activeScope": {"sceneId": scene_id},

            "facts": [fact.model_dump(mode="json") for fact in selected],

        }

        capabilities = {

            key: state.to_dict() for key, state in capability_states.items() if state.available

        }

        diagnostics: dict[str, Any] = {
            "allowedCategories": sorted(allowed),
            "charBudget": self.char_budget,
        }
        for entry in sorted(forbidden_applied):
            if entry not in denied_categories:
                denied_categories.append(entry)
        diagnostics["forbiddenCategories"] = sorted(denied_categories)

        final_omitted: list[str] = list(omitted)
        for entry in omitted_categories:
            if entry not in final_omitted:
                final_omitted.append(entry)
        for entry in denied_categories:
            if entry not in final_omitted:
                final_omitted.append(entry)

        return ContextPackage(

            schemaVersion=CONTEXT_PACKAGE_VERSION,

            projectId=project_id,

            activeScope={"sceneId": scene_id},

            facts=selected,

            omittedCategories=final_omitted,

            tokenEstimate=_estimate_tokens(json.dumps(payload, default=str)),

            contextHash=_hash_payload(payload),

            userMessageDelimited=_wrap_user_message(user_message),

            capabilities=capabilities,

            diagnostics=diagnostics,

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

