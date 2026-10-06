"""Build and persist the authority envelope before the agent runs."""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any

from sqlalchemy.orm import Session

from .models import AuthorityEnvelope, SemanticDecision, TurnMode
from .prompt import PROMPT_VERSION, prompt_hash

_NAVIGATE = (
    "go to ",
    "take me to ",
    "open the ",
    "navigate to ",
    "open character creator",
    "open timeline",
    "open image generator",
    "open voice studio",
    "open audio studio",
    "open environment creator",
    "open prop creator",
)
_PROPOSE = (
    "propose ",
    "don't apply",
    "do not apply",
    "don't place",
    "do not place",
    "just draft",
    "only draft",
    "before anything is placed",
    "before it is placed",
    "before placing",
    "what you are preparing",
    "don't create anything",
    "do not create anything",
)
# Explicit production commands only. Generic words such as add, use, change, and scene are not commands.
_EXPLICIT_MUTATE = (
    "create a new scene",
    "create a scene",
    "create a timeline scene",
    "create a new character",
    "create a character named",
    "add a timed prompt",
    "add this timed prompt",
    "place this timed prompt",
    "place the timed prompt",
    "generate a prop",
    "generate this prop",
    "create a prop",
    "generate a still",
    "create a still",
    "generate that shot",
    "generate this shot",
    "generate the shot",
    "shot after",
    "opening shot",
    "comes before",
    "publish this scene",
    "send the published scene",
)
_SURFACES = (
    ("timeline", ("use timeline", "in timeline")),
    ("image", ("use image generator", "in image generator")),
    ("character", ("use character creator", "in character creator")),
    ("voice", ("use voice studio", "in voice studio")),
    ("audio", ("use audio studio", "in audio studio")),
)
_DISCUSSION = (
    "how would",
    "how should",
    "how do you",
    "how can we",
    "how can i",
    "what if",
    "maybe ",
    "i think",
    "i'm thinking",
    "im thinking",
)
_VOICE_IDENTITY_TOOLS = (
    "character_creator.get_voice_status",
    "character_creator.get_voice_profile",
    "character_creator.get_voice_candidates",
    "character_creator.open_voice_creator",
    "character_creator.preview_voice_design",
    "character_creator.generate_voice_candidates",
    "character_creator.approve_voice_candidate",
)
_SURFACE_TOOLS = {
    "voice": ("voice.", "voice_performance.", "voice_environment.", *_VOICE_IDENTITY_TOOLS),
    "audio": ("audio.",),
    "timeline": ("timeline.", "create_scene", "set_scene_prompt", "update_scene_title", "references."),
}
_READ_PREFIXES = ("what", "who", "where", "when", "why", "how", "show", "list", "is ", "are ", "check", "inspect")


def _phrase_is_requested(folded: str, phrase: str) -> bool:
    """A negated mention is not an instruction to perform the action."""

    start = 0
    while True:
        index = folded.find(phrase, start)
        if index < 0:
            return False
        prefix = folded[max(0, index - 16) : index]
        if not any(marker in prefix for marker in ("not ", "don't ", "dont ", "never ", "no ")):
            return True
        start = index + len(phrase)


def _on_named_surface(tool_id: str, surface_name: str) -> bool:
    if "inpaint" in tool_id:
        return False
    for item in _SURFACE_TOOLS.get(surface_name, ()):
        if item.endswith("."):
            if tool_id.startswith(item):
                return True
        elif tool_id == item:
            return True
    return False


def named_surface(text: str) -> str | None:
    """A named studio when the creator asked to use that studio."""

    folded = " ".join((text or "").lower().split())
    for name, markers in _SURFACES:
        if any(marker in folded for marker in markers):
            return name
    return None


def _has_explicit_mutation(folded: str) -> bool:
    """A mutation hint requires a full command, not a production word in passing."""

    if any(_phrase_is_requested(folded, phrase) for phrase in _EXPLICIT_MUTATE):
        return True
    surface = named_surface(folded)
    if not surface:
        return False
    verbs = ["create ", "generate ", "place ", "add a ", "add the "]
    if surface == "voice":
        verbs.extend(("give ", "assign "))
        if any(phrase in folded for phrase in (" say ", "say,", "say '", 'say "')):
            verbs.append("have ")
    elif surface == "audio":
        verbs.append("make ")
    return any(_phrase_is_requested(folded, verb) for verb in verbs)


