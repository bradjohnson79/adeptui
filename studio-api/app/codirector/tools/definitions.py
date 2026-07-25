"""Declarative tool definitions and the wire contracts around them.

A tool is data, not code: `ToolDefinition` describes what it is called, what arguments it
accepts, which capability it needs, and whether it reads or mutates. `registry.py` is the only
place that binds a definition to a handler function, so adding a tool can never accidentally
add a new execution path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

TOOL_SCHEMA_VERSION = 1

ToolKind = Literal["read", "mutating"]
ParamType = Literal["string", "integer", "number", "boolean"]

# Capability keys the registry knows about. Each maps to exactly one existing probe in
# `capabilities.py` — this list is not a readiness matrix, it is the set of preconditions the
# declared tools actually need.
CAPABILITY_KEYS: tuple[str, ...] = (
    "project",
    "bible",
    "provider",
    "comfyui",
    "references",
    "source_manager",
    "preview_engine",
    "vision",
)

# Hard ceiling on a serialized tool result, in characters. Individual tools may ask for less.
# A result over its budget is truncated (and signalled), never silently dropped.
DEFAULT_RESULT_CHAR_BUDGET = 4000


@dataclass(frozen=True)
class ToolParameter:
    name: str
    type: ParamType
    required: bool = False
    description: str = ""
    max_length: Optional[int] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    choices: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "type": self.type,
            "required": self.required,
            "description": self.description,
        }
        if self.max_length is not None:
            out["maxLength"] = self.max_length
        if self.minimum is not None:
            out["minimum"] = self.minimum
        if self.maximum is not None:
            out["maximum"] = self.maximum
        if self.choices:
            out["choices"] = list(self.choices)
        return out


@dataclass(frozen=True)
class ToolDefinition:
    tool_id: str
    kind: ToolKind
    title: str
    description: str
    parameters: tuple[ToolParameter, ...] = ()
    capability: str = "project"
    # Only meaningful for mutating tools: which resources this tool's proposal is pinned to.
    # "bible" | "scene" | "project" — used to build `baseResourceVersions`.
    pinned_resources: tuple[str, ...] = ()
    proposal_type: str = "tool_call"
    result_char_budget: int = DEFAULT_RESULT_CHAR_BUDGET
    schema_version: int = TOOL_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "toolId": self.tool_id,
            "toolSchemaVersion": self.schema_version,
            "kind": self.kind,
            "title": self.title,
            "description": self.description,
            "capability": self.capability,
            "parameters": [p.to_dict() for p in self.parameters],
            "requiresApproval": self.kind == "mutating",
            "pinnedResources": list(self.pinned_resources),
            "resultCharBudget": self.result_char_budget,
        }


# --------------------------------------------------------------------------
# Wire contracts
# --------------------------------------------------------------------------


class ToolPreview(BaseModel):
    """Human-reviewable description of what a mutating tool would do, computed server-side."""

    summary: str = ""
    lines: list[str] = Field(default_factory=list)
    resourceKind: Optional[str] = None
    resourceId: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


class ToolCallPayload(BaseModel):
    """The server-owned payload of a `tool_call` proposal.

    Every field is produced by the server at proposal time. The model contributes only the
    tool id and raw arguments, and even those are re-validated against the tool's declared
    schema before they are stored — the stored `arguments` are the sanitized ones, so approving
    a proposal can never replay something the registry would reject.
    """

    toolId: str
    toolSchemaVersion: int = TOOL_SCHEMA_VERSION
    arguments: dict[str, Any] = Field(default_factory=dict)
    capabilitySnapshot: dict[str, Any] = Field(default_factory=dict)
    preview: ToolPreview = Field(default_factory=ToolPreview)
    inputHash: str = ""
    baseResourceVersions: dict[str, Optional[str]] = Field(default_factory=dict)


class ToolInvocationOut(BaseModel):
    id: str
    projectId: str
    toolId: str
    toolSchemaVersion: int
    kind: ToolKind
    status: str  # succeeded | failed | blocked
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: Optional[dict[str, Any]] = None
    resultTruncated: bool = False
    resultHash: Optional[str] = None
    errorCode: Optional[str] = None
    errorMessage: Optional[str] = None
    proposalId: Optional[str] = None
    requestId: Optional[str] = None
    durationMs: int = 0
    createdBy: str = "assistant"
    createdAt: str = ""


class ToolAvailability(BaseModel):
    toolId: str
    available: bool
    capability: str
    capabilityStatus: str
    reason: Optional[str] = None
    errorCode: Optional[str] = None


class ToolReadRequest(BaseModel):
    toolId: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    sceneId: Optional[str] = None
    requestId: Optional[str] = None


class ToolProposalRequest(BaseModel):
    toolId: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    sceneId: Optional[str] = None
    requestId: Optional[str] = None
    createdBy: str = "user"


# --------------------------------------------------------------------------
# The registry contents. Read tools first, then mutating tools.
# --------------------------------------------------------------------------

_ENGINE_CHOICES = ("ltx", "wan", "auto", "fal_seedance", "fal_kling", "fal_veo", "fal_runway")

READ_TOOLS: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        tool_id="get_project_profile",
        kind="read",
        title="Get project profile",
        description="Identity and format settings for the current project (name, director, resolution, fps, default engine).",
        capability="project",
    ),
    ToolDefinition(
        tool_id="get_project_status",
        kind="read",
        title="Get project status",
        description="Scene/asset counts, render progress, active job count, and the project's derived status label.",
        capability="project",
    ),
    ToolDefinition(
        tool_id="list_scenes",
        kind="read",
        title="List scenes",
        description="Ordered list of this project's scenes with engine, duration, and whether each has a rendered output.",
        capability="project",
        parameters=(
            ToolParameter("limit", "integer", description="Maximum scenes to return.", minimum=1, maximum=100),
        ),
    ),
    ToolDefinition(
        tool_id="get_scene",
        kind="read",
        title="Get scene",
        description="Full detail for one scene in this project.",
        capability="project",
        parameters=(ToolParameter("sceneId", "string", required=True, max_length=64),),
    ),
    ToolDefinition(
        tool_id="get_active_scene",
        kind="read",
        title="Get active scene",
        description="The scene the user currently has selected, if any.",
        capability="project",
    ),
    ToolDefinition(
        tool_id="get_current_bible_version",
        kind="read",
        title="Get current Production Bible version",
        description="Version number, summary, and entity/fact counts for the Bible version in effect right now.",
        capability="bible",
    ),
    ToolDefinition(
        tool_id="get_bible_entity",
        kind="read",
        title="Get Production Bible entity",
        description="One entity (character, location, prop, rule…) from the current Bible version, by key.",
        capability="bible",
        parameters=(ToolParameter("entityKey", "string", required=True, max_length=160),),
    ),
    ToolDefinition(
        tool_id="list_bible_entities",
        kind="read",
        title="List Production Bible entities",
        description="Entities in the current Bible version, optionally filtered to one entity type.",
        capability="bible",
        parameters=(
            ToolParameter("entityType", "string", max_length=32),
            ToolParameter("limit", "integer", minimum=1, maximum=200),
        ),
    ),
    ToolDefinition(
        tool_id="get_relevant_bible_context",
        kind="read",
        title="Get relevant Bible context",
        description="The same bounded Bible excerpt Co-Director injects into chat context, with its manifest.",
        capability="bible",
        parameters=(
            ToolParameter("tokenBudget", "integer", description="Soft token budget for the excerpt.", minimum=100, maximum=4000),
        ),
    ),
    ToolDefinition(
        tool_id="get_production_bible_summary",
        kind="read",
        title="Get Production Bible summary",
        description="Project Bible health, entity counts, and conflict summary.",
        capability="bible",
    ),
    ToolDefinition(
        tool_id="get_scene_bible_context",
        kind="read",
        title="Get scene Bible context",
        description="Scene-scoped Bible context: appearances, wardrobe, canon, style overrides.",
        capability="bible",
        parameters=(ToolParameter("sceneId", "string", max_length=64),),
    ),
    ToolDefinition(
        tool_id="get_character_bible_context",
        kind="read",
        title="Get character Bible context",
        description="Full character context package by stableId.",
        capability="bible",
        parameters=(ToolParameter("stableId", "string", required=True, max_length=36),),
    ),
    ToolDefinition(
        tool_id="get_location_bible_context",
        kind="read",
        title="Get location Bible context",
        description="Full location context package by stableId.",
        capability="bible",
        parameters=(ToolParameter("stableId", "string", required=True, max_length=36),),
    ),
    ToolDefinition(
        tool_id="list_canon_records",
        kind="read",
        title="List canon records",
        description="All canon_record entities in the current Bible version.",
        capability="bible",
    ),
    ToolDefinition(
        tool_id="list_continuity_warnings",
        kind="read",
        title="List continuity warnings",
        description="Detected continuity conflicts and warnings.",
        capability="bible",
    ),
    ToolDefinition(
        tool_id="get_generation_reference_package",
        kind="read",
        title="Get generation reference package",
        description="Primary/supporting/negative references plus style and continuity constraints.",
        capability="bible",
        parameters=(ToolParameter("sceneId", "string", max_length=64),),
    ),
    ToolDefinition(
        tool_id="get_provider_health",
        kind="read",
        title="Get Co-Director provider health",
        description="Reachability and readiness of the local model provider backing Co-Director.",
        capability="provider",
    ),
    ToolDefinition(
        tool_id="get_selected_model",
        kind="read",
        title="Get selected model",
        description="Which local model Co-Director is currently configured to use, and whether it is installed.",
        capability="provider",
    ),
    ToolDefinition(
        tool_id="get_comfyui_health",
        kind="read",
        title="Get ComfyUI health",
        description="Whether the local ComfyUI render backend is reachable, plus its reported VRAM headroom.",
        capability="comfyui",
    ),
    ToolDefinition(
        tool_id="get_source_manager_status",
        kind="read",
        title="Get Source Manager status",
        description="Counts of registered model sources, verified sources, and component assignments.",
        capability="source_manager",
    ),
    ToolDefinition(
        tool_id="get_reference_capabilities",
        kind="read",
        title="Get visual reference capabilities",
        description="Whether Director visual references (Ingredients IC-LoRA) are usable for this project, and what blocks them.",
        capability="references",
    ),
    ToolDefinition(
        tool_id="get_engine_capabilities",
        kind="read",
        title="Get engine capabilities",
        description="Preview/streaming capabilities for a generation engine.",
        capability="preview_engine",
        parameters=(ToolParameter("engine", "string", choices=_ENGINE_CHOICES),),
    ),
    ToolDefinition(
        tool_id="vision_validation_status",
        kind="read",
        title="Vision validation status",
        description="Read vision validation session status for this project (M2.5).",
        capability="vision",
        parameters=(
            ToolParameter("sessionId", "string", max_length=64),
            ToolParameter("limit", "integer", minimum=1, maximum=100),
        ),
    ),
    ToolDefinition(
        tool_id="vision_validation_report",
        kind="read",
        title="Vision validation report",
        description="Read a persisted vision validation report by reportId or sessionId (M2.5).",
        capability="vision",
        parameters=(
            ToolParameter("reportId", "string", max_length=64),
            ToolParameter("sessionId", "string", max_length=64),
        ),
    ),
    ToolDefinition(
        tool_id="get_timeline_image",
        kind="read",
        title="Get timeline image",
        description="Resolve a timeline image by @ImageN tag or item id, including its active Reference Set metadata (M2.6).",
        capability="references",
        parameters=(
            ToolParameter("sceneId", "string", required=True, max_length=36),
            ToolParameter("displayTag", "string", max_length=32),
            ToolParameter("timelineItemId", "string", max_length=64),
        ),
    ),
    ToolDefinition(
        tool_id="list_timeline_images",
        kind="read",
        title="List timeline images",
        description="List scene timeline images with stable @ImageN tags and reference counts (M2.6).",
        capability="references",
        parameters=(ToolParameter("sceneId", "string", required=True, max_length=36),),
    ),
    ToolDefinition(
        tool_id="get_reference_set",
        kind="read",
        title="Get reference set",
        description="Read the active Reference Set for a timeline image item (M2.6).",
        capability="references",
        parameters=(
            ToolParameter("sceneId", "string", required=True, max_length=36),
            ToolParameter("timelineItemId", "string", required=True, max_length=64),
        ),
    ),
    ToolDefinition(
        tool_id="list_reference_bindings",
        kind="read",
        title="List reference bindings",
        description="List bindings in the active Reference Set for a timeline image (M2.6).",
        capability="references",
        parameters=(
            ToolParameter("sceneId", "string", required=True, max_length=36),
            ToolParameter("timelineItemId", "string", required=True, max_length=64),
        ),
    ),
    ToolDefinition(
        tool_id="build_generation_reference_package",
        kind="read",
        title="Build generation reference package",
        description="Build a provider-neutral reference package (primaryFrame + optional referenceSet) for a timeline image (M2.6).",
        capability="references",
        parameters=(
            ToolParameter("sceneId", "string", required=True, max_length=36),
            ToolParameter("timelineItemId", "string", required=True, max_length=64),
        ),
    ),
    ToolDefinition(
        tool_id="suggest_reference_bindings",
        kind="read",
        title="Suggest reference bindings",
        description="Suggest optional reference bindings for a timeline image without mutating state (M2.6).",
        capability="references",
        parameters=(
            ToolParameter("sceneId", "string", required=True, max_length=36),
            ToolParameter("timelineItemId", "string", required=True, max_length=64),
        ),
    ),
)

MUTATING_TOOLS: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        tool_id="create_scene",
        kind="mutating",
        title="Create a scene",
        description="Append a new scene to the end of this project's timeline.",
        capability="project",
        pinned_resources=("project",),
        parameters=(
            ToolParameter("name", "string", max_length=200),
            ToolParameter("prompt", "string", max_length=4000),
            ToolParameter("engine", "string", choices=_ENGINE_CHOICES),
            ToolParameter("durationSec", "number", minimum=0.5, maximum=120.0),
        ),
    ),
    ToolDefinition(
        tool_id="update_scene_title",
        kind="mutating",
        title="Rename a scene",
        description="Change one scene's title.",
        capability="project",
        pinned_resources=("scene",),
        parameters=(
            ToolParameter("sceneId", "string", required=True, max_length=64),
            ToolParameter("name", "string", required=True, max_length=200),
        ),
    ),
    ToolDefinition(
        tool_id="set_scene_prompt",
        kind="mutating",
        title="Set a scene's prompt",
        description="Replace one scene's motion prompt.",
        capability="project",
        pinned_resources=("scene",),
        parameters=(
            ToolParameter("sceneId", "string", required=True, max_length=64),
            ToolParameter("prompt", "string", required=True, max_length=4000),
        ),
    ),
    ToolDefinition(
        tool_id="record_director_decision",
        kind="mutating",
        title="Record a director decision",
        description=(
            "Write a durable director decision into the Production Bible as a continuity fact, "
            "so later turns and later scenes inherit it."
        ),
        capability="bible",
        pinned_resources=("bible",),
        parameters=(
            ToolParameter("decision", "string", required=True, max_length=1000),
            ToolParameter("rationale", "string", max_length=1000),
            ToolParameter("entityKey", "string", description="Bible entity this decision is about, if any.", max_length=160),
        ),
    ),
    ToolDefinition(
        tool_id="propose_character_update",
        kind="mutating",
        title="Propose character update",
        description="Propose an update to a character entity (requires approval).",
        capability="bible",
        pinned_resources=("bible",),
        parameters=(
            ToolParameter("stableId", "string", max_length=36),
            ToolParameter("entityKey", "string", max_length=160),
            ToolParameter("displayName", "string", max_length=200),
        ),
    ),
    ToolDefinition(
        tool_id="propose_canon_record",
        kind="mutating",
        title="Propose canon record",
        description="Propose a new canon record (requires approval).",
        capability="bible",
        pinned_resources=("bible",),
        parameters=(ToolParameter("claim", "string", required=True, max_length=1000),),
    ),
    ToolDefinition(
        tool_id="propose_canon_supersession",
        kind="mutating",
        title="Propose canon supersession",
        description="Propose a new canon record that supersedes an existing one.",
        capability="bible",
        pinned_resources=("bible",),
        parameters=(
            ToolParameter("claim", "string", required=True, max_length=1000),
            ToolParameter("supersedesStableId", "string", required=True, max_length=36),
        ),
    ),
    ToolDefinition(
        tool_id="propose_continuity_update",
        kind="mutating",
        title="Propose continuity update",
        description="Propose a continuity state update.",
        capability="bible",
        pinned_resources=("bible",),
        parameters=(ToolParameter("aspect", "string", max_length=32),),
    ),
    ToolDefinition(
        tool_id="propose_reference_link",
        kind="mutating",
        title="Propose reference link",
        description="Propose linking an asset reference to a Bible entity.",
        capability="bible",
        pinned_resources=("bible",),
        parameters=(
            ToolParameter("assetId", "string", required=True, max_length=36),
            ToolParameter("targetStableId", "string", required=True, max_length=36),
        ),
    ),
    ToolDefinition(
        tool_id="propose_production_decision",
        kind="mutating",
        title="Propose production decision",
        description="Propose a production decision entity.",
        capability="bible",
        pinned_resources=("bible",),
        parameters=(ToolParameter("decision", "string", required=True, max_length=1000),),
    ),
    ToolDefinition(
        tool_id="propose_visual_language_update",
        kind="mutating",
        title="Propose visual language update",
        description="Propose an update to the project's visual language.",
        capability="bible",
        pinned_resources=("bible",),
        parameters=(ToolParameter("description", "string", max_length=2000),),
    ),
    ToolDefinition(
        tool_id="propose_storyboard_generation",
        kind="mutating",
        title="Propose storyboard generation",
        description=(
            "Prepare a storyboard image generation package for the selected scene. "
            "Nothing renders until the user approves the proposal."
        ),
        capability="comfyui",
        pinned_resources=("scene", "bible"),
        parameters=(
            ToolParameter("sceneId", "string", required=True, max_length=64),
            ToolParameter("shotPurpose", "string", max_length=500),
            ToolParameter("prompt", "string", max_length=4000),
            ToolParameter("workflow", "string", max_length=120),
            ToolParameter("referencesReady", "boolean"),
        ),
    ),
    ToolDefinition(
        tool_id="propose_vision_correction",
        kind="mutating",
        title="Propose vision correction",
        description="Propose prompt/package corrections from a vision validation report (no auto-regenerate).",
        capability="vision",
        pinned_resources=("project",),
        parameters=(
            ToolParameter("sessionId", "string", required=True, max_length=64),
            ToolParameter("notes", "string", max_length=2000),
        ),
    ),
    ToolDefinition(
        tool_id="propose_asset_bible_link",
        kind="mutating",
        title="Propose asset Bible link",
        description="Propose linking a validated asset into the Production Bible (approval required).",
        capability="bible",
        pinned_resources=("bible",),
        parameters=(
            ToolParameter("sessionId", "string", required=True, max_length=64),
            ToolParameter("assetId", "string", max_length=64),
            ToolParameter("reportId", "string", max_length=64),
        ),
    ),
    ToolDefinition(
        tool_id="record_vision_review",
        kind="mutating",
        title="Record vision review",
        description="Record a human approve/reject decision for a vision validation session.",
        capability="vision",
        pinned_resources=("project",),
        parameters=(
            ToolParameter("sessionId", "string", required=True, max_length=64),
            ToolParameter(
                "decision",
                "string",
                required=True,
                choices=("approved", "rejected", "override_approve", "override_reject"),
            ),
            ToolParameter("notes", "string", max_length=2000),
            ToolParameter("linkToBible", "boolean"),
            ToolParameter("reviewer", "string", max_length=64),
        ),
    ),
    ToolDefinition(
        tool_id="create_reference_set_proposal",
        kind="mutating",
        title="Propose create reference binding",
        description="Propose adding the first/next binding on a timeline image Reference Set (M2.2 approval).",
        capability="references",
        pinned_resources=("timeline_reference_set",),
        parameters=(
            ToolParameter("sceneId", "string", required=True, max_length=36),
            ToolParameter("timelineItemId", "string", required=True, max_length=64),
            ToolParameter("referenceAssetId", "string", required=True, max_length=36),
            ToolParameter("role", "string", required=True, max_length=64),
            ToolParameter("influence", "string", max_length=32),
            ToolParameter("source", "string", max_length=64),
            ToolParameter("label", "string", max_length=200),
            ToolParameter("notes", "string", max_length=2000),
            ToolParameter("sourceTimelineItemId", "string", max_length=64),
        ),
    ),
    ToolDefinition(
        tool_id="propose_add_reference_binding",
        kind="mutating",
        title="Propose add reference binding",
        description="Propose adding a supporting reference binding to a timeline image (M2.2 approval).",
        capability="references",
        pinned_resources=("timeline_reference_set",),
        parameters=(
            ToolParameter("sceneId", "string", required=True, max_length=36),
            ToolParameter("timelineItemId", "string", required=True, max_length=64),
            ToolParameter("referenceAssetId", "string", required=True, max_length=36),
            ToolParameter("role", "string", required=True, max_length=64),
            ToolParameter("influence", "string", max_length=32),
            ToolParameter("source", "string", max_length=64),
            ToolParameter("label", "string", max_length=200),
            ToolParameter("notes", "string", max_length=2000),
            ToolParameter("sourceTimelineItemId", "string", max_length=64),
        ),
    ),
    ToolDefinition(
        tool_id="propose_remove_reference_binding",
        kind="mutating",
        title="Propose remove reference binding",
        description="Propose removing a binding from a timeline image Reference Set (M2.2 approval).",
        capability="references",
        pinned_resources=("timeline_reference_set",),
        parameters=(
            ToolParameter("sceneId", "string", required=True, max_length=36),
            ToolParameter("timelineItemId", "string", required=True, max_length=64),
            ToolParameter("bindingId", "string", required=True, max_length=36),
        ),
    ),
    ToolDefinition(
        tool_id="propose_update_reference_binding",
        kind="mutating",
        title="Propose update reference binding",
        description="Propose updating role/influence/notes on a reference binding (M2.2 approval).",
        capability="references",
        pinned_resources=("timeline_reference_set",),
        parameters=(
            ToolParameter("sceneId", "string", required=True, max_length=36),
            ToolParameter("timelineItemId", "string", required=True, max_length=64),
            ToolParameter("bindingId", "string", required=True, max_length=36),
            ToolParameter("role", "string", max_length=64),
            ToolParameter("influence", "string", max_length=32),
            ToolParameter("label", "string", max_length=200),
            ToolParameter("notes", "string", max_length=2000),
            ToolParameter("expectedVersion", "integer", minimum=0),
        ),
    ),
    ToolDefinition(
        tool_id="propose_apply_reference_preset",
        kind="mutating",
        title="Propose apply reference preset",
        description="Propose applying a project reference preset to a timeline image (M2.2 approval).",
        capability="references",
        pinned_resources=("timeline_reference_set",),
        parameters=(
            ToolParameter("sceneId", "string", required=True, max_length=36),
            ToolParameter("timelineItemId", "string", required=True, max_length=64),
            ToolParameter("presetId", "string", required=True, max_length=36),
            ToolParameter("mode", "string", choices=("replace", "merge")),
            ToolParameter("expectedVersion", "integer", minimum=0),
        ),
    ),

)

TOOL_DEFINITIONS: tuple[ToolDefinition, ...] = READ_TOOLS + MUTATING_TOOLS

TOOL_IDS: tuple[str, ...] = tuple(t.tool_id for t in TOOL_DEFINITIONS)


@dataclass
class ToolContext:
    """Everything a handler is allowed to see. Handlers get no other ambient state."""

    db: Any
    project_id: str
    scene_id: Optional[str] = None
    request_id: Optional[str] = None
    capabilities: dict[str, Any] = field(default_factory=dict)
