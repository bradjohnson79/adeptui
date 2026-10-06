"""Still-image generation intent for Co-Director.

When a creator asks for a picture, Co-Director generates it from the visual
brief they already gave. Sound, music, and world-building interviews do not
help a still and must not interrupt the turn.
"""

from __future__ import annotations

import re

_IMAGE_VERB_RE = re.compile(
    r"\b(?:create|generate|make|render|draw|paint|enhance|improve|refine|edit)\b",
    re.I,
)

_FIRST_FRAME_RE = re.compile(
    r"\b(?:create|generate|make|render|draw)\b.+\bfirst\s+frame\b",
    re.I,
)

_STILL_OBJECT_RE = re.compile(
    r"\b(?:"
    r"image|picture|still|photo|photograph|concept art|key art|"
    r"first\s+frame|opening\s+frame|"
    r"master shot|wide shot|establishing shot|hero shot|"
    r"full[-\s]?wide(?:\s+master)?\s+shot|"
    r"scene\s+(?:image|still|shot|picture)|"
    r"location\s+(?:image|still|shot)|"
    r"environment\s+(?:image|still|shot)|"
    r"(?:last|previous|latest|this|that|the)\s+(?:\w+\s+){0,3}shot"
    r")\b",
    re.I,
)

_SCENE_PLUS_VISUAL_RE = re.compile(
    r"\b(?:create|generate|make|render|draw|paint)\b"
    r".+\b(?:scene|corridor|interior|exterior|location|environment|set)\b"
    r".+\b(?:shot|image|still|picture|visual)\b",
    re.I,
)

_CREATE_PLACE_RE = re.compile(
    r"\b(?:create|generate|make|render|draw|paint)\b"
    r".+\b(?:corridor|interior|exterior|environment|location)\b",
    re.I,
)

_NON_STILL_RE = re.compile(
    r"\b(?:"
    r"atlas(?:\s+shot)?|roofless\s+(?:shot|map|view)|top[-\s]?down|"
    r"spatial\s+map|"
    r"environment\s+reference(?:\s+(?:sheet|package|set))?|\bers\b|"
    r"character\s+reference\s+sheet|\bcrs\b|visual\s+sheet|"
    r"story\s?board|"
    r"voice\s+(?:clip|over|take)|soundtrack|sound\s+design|"
    r"\bvideo\b|\bclip\b|animation\s+sequence"
    r")\b",
    re.I,
)

_SCENE_CREATOR_COUNT_RE = re.compile(
    r"\b(?:generate|create|make|render|build)\b\s+"
    r"(?:(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"a\s+couple\s+of|a\s+few)\s+)"
    r"(?:scene\s+)?(?:shots?|images?)\b",
    re.I,
)

_VISUAL_BRIEF_RE = re.compile(
    r"\b(?:"
    r"metallic|silver|sci-?fi|futuristic|underground|facility|corridor|"
    r"interior|exterior|elevator|chamber|research|cinematic|wide|"
    r"master|establishing|lighting|lit|neon|concrete|steel|glass|"
    r"look(?:s| like)|atmosphere|color|palette|wardrobe|costume"
    r")\b",
    re.I,
)

_SOUND_QUESTION_RE = re.compile(
    r"\b(?:look and sound|how should this (?:place|space|scene) (?:look and )?sound|"
    r"ambient tension|hum of machinery|echoing footsteps|sterile silence|"
    r"sound on screen|what should (?:we|it) sound)\b",
    re.I,
)

_PROMPT_ONLY_RE = re.compile(
    r"\b(?:"
    r"(?:give|write|draft|show|send)\s+(?:me\s+)?(?:a\s+|the\s+|an?\s+)?"
    r"(?:flux\s+|qwen\s+|z-?image\s+|optimized\s+)?"
    r"prompt"
    r"|(?:just|only)\s+(?:the\s+|a\s+)?prompt"
    r"|don['’]?t\s+(?:generate|create|render|make)"
    r"|do\s+not\s+(?:generate|create|render|make)"
    r")\b",
    re.I,
)

# Timed prompts (Intelligence mission 2026-09-19, Phase 5): authoring a timed
# prompt is prompt-WRITING, never a generation job and never asset placement.
_TIMED_PROMPT_RE = re.compile(
    r"\b(?:timed\s+prompt|prompt\s+segment|prompt\s+clip|prompt\s+track)\b",
    re.I,
)

