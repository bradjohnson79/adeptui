"""Co-Director Capability Registry — the authoritative map from capability to handler.

Spec §9: "Create/reuse one authoritative Co-Director capability registry."
Spec §10: "Avoid sending the entire raw API universe into the language model."

Each `CapabilityDefinition` maps a high-level capability (e.g. `image.generate`,
`storyboard.generate`) to its handler kind, required context, approval policy,
and the underlying tool IDs that implement it. The dispatcher reads this
registry to resolve what to execute.

The `ApprovalPolicy` encodes spec §50:
- DIRECT: can execute immediately (image.generate, storyboard.generate, analysis)
- NEEDS_CHOICE: requires explicit user choice (approve casting image, approve voice)
- NEEDS_CONFIRMATION: destructive operations (delete reference, replace locked)

FROZEN CONTRACT — Law #16. Do not change capability IDs without primary approval.
New capabilities can be added, but existing IDs are stable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ApprovalPolicy(str, Enum):
    """Spec §50 — human approval law."""

    # Can execute directly without user approval.
    DIRECT = "direct"
    # Requires explicit user choice (casting image, voice identity).
    NEEDS_CHOICE = "needs_choice"
    # Destructive — requires explicit confirmation.
    NEEDS_CONFIRMATION = "needs_confirmation"


class HandlerKind(str, Enum):
    """Where the capability handler lives."""

    # New execution handler in capabilities/handlers/
    CAPABILITY_HANDLER = "capability_handler"
    # Existing tool in the tool registry
    TOOL = "tool"
    # Existing production_intent operation
    PRODUCTION_INTENT = "production_intent"


@dataclass(frozen=True)
class CapabilityDefinition:
    """One high-level Co-Director capability.

    `tool_ids` lists the underlying tool IDs from the tool registry that
    implement this capability. The dispatcher uses the first applicable one.
    For `handler_kind == CAPABILITY_HANDLER`, the handler module/function is
    resolved by convention: `capabilities/handlers/{capability.replace('.', '_')}.py`.
    """

    id: str
    title: str
    description: str
    handler_kind: HandlerKind = HandlerKind.CAPABILITY_HANDLER
    approval_policy: ApprovalPolicy = ApprovalPolicy.DIRECT
    required_context: tuple[str, ...] = ()
    optional_context: tuple[str, ...] = ()
    tool_ids: tuple[str, ...] = ()
    # Surface type for the Live Agent Work Surface (spec §19).
    surface_type: str = ""


# The authoritative registry. ~20 capabilities from spec §9.
CAPABILITY_REGISTRY: tuple[CapabilityDefinition, ...] = (
    CapabilityDefinition(
        id="project.context.read",
        title="Read Project Context",
        description="Retrieve project context for analysis (story, script, characters, foundation).",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        tool_ids=("project_context.read",),
        surface_type="",
    ),
    CapabilityDefinition(
        id="story.read",
        title="Read Story",
        description="Read story entries and narrative context.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        tool_ids=("story.read",),
        surface_type="",
    ),
    CapabilityDefinition(
        id="story.refine",
        title="Refine Story",
        description="Propose a refinement to story content.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.NEEDS_CHOICE,
        required_context=("project", "story"),
        tool_ids=("story.propose_edit",),
        surface_type="script_operation",
    ),
    CapabilityDefinition(
        id="script.read",
        title="Read Script",
        description="Read script elements and scene structure.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        tool_ids=("script.inspect",),
        surface_type="",
    ),
    CapabilityDefinition(
        id="script.time",
        title="Time Script",
        description="Estimate script runtime and scene timing.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project", "script"),
        tool_ids=("script.timing",),
        surface_type="",
    ),
    CapabilityDefinition(
        id="script.propose_edit",
        title="Propose Script Edit",
        description="Propose a script edit for user approval.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.NEEDS_CHOICE,
        required_context=("project", "script"),
        tool_ids=("script.propose_insert", "script.propose_replace", "script.propose_delete"),
        surface_type="script_operation",
    ),
    CapabilityDefinition(
        id="character.read",
        title="Read Character",
        description="Read character profile and references.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project", "character"),
        tool_ids=("character.list_profiles", "character.inspect_profile"),
        surface_type="",
    ),
    CapabilityDefinition(
        id="character.generate_candidates",
        title="Generate Character Candidates",
        description="Generate N visual candidate images for a character.",
        handler_kind=HandlerKind.CAPABILITY_HANDLER,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project", "character"),
        optional_context=("visual_style", "visual_description", "reference_image"),
        surface_type="casting_candidates",
    ),
    CapabilityDefinition(
        id="character.assign_reference",
        title="Assign Character Reference",
        description="Approve a candidate as the canonical casting image.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.NEEDS_CHOICE,
        required_context=("project", "character", "asset"),
        tool_ids=("character.approve_candidate",),
        surface_type="",
    ),
    CapabilityDefinition(
        id="image.generate",
        title="Generate Image",
        description="Generate a single image from a prompt with optional character references.",
        handler_kind=HandlerKind.CAPABILITY_HANDLER,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        optional_context=("character", "reference_image", "visual_style", "script_scene"),
        surface_type="image_generation",
    ),
    CapabilityDefinition(
        id="image.edit",
        title="Edit Image",
        description="Edit an existing image (inpaint, outpaint, ref-edit).",
        handler_kind=HandlerKind.CAPABILITY_HANDLER,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project", "source_asset"),
        optional_context=("character", "reference_image", "mask"),
        surface_type="image_generation",
    ),
    CapabilityDefinition(
        id="image.generate_batch",
        title="Generate Image Batch",
        description="Generate N images as a batch with variation.",
        handler_kind=HandlerKind.CAPABILITY_HANDLER,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        optional_context=("character", "reference_image", "visual_style"),
        surface_type="image_generation",
    ),
    CapabilityDefinition(
        id="storyboard.generate",
        title="Generate Storyboard",
        description="Plan N distinct shots and generate N storyboard frame images.",
        handler_kind=HandlerKind.CAPABILITY_HANDLER,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        optional_context=("script_scene", "character", "reference_image", "visual_style", "story"),
        surface_type="storyboard_generation",
    ),
    CapabilityDefinition(
        id="storyboard.regenerate_frame",
        title="Regenerate Storyboard Frame",
        description="Regenerate a single frame of an existing storyboard, keeping others intact.",
        handler_kind=HandlerKind.CAPABILITY_HANDLER,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project", "execution", "frame_index"),
        surface_type="storyboard_generation",
    ),
    CapabilityDefinition(
        id="voice.generate",
        title="Generate Voice",
        description="Generate voice audio for a character.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project", "character"),
        optional_context=("script_scene",),
        tool_ids=("voice.generate_segments",),
        surface_type="voice_generation",
    ),
    CapabilityDefinition(
        id="voice.assign",
        title="Assign Voice",
        description="Approve a voice profile for a character.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.NEEDS_CHOICE,
        required_context=("project", "character", "voice_profile"),
        tool_ids=("voice.approve",),
        surface_type="",
    ),
    CapabilityDefinition(
        id="library.save",
        title="Save to Library",
        description="Save an asset to the project Library.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project", "asset"),
        tool_ids=("library.save_asset",),
        surface_type="",
    ),
    CapabilityDefinition(
        id="library.group",
        title="Create Library Collection",
        description="Create a named collection grouping of assets.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project", "assets"),
        tool_ids=("library.create_collection",),
        surface_type="",
    ),
    CapabilityDefinition(
        id="library.assign",
        title="Assign to Collection",
        description="Add assets to an existing collection.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project", "collection", "assets"),
        tool_ids=("library.add_to_collection",),
        surface_type="",
    ),
    CapabilityDefinition(
        id="timeline.add_asset",
        title="Add Asset to Timeline",
        description="Place a visual asset on the timeline.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project", "asset"),
        tool_ids=("editor.place_asset",),
        surface_type="",
    ),
    CapabilityDefinition(
        id="timeline.add_audio",
        title="Add Audio to Timeline",
        description="Place an audio asset on the timeline.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project", "asset"),
        tool_ids=("audio.place_on_timeline",),
        surface_type="",
    ),
    CapabilityDefinition(
        id="timeline.prepare",
        title="Prepare Timeline",
        description="Prepare timeline from storyboard panels.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.NEEDS_CHOICE,
        required_context=("project", "storyboard"),
        tool_ids=("storyboard.prepare_timeline",),
        surface_type="",
    ),
    # --- Spatial Map + ERS + Scene Creator (frozen contracts) ---
    CapabilityDefinition(
        id="atlas.generate",
        title="Generate Atlas Shot",
        description="Generate a roofless top-down environment reference for Spatial Map.",
        handler_kind=HandlerKind.CAPABILITY_HANDLER,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        optional_context=("visual_style", "scene_context"),
        surface_type="atlas_shot_generation",
    ),
    CapabilityDefinition(
        id="ers.generate",
        title="Generate Environment Reference Sheet",
        description="Generate directional N/E/S/W views from a spatial map, then assemble the ERS sheet programmatically.",
        handler_kind=HandlerKind.CAPABILITY_HANDLER,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project", "spatial_map"),
        surface_type="ers_generation",
    ),
    CapabilityDefinition(
        id="scene.generate",
        title="Generate Scene Images",
        description="Generate N scene images from shot requests + ERS + character/prop references.",
        handler_kind=HandlerKind.CAPABILITY_HANDLER,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        optional_context=("ers_package", "character", "reference_image", "visual_style"),
        surface_type="scene_generation",
    ),
)


# Index for fast lookup.
_BY_ID: dict[str, CapabilityDefinition] = {c.id: c for c in CAPABILITY_REGISTRY}


def get_capability(capability_id: str) -> Optional[CapabilityDefinition]:
    """Resolve a capability by its ID."""
    return _BY_ID.get(capability_id)


def all_capabilities() -> tuple[CapabilityDefinition, ...]:
    """Return all registered capabilities."""
    return CAPABILITY_REGISTRY


def requires_approval(capability_id: str) -> bool:
    """Check if a capability requires user approval before executing."""
    cap = get_capability(capability_id)
    if cap is None:
        return True  # Unknown capability — safe default.
    return cap.approval_policy != ApprovalPolicy.DIRECT


def surface_type_for(capability_id: str) -> str:
    """Get the Live Agent Work Surface type for a capability."""
    cap = get_capability(capability_id)
    if cap is None:
        return ""
    return cap.surface_type
