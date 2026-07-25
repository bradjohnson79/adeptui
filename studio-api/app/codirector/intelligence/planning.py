"""Production plan builder, validator, and M2.2 proposal bridge."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..errors import PLAN_INVALID, CoDirectorError
from ..tools import registry as tool_registry
from ..tools.execution import ToolExecutionService
from .schemas import IntentClassification, PlanStep, ProductionPlan, ProposedToolAction, SynthesisResult


class PlanBuilder:
    def build(
        self,
        *,
        project_id: str,
        intent: IntentClassification,
        synthesis: SynthesisResult,
        prompt_versions: dict[str, str],
        request_id: Optional[str] = None,
    ) -> ProductionPlan:
        steps: list[PlanStep] = []
        blockers = list(synthesis.blockers)

        if intent.playbookId:
            steps.append(
                PlanStep(
                    stepId="resolve-scope",
                    title="Resolve active scope",
                    description="Confirm project, scene, and intended shot scope.",
                    status="ready",
                    requiresApproval=False,
                )
            )
            steps.append(
                PlanStep(
                    stepId="compile-context",
                    title="Compile Production Bible context",
                    description="Gather bounded context for specialists and synthesis.",
                    status="ready",
                    requiresApproval=False,
                )
            )

        for index, action in enumerate(synthesis.proposedToolActions):
            definition = tool_registry.find(action.toolId)
            if definition is None:
                blockers.append(f"Unregistered tool '{action.toolId}' cannot be planned.")
                continue
            steps.append(
                PlanStep(
                    stepId=f"tool-{index + 1}",
                    title=definition.title,
                    description=action.purpose,
                    toolId=action.toolId,
                    capability=definition.capability,
                    requiresApproval=True,
                    status="blocked" if action.toolId == "propose_storyboard_generation" and blockers else "ready",
                    arguments=dict(action.arguments),
                    metadata={"requiresApproval": action.requiresApproval},
                )
            )

        if intent.primaryIntent == "create_storyboard" and not any(
            step.toolId == "propose_storyboard_generation" for step in steps
        ):
            steps.append(
                PlanStep(
                    stepId="storyboard-generation",
                    title="Propose storyboard generation",
                    description="Prepare storyboard image generation package for approval.",
                    toolId="propose_storyboard_generation",
                    capability="comfyui",
                    requiresApproval=True,
                    status="blocked" if blockers else "ready",
                    arguments={"sceneId": intent.targetSceneId},
                    metadata={"visualValidationPending": True},
                )
            )

        plan = ProductionPlan(
            planId=str(uuid.uuid4()),
            projectId=project_id,
            playbookId=intent.playbookId,
            title=self._title_for_intent(intent),
            summary=synthesis.recommendation,
            steps=steps,
            blockers=blockers,
            approvalRequired=any(step.requiresApproval for step in steps),
            visualValidationPending=intent.primaryIntent == "create_storyboard",
            promptVersions=prompt_versions,
            requestId=request_id,
        )
        PlanValidator.validate(plan)
        return plan

    @staticmethod
    def _title_for_intent(intent: IntentClassification) -> str:
        mapping = {
            "create_storyboard": "Storyboard Shot Plan",
            "revise_dialogue": "Dialogue Revision Plan",
            "plan_scene": "Scene Planning",
            "design_location": "Location Design Plan",
            "prepare_image_generation": "Image Generation Plan",
            "prepare_video_generation": "Video Generation Plan",
        }
        return mapping.get(intent.primaryIntent, "Production Plan")


class PlanValidator:
    @staticmethod
    def validate(plan: ProductionPlan) -> None:
        if not plan.planId or not plan.projectId:
            raise CoDirectorError(
                PLAN_INVALID,
                "Production plan is missing required identifiers.",
                recoverable=False,
            )
        for step in plan.steps:
            if step.toolId is None:
                continue
            definition = tool_registry.find(step.toolId)
            if definition is None:
                raise CoDirectorError(
                    PLAN_INVALID,
                    f"Plan references unregistered tool '{step.toolId}'.",
                    details={"toolId": step.toolId, "planId": plan.planId},
                    recoverable=False,
                )
            if definition.kind != "mutating":
                raise CoDirectorError(
                    PLAN_INVALID,
                    f"Plan step must reference a mutating tool, not '{step.toolId}'.",
                    details={"toolId": step.toolId},
                    recoverable=False,
                )


class PlanExecutorBridge:
    @staticmethod
    async def create_proposals(
        db: Session,
        *,
        project_id: str,
        plan: ProductionPlan,
        scene_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> list[Any]:
        proposals = []
        for step in plan.steps:
            if not step.toolId or not step.requiresApproval or step.status == "blocked":
                continue
            proposal = await ToolExecutionService.propose(
                db,
                project_id=project_id,
                tool_id=step.toolId,
                arguments=step.arguments,
                scene_id=scene_id,
                request_id=request_id,
                created_by="assistant",
            )
            proposals.append(proposal)
        return proposals
