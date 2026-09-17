"""Deterministic classifier for the Co-Director 2.0 router — Â§8 of the Phase 3 contract."""

from __future__ import annotations

import re
from typing import Optional

from .contracts import RouteActionClass, RouteDecision
from .v11_spatial_shelf import classify_v11_spatial_shelf_intent, is_spatial_map_creator_execution_gated


_NEGATION_PATTERN = re.compile(
    r"\b(?:don't|do not|won't|not|never|no|isn't|aren't|didn't|doesn't|can't|cannot|not yet)\b",
    re.I,
)

_NAVIGATE_PATTERN = re.compile(
    r"(?:"
    r"\b(?:open|show|switch to|take me to|go to|bring up|launch|load)\b.*\b(?:"
    r"script writer|timeline|audio studio|voice creator|voice studio|magi|continuity|"
    r"bible|runtime manager|references|characters|casting|"
    r"environment creator|scene creator|"
    r"editor|workspace|studio|panel|view|mode"
    r")"
    r"|"
    r"\b(?:open|show)\s+(?:script|writer|timeline|audio|voice)\b"
    r")",
    re.I,
)

_APPROVE_PATTERN = re.compile(
    r"\b(?:approve|accept(?: this)?|use this|looks good|confirmed|that works|go ahead|sounds? good|perfect"
    r"|proceed|yes|yep|yeah|sure|ok|okay|please proceed|do it|continue|start|approved|alright|let'?s do it"
    r"|that'?s fine|please continue|generate it)\b",
    re.I,
)

# Execution-specific confirmation pattern (spec Â§4) — affirmative responses that
# resolve a PENDING EXECUTION (not a Wiki/Bible proposal). Checked BEFORE generic
# intent classification so the LLM cannot hijack a confirmation turn (spec Â§35).
_EXECUTION_CONFIRMATION_PATTERN = re.compile(
    r"\b(?:yes|yep|yeah|sure|ok|okay|proceed|go ahead|do it|continue|start|generate it"
    r"|approved|sounds? good|let'?s do it|that'?s fine|alright|please proceed|please continue"
    r"|looks good|confirmed|perfect|that works|that'?ll do)\b",
    re.I,
)

_REJECT_PATTERN = re.compile(
    r"\b(?:reject|decline|don't use|keep mine|keep what I|revert|undo|discard|no[,.] keep|that's? not right|that's? wrong"
    r"|nope|no thanks|don't|stop|cancel|never mind)\b",
    re.I,
)

_READ_INSPECT_PATTERN = re.compile(
    r"\b(?:what|show me|inspect|list|get|find|search|describe|what's in|how many|what are)\b"
    r".*\b(?:scenes?|assets?|characters?|batch(?:es)?|plans?|clips?|tracks?|shots?|versions?|drafts?|"
    r"bible|wiki|locations?|canon|entries?|decisions?|proposals?|jobs?|renders?|images?|videos?|panels?|segments?)\b",
    re.I,
)

_DISCUSS_FEEDBACK_PATTERN = re.compile(
    r"\b(?:be honest|critique|does this work|what's your take|how do you feel about|what do you think)\b",
    re.I,
)

_DISCUSS_CORRECTION_PATTERN = re.compile(
    r"^(?:correction:|actually,\s?|instead,\s?|no[,.] that's wrong|no[,.] that didn't)",
    re.I,
)

_DISCUSS_EXPLAIN_PATTERN = re.compile(
    r"\b(?:I want to tell you|let me explain|before we start|walk you through|"
    r"let me give you|just listen|I'm going to tell)\b",
    re.I,
)

_DISCUSS_COLLABORATE_PATTERN = re.compile(
    r"\b(?:can you help me|let's (?:talk|discuss|work on|think about)|what about)\b",
    re.I,
)

_DISCUSS_OPINION_PATTERN = re.compile(
    r"\bwhat do you think\b|\bhow (?:do|would) you\b.*\b(?:feel|like|approach)\b",
    re.I,
)

_MODIFY_KNOWLEDGE_PATTERN = re.compile(
    r"\b(?:add|update|change|put|save|write|set)\b.*\b(?:"
    r"wiki|summary|bible|canon|knowledge|logline|synopsis|description|premise|tone|genre"
    r")\b",
    re.I,
)

_EXECUTE_DESTRUCTIVE_PATTERN = re.compile(
    r"\b(?:delete|remove|destroy|erase|clear|trash)\b.*\b(?:"
    r"batch|scene|clip|sequence|shot|track|asset|version|plan|block|frame"
    r")\b",
    re.I,
)

