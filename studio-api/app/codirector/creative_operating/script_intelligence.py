"""Script / source-asset intelligence — role-aware, format-agnostic."""

from __future__ import annotations

import re
from typing import Any

from .identity import resolve_identity


def detect_source_role(filename: str = "", mime: str = "", hint: str = "") -> str:
    corpus = f"{filename} {mime} {hint}".lower()
    if re.search(r"\b(script|screenplay|\.fountain|\.fdx)\b", corpus):
        return "script"
    if re.search(r"\b(treatment|outline)\b", corpus):
        return "treatment"
    if re.search(r"\b(storyboard)\b", corpus):
        return "storyboard"
    if re.search(r"\b(image|png|jpg|jpeg|webp|reference)\b", corpus):
        return "image"
    if re.search(r"\b(video|mp4|mov)\b", corpus):
        return "video"
    if re.search(r"\b(audio|wav|mp3|voice)\b", corpus):
        return "audio"
    return "source"


def parse_script_breakdown(
    text: str,
    *,
    alias_map: dict[str, str] | None = None,
    installment_hint: str | None = None,
) -> dict[str, Any]:
    """Lightweight structural parse — not a full screenplay parser."""
    body = text or ""
    scenes: list[dict[str, Any]] = []
    # Common scene headings
    for i, match in enumerate(
        re.finditer(r"^(INT\.|EXT\.|INT/EXT\.|I/E\.)\s+(.+)$", body, flags=re.I | re.M)
    ):
        heading = match.group(0).strip()
        scenes.append(
            {
                "index": i + 1,
                "heading": heading[:200],
                "location": match.group(2).strip()[:120],
            }
        )
        if len(scenes) >= 40:
            break

    # Character cues: ALL CAPS lines short enough to be speakers
    raw_names: list[str] = []
    for match in re.finditer(r"^([A-Z][A-Z0-9 \-\.'']{1,40})$", body, flags=re.M):
        name = match.group(1).strip()
        if name in {"INT", "EXT", "FADE IN", "FADE OUT", "CUT TO", "SMASH CUT"}:
            continue
        if len(name.split()) > 5:
            continue
        raw_names.append(name.title() if name.isupper() else name)

    characters: list[dict[str, Any]] = []
    seen: set[str] = set()
    for name in raw_names:
        resolved = resolve_identity(name, alias_map)
        if resolved.get("rejected") or not resolved.get("canonicalName"):
            continue
        key = resolved["canonicalName"].lower()
        if key in seen:
            continue
        seen.add(key)
        characters.append(resolved)

    locations = []
    seen_loc: set[str] = set()
    for sc in scenes:
        loc = str(sc.get("location") or "").split("-")[0].strip()
        if loc and loc.lower() not in seen_loc:
            seen_loc.add(loc.lower())
            locations.append(loc)

    installment = installment_hint
    if not installment:
        m = re.search(r"\b(episode|chapter|act)\s*(\d+)\b", body, flags=re.I)
        if m:
            installment = f"{m.group(1).title()} {m.group(2)}"

    summary = ""
    if scenes:
        summary = f"{len(scenes)} scenes parsed"
        if characters:
            summary += f"; {len(characters)} speaking characters identified"
        if installment:
            summary += f"; installment={installment}"
    elif characters:
        summary = f"{len(characters)} character identities identified from source text"

    return {
        "role": "script",
        "installment": installment,
        "scenes": scenes,
        "characters": characters,
        "locations": locations[:30],
        "summary": summary or "Source retained; professional breakdown pending richer content.",
        "openQuestions": _script_open_questions(scenes, characters),
        "canonState": "INFERRED",
    }


def _script_open_questions(scenes: list[dict], characters: list[dict]) -> list[str]:
    qs: list[str] = []
    if scenes and not any("day" in str(s.get("heading", "")).lower() or "night" in str(s.get("heading", "")).lower() for s in scenes[:5]):
        qs.append("Should scene headings lock time-of-day for continuity?")
    if characters and len(characters) >= 2:
        qs.append("Which relationship between the primary characters drives this installment?")
    if scenes and len(scenes) >= 3:
        qs.append("What must change between the opening and closing scene of this installment?")
    return qs[:3]


def build_installment_record(breakdown: dict[str, Any]) -> dict[str, Any]:
    """Clean Project Bible installment shape — not an attachment note."""
    return {
        "title": breakdown.get("installment") or "Installment",
        "overview": breakdown.get("summary") or "",
        "script": {"sceneCount": len(breakdown.get("scenes") or [])},
        "sceneBreakdown": breakdown.get("scenes") or [],
        "characters": [c.get("canonicalName") for c in (breakdown.get("characters") or []) if c.get("canonicalName")],
        "locations": breakdown.get("locations") or [],
        "continuity": {"openQuestions": breakdown.get("openQuestions") or []},
        "productionDetails": {},
        "openQuestions": breakdown.get("openQuestions") or [],
        "sourceRole": "script",
        "canonState": breakdown.get("canonState") or "INFERRED",
    }
