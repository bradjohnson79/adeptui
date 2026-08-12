"""Authoritative Co-Director pipeline stage contracts (foreground vs background)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ExecutionClass = Literal["FOREGROUND_REQUIRED", "FOREGROUND_OPTIONAL", "BACKGROUND"]
FailurePolicy = Literal[
    "FAIL_REQUEST",
    "CONTINUE_WITH_PARTIAL_CONTEXT",
    "RETRY_BACKGROUND",
    "DEFER",
]


class CoDirectorPipelineStageContract(BaseModel):
    stageId: str
    name: str
    executionClass: ExecutionClass
    requiredForModes: list[str] = Field(default_factory=lambda: ["chat"])
    latencyBudgetMs: int | None = None
    dependencies: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    failurePolicy: FailurePolicy = "CONTINUE_WITH_PARTIAL_CONTEXT"
    observable: bool = True


PIPELINE_STAGES: list[CoDirectorPipelineStageContract] = [
    CoDirectorPipelineStageContract(
        stageId="RECEIVING",
        name="Request receipt",
        executionClass="FOREGROUND_REQUIRED",
        latencyBudgetMs=250,
        outputs=["requestId"],
        failurePolicy="FAIL_REQUEST",
    ),
    CoDirectorPipelineStageContract(
        stageId="CLASSIFYING_INTENT",
        name="Intent and complexity classification",
        executionClass="FOREGROUND_REQUIRED",
        latencyBudgetMs=500,
        dependencies=["RECEIVING"],
        outputs=["intent", "complexity", "budget"],
    ),
    CoDirectorPipelineStageContract(
        stageId="RELATIONSHIP_LOAD",
        name="Relationship and ownership retrieval",
        executionClass="FOREGROUND_REQUIRED",
        latencyBudgetMs=300,
        dependencies=["CLASSIFYING_INTENT"],
        outputs=["relationship", "ownership"],
    ),
    CoDirectorPipelineStageContract(
        stageId="MOMENTUM_READ",
        name="Creative momentum and confidence read",
        executionClass="FOREGROUND_OPTIONAL",
        latencyBudgetMs=200,
        dependencies=["RELATIONSHIP_LOAD"],
        outputs=["momentum", "confidence"],
        failurePolicy="CONTINUE_WITH_PARTIAL_CONTEXT",
    ),
    CoDirectorPipelineStageContract(
        stageId="READING_PROJECT_CACHE",
        name="Project-cache retrieval",
        executionClass="FOREGROUND_REQUIRED",
        latencyBudgetMs=300,
        dependencies=["MOMENTUM_READ"],
        outputs=["projectCache", "cacheHit"],
    ),
    CoDirectorPipelineStageContract(
        stageId="BOUNDED_RETRIEVAL",
        name="Targeted context retrieval",
        executionClass="FOREGROUND_OPTIONAL",
        latencyBudgetMs=1500,
        dependencies=["READING_PROJECT_CACHE"],
        outputs=["contextPackage"],
        failurePolicy="CONTINUE_WITH_PARTIAL_CONTEXT",
    ),
    CoDirectorPipelineStageContract(
        stageId="SPECIALIST_SELECTION",
        name="Specialist selection",
        executionClass="FOREGROUND_OPTIONAL",
        latencyBudgetMs=200,
        dependencies=["CLASSIFYING_INTENT"],
        outputs=["specialistDecisions"],
        failurePolicy="DEFER",
    ),
    CoDirectorPipelineStageContract(
        stageId="ASSEMBLING_PROMPT",
        name="Prompt assembly",
        executionClass="FOREGROUND_REQUIRED",
        latencyBudgetMs=500,
        dependencies=["BOUNDED_RETRIEVAL"],
        outputs=["generationMessages", "tokenBuckets"],
    ),
    CoDirectorPipelineStageContract(
        stageId="WAITING_FOR_MODEL",
        name="Provider dispatch",
        executionClass="FOREGROUND_REQUIRED",
        latencyBudgetMs=1000,
        dependencies=["ASSEMBLING_PROMPT"],
        outputs=["providerConnected"],
        failurePolicy="FAIL_REQUEST",
    ),
    CoDirectorPipelineStageContract(
        stageId="STREAMING_RESPONSE",
        name="Token streaming",
        executionClass="FOREGROUND_REQUIRED",
        latencyBudgetMs=20000,
        dependencies=["WAITING_FOR_MODEL"],
        outputs=["tokens", "reply"],
        failurePolicy="FAIL_REQUEST",
    ),
    CoDirectorPipelineStageContract(
        stageId="GROUNDING",
        name="Fast response grounding",
        executionClass="FOREGROUND_REQUIRED",
        latencyBudgetMs=500,
        dependencies=["STREAMING_RESPONSE"],
        outputs=["groundingOk"],
    ),
    CoDirectorPipelineStageContract(
        stageId="PERSIST_CONVERSATION",
        name="Conversation persistence",
        executionClass="FOREGROUND_REQUIRED",
        latencyBudgetMs=800,
        dependencies=["GROUNDING"],
        outputs=["messageId"],
    ),
    CoDirectorPipelineStageContract(
        stageId="NEXT_STEP_OPTIONS",
        name="Contextual next-step options",
        executionClass="FOREGROUND_OPTIONAL",
        latencyBudgetMs=400,
        dependencies=["STREAMING_RESPONSE"],
        outputs=["nextStepOptions"],
        failurePolicy="DEFER",
    ),
    CoDirectorPipelineStageContract(
        stageId="COMPLETE",
        name="Response complete",
        executionClass="FOREGROUND_REQUIRED",
        dependencies=["PERSIST_CONVERSATION"],
        outputs=["completed"],
    ),
    CoDirectorPipelineStageContract(
        stageId="UPDATING_WIKI",
        name="Wiki extract persist read-back",
        executionClass="BACKGROUND",
        latencyBudgetMs=15000,
        dependencies=["STREAMING_RESPONSE"],
        outputs=["wikiResult"],
        failurePolicy="RETRY_BACKGROUND",
    ),
    CoDirectorPipelineStageContract(
        stageId="MOMENTUM_UPDATE",
        name="Creative momentum update",
        executionClass="BACKGROUND",
        latencyBudgetMs=2000,
        dependencies=["STREAMING_RESPONSE"],
        outputs=["momentum"],
        failurePolicy="RETRY_BACKGROUND",
    ),
    CoDirectorPipelineStageContract(
        stageId="CONFIDENCE_UPDATE",
        name="Creative confidence update",
        executionClass="BACKGROUND",
        latencyBudgetMs=2000,
        dependencies=["STREAMING_RESPONSE"],
        outputs=["confidence"],
        failurePolicy="RETRY_BACKGROUND",
    ),
    CoDirectorPipelineStageContract(
        stageId="CACHE_REVISION",
        name="Project cache revision",
        executionClass="BACKGROUND",
        latencyBudgetMs=1000,
        dependencies=["UPDATING_WIKI"],
        outputs=["projectCache"],
        failurePolicy="RETRY_BACKGROUND",
    ),
]


def stage_by_id(stage_id: str) -> CoDirectorPipelineStageContract | None:
    for stage in PIPELINE_STAGES:
        if stage.stageId == stage_id:
            return stage
    return None


def pipeline_manifest_dict() -> dict:
    return {
        "version": 1,
        "stages": [s.model_dump(mode="json") for s in PIPELINE_STAGES],
    }
