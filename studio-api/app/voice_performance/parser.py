"""Performance markup parser → provider-neutral segments + validation issues."""

from __future__ import annotations

import re
import uuid
from typing import Any

from .schemas import PerformanceSegmentOut, ValidationIssue
from .tag_registry import EMOTIONS, get_definition, is_blocked_key

# Bracket tags: [emotion: amused] or [whisper] or [pause: 280ms]
_BRACKET = re.compile(r"\[([^\]]+)\]")
# XML-ish: <emotion value="annoyed">...</emotion>
_XML_OPEN = re.compile(r"<(\w+)\s+value=\"([^\"]*)\"\s*>", re.I)
_XML_CLOSE = re.compile(r"</(\w+)\s*>", re.I)
# Speaker line: NAME at start of line (all caps-ish)
_SPEAKER = re.compile(r"^([A-Z][A-Z0-9_\- ]{0,40})\s*$")

_DURATION = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*(ms|s|sec|seconds)?\s*$", re.I)

_PAUSE_WORDS = {"short": 150, "medium": 400, "long": 800, "beat": 500}


def parse_duration_ms(raw: str) -> tuple[int | None, ValidationIssue | None]:
    s = (raw or "").strip().lower()
    if s in _PAUSE_WORDS:
        return _PAUSE_WORDS[s], ValidationIssue(
            code="DURATION_NORMALIZED",
            severity="warning",
            message=f"Normalized pause '{s}' → {_PAUSE_WORDS[s]}ms",
            tagKey="pause",
        )
    m = _DURATION.match(s)
    if not m:
        return None, ValidationIssue(
            code="INVALID_DURATION",
            severity="error",
            message=f"Invalid duration: {raw}",
            tagKey="pause",
        )
    val = float(m.group(1))
    unit = (m.group(2) or "ms").lower()
    if unit in ("s", "sec", "seconds"):
        ms = int(val * 1000)
    else:
        ms = int(val)
    if ms < 0:
        return None, ValidationIssue(
            code="INVALID_DURATION",
            severity="blocked",
            message="Negative durations are not allowed.",
            tagKey="pause",
        )
    return ms, None


def _parse_tag_body(body: str) -> tuple[str, str]:
    body = body.strip()
    if ":" in body:
        key, _, rest = body.partition(":")
        return key.strip().lower(), rest.strip()
    return body.strip().lower(), ""