def is_open_discussion(text: str) -> bool:
    """A hypothetical or a thought, before any production command is considered."""

    folded = " ".join((text or "").lower().split())
    return folded.startswith(_DISCUSSION)


def magi_edit_request(text: str) -> bool:
    """A MAGI finishing sentence that must reach the existing edit owner."""

    folded = " ".join((text or "").lower().split())
    if re.search(r"\brecipe\b", folded) and re.search(r"\bapply\b", folded):
        return True
    if re.search(r"\b(dissolve|wipe|fade)\b", folded) and re.search(r"\b(add|between)\b", folded):
        return True
    if re.search(r"\b(lighting|warmer|cooler|brightness|highlights|shadows)\b", folded):
        return True
    if re.search(r"\bcompare\b", folded) and re.search(r"\boriginal\b", folded):
        return True
    return False


def classify_turn_mode(text: str) -> TurnMode:
    folded = " ".join((text or "").lower().split())
    if any(_phrase_is_requested(folded, phrase) for phrase in _PROPOSE):
        return "PROPOSE"
    if magi_edit_request(folded):
        return "MUTATE"
    if is_open_discussion(folded):
        return "CONVERSATION"
    if _has_explicit_mutation(folded):
        return "MUTATE"
    if any(_phrase_is_requested(folded, phrase) for phrase in _NAVIGATE):
        return "NAVIGATE"
    if folded.startswith(_READ_PREFIXES) and not folded.startswith(
        ("how would", "how should", "how do you", "how can we", "how can i")
    ):
        return "READ"
    return "CONVERSATION"


_MODES = {"CONVERSATION", "READ", "NAVIGATE", "PROPOSE", "MUTATE"}
_SURFACES_TYPED = {
    "TIMELINE",
    "CHARACTER_CREATOR",
    "PROP_CREATOR",
    "ENVIRONMENT_CREATOR",
    "IMAGE_GENERATOR",
    "VOICE_STUDIO",
    "AUDIO_STUDIO",
    "NONE",
}


def voice_identity_requested(text: str) -> bool:
    """A character-voice question or request, not a bare mention of the studio."""

    folded = " ".join((text or "").lower().split())
    if not any(
        phrase in folded
        for phrase in (
            "what voice",
            "which voice",
            "voice is",
            "voice assigned",
            "assigned voice",
            "give ",
            "assign ",
            "a voice",
            " say ",
            "say,",
            "say '",
            'say "',
        )
    ):
        return False
    surface = named_surface(folded)
    return surface in {None, "voice"}


def voice_status_question(text: str) -> bool:
    folded = " ".join((text or "").lower().split())
    return folded.startswith(("what", "which", "who", "show", "check", "is ", "are ")) and "voice" in folded


_MAGI_WORKSPACES = {"magi", "magi-editor", "magieditor"}


def workspace_is_magi(surface: str | None) -> bool:
    return (surface or "").strip().lower() in _MAGI_WORKSPACES


def magi_final_render_request(text: str) -> bool:
    """A final render of the open scene. Grade and upscale stay separate requests."""

    folded = " ".join((text or "").lower().split())
    if named_surface(folded) is not None:
        return False
    return "final render" in folded


def scene_audio_placement(text: str) -> bool:
    """Add or place music or a sound effect on the open scene. Not an Audio Studio name."""

    folded = " ".join((text or "").lower().split())
    if named_surface(folded) is not None:
        return False
    if audio_operation(text) not in {"music", "sfx"}:
        return False
    return any(token in folded for token in ("add ", "place ", "put ", "underneath"))


