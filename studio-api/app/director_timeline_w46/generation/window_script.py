"""Master is the Timed Prompt authority.

A later window that already has story text is left alone. A later window
with no story receives one slice from the scene-level prompt, stored on
Master before any provider submit. Generate does not slice again at submit.
Continuation headers and window-scope notes are never stored.
"""

from __future__ import annotations

import re
from typing import Any

_STRUCTURED_HEADING = re.compile(
    r"(?m)^(SHOT|ENVIRONMENT|SUBJECTS|ACTION|CAMERA|MOTION|CONTINUITY|CONSTRAINTS|NEGATIVE)\b"
)
_CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")
_MACHINE_TAIL = re.compile(
    r"(?s)\n*WINDOW SCOPE\b.*|\n*\[CONTINUATION window[^\]]*\][^\n]*"
)
_LANGUAGE_NAMES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "ja": "Japanese",
    "zh": "Chinese",
    "ko": "Korean",
    "pt": "Portuguese",
}


def is_structured_scene_prompt(text: str) -> bool:
    """Compiler section prompts stay on the existing window-scope path."""
    return bool(_STRUCTURED_HEADING.search(text or ""))


def story_blocks(text: str) -> list[str]:
    body = _MACHINE_TAIL.sub("", text or "").strip()
    return [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip()]


def slice_story_for_window(text: str, index: int, count: int) -> str:
    """Contiguous share of an unstructured full-scene script for one window."""
    raw = (text or "").strip()
    if count <= 1 or index < 0 or index >= count or is_structured_scene_prompt(raw):
        return raw
    blocks = story_blocks(raw)
    if len(blocks) < 2:
        return raw
    base, extra = divmod(len(blocks), count)
    sizes = [base + (1 if i < extra else 0) for i in range(count)]
    start = sum(sizes[:index])
    chosen = blocks[start : start + sizes[index]]
    return "\n\n".join(chosen).strip()

def h3_spoken_lock(language: str | None, prompt: str) -> str:
    """Language line for H3. The Comfy node has no language control.

    MiniMax otherwise speaks Chinese. An explicit non-English scene language
    is honored. A creator script that is already in another script is not
    overwritten with English.
    """
    code = str(language or "").strip().lower().split("-")[0]
    body = prompt or ""
    if _CJK.search(body) and code in {"", "en"}:
        return ""
    if not code:
        code = "en"
    name = _LANGUAGE_NAMES.get(code)
    if not name:
        return ""
    if code == "en":
        return (
            "Spoken dialogue language: English. "
            "Every spoken word is English. "
            "Do not speak Chinese or any other language."
        )
    return (
        f"Spoken dialogue language: {name}. "
        f"Speak every scripted line in {name}. "
        "Do not switch to another language."
    )


def scrub_observation_line(text: str) -> str:
    """Drop Qwen Omni text that is not English before it can enter a prompt.

    A Chinese-only observation is a hallucination relative to an English
    scene. Mixed lines keep their English words and lose the foreign script.
    """
    raw = (text or "").strip()
    if not raw:
        return ""
    if _CJK.search(raw) and not re.search(r"[A-Za-z]{3,}", raw):
        return ""
    cleaned = _CJK.sub("", raw)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,;:-")
    return cleaned


