"""Deterministic scene-intent extraction. LLM JSON is never trusted without schema validation."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from .contracts import (
    CameraSpec,
    ProductionReferenceQuery,
    ScaleRelationship,
    SceneProductionSpec,
)
from .errors import SceneIntentParseError

_GENERATOR_ALIASES = {
    "minimax-h3": "minimax-h3",
    "minimax h3": "minimax-h3",
    "minimax": "minimax-h3",
    "h3": "minimax-h3",
    "hailuo": "minimax-h3",
    "ltx": "ltx-2.5",
    "ltx 2.5": "ltx-2.5",
    "ltx-2.5": "ltx-2.5",
    "seedance": "seedance-2.0",
    "seedance 2.0": "seedance-2.0",
}

_ASPECT_RE = re.compile(r"\b(\d{1,2}\s*:\s*\d{1,2})\b")
_DURATION_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*-?\s*seconds?\b", re.I)
_MP_RE = re.compile(
    r"\bmegapixels?\s*([0-9]+(?:\.[0-9]+)?)\b|\b([0-9]+(?:\.[0-9]+)?)\s*(?:megapixels?|mp)\b",
    re.I,
)
_BATCH_RE = re.compile(r"\b(?:single|one|1)\s+batch\b|\bbatch\s+count\s*[:=]?\s*(\d+)\b|\b(\d+)\s+batches?\b", re.I)
_NEW_SCENE_RE = re.compile(
    r"\b(?:build|create|make|prepare|set\s+up)\b.+\b(?:scene|shot|take)\b.+\btimeline\b"
    r"|\bbuild\s+(?:this|a|the)\s+scene\b"
    r"|\bscene\s+will\s+be\s+created\s+in\s+timeline\b",
    re.I,
)
_EDIT_RE = re.compile(
    r"\b(?:make|change|update|adjust|tweak|enlarge|slow|faster|bigger|smaller|more|less)\b",
    re.I,
)
_NEW_SHOT_RE = re.compile(r"\b(?:new|another|separate)\s+(?:scene|shot|take|batch)\b", re.I)
_ESTABLISHING_RE = re.compile(r"\bestablishing\s+shot\b", re.I)
_SHEET_RE = re.compile(
    r"(?:use|using|with|and also)\s+(?:the\s+)?"
    r"((?:[A-Za-z][\w'’]*)(?:\s+[A-Za-z][\w'’]*){0,4})\s+"
    r"(Character|Prop|Environment)\s+Reference\s+Sheet",
    re.I,
)
_REF_NAME_STOP = r"(?!inside\b|in\b|at\b|on\b|using\b|with\b|within\b|into\b|and\b|for\b|as\b)"
_REVERSED_REF_RE = re.compile(
    r"\b(Character|Prop|Environment)\s+reference(?:\s+sheet)?\s+of\s+"
    r"((?:[A-Za-z][\w'’]*)(?:\s+" + _REF_NAME_STOP + r"[A-Za-z][\w'’]*){0,4})",
    re.I,
)
_BARE_SHEET_RE = re.compile(
    r"((?:[A-Z][\w'’]*)(?:\s+" + _REF_NAME_STOP + r"[A-Za-z][\w'’]*){0,4})\s+"
    r"((?i:environment|prop|character))\s+reference\s+sheet",
)
_EXPLICIT_TAG_RE = re.compile(r"(?<![\w])([@#%])([A-Z][A-Za-z0-9]{2,}(?:[A-Z][A-Za-z0-9]+)*)\b")
_SETTING_RE = re.compile(
    r"(?:use|using|with|in)\s+(?:the\s+)?((?:[A-Za-z][\w'’]*)(?:\s+[A-Za-z][\w'’]*){0,4})\s+"
    r"as\s+the\s+setting\b",
    re.I,
)
_ENV_WORD_RE = re.compile(
    r"(?:in|inside|within|at)\s+(?:the\s+)?"
    r"((?:[A-Z][\w'’]*)(?:\s+" + _REF_NAME_STOP + r"[A-Za-z][\w'’]*){0,4})\s+"
    r"environment\b(?!\s+reference)",
)
_LENGTH_RE = re.compile(
    r"([A-Z][\w'’ -]{2,40}?)\s+(?:is|is over|over)\s+"
    r"(?:over\s+)?(\d+(?:\.\d+)?|a|an|one)\s*(kilometers?|km|meters?|metres?|m)\b",
    re.I,
)
_NUMBER_WORDS = {"a": 1.0, "an": 1.0, "one": 1.0}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _resolve_generator(text: str) -> str:
    lower = text.lower()
    if re.search(r"\bminimax(?:\s*-?\s*h3)?\b|\bh3\b|\bhailuo\b", lower):
        return "minimax-h3"
    if re.search(r"\bltx(?:\s*-?\s*2(?:[.\s]*[35])?)?\b", lower):
        return "ltx-2.5"
    if re.search(r"\bseedance\b|\bsee\s*dance\b", lower):
        return "seedance-2.0"
    return ""


def _expected_type(label: str) -> str:
    token = (label or "").strip().lower()
    if token.startswith("prop"):
        return "prop"
    if token.startswith("env"):
        return "environment"
    if token.startswith("char"):
        return "character"
    return ""


def _extract_references(text: str) -> list[ProductionReferenceQuery]:
    found: list[ProductionReferenceQuery] = []
    seen: set[str] = set()

    def _add(name: str, expected: str = "") -> None:
        name = _norm(name)
        name = re.sub(r"^(?:the|a|an|also)\s+", "", name, flags=re.I)
        # Patterns like _SETTING_RE can swallow the trailing "environment
        # reference sheet" into the captured name — identity names never
        # include the reference-sheet tail, so strip it before dedupe.
        name = re.sub(
            r"\s+(?:(?:environment|prop|character)\s+)?reference\s+(?:sheet|package|set)$",
            "",
            name,
            flags=re.I,
        ).strip()
        key = _normalize_name(name)
        if not key or key in seen:
            return
        seen.add(key)
        found.append(
            ProductionReferenceQuery(
                query=name,
                expected_type=expected or None,  # type: ignore[arg-type]
            )
        )

    for match in _SHEET_RE.finditer(text):
        _add(match.group(1), _expected_type(match.group(2)))
    for match in _REVERSED_REF_RE.finditer(text):
        _add(match.group(2), _expected_type(match.group(1)))
    for match in _BARE_SHEET_RE.finditer(text):
        _add(match.group(1), _expected_type(match.group(2)))
    for match in _EXPLICIT_TAG_RE.finditer(text):
        prefix, body = match.group(1), match.group(2)
        expected = {"@": "character", "#": "environment", "%": "prop"}.get(prefix, "")
        spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", body)
        _add(spaced, expected)
    for match in _SETTING_RE.finditer(text):
        _add(match.group(1), "environment")
    for match in _ENV_WORD_RE.finditer(text):
        _add(match.group(1), "environment")
    return found


def merge_reference_queries(
    spec: SceneProductionSpec,
    extra: list[tuple[str, str]],
) -> None:
    """Merge (name, hinted_type) pairs into spec.reference_queries, deduped."""
    seen = {_normalize_name(q.query) for q in spec.reference_queries}
    for name, hinted in extra:
        key = _normalize_name(name)
        if not key or key in seen:
            continue
        expected = _expected_type(hinted)
        seen.add(key)
        spec.reference_queries.append(
            ProductionReferenceQuery(query=_norm(name), expected_type=expected or None)  # type: ignore[arg-type]
        )


def _extract_scale(text: str) -> list[ScaleRelationship]:
    lengths: list[tuple[str, float, str]] = []
    for match in _LENGTH_RE.finditer(text):
        name = re.sub(r"^(?:the|and|also)\s+", "", _norm(match.group(1)), flags=re.I)
        raw_value = match.group(2).lower()
        value = _NUMBER_WORDS.get(raw_value, float(raw_value) if raw_value[0].isdigit() else 0.0)
        if value <= 0:
            continue
        unit = match.group(3).lower()
        meters = value * 1000.0 if unit.startswith("k") else value
        label = f"{value:g} {unit}" if raw_value not in _NUMBER_WORDS else f"over 1 {unit.rstrip('s')}"
        lengths.append((name, meters, label))
    if len(lengths) < 2:
        return []
    lengths.sort(key=lambda item: item[1], reverse=True)
    large, small = lengths[0], lengths[-1]
    if small[1] <= 0:
        return []
    ratio = large[1] / small[1]
    return [
        ScaleRelationship(
            subject_a=large[0],
            subject_b=small[0],
            relationship="extreme_size_difference" if ratio >= 50 else "relative_scale",
            approximate_ratio=f"{int(ratio)}:1" if ratio >= 10 else f"{ratio:.1f}:1",
            subject_a_length=large[2],
            subject_b_length=small[2],
            prompt_language=(
                f"Maintain accurate extreme scale separation. {large[0]} is {large[2]} "
                f"and must dwarf {small[0]} ({small[2]}). They must not appear similar in size."
            ),
        )
    ]


def _batch_count(text: str) -> int:
    if re.search(r"\b(?:single|one)\s+batch\b", text, re.I):
        return 1
    match = _BATCH_RE.search(text)
    if match:
        for group in match.groups():
            if group and group.isdigit():
                return max(1, int(group))
    return 1


def _quality(text: str, megapixels: float | None) -> str:
    if megapixels is not None:
        label = f"{megapixels:.1f}" if float(megapixels) != int(megapixels) or megapixels == 2 else f"{megapixels:g}"
        if megapixels == 2:
            label = "2.0"
        return f"megapixels-{label}"
    if re.search(r"\bmegapixels?\s*2(?:\.0)?\b|\b2(?:\.0)?\s*megapixels?\b", text, re.I):
        return "megapixels-2.0"
    return ""


def _camera(text: str) -> CameraSpec:
    shot = "establishing" if _ESTABLISHING_RE.search(text) else ""
    movement = ""
    if re.search(
        r"\brestrained\s+(?:camera|movement|dolly|shot|push)\b|\bno unnecessary camera shake\b|\bsmooth controlled\s+(?:camera|movement)\b",
        text,
        re.I,
    ):
        movement = "restrained cinematic"
    framing = "wide" if re.search(r"\bwide|establishing|orbit\b", text, re.I) else ""
    return CameraSpec(shot_type=shot, movement=movement, framing=framing)


def is_timeline_scene_prepare_request(message: str) -> bool:
    text = message or ""
    if not text.strip():
        return False
    if _NEW_SCENE_RE.search(text):
        return True
    if re.search(r"\btimeline\b", text, re.I) and re.search(
        r"\b(?:build|create|make|prepare)\b.+\b(?:scene|establishing shot)\b",
        text,
        re.I,
    ):
        return True
    return False


_RETRY_FOLLOW_UP_RE = re.compile(
    r"\b(?:retry(?:\s+that)?|try\s+again|prepare\s+again|reprocess)\b",
    re.I,
)


def is_follow_up_edit(message: str) -> bool:
    text = message or ""
    if is_timeline_scene_prepare_request(text) or _NEW_SHOT_RE.search(text):
        return False
    if _RETRY_FOLLOW_UP_RE.search(text):
        return True
    return bool(_EDIT_RE.search(text)) and not bool(
        re.search(r"\b(?:generate|render)\s+(?:this\s+|the\s+)?shot\b", text, re.I)
    )


def mentions_aspect_ratio(message: str) -> bool:
    return bool(_ASPECT_RE.search(message or ""))


def mentions_megapixels(message: str) -> bool:
    return bool(_MP_RE.search(message or ""))


def mentions_batch_count(message: str) -> bool:
    """True when the creator explicitly states a batch count — including
    "single batch" / "one batch" / "1 batch". A follow-up that says so must be
    honored, not overwritten by the prior scene's count."""
    text = message or ""
    return bool(_BATCH_RE.search(text))