_EXECUTE_GENERATE_PATTERN = re.compile(
    r"\b(?:create|generate|render|build|execute|run|queue|start|begin|make)\b.*\b(?:"
    r"scene|shot|clip|batch|plan|sequence|render|image|video|portrait|storyboard|frame|picture|version|variation|alternative"
    r")\b",
    re.I,
)

_DISCUSS_SEEKING_PATTERN = re.compile(
    r"\b(?:think about|opinion|suggest)\b",
    re.I,
)


# --- Spatial Map + Atlas + ERS + Scene Creator operational commands (m413) ---
#
# Amendment #52 (Co-Director routing for spatial/scene ops). These patterns
# classify explicit operational commands as EXECUTE_PRODUCTION with a
# `capability` hint carried via RouteDecision.target so the downstream
# unified-intent classifier can resolve the capability id. They run BEFORE
# the generic `_EXECUTE_GENERATE_PATTERN` so a specific "generate the ers"
# is not collapsed into a generic image-generation intent.
#
# The deterministic classifier itself does not resolve capability ids — it
# only sets `RouteDecision.target` to a stable marker string. The unified
# intent classifier (`routing.unified_intent._resolve_capability`) maps the
# message text to the registered capability id (atlas.generate / ers.generate
# / image.generate). See `_CAPABILITY_PATTERNS` in `unified_intent.py`.

# "create an atlas shot of X" / "generate atlas shot" / "make an atlas shot"
_ATLAS_SHOT_PATTERN = re.compile(
    r"\b(?:create|generate|make|render|build)\b\s+(?:an?\s+)?(?:atlas\s+shot|roofless\s+(?:shot|map|view))\b",
    re.I,
)

# "use that as the spatial map" / "use it as the spatial map" / "set it as the background"
_USE_AS_SPATIAL_MAP_PATTERN = re.compile(
    r"\buse\s+(?:that|it|this|the\s+(?:last\s+)?atlas(?:\s+shot)?)\s+as\s+(?:the\s+)?(?:spatial\s+map|map\s+background|background)\b",
    re.I,
)

# "put @Korri behind the bar" / "place @character at <location>"
# Deferred — requires LLM spatial reasoning to extract a normalized (x,y)
# placement. We still classify deterministically as EXECUTE_PRODUCTION so the
# downstream LLM/curated-tools path can resolve the placement.
_PLACE_CHARACTER_PATTERN = re.compile(
    r"\b(?:put|place|position|move|set)\s+@([A-Za-z][A-Za-z0-9_]*)\s+(?:behind|in\s+front\s+of|at|on|near|by|next\s+to|under|over|beside)\b",
    re.I,
)

# "place #coffeecup in front of her" / "put #prop at <location>"
_PLACE_PROP_PATTERN = re.compile(
    r"\b(?:put|place|position|move|set)\s+#([A-Za-z][A-Za-z0-9_-]*)\s+(?:behind|in\s+front\s+of|at|on|near|by|next\s+to|under|over|beside)\b",
    re.I,
)

# "generate the ers" / "generate environment reference sheet" / "make the ers"
_ERS_GENERATE_PATTERN = re.compile(
    r"\b(?:generate|create|make|build|render|assemble)\b\s+(?:the\s+)?(?:ers|environment\s+reference\s+(?:sheet|package|set))\b",
    re.I,
)

_CRS_CREATE_PATTERN = re.compile(
    r"\b(?:create|generate|build|make|run)\b.+\b(?:character reference sheet|\bcrs\b|visual sheet)\b",
    re.I,
)
_CRS_ADVICE_RE = re.compile(
    r"^\s*(?:should we|should i|shall we|do you think|would creating|what if)\b",
    re.I,
)

# "suggest a close-up" / "suggest a shot" — NOT an execution; a suggestion.
# Returns READ_INSPECT (analysis) so the LLM proposes shots without firing
# the image.generate capability.
_SUGGEST_SHOT_PATTERN = re.compile(
    r"\b(?:suggest|propose|recommend)\s+(?:a\s+|an\s+|some\s+)?(?:close-?up|wide|medium|over[-\s]?the-?shoulder|two[-\s]?shot|insert|establishing|shot|shots|camera\s+angle|framing)\b",
    re.I,
)


# "generate four images" / "create a batch of images" / "generate N images"
# Image-batch generation. Must be checked BEFORE _GENERATE_N_SHOTS_PATTERN so
# that image batches are not stolen by the production-still / image.generate route.
_IMAGE_BATCH_PATTERN = re.compile(
    r"\b(?:generate|create|make|render|build)\b\s+"
    r"(?:"
    r"(?:(\d+|one|two|three|four|five|six|seven|eight|nine|ten|a\s+batch\s+of|a\s+few|several|multiple)\s+)(?:images?|pictures?|stills?|frames?)"
    r"|"
    r"(?:a\s+batch\s+of\s+(?:images?|pictures?|stills?))"
    r")\b",
    re.I,
)

