"""Script continuity checks — recommendations, not absolute judgments."""

from __future__ import annotations

from typing import Any

from .models import ScriptDocument


def analyze_continuity(doc: ScriptDocument) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    seen_chars: set[str] = set()
    last_location: str | None = None
    for el in sorted(doc.elements, key=lambda e: e.order):
        if el.type == "scene_heading":
            text = (el.text or "").upper()
            # crude location extract
            loc = text
            for prefix in ("INT.", "EXT.", "INT./EXT.", "EXT./INT.", "I/E."):
                if text.startswith(prefix):
                    loc = text[len(prefix) :].split("-")[0].strip()
                    break
            if last_location and loc and loc == last_location:
                findings.append(
                    {
                        "severity": "informational",
                        "code": "SAME_LOCATION_SEQUENCE",
                        "message": f"Consecutive scenes share location “{loc}”.",
                        "elementId": el.id,
                    }
                )
            last_location = loc or last_location
        if el.type == "character":
            name = (el.text or "").strip().upper()
            if name and name not in seen_chars:
                # first appearance is fine; track
                seen_chars.add(name)
        if el.type == "dialogue":
            speaker = str((el.metadata or {}).get("speaker") or "").upper()
            if speaker and speaker not in seen_chars:
                findings.append(
                    {
                        "severity": "possible_concern",
                        "code": "DIALOGUE_BEFORE_CHARACTER_CUED",
                        "message": f"Dialogue may lack a prior character cue for “{speaker}”.",
                        "elementId": el.id,
                    }
                )
    # Identical voice heuristic: same first 5 words across two characters
    by_char: dict[str, list[str]] = {}
    current = ""
    for el in doc.elements:
        if el.type == "character":
            current = (el.text or "").strip().upper()
        elif el.type == "dialogue" and current:
            by_char.setdefault(current, []).append((el.text or "").strip().lower()[:40])
    # light check
    if len(by_char) >= 2:
        samples = {k: (v[0] if v else "") for k, v in by_char.items()}
        vals = list(samples.values())
        if vals[0] and vals.count(vals[0]) > 1:
            findings.append(
                {
                    "severity": "likely_inconsistency",
                    "code": "SIMILAR_OPENING_DIALOGUE",
                    "message": "Multiple characters open with very similar dialogue phrasing.",
                    "elementId": None,
                }
            )
    return findings
