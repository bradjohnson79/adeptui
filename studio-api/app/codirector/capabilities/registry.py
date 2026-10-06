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
    # Requires user approval via Approve/Refine queue (generation queue).
    NEEDS_APPROVAL = "needs_approval"


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
        tool_ids=("project.read_context",),
        surface_type="",
    ),
    CapabilityDefinition(
        id="story.read",
        title="Read Story",
        description="Read story entries and narrative context.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        tool_ids=("project.read_context",),
        surface_type="",
    ),
    CapabilityDefinition(
        id="story.refine",
        title="Refine Story",
        description="Propose a refinement to story content.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.NEEDS_CHOICE,
        required_context=("project", "story"),
        tool_ids=("propose_canon_record",),
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
        tool_ids=("script.estimate_timing",),
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
        tool_ids=("character.list", "list_character_profiles"),
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
        id="character.generate_visual_sheet",
        title="Generate Character Reference Sheet",
        description="Generate a Character Reference Sheet via Character Creator (AUTO, extras off).",
        handler_kind=HandlerKind.CAPABILITY_HANDLER,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project", "character"),
        optional_context=("visual_style", "visual_description"),
        tool_ids=("character_creator.propose_visual_sheet",),
        surface_type="character_sheet",
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
        title="Generate Production Still",
        description=(
            "Generate a production still via the Image Generator engine "
            "(prompt / refs / ERS / character-prop context). Not Scene Creator Standard UI."
        ),
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
        approval_policy=ApprovalPolicy.NEEDS_APPROVAL,
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
        id="film.send_to_magi",
        title="Send this scene to MAGI",
        description="Open MAGI only when the published scene picture is still current.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        optional_context=("scene",),
        tool_ids=("film_timeline.send_to_magi",),
        surface_type="",
    ),
    CapabilityDefinition(
        id="voice.creator",
        title="Open Voice Creator",
        description="Open Voice Creator to create or assign a character's default voice.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project", "character"),
        tool_ids=("character_creator.open_voice_creator",),
        surface_type="",
    ),
    CapabilityDefinition(
        id="voice.inspect",
        title="Inspect Voice",
        description="Read a character's active approved default voice without inventing one.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project", "character"),
        tool_ids=("character_creator.get_voice_status", "character_creator.get_voice_profile"),
        surface_type="",
    ),
    CapabilityDefinition(
        id="audio.open",
        title="Open Audio Studio",
        description="Open Audio Studio for music, sound effects, ambience, or project audio.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        tool_ids=("audio.open_studio",),
        surface_type="",
    ),
    CapabilityDefinition(
        id="audio.music",
        title="Create Music",
        description="Open Audio Studio Music or generate a score cue for the current project.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        tool_ids=("audio.generate_music", "audio.preview_music", "audio.open_studio"),
        surface_type="",
    ),
    CapabilityDefinition(
        id="audio.sfx",
        title="Create Sound Effects",
        description="Open Audio Studio Sound Effects or generate a one-shot effect.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        tool_ids=("audio.generate_sfx", "audio.preview_sfx", "audio.place", "audio.open_studio"),
        surface_type="",
    ),
    CapabilityDefinition(
        id="audio.ambience",
        title="Create Ambience",
        description="Open Audio Studio Ambience or generate a scene bed.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        tool_ids=("audio.generate_ambience", "audio.preview_ambience", "audio.open_studio"),
        surface_type="",
    ),
    CapabilityDefinition(
        id="voice.generate",
        title="Generate Voice",
        description="Generate voice audio for a character.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project", "character"),
        optional_context=("script_scene",),
        tool_ids=("voice_performance.generate_segments",),
        surface_type="voice_generation",
    ),
    CapabilityDefinition(
        id="voice.assign",
        title="Assign Voice",
        description="Approve a voice profile for a character.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.NEEDS_CHOICE,
        required_context=("project", "character", "voice_profile"),
        tool_ids=("voice.approve_take",),
        surface_type="",
    ),
    CapabilityDefinition(
        id="library.save",
        title="Save to Library",
        description="Classify or move an asset into the project Library folder map.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.NEEDS_CHOICE,
        required_context=("project", "asset"),
        tool_ids=("propose_asset_library_assignment",),
        surface_type="",
    ),
    CapabilityDefinition(
        id="timeline.add_asset",
        title="Add Asset to Timeline",
        description="Place a visual asset on the timeline (image/video clip). Audio uses timeline.add_audio.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project", "asset"),
        # ORDER19: prefer propose_add_image_clip; editor.place_asset secondary (visual branch in _place_asset).
        tool_ids=("timeline.propose_add_image_clip", "editor.place_asset"),
        surface_type="",
    ),
    CapabilityDefinition(
        # Intelligence mission 2026-09-19 (Phase 5): timed-prompt PLACEMENT is a
        # distinct operation from ADD ASSET and from prompt AUTHORING. This
        # capability maps to the EXISTING registered tool
        # `timeline.propose_add_prompt_segment` ("Add a Timed Instruction
        # (prompt segment) after approval", tools/definitions.py) — no
        # destination system is rewritten. Prompt AUTHORING (writing the text)
        # never routes here; it stays with the LLM.
        id="timeline.add_prompt_segment",
        title="Add Timed Prompt to Timeline",
        description="Place the timed prompt text on the timeline as an approved prompt segment (timed instruction).",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        optional_context=("scene",),
        tool_ids=("timeline.propose_add_prompt_segment",),
        surface_type="",
    ),
    CapabilityDefinition(
        id="timeline.attach_optional_reference",
        title="Attach Timeline Reference",
        description="Attach an optional visual/background reference to a timeline batch (approval-gated).",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.NEEDS_CHOICE,
        required_context=("project", "asset"),
        optional_context=("scene",),
        tool_ids=("timeline.attach_optional_reference",),
        surface_type="",
    ),
    CapabilityDefinition(
        id="timeline.add_audio",
        title="Add Audio to Timeline",
        description="Place approved audio or timed SFX onto the scene Timeline.",
        handler_kind=HandlerKind.CAPABILITY_HANDLER,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        optional_context=("scene", "asset"),
        tool_ids=("audio.place",),
        surface_type="",
    ),
    CapabilityDefinition(
        id="timeline.prepare",
        title="Prepare Timeline",
        description="Prepare timeline from storyboard panels.",
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.NEEDS_CHOICE,
        required_context=("project", "storyboard"),
        tool_ids=("script.prepare_timeline",),
        surface_type="",
    ),
    # --- Spatial Map + ERS + Scene Creator (frozen contracts) ---
    # Adept UI v1.1: Spatial Map creator flows are SHELVED (dormant, not deleted).
    # Do not advertise atlas.generate / atlas.assign as active creator recommendations.
    # Compatibility handlers remain registered; Co-Director routing gates execution.
    CapabilityDefinition(
        id="atlas.generate",
        title="Generate Atlas Shot (shelved v1.1)",
        description=(
            "DORMANT in Adept UI v1.1 — Spatial Map is not an active creator flow. "
            "Do not recommend or open Spatial Map. For environments/ERS use Environment Creator Express. "
            "Tool retained for compatibility only."
        ),
        handler_kind=HandlerKind.CAPABILITY_HANDLER,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        optional_context=("visual_style", "scene_context"),
        surface_type="atlas_shot_generation",
    ),
    CapabilityDefinition(
        id="atlas.assign",
        title="Use Existing Spatial Map (shelved v1.1)",
        description=(
            "DORMANT in Adept UI v1.1 — Spatial Map is not an active creator flow. "
            "Do not recommend opening Spatial Map. Existing Spatial Map project data is preserved. "
            "Retained for compatibility only."
        ),
        handler_kind=HandlerKind.CAPABILITY_HANDLER,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        optional_context=("asset", "scene_context"),
        surface_type="atlas_assign",
    ),
    CapabilityDefinition(
        id="environment.creator",
        title="Open Environment Creator Express",
        description=(
            "Open Environment Creator Express (contentTab scene_creator) for create-environment / ERS intents. "
            "Not Scene Creator Standard. Not Spatial Map."
        ),
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        tool_ids=("workspace.open_scene_creator",),
        surface_type="environment_creator",
    ),
    CapabilityDefinition(
        id="ers.generate",
        title="Generate Environment Reference Sheet",
        description=(
            "Generate an Environment Reference Sheet using GPT Image 2 API only. "
            "Spatial Map is optional enrichment (shelved in Adept UI v1.1); ERS is the environment authority. "
            "Do not fail-closed when spatialMapId is missing. Qwen local is not used for ERS."
        ),
        handler_kind=HandlerKind.CAPABILITY_HANDLER,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        optional_context=("spatial_map", "reference_image", "source_asset", "visual_style", "name", "description"),
        surface_type="ers_generation",
    ),
    CapabilityDefinition(
        id="ers.repair",
        title="Repair Environment Reference Sheet",
        description=(
            "Repair or regenerate an existing Environment Reference Sheet. "
            "Spatial Map is not required. Preserves approved views unless the creator asks for a wider rebuild."
        ),
        handler_kind=HandlerKind.CAPABILITY_HANDLER,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        optional_context=("spatial_map", "reference_image", "source_asset", "visual_style", "name", "description"),
        surface_type="ers_generation",
    ),
    CapabilityDefinition(
        id="ers.edit",
        title="Edit Environment Reference Sheet",
        description=(
            "Edit an existing Environment Reference Sheet (masked inpaint / region edit). "
            "Creates a NEW draft ERS version from the derivative. Does NOT auto-approve; "
            "creator Approve is required before the version becomes downstream canonical."
        ),
        handler_kind=HandlerKind.CAPABILITY_HANDLER,
        approval_policy=ApprovalPolicy.NEEDS_APPROVAL,
        required_context=("project",),
        optional_context=("reference_image", "source_asset", "mask", "visual_style", "name", "description"),
        surface_type="ers_edit",
    ),
    CapabilityDefinition(
        id="image.generator",
        title="Open Image Generator",
        description=(
            "Open the Cinematic Image Generator (workspace imagegen) for production stills. "
            "Not Scene Creator Standard. Not Environment Creator Express."
        ),
        handler_kind=HandlerKind.TOOL,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        tool_ids=("workspace.open_image_generator",),
        surface_type="image_generator",
    ),
    CapabilityDefinition(
        id="scene.generate",
        title="Generate Production Stills",
        description=(
            "Generate production stills via the Image Generator engine path "
            "(prompt / refs / ERS / character-prop context). Not Scene Creator Standard UI. "
            "Prefer image.generate / image.generator for creator still intents in v1.1."
        ),
        handler_kind=HandlerKind.CAPABILITY_HANDLER,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        optional_context=("ers_package", "character", "reference_image", "visual_style"),
        surface_type="scene_generation",
    ),

    CapabilityDefinition(
        id="video.generate",
        title="Generate Video",
        description="Standalone Co-Director video. Timeline R2V stays on Timeline.",
        handler_kind=HandlerKind.CAPABILITY_HANDLER,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        optional_context=("reference_image", "visual_style", "script_scene"),
        surface_type="video_generation",
    ),
    CapabilityDefinition(
        id="timeline.deposit_video",
        title="Deposit Completed Video to Timeline Visual",
        description="Deposit a completed 1F/3F Library video onto Timeline Visual (mediaType=video). No regenerate.",
        handler_kind=HandlerKind.CAPABILITY_HANDLER,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        optional_context=("scene", "asset"),
        tool_ids=("omni.deposit_video_to_timeline",),
        surface_type="timeline_deposit",
    ),
    CapabilityDefinition(
        id="timeline.prepare_scene",
        title="Prepare Timeline Scene",
        description="Parse a natural-language scene request, bind references, compile a generator prompt, and create a Timeline shot. Does not start generation.",
        handler_kind=HandlerKind.CAPABILITY_HANDLER,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        optional_context=("script_scene",),
        surface_type="timeline_production",
    ),
    CapabilityDefinition(
        id="timeline.generate_shot",
        title="Generate Timeline Shot",
        description="Generate an existing Timeline shot through the shared Timeline generate service.",
        handler_kind=HandlerKind.CAPABILITY_HANDLER,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        optional_context=("script_scene",),
        surface_type="timeline_production",
    ),
    CapabilityDefinition(
        id="analyze.video",
        title="Review Timeline Video",
        description="Watch and hear a Timeline clip through Media Intelligence. Returns a timestamped packet — does not place audio.",
        handler_kind=HandlerKind.CAPABILITY_HANDLER,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project",),
        optional_context=("scene", "asset"),
        surface_type="media_intelligence",
    ),
    CapabilityDefinition(
        id="timeline.extend",
        title="Review & Extend",
        description="Review the current Timeline scene and continue it with the next legal H3 segment.",
        handler_kind=HandlerKind.CAPABILITY_HANDLER,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project", "scene"),
        surface_type="timeline_extend",
    ),
    CapabilityDefinition(
        id="timeline.reorder",
        title="Reorder Timeline Clips",
        description="Move a Visual Track clip earlier, later, or beside another shot. Uses the Timeline composition order.",
        handler_kind=HandlerKind.CAPABILITY_HANDLER,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project", "scene"),
        surface_type="timeline_reorder",
    ),
    CapabilityDefinition(
        id="timeline.stitch",
        title="Stitch Timeline Scene",
        description="Assemble the current Visual Track with the Timeline stitch service.",
        handler_kind=HandlerKind.CAPABILITY_HANDLER,
        approval_policy=ApprovalPolicy.DIRECT,
        required_context=("project", "scene"),
        surface_type="timeline_stitch",
    ),
)


# Index for fast lookup.
_BY_ID: dict[str, CapabilityDefinition] = {c.id: c for c in CAPABILITY_REGISTRY}
_ALIASES = {
    "create_character_reference_sheet": "character.generate_visual_sheet",
}


def get_capability(capability_id: str) -> Optional[CapabilityDefinition]:
    """Resolve a capability by its ID."""
    if not capability_id:
        return None
    return _BY_ID.get(capability_id) or _BY_ID.get(_ALIASES.get(capability_id, ""))


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


def capability_live_destination(cap: CapabilityDefinition) -> str:
    """Return the reachable handler module or tool id for an advertised capability.

    Empty string means the capability is advertised but cannot execute.
    """
    if cap.handler_kind == HandlerKind.CAPABILITY_HANDLER:
        return f"app.codirector.capabilities.handlers.{cap.id.replace('.', '_')}"
    if cap.handler_kind == HandlerKind.TOOL:
        return cap.tool_ids[0] if cap.tool_ids else ""
    if cap.handler_kind == HandlerKind.PRODUCTION_INTENT:
        return cap.id
    return ""