def production_request_id(project_id: str, spec: SceneProductionSpec) -> str:
    refs = ",".join(sorted(_normalize_name(q.query) for q in spec.reference_queries))
    raw = "|".join(
        [
            project_id,
            spec.generator_id,
            str(spec.duration_seconds),
            spec.aspect_ratio,
            spec.quality,
            str(spec.batch_count),
            refs,
            _normalize_name(spec.camera.shot_type),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def parse_scene_intent(
    message: str,
    *,
    project_id: str,
    follow_up: bool = False,
) -> SceneProductionSpec:
    raw_message = (message or "").strip()
    text = _norm(message)
    if not text:
        raise SceneIntentParseError("The scene request was empty.")

    generator = _resolve_generator(text) or ("minimax-h3" if follow_up else "")
    duration_match = _DURATION_RE.search(text)
    duration = float(duration_match.group(1)) if duration_match else (10.0 if follow_up else 0.0)
    aspect_match = _ASPECT_RE.search(text)
    aspect = aspect_match.group(1).replace(" ", "") if aspect_match else ("16:9" if follow_up else "")
    mp_match = _MP_RE.search(text)
    megapixels = None
    if mp_match:
        raw = mp_match.group(1) or mp_match.group(2)
        megapixels = float(raw)
    if megapixels is None and re.search(r"\bmegapixels?\s*2(?:\.0)?\b", text, re.I):
        megapixels = 2.0

    spec = SceneProductionSpec(
        project_id=project_id,
        generator_id=generator or "minimax-h3",
        duration_seconds=duration or 10.0,
        aspect_ratio=aspect or "16:9",
        quality=_quality(text, megapixels),
        megapixels=megapixels,
        batch_count=_batch_count(text),
        source_user_prompt=raw_message,
        scene_intent="",
        camera_intent=_camera(text).shot_type,
        reference_queries=_extract_references(text),
        camera=_camera(text),
        scale_relationships=_extract_scale(text),
        follow_up=follow_up,
        preparation_state="parsing",
    )
    spec.production_request_id = production_request_id(project_id, spec)
    if not spec.generator_id:
        raise SceneIntentParseError("Could not resolve a video generator from the request.")
    return spec


def validate_parsed_spec(data: dict[str, Any]) -> SceneProductionSpec:
    try:
        return SceneProductionSpec.model_validate(data)
    except Exception as exc:
        raise SceneIntentParseError(f"Scene intent failed schema validation: {exc}") from exc