def audio_operation(text: str) -> str | None:
    """The audio family named by the request. None when the sentence does not ask for one."""

    folded = " ".join((text or "").lower().split())
    surface = named_surface(folded)
    if surface not in {None, "audio"}:
        return None
    if any(phrase in folded for phrase in ("ambience", "ambient", "room tone")):
        return "ambience"
    if any(phrase in folded for phrase in ("underscore", "score", "music")):
        return "music"
    if any(phrase in folded for phrase in ("sound effect", "sfx", "impact", "metallic")):
        return "sfx"
    return None


def explicit_studio_production(text: str) -> bool:
    """Use Voice Studio / Use Audio Studio plus a production verb. A question is not one."""

    if explicit_no_execute(text) or is_open_discussion(text):
        return False
    folded = " ".join((text or "").lower().split())
    if named_surface(folded) not in {"voice", "audio"}:
        return False
    if voice_status_question(text):
        return False
    return classify_turn_mode(text) == "MUTATE"


def explicit_no_execute(text: str) -> bool:
    folded = " ".join((text or "").lower().split())
    return any(_phrase_is_requested(folded, phrase) for phrase in _PROPOSE)


def validate_semantic_decision(user_text: str, raw: dict | None) -> SemanticDecision:
    """Accept the model's reading unless a hard safety constraint forbids execution.

    Missing model output uses only an explicit command. Ambiguous wording stays a conversation.
    """

    hinted = classify_turn_mode(user_text)
    if not isinstance(raw, dict):
        return SemanticDecision(
            mode=hinted,
            confidence="high" if hinted != "CONVERSATION" else "low",
        )
    mode = str(raw.get("mode") or "").strip().upper()
    if mode not in _MODES:
        mode = hinted
    confidence = str(raw.get("confidence") or "medium").strip().lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "medium"
    surface = str(raw.get("surface") or "NONE").strip().upper()
    if surface not in _SURFACES_TYPED:
        surface = "NONE"
    entities = raw.get("entities") if isinstance(raw.get("entities"), dict) else {}
    constraints = raw.get("constraints") if isinstance(raw.get("constraints"), dict) else {}
    no_execute = explicit_no_execute(user_text) or bool(constraints.get("no_execute"))
    if no_execute and mode == "MUTATE":
        mode = "PROPOSE"
    if mode == "MUTATE" and confidence == "low":
        mode = "CONVERSATION"
    if mode == "MUTATE" and confidence != "high" and hinted != "MUTATE":
        mode = "CONVERSATION"
    if explicit_studio_production(user_text) and mode == "CONVERSATION" and not no_execute:
        mode = "MUTATE"
        confidence = "high"
    tool_id = str(raw.get("tool_id") or "").strip() or None
    if mode == "CONVERSATION":
        tool_id = None
    arguments = raw.get("arguments") if isinstance(raw.get("arguments"), dict) else {}
    return SemanticDecision(
        mode=mode,  # type: ignore[arg-type]
        surface=surface,  # type: ignore[arg-type]
        action=str(raw.get("action") or "")[:200],
        entities={
            "characters": [str(item) for item in list(entities.get("characters") or [])[:8]],
            "props": [str(item) for item in list(entities.get("props") or [])[:8]],
            "environments": [str(item) for item in list(entities.get("environments") or [])[:8]],
            "scenes": [str(item) for item in list(entities.get("scenes") or [])[:8]],
        },
        constraints={
            "duration": (str(constraints.get("duration")) if constraints.get("duration") else None),
            "aspect_ratio": (str(constraints.get("aspect_ratio")) if constraints.get("aspect_ratio") else None),
            "no_execute": no_execute,
        },
        confidence=confidence,  # type: ignore[arg-type]
        reply=str(raw.get("reply") or "")[:4000],
        tool_id=tool_id,
        arguments=arguments,
    )