# "generate four shots" / "generate N shots" / "make 3 scene shots"
# Captures the count (digit OR common word-number) into group 1. Word
# numbers are handled so "generate four shots" classifies the same as
# "generate 4 shots". The generic ``_EXECUTE_GENERATE_PATTERN`` uses
# ``\bshot\b`` (no optional ``s``), so plural "shots" would otherwise fall
# through to the semantic classifier — this specific pattern wins first.
#
# The pattern requires EITHER an explicit count (digit or word-number) OR
# the "scene" qualifier, so a bare "create shots." still falls through to
# the semantic classifier (preserves the ``test_phase3_router`` corpus
# expectation that bare "Create shots." is not a deterministic match).
_GENERATE_N_SHOTS_PATTERN = re.compile(
    r"\b(?:generate|create|make|render|build)\b\s+"
    r"(?:"
    # (1) explicit count + (optional "scene") + shots/images
    r"(?:(\d+|one|two|three|four|five|six|seven|eight|nine|ten|a\s+couple\s+of|a\s+few)\s+)"
    r"(?:scene\s+)?(?:shots?|images?|scene\s+images?)"
    r"|"
    # (2) optional article + "scene" qualifier + shots/images (no count)
    r"(?:an?\s+|some\s+)?scene\s+(?:shots?|images?)"
    r")\b",
    re.I,
)

# "regenerate shot 2" / "redo shot 3" / "regenerate the second shot"
_REGENERATE_SHOT_PATTERN = re.compile(
    r"\b(?:regenerate|redo|re-?render|re-?make|retry)\s+(?:shot|frame)\s*(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b",
    re.I,
)

# "send those to timeline" / "send to timeline" / "send these shots to the timeline"

# Wave 4 Omni: deposit completed 1F/3F video → Timeline Visual (not Scene Creator send)
_DEPOSIT_COMPLETED_VIDEO_PATTERN = re.compile(
    r"\b(?:deposit|export|send)\b.+\b(?:completed|finished)?\s*(?:1\s*f(?:rame)?|3\s*f(?:rame)?|one[\s-]?frame|three[\s-]?frame)\b.+\b(?:timeline|visual)\b"
    r"|\b(?:deposit|export|send)\b.+\b(?:completed|finished)\s+video\b.+\b(?:timeline(?:\s+visual)?|visual)\b"
    r"|\bdeposit\b.+\b(?:video|take)\b.+\b(?:timeline|visual)\b",
    re.I,
)

_SEND_TO_TIMELINE_PATTERN = re.compile(
    r"\bsend\s+(?:those|these|them|the\s+shots?|the\s+batch)?\s*(?:shots?|images?|frames?)?\s*to\s+(?:the\s+)?timeline\b",
    re.I,
)

# --- Production-orchestrator milestone: conversational production commands ---
#
# "create images from the ERS" / "generate images from the ers using the four saved cameras"
# -> image.generate (v1.1 Image Generator production stills; Spatial Map shelved).
_ERS_TO_SCENE_PATTERN = re.compile(
    r"\b(?:create|generate|make|render|build)\b.*\bimages?\b.*\bfrom\s+(?:the\s+)?(?:ers|environment\s+reference\s+(?:sheet|package))\b",
    re.I,
)

# "create shots using the four saved cameras" / "make images from the saved cameras"
_CAMERA_SHOTS_PATTERN = re.compile(
    r"\b(?:create|generate|make|render)\b.*\b(?:shots?|images?)\b.*\b(?:using|from|with)\s+(?:the\s+)?(?:[a-z]+\s+)?(?:saved\s+)?cameras?\b",
    re.I,
)

# Timeline edit vocabulary (mission Parts 17-28): put/add/move on the timeline,
# timed prompts, batches, generator selection, frame size, exact durations.
_TIMELINE_EDIT_PATTERN = re.compile(
    r"\b(?:put|add|place|move|drop|insert|attach)\b.*\b(?:on|to|into|in|at|onto)\s+(?:the\s+)?timeline\b"
    r"|\b(?:put|add|place|move)\b.*\b(?:at|near)\s+(?:the\s+)?(?:start|beginning|end|top|head)\s+of\s+(?:the\s+)?timeline\b"
    r"|\b(?:timed\s+prompt|prompt\s+clip|prompt\s+track)\b"
    r"|\b(?:create|make|add|build|start)\s+(?:a\s+|the\s+|another\s+|next\s+)?batch\b"
    r"|\b(?:run|generate)\s+(?:this|the|that|it|batch\s*\d*)\s+(?:in|with)\s+(?:minimax|qwen|ltx)\b"
    r"|\b(?:make|set)\s+(?:the\s+)?(?:clip|shot|batch|it|this)\s+\d+\s*seconds?\b",

    re.I,
)