def _planned(batch: Any) -> float:
    dur = getattr(batch, "duration", None)
    try:
        return float(getattr(dur, "plannedDuration", None) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def story_body(text: str) -> str:
    """Creator story with machine window headers removed."""
    return _MACHINE_TAIL.sub("", text or "").strip()


def prompt_story_ready(text: str | None) -> bool:
    """True when stored text has a story. A bare continuation stub is not ready."""
    return bool(story_blocks(text or ""))


def batch_prompt_ready(batch: Any) -> bool:
    segs = list(getattr(batch, "promptSegments", None) or [])
    if not segs:
        return False
    return prompt_story_ready(str(getattr(segs[0], "text", "") or ""))


def _segment_text(batch: Any) -> str:
    segs = list(getattr(batch, "promptSegments", None) or [])
    if not segs:
        return ""
    return str(getattr(segs[0], "text", "") or "").strip()


def _segment_length(batch: Any) -> float:
    segs = list(getattr(batch, "promptSegments", None) or [])
    if not segs:
        return 0.0
    try:
        return float(getattr(segs[0], "length", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


_VISUAL_REFERENCE_KINDS = {
    "entity",
    "image",
    "character",
    "place",
    "prop",
    "environment",
    "start_image",
}
_VISUAL_REFERENCE_ROLES = {
    "character",
    "place",
    "prop",
    "environment",
    "entity_reference",
    "start_image",
    "start",
    "i2v_start",
    "opening",
}


def _visual_reference_rows(batch: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ref in getattr(batch, "references", None) or []:
        if not isinstance(ref, dict) or not str(ref.get("assetId") or "").strip():
            continue
        kind = str(ref.get("kind") or "").lower()
        role = str(ref.get("role") or "").lower()
        if kind in _VISUAL_REFERENCE_KINDS or role in _VISUAL_REFERENCE_ROLES:
            rows.append(dict(ref))
    return rows


def carry_root_references_to_empty_windows(master: Any) -> bool:
    """Later windows with no pictures use the first window's checked cast.

    A continuation window is the same scene. Seedance Mini cannot render that
    window as text alone, and a fresh execution window does not inherit the
    root's character, place, and prop bindings by itself.
    """
    blocks = list(getattr(master, "batchBlocks", None) or [])
    blocks.sort(key=lambda batch: int(getattr(batch, "order", 0) or 0))
    if len(blocks) < 2:
        return False
    root = blocks[0]
    root_rows = _visual_reference_rows(root)
    root_segs = list(getattr(root, "promptSegments", None) or [])
    root_seg = root_segs[0] if root_segs else None
    root_ids = list(getattr(root_seg, "referenceBindingIds", None) or []) if root_seg is not None else []
    root_names = list(getattr(root_seg, "referenceNameBindings", None) or []) if root_seg is not None else []
    if not root_rows and not root_ids and not root_names:
        return False
    changed = False
    for batch in blocks[1:]:
        if not _visual_reference_rows(batch) and root_rows:
            kept = [
                ref
                for ref in (getattr(batch, "references", None) or [])
                if isinstance(ref, dict)
            ]
            batch.references = kept + [dict(row) for row in root_rows]
            changed = True
        segs = list(getattr(batch, "promptSegments", None) or [])
        if not segs or root_seg is None:
            continue
        seg = segs[0]
        has_ids = list(getattr(seg, "referenceBindingIds", None) or [])
        has_names = list(getattr(seg, "referenceNameBindings", None) or [])
        if has_ids or has_names or not (root_ids or root_names):
            continue
        seg.referenceBindingIds = list(root_ids)
        copied = []
        for row in root_names:
            if hasattr(row, "model_copy"):
                copied.append(row.model_copy(deep=True))
            elif isinstance(row, dict):
                copied.append(dict(row))
            else:
                copied.append(row)
        seg.referenceNameBindings = copied
        changed = True
    return changed


def _store_window_story(batch: Any, text: str) -> None:
    """Write one already-sliced story onto an empty window. Does not prefix it."""
    segs = list(getattr(batch, "promptSegments", None) or [])
    if segs:
        segs[0].text = text
        return
    from ..contracts import TimelinePromptSegment

    planned = _planned(batch) or 15.0
    batch.promptSegments = [TimelinePromptSegment(text=text, start=0.0, length=planned)]


def assign_later_window_scripts(master: Any) -> bool:
    """Persist per-window story text, then carry pictures onto empty windows.

    Case A: a later window that already has story text stays unchanged.
    Case B: a later window with no story receives one slice of the root story.
    The slice is stored here, before submit. A second call does not rewrite it.
    Continuation headers and window-scope notes are not stored. This function
    does not read project identity.
    """
    blocks = list(getattr(master, "batchBlocks", None) or [])
    blocks.sort(key=lambda batch: int(getattr(batch, "order", 0) or 0))
    if len(blocks) < 2:
        return False
    changed = carry_root_references_to_empty_windows(master)
    root_text = story_body(_segment_text(blocks[0]))
    if not prompt_story_ready(root_text):
        return changed
    count = len(blocks)
    for index, batch in enumerate(blocks[1:], start=1):
        current = _segment_text(batch)
        if prompt_story_ready(current):
            continue
        sliced = story_body(slice_story_for_window(root_text, index, count))
        if not sliced or sliced == current:
            continue
        _store_window_story(batch, sliced)
        changed = True
    return changed