def resolve_admitted_tool(
    user_text: str,
    raw: dict | None,
    *,
    allowed: set[str],
    fallback: str,
) -> SemanticDecision:
    """Keep the model's tool. Fill one in only when an explicit command had no tool."""

    declined = (
        isinstance(raw, dict)
        and str(raw.get("mode") or "").strip().upper() == "CONVERSATION"
        and str(raw.get("confidence") or "").strip().lower() == "high"
        and not explicit_studio_production(user_text)
        and not _has_explicit_mutation(" ".join((user_text or "").lower().split()))
        and not scene_audio_placement(user_text)
        and not magi_final_render_request(user_text)
        and not magi_edit_request(user_text)
        and not (voice_status_question(user_text) and not is_open_discussion(user_text))
    )
    decision = validate_semantic_decision(user_text, raw)
    tool_id = "" if declined else str(decision.tool_id or "")
    if tool_id and tool_id not in allowed:
        tool_id = ""
    if not tool_id and not declined and fallback and fallback in allowed:
        tool_id = fallback
        kind = ""
        try:
            from ..tools.registry import find

            kind = find(fallback).kind
        except Exception:
            kind = ""
        if kind == "read":
            if decision.mode != "READ":
                decision = decision.model_copy(update={"mode": "READ"})
        elif decision.mode not in {"PROPOSE", "MUTATE"}:
            hinted = classify_turn_mode(user_text)
            decision = decision.model_copy(update={"mode": "PROPOSE" if hinted == "PROPOSE" else "MUTATE"})
    elif (
        not declined
        and fallback
        and fallback in allowed
        and tool_id
        and tool_id != fallback
        and decision.mode in {"PROPOSE", "MUTATE"}
    ):
        tool_id = fallback
    if tool_id:
        kind = ""
        try:
            from ..tools.registry import find

            kind = find(tool_id).kind
        except Exception:
            kind = ""
        if kind == "read" and decision.mode != "READ":
            decision = decision.model_copy(update={"mode": "READ"})
        elif kind == "mutating" and decision.mode not in {"PROPOSE", "MUTATE"}:
            hinted = classify_turn_mode(user_text)
            decision = decision.model_copy(update={"mode": "PROPOSE" if hinted == "PROPOSE" else "MUTATE"})
    return decision.model_copy(update={"tool_id": tool_id or None})