# Placement phrasing hands the turn to the Timeline prompt-segment tool
# instead of prompt authorship.
_TIMELINE_PLACEMENT_RE = re.compile(
    r"\b(?:add|put|place|insert|attach|drop)\b.*\b(?:on|to|into|in)\s+(?:the\s+)?timeline\b",
    re.I,
)

# A full production specification (duration/batches/aspect/engine) means the
# turn is a scene PREPARE/RUN request even when the word "prompt" appears.
_PRODUCTION_SPEC_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:seconds?|secs?|s)\b"
    r"|\b\d+\s*(?:batches?|shots?|frames?)\b"
    r"|\b\d+\s*:\s*\d+\b"
    r"|megapixels?"
    r"|\b(?:minimax|\bh3\b|ltx|wan|seedance|kling|veo)\b"
    r"|\bfps\b",
    re.I,
)

_GENERATE_NOW_RE = re.compile(
    r"\b(?:generate|create|render|make|do|run)\s+(?:it|that|this)(?:\s+now)?\b"
    r"|\bdo\s+it\b",
    re.I,
)

_VISUAL_REFERENCE_GEN_RE = re.compile(
    r"(?:"
    r"more like what you see attached|more like (?:this|the attached|what you see)|"
    r"look(?:s)? more like|match(?:es)? the (?:lighting|style|materials|visual)|"
    r"use this as (?:the )?(?:visual |style |environment )?reference|"
    r"created image more like|like (?:the |this )?(?:attached|reference)|"
    r"create another .{0,80}match"
    r")",
    re.I,
)


_USE_PROVIDER_FOR_IMAGE_RE = re.compile(
    r"\b(?:use|try|switch\s+to|go\s+with)\s+[A-Za-z][\w.\-]{1,40}"
    r".{0,80}\b(?:image|still|shot|picture|photo)\b",
    re.I,
)

_ENHANCE_STILL_RE = re.compile(
    r"\b(?:enhance|improve|refine|edit)\b.{0,80}"
    r"\b(?:last|previous|latest|this|that)\b.{0,40}"
    r"\b(?:image|still|shot|picture|photo)\b",
    re.I,
)


def is_visual_image_request(user_message: str) -> bool:
    """True when the creator is asking for a still image, not audio or multi-shot scene work."""

    text = (user_message or "").strip()
    if not text:
        return False
    from ...routing.generation_authority import looks_like_video_production_request

    if looks_like_video_production_request(text):
        return False
    if _NON_STILL_RE.search(text) or _SCENE_CREATOR_COUNT_RE.search(text):
        return False
    if _FIRST_FRAME_RE.search(text):
        return True
    if _ENHANCE_STILL_RE.search(text) or _USE_PROVIDER_FOR_IMAGE_RE.search(text):
        return True
    if _IMAGE_VERB_RE.search(text) and _STILL_OBJECT_RE.search(text):
        return True
    if _SCENE_PLUS_VISUAL_RE.search(text):
        return True
    if _CREATE_PLACE_RE.search(text):
        return True
    return False


def has_usable_visual_brief(user_message: str) -> bool:
    """True when the message already has enough visual content to generate."""

    text = (user_message or "").strip()
    if not text:
        return False
    words = text.split()
    if _FIRST_FRAME_RE.search(text) and _VISUAL_BRIEF_RE.search(text):
        return True
    if len(words) >= 18 and _VISUAL_BRIEF_RE.search(text):
        return True
    if len(words) >= 6 and _STILL_OBJECT_RE.search(text) and _VISUAL_BRIEF_RE.search(text):
        return True
    if len(words) >= 5 and _IMAGE_VERB_RE.search(text) and _VISUAL_BRIEF_RE.search(text):
        return True
    return False


def is_first_frame_image_request(user_message: str) -> bool:
    """First frame is an image job with video intent, not a video call."""

    text = (user_message or "").strip()
    if not text or _NON_STILL_RE.search(text):
        return False
    return bool(_FIRST_FRAME_RE.search(text))


def is_visual_reference_generation(user_message: str) -> bool:
    """True when the creator wants a new image matched to an attached/prior reference."""

    text = (user_message or "").strip()
    if not text or _NON_STILL_RE.search(text) or is_prompt_only_request(text):
        return False
    return bool(_VISUAL_REFERENCE_GEN_RE.search(text))