NAVIGATION_TARGETS: dict[str, str] = {
    "script writer": "script_writer",
    "script": "script_writer",
    "writer": "script_writer",
    "timeline": "timeline",
    "audio studio": "audiostudio",
    "audio": "audiostudio",
    "voice creator": "voice_creator",
    "voice studio": "voicestudio",
    "voice": "voicestudio",
    "magi": "magi",
    "continuity": "continuity",
    "bible": "bible",
    "posecraft": "imagegen",
    "pose craft": "imagegen",
    "runtime manager": "runtime_manager",
    "references": "references",
    "characters": "characters",
    "casting": "casting",
    "environment creator": "environment_creator",
    "image generator": "imagegen",
    "image studio": "imagegen",
    "cinematic image generator": "imagegen",
    "scene creator": "imagegen",  # Standard retired -> Image Generator (v1.1)
    "editor": "editor",
}

_ENTITY_TOOL_MAP: dict[str, list[str]] = {
    "scene": ["scene.list", "scene.get", "scene.list_characters"],
    "scenes": ["scene.list", "scene.get", "scene.list_characters"],
    "asset": ["asset.list", "asset.get"],
    "assets": ["asset.list", "asset.get"],
    "character": ["character.list", "character.get"],
    "characters": ["character.list", "character.get"],
    "batch": ["batch.list", "batch.get"],
    "plan": ["plan.list", "plan.get"],
    "plans": ["plan.list", "plan.get"],
    "clip": ["clip.list", "clip.get"],
    "clips": ["clip.list", "clip.get"],
    "track": ["track.list", "track.get"],
    "tracks": ["track.list", "track.get"],
    "shot": ["shot.list", "shot.get"],
    "shots": ["shot.list", "shot.get"],
    "version": ["version.list", "version.get"],
    "versions": ["version.list", "version.get"],
    "draft": ["draft.list", "draft.get"],
    "drafts": ["draft.list", "draft.get"],
    "bible": ["bible.list", "bible.get", "bible.search"],
    "wiki": ["bible.list", "bible.search"],
    "location": ["location.list", "location.get"],
    "locations": ["location.list", "location.get"],
    "canon": ["canon.list", "canon.get"],
    "entry": ["entry.list", "entry.get"],
    "entries": ["entry.list", "entry.get"],
    "decision": ["decision.list", "decision.get"],
    "decisions": ["decision.list", "decision.get"],
    "proposal": ["proposal.list", "proposal.get"],
    "proposals": ["proposal.list", "proposal.get"],
    "job": ["job.list", "job.get"],
    "jobs": ["job.list", "job.get"],
    "render": ["render.list", "render.get"],
    "renders": ["render.list", "render.get"],
    "image": ["image.list", "image.get"],
    "images": ["image.list", "image.get"],
    "video": ["video.list", "video.get"],
    "videos": ["video.list", "video.get"],
    "panel": ["panel.list", "panel.get"],
    "panels": ["panel.list", "panel.get"],
    "segment": ["segment.list", "segment.get"],
    "segments": ["segment.list", "segment.get"],
}


_NEGATED_ACTION_VERB_RE = re.compile(
    r"\b(?:don'?t|do\s+not|does\s+not|doesn'?t|won'?t|never|"
    r"isn'?t|is\s+not|aren'?t|are\s+not|didn'?t|did\s+not|can'?t|cannot|not)\b"
    r"[\s,]+(?:actually\s+|really\s+|please\s+|want\s+to\s+|going\s+to\s+|gonna\s+)*"
    r"(?:open|switch|take|go|bring|launch|load|"
    r"approve|accept|reject|decline|proceed|continue|"
    r"add|update|change|put|save|write|set|"
    r"delete|remove|destroy|erase|clear|trash|"
    r"create|generate|render|build|execute|run|queue|start|begin|make|"
    r"inspect|list|get|find|search|describe)\b",
    re.I,
)


