"""IntelligenceService orchestrating the full M2.4 production intelligence run."""

from __future__ import annotations

from typing import Any, AsyncIterator, Optional

from sqlalchemy.orm import Session

from ..errors import (
    CONTEXT_INCOMPLETE,
    INTENT_CLASSIFICATION_FAILED,
    SYNTHESIS_FAILED,
    CoDirectorError,
)
from ..prompts.loader import get_prompt_library
from ..providers.base import CoDirectorProvider
from .intent import classify_intent
from .planning import PlanBuilder, PlanExecutorBridge
from .schemas import IntentClassification, ProductionPlan, SynthesisResult
from .specialist_runner import (
    LIMITED_ANALYSIS_MODE,
    SpecialistRunner,
    resolve_provider_for_specialists,
)
from .specialist_selector import SpecialistSelector
from .specialist_registry import SpecialistRegistry
from .stage_router import route_stage
from .store import IntelligenceStore
from .synthesis import SynthesisEngine

try:
    from ..foundation.pipeline import (
        merge_findings_for_synthesis,
        resolve_domain_profile_ids,
        run_foundation_creative_pass,
        should_run_foundation_creative,
    )
except Exception:  # noqa: BLE001
    merge_findings_for_synthesis = None  # type: ignore[assignment]
    resolve_domain_profile_ids = None  # type: ignore[assignment]
    run_foundation_creative_pass = None  # type: ignore[assignment]
    should_run_foundation_creative = None  # type: ignore[assignment]