def is_visual_inspection_only(user_message: str) -> bool:
    """Describe/compare the picture — do not start a generation job."""

    text = (user_message or "").strip()
    if not text or is_visual_reference_generation(text) or is_visual_image_request(text):
        return False
    return bool(
        re.search(
            r"\b(?:what do you see|describe (?:this|the) (?:image|picture|photo)|"
            r"which (?:one|image) is|compare (?:these|the))\b",
            text,
            re.I,
        )
    )


def is_executable_image_turn(
    user_message: str,
    *,
    has_visual_reference: bool = False,
) -> bool:
    """Create-the-picture turn: image request plus a usable visual brief."""

    if is_visual_inspection_only(user_message):
        return False
    if is_visual_reference_generation(user_message) and (
        has_visual_reference or has_usable_visual_brief(user_message)
    ):
        return True
    if is_first_frame_image_request(user_message) and has_usable_visual_brief(user_message):
        return True
    return is_visual_image_request(user_message) and (
        has_usable_visual_brief(user_message) or has_visual_reference
    )


def is_non_visual_interrupt_question(question: str) -> bool:
    """True for interview questions that do not help still-image generation."""

    return bool(_SOUND_QUESTION_RE.search(question or ""))


def visual_only_clarification(
    user_message: str,
    *,
    has_visual_reference: bool = False,
) -> str | None:
    """Ask only if the image request has no visual brief. Never ask about sound."""

    if has_visual_reference or is_visual_reference_generation(user_message):
        return None
    if is_visual_image_request(user_message) and not has_usable_visual_brief(user_message):
        return "What should this image show — the place, who is in it, and the shot you want?"
    return None


def is_prompt_only_request(user_message: str) -> bool:
    """True when the creator wants a prompt written, not a generation job."""

    text = (user_message or "").strip()
    if not text:
        return False
    # Timed prompts (Intelligence mission Phase 5): authoring a timed prompt is
    # prompt-writing — unless the creator is asking to PLACE one on the
    # timeline (that is the prompt-segment tool, not authorship), or the turn
    # carries a full production specification (scene PREPARE/RUN, not
    # authorship).
    if _TIMED_PROMPT_RE.search(text) and not _TIMELINE_PLACEMENT_RE.search(text) and not _PRODUCTION_SPEC_RE.search(text):
        return True
    return bool(_PROMPT_ONLY_RE.search(text))


def _message_role_content(item: object) -> tuple[str, str]:
    if isinstance(item, dict):
        return str(item.get("role") or ""), str(item.get("content") or "")
    return str(getattr(item, "role", "") or ""), str(getattr(item, "content", "") or "")


def _looks_like_drafted_prompt(text: str) -> bool:
    blob = text or ""
    if re.search(
        r"\b(?:when you run|paste (?:this|into)|guidance(?: scale)?|steps\s*[:=]|cfg\s*[:=])\b",
        blob,
        re.I,
    ):
        return True
    return has_usable_visual_brief(blob) and len(blob.split()) >= 18


def inherit_visual_prompt_from_history(recent_messages: list[object] | None) -> str:
    """Prior visual brief or drafted prompt — used when the creator says generate it now."""

    for item in reversed(list(recent_messages or [])):
        role, content = _message_role_content(item)
        content = content.strip()
        if not content:
            continue
        if role == "user" and (
            is_executable_image_turn(content)
            or has_usable_visual_brief(content)
            or is_visual_image_request(content)
        ):
            return content
        if role == "assistant" and _looks_like_drafted_prompt(content):
            return content
    return ""


def is_generate_now_followup(
    user_message: str,
    recent_messages: list[object] | None = None,
) -> bool:
    """Short 'generate it now' after a brief or a drafted prompt."""

    text = (user_message or "").strip()
    if not text or is_prompt_only_request(text):
        return False
    if is_executable_image_turn(text):
        return False
    if not _GENERATE_NOW_RE.search(text):
        return False
    return bool(inherit_visual_prompt_from_history(recent_messages))


def generate_means_execute_valid(
    *,
    capability: str,
    dispatch: str,
    intent: str,
    job_id: str = "",
    execution_id: str = "",
    conversational_only: bool = False,
) -> bool:
    """GENERATE+READY without a submitted job is invalid."""

    ready = (
        str(intent).upper() == "EXECUTION"
        and str(dispatch).lower() == "deterministic"
        and str(capability) == "image.generate"
    )
    if not ready:
        return True
    if conversational_only:
        return False
    return bool(str(job_id or "").strip() or str(execution_id or "").strip())