def master_hash(db: Session, project_id: str, scene_id: str | None) -> str | None:
    if not scene_id:
        return None
    try:
        from ...director_timeline_w46.store import load_master

        master = load_master(db, project_id, scene_id)
    except Exception:
        return None
    encoded = json.dumps(master, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def context_snapshot_id(db: Session, project_id: str) -> str:
    try:
        from ...db import CoDirectorConversation

        row = db.get(CoDirectorConversation, project_id)
        if row is None:
            return "conversation:none"
        revision = getattr(row, "revision", None)
        return f"conversation:{revision if revision is not None else 'unknown'}"
    except Exception:
        return "conversation:unavailable"


def feature_flags() -> dict[str, Any]:
    return {
        "providerEnv": os.environ.get("ADEPT_CODIRECTOR_PROVIDER", "").strip().lower(),
        "promptVersion": PROMPT_VERSION,
    }


_TIMED_INSTRUCTION = ("timed prompt", "timed instruction", "prompt segment")
_TIMED_TOOL = "timeline.propose_add_prompt_segment"
_SCENE_PROMPT_TOOL = "set_scene_prompt"


def is_timed_instruction(text: str) -> bool:
    folded = " ".join((text or "").lower().split())
    return any(phrase in folded for phrase in _TIMED_INSTRUCTION)


_VIDEO_TOOL = ("video", "minimax", "seedance", "ltx", "kling", "veo", "lipsync", "propose_generate_scene")
_CHARACTER_UPDATE = ("propose_character_update", "character.approve_candidate", "delete", "remove_character")


def _conflicts(tool_id: str, *, surface_name: str | None, user_text: str) -> bool:
    folded = tool_id.lower()
    if surface_name == "image" or "do not create a video" in user_text.lower() or "don't create a video" in user_text.lower():
        if surface_name == "image" and any(marker in folded for marker in _VIDEO_TOOL):
            return True
        if surface_name == "image" and (folded.startswith("timeline.") or folded.startswith("character")):
            return True
    if surface_name == "character":
        if any(marker in folded for marker in _CHARACTER_UPDATE):
            return True
        if folded.startswith(("timeline.", "voice", "image")) or folded in {"propose_image_generate", "create_scene"}:
            return True
        if len(user_text) > 80 and folded == "create_draft_character_profile":
            return True
    if surface_name == "timeline" and is_timed_instruction(user_text):
        if folded == _SCENE_PROMPT_TOOL:
            return True
        if any(marker in folded for marker in _VIDEO_TOOL):
            return True
        if folded.startswith("timeline.propose_") and folded != _TIMED_TOOL:
            return True
    return False


def exposed_tool_ids(*, surface: str | None, user_text: str) -> list[str]:
    """Closed exposure. A failure here does not fall back to the full registry."""

    from ..tools.exposure import expose_ordered, is_shelved_tool

    try:
        ordered = expose_ordered(workspace_surface=surface, intent=user_text)
    except Exception as exc:
        raise RuntimeError(f"Tool exposure failed closed: {exc}") from exc
    surface_name = named_surface(user_text)
    cleaned = []
    for tool_id in ordered:
        if is_shelved_tool(tool_id) or _conflicts(tool_id, surface_name=surface_name, user_text=user_text):
            continue
        cleaned.append(tool_id)
    if is_timed_instruction(user_text):
        cleaned = [tool_id for tool_id in cleaned if tool_id != _SCENE_PROMPT_TOOL]
        if _TIMED_TOOL not in cleaned and not is_shelved_tool(_TIMED_TOOL):
            cleaned.append(_TIMED_TOOL)
    if surface_name == "image" and "propose_image_generate" not in cleaned and not is_shelved_tool("propose_image_generate"):
        cleaned.append("propose_image_generate")
    from .bind import is_reference_sheet_request

    if is_reference_sheet_request(user_text):
        sheet_tool = "character_creator.propose_visual_sheet"
        if sheet_tool not in cleaned and not is_shelved_tool(sheet_tool):
            cleaned.append(sheet_tool)
    elif surface_name == "character" and "character_creator.create_from_brief" not in cleaned:
        cleaned.append("character_creator.create_from_brief")
    from .bind import is_environment_generation_request, ordered_execution_plan

    plan = ordered_execution_plan(user_text)
    if plan:
        planned = [str(step.get("toolId") or "") for step in plan if step.get("toolId")]
        cleaned = [tool_id for tool_id in planned if tool_id and not is_shelved_tool(tool_id)]
    elif surface_name in _SURFACE_TOOLS:
        cleaned = [tool_id for tool_id in cleaned if _on_named_surface(tool_id, surface_name)]
        if not cleaned:
            from ..tools.registry import all_definitions

            cleaned = [
                definition.tool_id
                for definition in all_definitions()
                if _on_named_surface(definition.tool_id, surface_name) and not is_shelved_tool(definition.tool_id)
            ]
    if is_environment_generation_request(user_text) and not plan:
        env_tool = "ers.generate"
        if env_tool not in cleaned and not is_shelved_tool(env_tool):
            cleaned.append(env_tool)
    if not plan and voice_identity_requested(user_text) and surface_name in {None, "voice"}:
        for tool_id in _VOICE_IDENTITY_TOOLS:
            if tool_id not in cleaned and not is_shelved_tool(tool_id):
                cleaned.append(tool_id)
        preferred = (
            "character_creator.get_voice_status"
            if voice_status_question(user_text)
            else "character_creator.generate_voice_candidates"
        )
        if preferred in cleaned:
            cleaned = [preferred] + [item for item in cleaned if item != preferred]
    operation = None if plan else audio_operation(user_text)
    if operation in {"music", "sfx"} and workspace_is_magi(surface) and surface_name is None and not plan:
        cleaned = [item for item in cleaned if not item.startswith("audio.generate_")]
        magi_audio = "magi.audio.generate"
        if magi_audio not in cleaned and not is_shelved_tool(magi_audio):
            cleaned.append(magi_audio)
        if magi_audio in cleaned:
            cleaned = [magi_audio] + [item for item in cleaned if item != magi_audio]
    elif operation and surface_name in {None, "audio"}:
        audio_tool = f"audio.generate_{operation}"
        if audio_tool not in cleaned and not is_shelved_tool(audio_tool):
            cleaned.append(audio_tool)
        if audio_tool in cleaned:
            cleaned = [audio_tool] + [item for item in cleaned if item != audio_tool]
    if magi_final_render_request(user_text) and workspace_is_magi(surface) and not plan:
        render_tool = "magi.render"
        cleaned = [
            item
            for item in cleaned
            if item not in {"magi.propose_finish", "magi.upscale", "magi.color.apply"}
        ]
        if render_tool not in cleaned and not is_shelved_tool(render_tool):
            cleaned.append(render_tool)
        if render_tool in cleaned:
            cleaned = [render_tool] + [item for item in cleaned if item != render_tool]
    elif workspace_is_magi(surface) and not plan:
        surface_tool = None
        if re.search(r"\brecipe\b", user_text or "", re.I):
            surface_tool = "magi.recipe.apply"
        elif re.search(r"\b(dissolve|wipe|fade)\b", user_text or "", re.I):
            surface_tool = "magi.transition.apply"
        elif re.search(r"\b(lighting|warmer|cooler|brightness|highlights|shadows)\b", user_text or "", re.I):
            surface_tool = "magi.color.apply"
        elif re.search(r"\bcompare\b", user_text or "", re.I):
            surface_tool = "magi.compare"
        if surface_tool:
            if surface_tool not in cleaned and not is_shelved_tool(surface_tool):
                cleaned.append(surface_tool)
            if surface_tool in cleaned:
                cleaned = [surface_tool] + [item for item in cleaned if item != surface_tool]
    if re.search(r"\bsend\b", user_text or "", re.I) and re.search(r"\bmagi\b", user_text or "", re.I):
        magi_tool = "film_timeline.send_to_magi"
        if magi_tool not in cleaned and not is_shelved_tool(magi_tool):
            cleaned.append(magi_tool)
    if re.search(r"\bpublish\b", user_text or "", re.I) and re.search(r"\bscene\b", user_text or "", re.I):
        publish_tool = "timeline.publish_scene"
        if publish_tool not in cleaned and not is_shelved_tool(publish_tool):
            cleaned.append(publish_tool)
    if re.search(r"\bshot\b", user_text or "", re.I) and re.search(
        r"\b(?:before|opening|prequel|prepend)\b", user_text or "", re.I
    ):
        prepend_tool = "timeline.prepend_shot"
        if prepend_tool not in cleaned and not is_shelved_tool(prepend_tool):
            cleaned.append(prepend_tool)
    if re.search(r"\b(?:generate|render)\s+(?:this\s+|that\s+|the\s+)?shot\b", user_text or "", re.I):
        shot_tool = "timeline.generate_shot"
        if shot_tool not in cleaned and not is_shelved_tool(shot_tool):
            cleaned.append(shot_tool)
    if re.search(r"\bshot\b", user_text or "", re.I) and re.search(r"\b(?:after|continue|extend)\b", user_text or "", re.I):
        continue_tool = "timeline.continue_shot"
        if continue_tool not in cleaned and not is_shelved_tool(continue_tool):
            cleaned.append(continue_tool)
    if not cleaned:
        raise RuntimeError("Tool exposure failed closed: no tools were admitted.")
    return cleaned


def build_envelope(
    db: Session,
    *,
    workflow_id: str,
    project_id: str,
    scene_id: str | None,
    user_text: str,
    surface: str | None,
    provider_id: str,
    model_id: str,
    selected_character_id: str | None = None,
) -> AuthorityEnvelope:
    mode = classify_turn_mode(user_text)
    return AuthorityEnvelope(
        workflow_id=workflow_id,
        project_id=project_id,
        scene_id=scene_id,
        turn_mode=mode,
        system_prompt_version=PROMPT_VERSION,
        system_prompt_hash=prompt_hash(),
        provider_id=provider_id,
        model_id=model_id or "",
        exposed_tool_ids=exposed_tool_ids(surface=surface, user_text=user_text),
        feature_flags=feature_flags(),
        master_hash_before=master_hash(db, project_id, scene_id),
        context_snapshot_id=context_snapshot_id(db, project_id),
        user_text=user_text,
        surface=surface,
        selected_character_id=(selected_character_id or "").strip() or None,
    )