class IntelligenceService:
    PROGRESS_STAGES = (
        "classifying_intent",
        "compiling_context",
        "selecting_specialists",
        "running_specialists",
        "synthesizing",
        "building_plan",
        "creating_proposals",
        "complete",
    )

    def __init__(self) -> None:
        self.registry = SpecialistRegistry()
        self.selector = SpecialistSelector(self.registry)
        self.runner = SpecialistRunner(self.registry)
        self.synthesis = SynthesisEngine()
        self.plan_builder = PlanBuilder()
        self.prompt_library = get_prompt_library()

    def should_use_intelligence(self, intent: IntentClassification) -> bool:
        if intent.isSimpleQuestion and intent.primaryIntent == "answer_question":
            return False
        return intent.primaryIntent not in ("unknown",) or bool(intent.playbookId)

    async def run_intelligence(
        self,
        db: Session,
        *,
        project_id: str,
        user_message: str,
        scene_id: Optional[str] = None,
        mode: str = "chat",
        provider: Optional[CoDirectorProvider] = None,
        model_id: Optional[str] = None,
        request_id: Optional[str] = None,
        use_provider: bool | None = None,
        route_decision: Optional[Any] = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        async for event in self.stream_intelligence(
            db,
            project_id=project_id,
            user_message=user_message,
            scene_id=scene_id,
            mode=mode,
            provider=provider,
            model_id=model_id,
            request_id=request_id,
            use_provider=use_provider,
            route_decision=route_decision,
        ):
            event_type = event.get("type")
            if event_type == "intelligence_result":
                result["synthesis"] = event.get("synthesis")
            elif event_type == "intelligence_plan":
                result["plan"] = event.get("plan")
            elif event_type == "intelligence_proposal":
                result.setdefault("proposals", []).append(event.get("proposal"))
            elif event_type == "error":
                result["error"] = event.get("error")
        return result

    async def stream_intelligence(
        self,
        db: Session,
        *,
        project_id: str,
        user_message: str,
        scene_id: Optional[str] = None,
        mode: str = "chat",
        provider: Optional[CoDirectorProvider] = None,
        model_id: Optional[str] = None,
        request_id: Optional[str] = None,
        use_provider: bool | None = None,
        attachment_ids: Optional[list[str]] = None,
        recent_messages: Optional[list[dict[str, Any]]] = None,
        conversation_plan: Optional[dict[str, Any]] = None,
        route_decision: Optional[Any] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        request_id = request_id or "intelligence"
        prompt_versions = self.prompt_library.version_map()
        provider, use_provider_effective, analysis_mode = await resolve_provider_for_specialists(
            provider,
            prefer_provider=use_provider,
        )

        yield {
            "type": "intelligence_progress",
            "requestId": request_id,
            "stage": "classifying_intent",
            "message": "Understanding the request",
            "promptVersions": prompt_versions,
            "analysisMode": analysis_mode,
        }

        try:
            intent = classify_intent(user_message, scene_id=scene_id, mode=mode)
            intent.productionStage = route_stage(intent)
        except Exception as exc:  # noqa: BLE001
            err = CoDirectorError(
                INTENT_CLASSIFICATION_FAILED,
                "Could not classify the production intent for this request.",
                details={"reason": str(exc)[:200]},
                recoverable=True,
            )
            yield {"type": "error", "requestId": request_id, "error": err.to_dict()}
            return

        if not self.should_use_intelligence(intent):
            yield {
                "type": "intelligence_progress",
                "requestId": request_id,
                "stage": "complete",
                "message": "Simple question — intelligence path skipped",
                "intent": intent.model_dump(mode="json"),
            }
            return

        use_foundation = bool(
            should_run_foundation_creative is not None
            and run_foundation_creative_pass is not None
            and should_run_foundation_creative(intent.primaryIntent)
        )
        findings = []
        specialist_ids: list[str] = []
        foundation_review = None
        foundation_knowledge_refs: list[str] = []

        if use_foundation:
            # One foundation orchestration path for creative intents (no parallel legacy stack).
            yield {
                "type": "intelligence_progress",
                "requestId": request_id,
                "stage": "foundation_specialists",
                "message": "Consulting creative foundation",
                "intent": intent.model_dump(mode="json"),
            }
            domain_ids: list[str] = []
            if resolve_domain_profile_ids is not None:
                try:
                    import json as _json

                    from ...db import Project as _Project

                    project_row = db.get(_Project, project_id) if project_id else None
                    primary = getattr(project_row, "primary_project_type", None) or "custom"
                    traits_raw = getattr(project_row, "project_traits_json", "[]") or "[]"
                    try:
                        traits = _json.loads(traits_raw) if isinstance(traits_raw, str) else traits_raw
                    except Exception:  # noqa: BLE001
                        traits = []
                    subtype = str(traits[0]) if isinstance(traits, list) and traits else None
                    domain_ids = resolve_domain_profile_ids(
                        primary_slug=str(primary),
                        subtype_slug=subtype,
                        traits=traits,
                    )
                except Exception:  # noqa: BLE001
                    domain_ids = []
            stage = conversation_plan.get("creativeStage") if conversation_plan else None
            substate = conversation_plan.get("creativeSubstate") if conversation_plan else None
            findings, foundation_review, foundation_knowledge_refs = run_foundation_creative_pass(
                project_id=project_id,
                user_message=user_message,
                intent_kind=intent.primaryIntent,
                domain_profile_ids=domain_ids,
                creative_stage=stage,
                creative_substate=substate,
            )
            specialist_ids = [getattr(item, "specialistId", "") for item in findings if getattr(item, "specialistId", "")]
            if not findings:
                err = CoDirectorError(
                    CONTEXT_INCOMPLETE,
                    "No foundation specialists could be selected for this request.",
                    details={"intent": intent.primaryIntent},
                    recoverable=True,
                )
                yield {"type": "error", "requestId": request_id, "error": err.to_dict()}
                return
        else:
            yield {
                "type": "intelligence_progress",
                "requestId": request_id,
                "stage": "selecting_specialists",
                "message": "Selecting production specialists",
                "intent": intent.model_dump(mode="json"),
            }
            # Phase 7 — RouteDecision-aware specialist selection
            if route_decision is not None:
                from .specialist_selector import SpecialistContext
                ctx = SpecialistContext(
                    route_decision=route_decision,
                    creator_goal=getattr(conversation_plan or {}, "userGoalSummary", None) if conversation_plan else None,
                )
                selection = self.selector.select(ctx)
            else:
                # Fallback: legacy IntentKind-driven selection (preserved for backward compatibility)
                selection = self.selector.select(intent)
            specialist_ids = list(selection.all_selected)
            if not specialist_ids:
                err = CoDirectorError(
                    CONTEXT_INCOMPLETE,
                    "No specialists could be selected for this request.",
                    details={"intent": intent.primaryIntent},
                    recoverable=True,
                )
                yield {"type": "error", "requestId": request_id, "error": err.to_dict()}
                return

            yield {
                "type": "intelligence_progress",
                "requestId": request_id,
                "stage": "running_specialists",
                "message": "Reviewing project context",
                "specialists": list(specialist_ids),
            }
            findings, specialist_errors = await self.runner.run_all(
                db,
                project_id=project_id,
                user_message=user_message,
                specialist_ids=specialist_ids,
                scene_id=scene_id,
                provider=provider,
                model_id=model_id,
                request_id=request_id,
                use_provider=use_provider_effective,
                attachment_ids=attachment_ids,
                recent_messages=recent_messages,
                conversation_plan=conversation_plan,
            )
            if findings:
                package = await self.runner.context_compiler.compile(
                    db,
                    project_id=project_id,
                    user_message=user_message,
                    scene_id=scene_id,
                    specialists=[self.registry.require(sid) for sid in specialist_ids],
                    attachment_ids=attachment_ids,
                    recent_messages=recent_messages,
                    conversation_plan=conversation_plan,
                )
                for finding in findings:
                    IntelligenceStore.save_finding(
                        db,
                        project_id=project_id,
                        request_id=request_id,
                        finding=finding,
                        context_hash=package.contextHash,
                    )
            for err in specialist_errors:
                yield {"type": "error", "requestId": request_id, "error": err.to_dict()}

        yield {
            "type": "intelligence_progress",
            "requestId": request_id,
            "stage": "synthesizing",
            "message": "Preparing the shot",
        }

        try:
            synthesis = self.synthesis.synthesize(
                user_message=user_message,
                intent=intent,
                findings=findings,
            )
            if foundation_review is not None and foundation_review.prioritizedRecommendations:
                synthesis.recommendation = foundation_review.prioritizedRecommendations[0]
                if foundation_review.overloadRisk == "high":
                    synthesis.assumptions = list(synthesis.assumptions) + [
                        "Creative Director trimmed overlapping specialist advice to reduce overload."
                    ]
                if foundation_review.contradictions:
                    synthesis.conflictsResolved = list(
                        dict.fromkeys([*synthesis.conflictsResolved, *foundation_review.contradictions])
                    )
                # Keep creator-facing prose coherent; never dump specialist ids or confidence.
                if foundation_review.prioritizedRecommendations:
                    synthesis.userMessage = foundation_review.prioritizedRecommendations[0]
            if foundation_knowledge_refs:
                synthesis.structuredRecommendation = {
                    **(synthesis.structuredRecommendation or {}),
                    "knowledgeRefs": foundation_knowledge_refs[:8],
                }
        except Exception as exc:  # noqa: BLE001
            err = CoDirectorError(
                SYNTHESIS_FAILED,
                "Could not synthesize specialist findings.",
                details={"reason": str(exc)[:200]},
                recoverable=True,
            )
            yield {"type": "error", "requestId": request_id, "error": err.to_dict()}
            return

        if analysis_mode == LIMITED_ANALYSIS_MODE and "Limited-analysis" not in " ".join(
            synthesis.assumptions
        ):
            synthesis.assumptions = list(synthesis.assumptions) + [
                "Limited-analysis / heuristic path — provider unavailable or STUDIO_E2E; "
                "not deep story or emotional intelligence."
            ]

        yield {
            "type": "intelligence_result",
            "requestId": request_id,
            "synthesis": synthesis.model_dump(mode="json"),
            "promptVersions": prompt_versions,
            "analysisMode": analysis_mode,
        }

        yield {
            "type": "intelligence_progress",
            "requestId": request_id,
            "stage": "building_plan",
            "message": "Checking production requirements",
        }

        plan: ProductionPlan | None = None
        if intent.primaryIntent not in ("answer_question",):
            plan = self.plan_builder.build(
                project_id=project_id,
                intent=intent,
                synthesis=synthesis,
                prompt_versions=prompt_versions,
                request_id=request_id,
            )
            IntelligenceStore.save_plan(db, plan=plan)
            IntelligenceStore.save_synthesis(
                db,
                project_id=project_id,
                request_id=request_id,
                synthesis=synthesis,
                specialist_ids=specialist_ids,
                prompt_versions_json=prompt_versions,
                plan_id=plan.planId,
                model_id=model_id,
            )
            yield {
                "type": "intelligence_plan",
                "requestId": request_id,
                "plan": plan.model_dump(mode="json"),
            }

        if plan and not plan.blockers:
            yield {
                "type": "intelligence_progress",
                "requestId": request_id,
                "stage": "creating_proposals",
                "message": "Ready for approval",
            }
            try:
                proposals = await PlanExecutorBridge.create_proposals(
                    db,
                    project_id=project_id,
                    plan=plan,
                    scene_id=scene_id,
                    request_id=request_id,
                )
                for proposal in proposals:
                    yield {
                        "type": "intelligence_proposal",
                        "requestId": request_id,
                        "proposal": proposal.model_dump(mode="json"),
                    }
            except CoDirectorError as err:
                yield {"type": "error", "requestId": request_id, "error": err.to_dict()}

        yield {
            "type": "intelligence_progress",
            "requestId": request_id,
            "stage": "complete",
            "message": "Complete",
            "promptVersions": prompt_versions,
        }

        yield {
            "type": "completed",
            "requestId": request_id,
            "content": synthesis.userMessage,
            "responseType": synthesis.responseType,
            "structuredRecommendation": synthesis.structuredRecommendation,
        }