def _has_negated_action(message: str) -> bool:
    """True only when the negation attaches to the production action verb.

    "don't generate", "do not create a scene", "never run that" negate the
    action itself -> the turn is a discussion, not an execution. Cinematic
    exclusion constraints inside a scene spec ("Do not reveal Cade before the
    blast", "Do not show the courier before the portal opens", "No additional
    characters", "Cade is NOT yet visible", "He does not rush") negate story
    events, not the request — they must not flip a production request to
    DISCUSS. Visibility verbs ("show", "reveal") are cinematic reveal-gating
    vocabulary, not production actions, so they are deliberately absent from
    the verb list.
    """
    return bool(_NEGATED_ACTION_VERB_RE.search(message or ""))


def is_execution_confirmation(message: str) -> bool:
    """Return True if `message` is an affirmative confirmation of a pending execution.

    Spec Â§4 + Â§35: this is checked BEFORE generic intent classification so the LLM
    cannot hijack a confirmation turn. Returns False for negated/reject responses.
    """
    if not message:
        return False
    # "not sure", "don't proceed", "no, don't" etc. are rejections, not confirmations.
    if _NEGATION_PATTERN.search(message):
        return False
    if _REJECT_PATTERN.search(message):
        return False
    return bool(_EXECUTION_CONFIRMATION_PATTERN.search(message))


def is_execution_rejection(message: str) -> bool:
    """Return True if `message` rejects a pending execution."""
    if not message:
        return False
    lower = message.lower().strip()
    # Standalone "no" is a rejection.
    if lower in ("no", "nope", "n", "no.", "no,", "cancel", "stop"):
        return True
    return bool(_REJECT_PATTERN.search(message))


def _extract_navigate_target(
    message: str,
    available_workspaces: Optional[frozenset[str]],
) -> tuple[Optional[str], Optional[str]]:
    lower = message.lower()
    for name, ws_id in sorted(NAVIGATION_TARGETS.items(), key=lambda x: -len(x[0])):
        if name in lower:
            if available_workspaces is not None and ws_id not in available_workspaces:
                return None, ws_id
            return ws_id, ws_id
    return None, None


def _detect_read_entity(message: str) -> Optional[list[str]]:
    lower = message.lower()
    for entity, tool_ids in sorted(_ENTITY_TOOL_MAP.items(), key=lambda x: -len(x[0])):
        if entity in lower:
            return tool_ids
    return None


def _is_discussion_seeking(message: str) -> bool:
    return bool(_DISCUSS_SEEKING_PATTERN.search(message))