def parse_markup(source_text: str) -> dict[str, Any]:
    """Parse canonical bracket/XML markup into segments + issues."""
    issues: list[ValidationIssue] = []
    lines = (source_text or "").replace("\r\n", "\n").split("\n")
    speaker: str | None = None
    pending: dict[str, Any] = {}
    segments: list[PerformanceSegmentOut] = []
    order = 0
    open_xml: list[tuple[str, str]] = []

    def flush_text(text: str) -> None:
        nonlocal order, pending
        t = text.strip()
        if not t and not pending:
            return
        seg_type = "speech"
        emotion = None
        delivery: dict[str, Any] = {}
        pace = pending.pop("pace", None)
        volume = pending.pop("volume", None)
        pitch = pending.pop("pitch", None)
        if "emotion" in pending:
            emotion = {"primary": pending.pop("emotion"), "intensity": pending.pop("intensity", 0.7)}
        if "delivery" in pending:
            delivery["style"] = pending.pop("delivery")
        if pending.get("whisper"):
            delivery["whisper"] = True
            pending.pop("whisper", None)
        if pending.get("shout"):
            delivery["shout"] = True
            pending.pop("shout", None)
        reaction = pending.pop("reaction", None)
        pause_ms = pending.pop("pause_ms", None)
        beat = pending.pop("beat", None)
        silence_ms = pending.pop("silence_ms", None)
        breath = pending.pop("breath", None)
        overlap = pending.pop("overlap", None)
        interrupt = pending.pop("interrupt", None)
        emphasis = pending.pop("emphasis", [])
        pron = pending.pop("pronunciation", [])
        rel = pending.pop("relationship_tone", None)
        notes = pending.pop("notes", None)

        if silence_ms is not None and not t:
            seg_type = "silence"
        elif reaction and not t:
            seg_type = "reaction"
        elif pause_ms is not None and not t:
            seg_type = "pause"
        elif beat and not t:
            seg_type = "beat"

        # Conflict: two emotions without transition
        if emotion and pending.get("_prior_emotion") and pending.get("_prior_emotion") != emotion["primary"]:
            # already consumed — track on segment notes
            pass

        order += 1
        segments.append(
            PerformanceSegmentOut(
                id=str(uuid.uuid4()),
                orderIndex=order,
                segmentType=seg_type,
                text=t or None,
                emotion=emotion,
                delivery=delivery or None,
                pace=pace,
                volume=volume,
                pitch=pitch,
                emphasis=[{"word": e} for e in emphasis] if isinstance(emphasis, list) else [],
                pronunciationOverrides=[{"word": p} for p in pron] if isinstance(pron, list) else [],
                reactionKey=reaction,
                pauseMs=pause_ms if seg_type in ("pause", "speech") else (silence_ms if seg_type == "silence" else pause_ms),
                beatType=beat,
                breathType=breath,
                overlapGroup=overlap,
                interruptTarget=interrupt,
                expectedDurationMs=silence_ms or pause_ms,
                relationshipContext={"tone": rel} if rel else None,
                notes=notes,
                status="pending",
            )
        )
        # Clear one-shot flags that shouldn't stick across lines
        for k in list(pending.keys()):
            if k.startswith("_"):
                continue
            pending.pop(k, None)

    def apply_tag(key: str, value: str, *, start: int = 0, end: int = 0) -> None:
        if is_blocked_key(key):
            issues.append(
                ValidationIssue(
                    code="UNSAFE_TAG",
                    severity="blocked",
                    message=f"Unsafe directive rejected: {key}",
                    tagKey=key,
                    sourceRange={"start": start, "end": end},
                )
            )
            return
        defn = get_definition(key)
        if defn is None:
            issues.append(
                ValidationIssue(
                    code="UNKNOWN_TAG",
                    severity="warning",
                    message=f"Unknown tag [{key}] ignored for runtime.",
                    tagKey=key,
                    sourceRange={"start": start, "end": end},
                )
            )
            return
        if key in ("pause",):
            ms, issue = parse_duration_ms(value or "medium")
            if issue:
                issues.append(issue)
            if ms is not None:
                # If we already have pending speech attrs, attach pause after text flush
                if any(k in pending for k in ("emotion", "delivery", "pace")) or not value:
                    pending["pause_ms"] = ms
                else:
                    pending["pause_ms"] = ms
                    flush_text("")
            return
        if key == "silence":
            ms, issue = parse_duration_ms(value or "0")
            if issue:
                issues.append(issue)
            if ms is not None:
                pending["silence_ms"] = ms
                flush_text("")
            return
        if key == "beat":
            pending["beat"] = value or "beat"
            flush_text("")
            return
        if key == "reaction":
            pending["reaction"] = value or "custom"
            # reaction-only if next content empty — will flush on next empty or after
            return
        if key == "emotion":
            ev = (value or "neutral").strip().lower()
            if defn.allowed_values and ev not in defn.allowed_values:
                # allow close synonyms? else warning
                if ev not in EMOTIONS:
                    issues.append(
                        ValidationIssue(
                            code="UNKNOWN_EMOTION",
                            severity="warning",
                            message=f"Emotion '{ev}' not in registry; treating as prompt-guided custom.",
                            tagKey="emotion",
                        )
                    )
            if pending.get("emotion") and pending["emotion"] != ev:
                issues.append(
                    ValidationIssue(
                        code="CONFLICTING_EMOTION",
                        severity="warning",
                        message=f"Conflicting emotions on same segment: {pending['emotion']} vs {ev}",
                        tagKey="emotion",
                    )
                )
            pending["emotion"] = ev
            return
        if key in ("interrupt", "interrupts"):
            pending["interrupt"] = value
            return
        if key == "overlap":
            pending["overlap"] = value
            return
        if key in ("whisper", "shout", "cut_off", "resume"):
            pending[key] = True
            return
        if key == "emphasis":
            pending.setdefault("emphasis", []).append(value)
            return
        if key == "pronunciation":
            pending.setdefault("pronunciation", []).append(value)
            return
        if key == "delivery":
            pending["delivery"] = value
            return
        if key in ("pace", "volume", "pitch", "breath", "timing", "relationship_tone"):
            pending[key if key != "timing" else "notes"] = value
            return
        pending[key] = value

    for line in lines:
        # XML open/close on line
        xm = _XML_OPEN.search(line)
        if xm:
            open_xml.append((xm.group(1).lower(), xm.group(2)))
            apply_tag(xm.group(1).lower(), xm.group(2))
            line = _XML_OPEN.sub("", line)
        if _XML_CLOSE.search(line):
            open_xml.clear()
            line = _XML_CLOSE.sub("", line)

        sp = _SPEAKER.match(line.strip())
        if sp and "[" not in line:
            # Flush any pending reaction-only
            if pending.get("reaction") and not any(
                k in pending for k in ("emotion", "delivery", "pace")
            ):
                flush_text("")
            speaker = sp.group(1).strip()
            continue

        # Extract bracket tags then remaining text
        pos = 0
        text_parts: list[str] = []
        for m in _BRACKET.finditer(line):
            before = line[pos : m.start()]
            if before.strip():
                text_parts.append(before)
            key, value = _parse_tag_body(m.group(1))
            apply_tag(key, value, start=m.start(), end=m.end())
            # Standalone reaction/pause after text on same line: if text_parts already, flush first
            if key in ("reaction", "pause", "silence", "beat") and text_parts:
                flush_text(" ".join(text_parts))
                text_parts = []
                if key == "reaction":
                    flush_text("")
            pos = m.end()
        tail = line[pos:]
        if tail.strip():
            text_parts.append(tail)
        if text_parts:
            flush_text(" ".join(text_parts))
        elif pending.get("reaction") or pending.get("pause_ms") is not None or pending.get("silence_ms") is not None or pending.get("beat"):
            flush_text("")

    # Trailing pending reaction
    if pending:
        flush_text("")

    status = "resolved"
    if any(i.severity == "blocked" for i in issues):
        status = "blocked"
    elif any(i.severity == "error" for i in issues):
        status = "needs_review"
    elif any(i.severity == "warning" for i in issues):
        status = "resolved_with_warning"

    return {
        "ok": status in ("resolved", "resolved_with_warning"),
        "status": status,
        "sourceText": source_text,
        "speaker": speaker,
        "segments": segments,
        "issues": issues,
        "mock": False,
    }
