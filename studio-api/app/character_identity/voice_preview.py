"""Voice Studio generate helpers — character-bound design briefs and aliases.

Do not silently change character, engine, or device. Full-quality generate
keeps the chosen Qwen3-TTS Voice Design worker warm.
"""

from __future__ import annotations

from typing import Any

DESIGN_VRAM_MIB_REQUIRED = 4096
PREVIEW_VRAM_MIB_REQUIRED = DESIGN_VRAM_MIB_REQUIRED
PREVIEW_QUALITY_LABEL = "full"
PREVIEW_ENGINE = "qwen3-tts"
PREVIEW_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
PREVIEW_MAX_NEW_TOKENS = 96
PREVIEW_WORD_LIMIT = 14

PREVIEW_VARIATIONS: tuple[str, ...] = (
    "",
    "Keep the exact same person. Slightly brighter and more forward.",
    "Keep the exact same person. Slightly warmer and closer-mic.",
    "Keep the exact same person. Slightly more intimate, quieter energy.",
)


def _body_field(body: Any, *names: str, default: Any = None) -> Any:
    if isinstance(body, dict):
        for name in names:
            if name in body and body[name] is not None:
                return body[name]
        return default
    for name in names:
        value = getattr(body, name, None)
        if value is not None:
            return value
    return default


def preview_sample_line(script: str | None, fallback: str) -> str:
    text = " ".join((script or "").split()) or " ".join((fallback or "").split())
    if not text:
        text = "Hey. Listen close — this is only a voice preview."
    words = text.split()
    if len(words) > PREVIEW_WORD_LIMIT:
        return " ".join(words[:PREVIEW_WORD_LIMIT])
    return text


def brief_from_identity_fields(
    *,
    sex: str | None = None,
    age: str | None = None,
    accent: str | None = None,
    archetype: str | None = None,
    prompt: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    brief: dict[str, Any] = dict(extra or {})
    gender = (sex or brief.get("gender") or "").strip()
    if gender.lower() in {"female", "f"}:
        brief["gender"] = "Female"
    elif gender.lower() in {"male", "m"}:
        brief["gender"] = "Male"
    elif gender:
        brief["gender"] = gender
    if age:
        brief["perceivedAge"] = str(age).strip()
    if accent:
        brief["accent"] = str(accent).strip()
    if archetype:
        brief["archetype"] = str(archetype).strip()
    direction = (prompt or brief.get("additionalDirection") or "").strip()
    if direction:
        brief["additionalDirection"] = direction
    brief.setdefault("language", "English")
    return brief


def variation_instruct(base_prompt: str, index: int) -> str:
    hint = PREVIEW_VARIATIONS[index % len(PREVIEW_VARIATIONS)]
    core = " ".join((base_prompt or "").split())
    if not hint:
        return core
    return f"{core} {hint}".strip()


def _body_get(body: Any, *names: str, default: Any = None) -> Any:
    if isinstance(body, dict):
        for name in names:
            if name in body and body[name] is not None:
                return body[name]
        return default
    for name in names:
        value = getattr(body, name, None)
        if value is not None:
            return value
    return default


def normalize_design_request(body: Any) -> dict[str, Any]:
    """Accept the Voice Identity UI aliases without dropping the frozen generate contract."""
    design_brief = _body_get(body, "designBrief", "design_brief")
    if not isinstance(design_brief, dict):
        design_brief = None
    brief = brief_from_identity_fields(
        sex=_body_get(body, "sex"),
        age=_body_get(body, "age"),
        accent=_body_get(body, "accent") or (design_brief or {}).get("accent"),
        archetype=_body_get(body, "archetype") or (design_brief or {}).get("archetype"),
        prompt=_body_get(body, "prompt", "masterPrompt", "master_prompt"),
        extra=design_brief,
    )
    test_line = _body_get(body, "testLine", "script", "test_line")
    count = _body_get(body, "sampleCount", "candidateCount", "candidate_count", default=3)
    master_raw = _body_get(body, "masterPrompt", "prompt", "master_prompt")
    master = (str(master_raw).strip() if master_raw else "") or None
    return {
        "designBrief": brief,
        "testLine": (str(test_line).strip() if test_line else None),
        "candidateCount": max(1, min(int(count or 3), 6)),
        "masterPrompt": master,
        "name": _body_get(body, "name"),
        "method": _body_get(body, "method") or "design",
        "parentCandidateId": _body_get(body, "parentCandidateId", "parent_candidate_id"),
        "appendToVoiceId": _body_get(body, "appendToVoiceId", "append_to_voice_id"),
        "promptDocument": _body_get(body, "promptDocument", "prompt_document"),
    }