def classify_deterministic(
    message: str,
    *,
    active_workspace: Optional[str] = None,
    derived_stage: Optional[str] = None,
    pending_proposal_ids: Optional[list[str]] = None,
    available_workspaces: Optional[frozenset[str]] = None,
) -> Optional[RouteDecision]:
    """Classify a user message using deterministic patterns.

    Returns a RouteDecision for obvious matches, or None to fall back
    to the semantic classifier.
    """

    # 1. Negation detection (run FIRST — Â§8.7)
    if _has_negated_action(message):
        return RouteDecision(
            actionClass=RouteActionClass.DISCUSS,
            confidence=0.75,
            executionLane="discuss",
            writeAllowed=False,
            destructive=False,
            evidence=["Negation detected — action intent negated by user"],
        )
    # 1.5 Production-orchestrator commands (mission): explicit production verbs
    # run BEFORE the approve/reject checks so phrases like "put it at the start of
    # Timeline" (which contains the approve word "start") route to execution.
    if _ERS_TO_SCENE_PATTERN.search(message) or _CAMERA_SHOTS_PATTERN.search(message):
        return RouteDecision(
            actionClass=RouteActionClass.EXECUTE_PRODUCTION,
            target="image.generate",
            confidence=0.9,
            executionLane="proposal",
            writeAllowed=True,
            destructive=False,
            evidence=["Matched ERS/camera production-still pattern -> Image Generator"],
        )

    if _TIMELINE_EDIT_PATTERN.search(message):
        return RouteDecision(
            actionClass=RouteActionClass.EXECUTE_PRODUCTION,
            target="timeline.edit",
            confidence=0.88,
            executionLane="proposal",
            writeAllowed=True,
            destructive=False,
            evidence=["Matched timeline edit pattern"],
        )

    # Adept UI v1.1 Spatial Map shelf; Environment Creator Express for create-environment.
    shelf_kind = classify_v11_spatial_shelf_intent(message)
    if shelf_kind == "open_environment_creator":
        return RouteDecision(
            actionClass=RouteActionClass.NAVIGATE,
            target="environment_creator",
            targetWorkspace="environment_creator",
            confidence=0.94,
            executionLane="operator",
            writeAllowed=False,
            destructive=False,
            evidence=["Matched Environment Creator (v1.1 spatial/3D shelf)"],
        )
    if shelf_kind == "open_image_generator":
        return RouteDecision(
            actionClass=RouteActionClass.NAVIGATE,
            target="imagegen",
            targetWorkspace="imagegen",
            confidence=0.94,
            executionLane="operator",
            writeAllowed=False,
            destructive=False,
            evidence=["Matched Image Generator (v1.1 spatial/3D shelf)"],
        )

    # 2. NAVIGATE (Â§8.1)
    nav_match = _NAVIGATE_PATTERN.search(message)
    if nav_match:
        target_ws, unresolved_target = _extract_navigate_target(message, available_workspaces)
        confidence = 0.92
        target = target_ws if target_ws is not None else unresolved_target
        evidence_text = f"matched pattern: {nav_match.group().strip()}"
        evidence = [evidence_text]
        if unresolved_target is not None and target_ws is None:
            confidence = 0.85
            evidence.append(
                f"target workspace '{unresolved_target}' not in available workspaces"
            )
        return RouteDecision(
            actionClass=RouteActionClass.NAVIGATE,
            target=target,
            targetWorkspace=target,
            confidence=confidence,
            executionLane="operator",
            writeAllowed=False,
            destructive=False,
            evidence=evidence,
        )

    # 3. APPROVE (Â§8.4)
    if _APPROVE_PATTERN.search(message):
        if not pending_proposal_ids:
            return RouteDecision(
                actionClass=RouteActionClass.CLARIFY,
                target=None,
                confidence=0.9,
                executionLane="discuss",
                writeAllowed=False,
                destructive=False,
                evidence=["No pending proposal to approve — returning CLARIFY"],
            )
        return RouteDecision(
            actionClass=RouteActionClass.APPROVE,
            target=pending_proposal_ids[0],
            confidence=0.9,
            executionLane="approve",
            writeAllowed=True,
            destructive=False,
            evidence=["Matched approve pattern with pending proposals"],
        )

    # 4. REJECT (Â§8.4)
    if _REJECT_PATTERN.search(message):
        if not pending_proposal_ids:
            return RouteDecision(
                actionClass=RouteActionClass.CLARIFY,
                target=None,
                confidence=0.9,
                executionLane="discuss",
                writeAllowed=False,
                destructive=False,
                evidence=["No pending proposal to reject — returning CLARIFY"],
            )
        return RouteDecision(
            actionClass=RouteActionClass.REJECT,
            target=pending_proposal_ids[0],
            confidence=0.88,
            executionLane="reject",
            writeAllowed=True,
            destructive=False,
            evidence=["Matched reject pattern with pending proposals"],
        )

    # 5. READ_INSPECT (Â§8.2)
    if _READ_INSPECT_PATTERN.search(message) and not _is_discussion_seeking(message):
        entity_tools = _detect_read_entity(message)
        return RouteDecision(
            actionClass=RouteActionClass.READ_INSPECT,
            confidence=0.87,
            executionLane="read",
            writeAllowed=False,
            destructive=False,
            targetToolIds=entity_tools,
            evidence=["Matched read/inspect pattern"],
        )

    # 6. DISCUSS (Â§8.3) — ordered sub-patterns
    if _DISCUSS_FEEDBACK_PATTERN.search(message):
        return RouteDecision(
            actionClass=RouteActionClass.DISCUSS,
            confidence=0.86,
            executionLane="discuss",
            writeAllowed=False,
            destructive=False,
            evidence=["Matched feedback/critique discuss pattern"],
        )
    if _DISCUSS_CORRECTION_PATTERN.search(message):
        return RouteDecision(
            actionClass=RouteActionClass.DISCUSS,
            confidence=0.88,
            executionLane="discuss",
            writeAllowed=False,
            destructive=False,
            evidence=["Matched correction discuss pattern"],
        )
    if _DISCUSS_EXPLAIN_PATTERN.search(message):
        return RouteDecision(
            actionClass=RouteActionClass.DISCUSS,
            confidence=0.88,
            executionLane="discuss",
            writeAllowed=False,
            destructive=False,
            evidence=["Matched explain/listen discuss pattern"],
        )
    if _DISCUSS_COLLABORATE_PATTERN.search(message):
        return RouteDecision(
            actionClass=RouteActionClass.DISCUSS,
            confidence=0.82,
            executionLane="discuss",
            writeAllowed=False,
            destructive=False,
            evidence=["Matched collaborate discuss pattern"],
        )
    if _DISCUSS_OPINION_PATTERN.search(message):
        return RouteDecision(
            actionClass=RouteActionClass.DISCUSS,
            confidence=0.86,
            executionLane="discuss",
            writeAllowed=False,
            destructive=False,
            evidence=["Matched opinion-seeking discuss pattern"],
        )

    # 7. MODIFY_KNOWLEDGE (Â§8.5)
    if _MODIFY_KNOWLEDGE_PATTERN.search(message):
        return RouteDecision(
            actionClass=RouteActionClass.MODIFY_KNOWLEDGE,
            confidence=0.83,
            executionLane="proposal",
            writeAllowed=True,
            destructive=False,
            evidence=["Matched modify knowledge pattern"],
        )

    # 6b. Spatial Map + Atlas + ERS + Scene Creator operational commands (m413).
    # Specific patterns run BEFORE the generic EXECUTE_GENERATE_PATTERN so a
    # precise "generate the ers" is not collapsed into a generic image gen.
    # The `target` field carries a stable marker string consumed by the
    # unified-intent capability resolver; capability id is resolved there.

    # "suggest a close-up" / "suggest a shot" → analysis (NOT execution).
    # The LLM proposes shot text; the creator then says "generate four shots".
    if _SUGGEST_SHOT_PATTERN.search(message):
        return RouteDecision(
            actionClass=RouteActionClass.READ_INSPECT,
            target="scene.suggest_shot",
            confidence=0.85,
            executionLane="read",
            writeAllowed=False,
            destructive=False,
            evidence=["Matched scene shot suggestion pattern (analysis, not execution)"],
        )

    # "create an atlas shot of X" → atlas.generate
    if _ATLAS_SHOT_PATTERN.search(message) and not is_spatial_map_creator_execution_gated():
        return RouteDecision(
            actionClass=RouteActionClass.EXECUTE_PRODUCTION,
            target="atlas.generate",
            confidence=0.92,
            executionLane="proposal",
            writeAllowed=True,
            destructive=False,
            evidence=["Matched atlas shot generation pattern"],
        )

    # "use that as the spatial map" → set spatial map background (no capability
    # yet; this is an inline spatial map operation handled by the LLM/curated
    # tools path with the most recent atlas asset). Classified as EXECUTION so
    # the dispatcher acts rather than acknowledges (Law #13 — no fake
    # operation).
    if _USE_AS_SPATIAL_MAP_PATTERN.search(message) and not is_spatial_map_creator_execution_gated():
        return RouteDecision(
            actionClass=RouteActionClass.EXECUTE_PRODUCTION,
            target="spatial_map.use_as_background",
            confidence=0.88,
            executionLane="proposal",
            writeAllowed=True,
            destructive=False,
            evidence=["Matched 'use as spatial map' pattern"],
        )

    if _CRS_CREATE_PATTERN.search(message) and not _CRS_ADVICE_RE.search(message):
        return RouteDecision(
            actionClass=RouteActionClass.EXECUTE_PRODUCTION,
            target="character.generate_visual_sheet",
            confidence=0.93,
            executionLane="proposal",
            writeAllowed=True,
            destructive=False,
            evidence=["Matched Character Reference Sheet create pattern"],
        )

    # "generate the ers" → ers.generate
    if _ERS_GENERATE_PATTERN.search(message):
        return RouteDecision(
            actionClass=RouteActionClass.EXECUTE_PRODUCTION,
            target="ers.generate",
            confidence=0.92,
            executionLane="proposal",
            writeAllowed=True,
            destructive=False,
            evidence=["Matched ERS generation pattern"],
        )

    # "generate four images" / "create a batch of images" \u2192 image.generate_batch
    if _IMAGE_BATCH_PATTERN.search(message):
        return RouteDecision(
            actionClass=RouteActionClass.EXECUTE_PRODUCTION,
            target="image.generate_batch",
            confidence=0.88,
            executionLane="proposal",
            writeAllowed=True,
            destructive=False,
            evidence=["Matched image batch generation pattern"],
        )

