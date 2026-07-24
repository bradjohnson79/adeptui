"""Pydantic contracts for the Production Bible and proposal/approval APIs."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

EntityType = Literal[
    "project_profile",
    "character",
    "location",
    "visual_style",
    "production_rule",
    "continuity_rule",
    "narrative_thread",
    "scene_fact",
    "prop",
    "organization",
]

ENTITY_TYPES: tuple[str, ...] = (
    "project_profile",
    "character",
    "location",
    "visual_style",
    "production_rule",
    "continuity_rule",
    "narrative_thread",
    "scene_fact",
    "prop",
    "organization",
)

# Read-path priority: what gets included first when the token budget is tight. Project-level
# identity/style facts ground every turn; scene_fact is the most granular/least universally
# relevant, so it's trimmed first under pressure.
ENTITY_TYPE_PRIORITY: tuple[str, ...] = (
    "project_profile",
    "visual_style",
    "character",
    "location",
    "continuity_rule",
    "production_rule",
    "narrative_thread",
    "organization",
    "prop",
    "scene_fact",
)

ProposalStatus = Literal[
    "pending",
    "approved",
    "rejected",
    "revision_requested",
    "executing",
    "completed",
    "failed",
    "cancelled",
    "stale",
]

ProposalType = Literal[
    "bible_create",
    "bible_update",
    "entity_create",
    "entity_update",
    "fact_add",
    # M2.2: the model asked to run a mutating registry tool. `ProposalOut.toolCall` carries the
    # server-owned payload; `payload` stays an empty BibleMutationSet for these.
    "tool_call",
]

BIBLE_PROPOSAL_TYPES: tuple[str, ...] = (
    "bible_create",
    "bible_update",
    "entity_create",
    "entity_update",
    "fact_add",
)

TOOL_CALL_PROPOSAL_TYPE = "tool_call"


class BibleEntity(BaseModel):
    entityType: EntityType
    entityKey: str
    displayName: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class BibleFact(BaseModel):
    entityKey: Optional[str] = None
    factType: str = "continuity"
    statement: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class BibleVersionSummary(BaseModel):
    versionNumber: int
    parentVersionId: Optional[str] = None
    summary: str = ""
    changeReason: str = ""
    createdBy: str = "user"
    createdAt: str


class BibleVersionDetail(BibleVersionSummary):
    id: str
    bibleId: str
    entities: list[BibleEntity] = Field(default_factory=list)
    facts: list[BibleFact] = Field(default_factory=list)


class ProductionBibleOut(BaseModel):
    projectId: str
    currentVersion: Optional[BibleVersionDetail] = None
    versionCount: int = 0


class EntityMutation(BaseModel):
    """One entity upsert or removal. `remove=True` drops the entity from the next version."""

    entityType: EntityType
    entityKey: str
    displayName: Optional[str] = None
    data: Optional[dict[str, Any]] = None
    remove: bool = False


class FactMutation(BaseModel):
    """One fact upsert or removal, addressed by `factId` for existing facts or newly added."""

    factId: Optional[str] = None
    entityKey: Optional[str] = None
    factType: str = "continuity"
    statement: str = ""
    data: Optional[dict[str, Any]] = None
    remove: bool = False


class BibleMutationSet(BaseModel):
    """The structured payload a proposal (or a manual edit) applies to produce a new version."""

    entityMutations: list[EntityMutation] = Field(default_factory=list)
    factMutations: list[FactMutation] = Field(default_factory=list)
    summary: str = ""
    changeReason: str = ""


class ImportPreviewRequest(BaseModel):
    includeScenes: bool = True
    includeAssetsAsProps: bool = True


class ImportPreviewResponse(BaseModel):
    projectId: str
    entities: list[BibleEntity]
    facts: list[BibleFact]
    summary: str
    warnings: list[str] = Field(default_factory=list)


class ImportConfirmRequest(BaseModel):
    entities: list[BibleEntity]
    facts: list[BibleFact] = Field(default_factory=list)
    summary: str = "Imported from project data"
    changeReason: str = "initial_import"


class CreateVersionRequest(BaseModel):
    """Manual, user-authored Bible edit (no proposal round-trip needed for direct edits)."""

    mutations: BibleMutationSet
    createdBy: str = "user"


class ProposalOut(BaseModel):
    """One durable proposal, of either flavour.

    Bible proposals populate `payload`; tool proposals populate `toolCall` and leave `payload`
    empty. Keeping both fields (rather than a union) means every existing Bible consumer — the
    proposal card's mutation list, the preview diff, the E2E specs — keeps reading exactly the
    field it read before M2.2, and the tool flavour is recognized by `toolCall` being present.
    """

    id: str
    projectId: str
    bibleId: Optional[str] = None
    basedOnVersionId: Optional[str] = None
    basedOnVersionNumber: Optional[int] = None
    proposalType: ProposalType
    title: str
    summary: str
    payload: BibleMutationSet
    toolCall: Optional[dict[str, Any]] = None
    status: ProposalStatus
    requestId: Optional[str] = None
    createdBy: str = "assistant"
    createdAt: str
    updatedAt: str
    isStale: bool = False


class ProposalPreview(BaseModel):
    proposal: ProposalOut
    currentVersionNumber: Optional[int]
    wouldCreateVersionNumber: Optional[int]
    entityDiff: list[dict[str, Any]] = Field(default_factory=list)
    factDiff: list[dict[str, Any]] = Field(default_factory=list)
    isStale: bool = False


class ApprovalDecisionRequest(BaseModel):
    note: Optional[str] = None
    decidedBy: str = "user"


class ApprovalOut(BaseModel):
    id: str
    proposalId: str
    decision: str
    note: str = ""
    decidedBy: str
    decidedAt: str


class ExecutionReceiptOut(BaseModel):
    id: str
    proposalId: str
    inputHash: str
    status: str
    resultingVersionId: Optional[str] = None
    resultingVersionNumber: Optional[int] = None
    error: Optional[dict[str, Any]] = None
    executedAt: str
    # M2.2: populated when the approved proposal ran a registry tool rather than applying a
    # Bible mutation set. A tool that happens to write the Bible still fills resultingVersion*.
    toolId: Optional[str] = None
    toolInvocationId: Optional[str] = None
    toolResult: Optional[dict[str, Any]] = None
    toolResultTruncated: bool = False


class ContextManifest(BaseModel):
    projectId: str
    bibleVersionId: Optional[str] = None
    bibleVersionNumber: Optional[int] = None
    includedEntityKeys: list[str] = Field(default_factory=list)
    includedFactIds: list[str] = Field(default_factory=list)
    tokenBudget: int = 0
    estimatedTokens: int = 0
    truncated: bool = False
