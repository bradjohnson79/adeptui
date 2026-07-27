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

        yield {
            "type": "intelligence_progress",
            "requestId": request_id,
            "stage": "selecting_specialists",
            "message": "Selecting production specialists",
            "intent": intent.model_dump(mode="json"),
        }
        selection = self.selector.select(intent)
        specialist_ids = selection.all_selected
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
        )
        context_hash = ""
        if findings:
            package = await self.runner.context_compiler.compile(
                db,
                project_id=project_id,
                user_message=user_message,
                scene_id=scene_id,
                specialists=[self.registry.require(sid) for sid in specialist_ids],
            )
            context_hash = package.contextHash
            for finding in findings:
                IntelligenceStore.save_finding(
                    db,
                    project_id=project_id,
                    request_id=request_id,
                    finding=finding,
                    context_hash=context_hash,
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