# "repair/fix the ERS" -> ers.repair (Spatial Map not required)
    # "edit this environment / remove plant beside couch" -> ers.edit (no auto-approve)
    if re.search(
        r"\b(?:edit|inpaint)\b.{0,60}\b(?:ers|environment\s+reference|this\s+environment|the\s+environment)\b"
        r"|\bedit\s+this\s+environment\b"
        r"|\bremove\s+(?:the\s+)?plant\b.{0,40}\b(?:couch|sofa)\b",
        message,
        re.I | re.S,
    ):
        return RouteDecision(
            actionClass=RouteActionClass.EXECUTE_PRODUCTION,
            target="ers.edit",
            confidence=0.9,
            executionLane="proposal",
            writeAllowed=True,
            destructive=False,
            evidence=["Matched ERS edit pattern (creator Approve still required for canon)"],
        )


    if re.search(
        r"\b(?:repair|fix|rebuild|regenerate)\b.{0,40}\b(?:ers|environment\s+reference\s+(?:sheet|package))\b",
        message,
        re.I,
    ):
        return RouteDecision(
            actionClass=RouteActionClass.EXECUTE_PRODUCTION,
            target="ers.repair",
            confidence=0.9,
            executionLane="proposal",
            writeAllowed=True,
            destructive=False,
            evidence=["Matched ERS repair pattern (Spatial Map optional)"],
        )

    # "generate four shots" / "generate N shots" -> image.generate
    if _GENERATE_N_SHOTS_PATTERN.search(message):
        return RouteDecision(
            actionClass=RouteActionClass.EXECUTE_PRODUCTION,
            target="image.generate",
            confidence=0.9,
            executionLane="proposal",
            writeAllowed=True,
            destructive=False,
            evidence=["Matched production-still / shot generation pattern -> Image Generator"],
        )


# "regenerate shot 2" -> image.generate targeted regen (capability id
    # resolved downstream; the shot index is extracted by the LLM/curated
    # tools path from the message).
    if _REGENERATE_SHOT_PATTERN.search(message):
        return RouteDecision(
            actionClass=RouteActionClass.EXECUTE_PRODUCTION,
            target="scene.regenerate_shot",
            confidence=0.9,
            executionLane="proposal",
            writeAllowed=True,
            destructive=False,
            evidence=["Matched scene shot regeneration pattern"],
        )

    # "send those to timeline" → scene creator timeline handoff
        # Wave 4: completed Omni video deposit (prefer over Scene Creator send)
    if _DEPOSIT_COMPLETED_VIDEO_PATTERN.search(message):
        return RouteDecision(
            actionClass=RouteActionClass.EXECUTE_PRODUCTION,
            target="timeline.deposit_video",
            confidence=0.94,
            executionLane="proposal",
            writeAllowed=True,
            destructive=False,
            evidence=["Matched completed video → Timeline Visual deposit pattern"],
        )

    if _SEND_TO_TIMELINE_PATTERN.search(message):
        return RouteDecision(
            actionClass=RouteActionClass.EXECUTE_PRODUCTION,
            target="scene.send_to_timeline",
            confidence=0.92,
            executionLane="proposal",
            writeAllowed=True,
            destructive=False,
            evidence=["Matched scene-to-timeline handoff pattern"],
        )

    # "put @Korri behind the bar" / "place #coffeecup in front of her"
    # → spatial map placement. Classified as EXECUTION so the dispatcher
    # routes through curated tools. The LLM resolves the normalized (x,y)
    # placement from the location phrase (deferred — requires LLM spatial
    # reasoning; the deterministic router extracts the @/# tag and the
    # location phrase but does not compute coordinates).
    place_char = _PLACE_CHARACTER_PATTERN.search(message)
    if place_char and not is_spatial_map_creator_execution_gated():
        return RouteDecision(
            actionClass=RouteActionClass.EXECUTE_PRODUCTION,
            target="spatial_map.place_character",
            confidence=0.85,
            executionLane="proposal",
            writeAllowed=True,
            destructive=False,
            evidence=[
                f"Matched spatial map character placement pattern (entity=@{place_char.group(1)})",
                "Coordinate resolution deferred — requires LLM spatial reasoning",
            ],
        )
    place_prop = _PLACE_PROP_PATTERN.search(message)
    if place_prop and not is_spatial_map_creator_execution_gated():
        return RouteDecision(
            actionClass=RouteActionClass.EXECUTE_PRODUCTION,
            target="spatial_map.place_prop",
            confidence=0.85,
            executionLane="proposal",
            writeAllowed=True,
            destructive=False,
            evidence=[
                f"Matched spatial map prop placement pattern (entity=#{place_prop.group(1)})",
                "Coordinate resolution deferred — requires LLM spatial reasoning",
            ],
        )

    # 8. EXECUTE_PRODUCTION (Â§8.6)
    if _EXECUTE_DESTRUCTIVE_PATTERN.search(message):
        return RouteDecision(
            actionClass=RouteActionClass.EXECUTE_PRODUCTION,
            confidence=0.88,
            executionLane="proposal",
            writeAllowed=True,
            destructive=True,
            evidence=["Matched destructive production pattern"],
        )
    if _EXECUTE_GENERATE_PATTERN.search(message):
        return RouteDecision(
            actionClass=RouteActionClass.EXECUTE_PRODUCTION,
            confidence=0.88,
            executionLane="proposal",
            writeAllowed=True,
            destructive=False,
            evidence=["Matched generate production pattern"],
        )

    # 9. No deterministic match — fall back to semantic classifier
    return None
