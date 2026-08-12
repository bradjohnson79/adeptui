"""Classify a natural-language correction instruction.

LLM_INTERPRETS: when a provider is available, an LLM classifies intent and
targets. A deterministic heuristic classifier is the fallback. Apply is always
deterministic (DETERMINISTIC_CODE_APPLIES); classification only *interprets*.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from sqlalchemy.orm import Session

from ...conversation.snapshot import load_snapshot
from .contracts import (
    CorrectionPreview,
    CorrectionTarget,
    CorrectionType,
    EntityReclassification,
    ProposedChange,
)

_JSON_RE = re.compile(r"```json\s*([\s\S]*?)```", re.IGNORECASE)
_BRACE_RE = re.compile(r"\{[\s\S]*\}")

# High-stakes entity kinds: removing/renaming these without a clear target
# requires clarification rather than a guess (CORRECTION_MUST_NOT_GUESS_MAJOR_CANON).
_MAJOR_KINDS = {"character", "location", "organization"}

_ORG_TOKENS = {
    "fbi", "nsa", "cia", "dw6", "darpa", "nasa", "un", "nato", "kbg", "kgb",
    "agency", "institute", "bureau", "department", "division", "organization",
    "organisation", "corporation", "company", "foundation", "initiative",
}
_LOCATION_HINTS = ("is a location", "is a place", "is a city", "is a facility", "is a town", "is a region")
_ORG_HINTS = ("is an organization", "is an organisation", "is an agency", "is an institute", "is a company", "is a corporation", "is a bureau")
_AGE_RE = re.compile(r"\b(?:age\s+(\d{1,3})|(\d{1,3})\s+years?\s+old)\b", re.IGNORECASE)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _extract_quoted_names(instruction: str) -> list[str]:
    names = re.findall(r"[\"']([^\"']{2,60})[\"']", instruction)
    if names:
        return [n.strip() for n in names]
    return []


def _extract_capitalized_names(instruction: str) -> list[str]:
    # Capitalized tokens that are not sentence-initial common words.
    words = re.findall(r"\b([A-Z][a-zA-Z0-9]{2,})\b", instruction)
    stop = {
        "The", "This", "That", "Remove", "Merge", "Move", "Rename", "Add", "Delete",
        "Make", "Story", "Summary", "Wiki", "Character", "Location", "Organization",
        "Change", "Correct", "Fix", "Update", "It", "They", "He", "She", "There",
    }
    return [w for w in words if w not in stop]


def _looks_like_org(name: str) -> bool:
    low = name.lower()
    if low in _ORG_TOKENS:
        return True
    return any(tok in low.split() for tok in _ORG_TOKENS)


def _find_matching_records(
    snapshot: Any, names: list[str]
) -> list[dict[str, Any]]:
    """Find knowledge entries whose text mentions any of the names."""
    matched: list[dict[str, Any]] = []
    entries = getattr(snapshot, "knowledgeEntries", []) or []
    for entry in entries:
        state = str(getattr(entry, "state", "") or "")
        if state in {"rejected", "superseded"}:
            continue
        text = getattr(entry, "text", "") or ""
        low = _norm(text)
        for name in names:
            if _norm(name) and _norm(name) in low:
                matched.append(
                    {
                        "id": getattr(entry, "id", ""),
                        "text": text,
                        "section": getattr(entry, "section", ""),
                        "state": getattr(entry, "state", ""),
                    }
                )
                break
    return matched


def _heuristic_classify(
    instruction: str, snapshot: Any
) -> dict[str, Any]:
    """Deterministic keyword classification. Returns a classification dict."""
    low = _norm(instruction)
    names = _extract_quoted_names(instruction) or _extract_capitalized_names(instruction)
    matched = _find_matching_records(snapshot, names)

    result: dict[str, Any] = {
        "correctionType": "CANON_CORRECTION",
        "targets": [],
        "affectedRecordIds": [m["id"] for m in matched if m.get("id")],
        "requiresConfirmation": True,
        "clarificationQuestion": None,
        "learnedRule": "",
        "entityReclassifications": [],
        "aliases": {},
        "summaryRecompile": False,
    }

    # Age / attribute detection → ATTRIBUTE, attach to nearest person.
    age_match = _AGE_RE.search(instruction)
    if age_match:
        age = age_match.group(1) or age_match.group(2)
        person = next((n for n in names if not n.isdigit() and n.lower() not in {"age"}), None)
        result["correctionType"] = "RECLASSIFY"
        if person:
            result["entityReclassifications"].append(
                {"name": f"age {age}", "fromType": "character", "toType": "attribute", "attachTo": person}
            )
            result["learnedRule"] = f"{person}'s age is {age}; age is an attribute, not a character."
        return result

    # Location reclassification.
    if any(h in low for h in _LOCATION_HINTS):
        target = names[0] if names else ""
        result["correctionType"] = "RECLASSIFY"
        if target:
            result["entityReclassifications"].append(
                {"name": target, "fromType": "character", "toType": "location"}
            )
            result["learnedRule"] = f"{target} is a location, not a character."
        return result

    # Organization reclassification (explicit org phrase, or a known-org name the
    # creator says is not a character).
    if any(h in low for h in _ORG_HINTS) or (
        names and all(_looks_like_org(n) for n in names) and "not a character" in low
    ):
        target = names[0] if names else ""
        result["correctionType"] = "RECLASSIFY"
        if target:
            result["entityReclassifications"].append(
                {"name": target, "fromType": "character", "toType": "organization"}
            )
            result["learnedRule"] = f"{target} is an organization, not a character."
        return result

    # Merge.
    if "merge" in low or "same person" in low or "same character" in low or "are the same" in low:
        result["correctionType"] = "MERGE"
        if len(names) >= 2:
            canonical = names[0]
            for alias in names[1:]:
                result["aliases"][alias] = canonical
            result["learnedRule"] = f"{', '.join(names[1:])} and {canonical} are the same identity."
        return result

    # Remove.
    if "remove" in low or "delete" in low or "doesn't belong" in low or "does not belong" in low or "get rid of" in low:
        result["correctionType"] = "REMOVE"
        if not names and not matched:
            result["clarificationQuestion"] = (
                "Which record should I remove? I couldn't tell from your instruction."
            )
        return result

    # Move / doesn't belong in a section.
    if "move" in low or "belongs in" in low or "should be in" in low:
        result["correctionType"] = "MOVE"
        return result

    # Rename.
    if "rename" in low or "should be titled" in low or "should be called" in low or "call it" in low:
        result["correctionType"] = "RENAME"
        return result

    # Summary correction.
    if "summary" in low or "logline" in low:
        result["correctionType"] = "SUMMARY_CORRECTION"
        result["summaryRecompile"] = True
        return result

    # Rewrite.
    if "rewrite" in low or "rephrase" in low or "reword" in low:
        result["correctionType"] = "REWRITE"
        return result

    # Add.
    if low.startswith("add") or " add " in low or "include" in low:
        result["correctionType"] = "ADD"
        return result

    # Ambiguity gate: an instruction that could alter a confirmed character /
    # major canon but has no identifiable target must ask, not guess.
    if not names and not matched and any(
        k in low for k in ("character", "canon", "story", "timeline", "relationship")
    ):
        result["clarificationQuestion"] = (
            "I want to make sure I change the right thing. Which page, character, "
            "or record are you referring to?"
        )

    return result


def _build_classification_prompt(
    instruction: str, toc: list[str], matched: list[dict[str, Any]]
) -> list[dict[str, str]]:
    system = (
        "You classify a creator's natural-language correction to their Project Wiki. "
        "Return ONLY strict JSON with keys: correctionType (one of REWRITE, ADD, REMOVE, "
        "MERGE, RENAME, RECLASSIFY, MOVE, CANON_CORRECTION, SUMMARY_CORRECTION, "
        "RELATIONSHIP_CORRECTION, TIMELINE_CORRECTION, SCRIPT_CORRECTION), targets "
        "(array of {pageId?, sectionId?, pageType?, label?}), affectedRecordIds (array), "
        "requiresConfirmation (bool), clarificationQuestion (string or null), learnedRule "
        "(string), entityReclassifications (array of {name, fromType, toType, attachTo?}), "
        "aliases (object mapping alias->canonical), summaryRecompile (bool). "
        "If the instruction is ambiguous about a major canon element (a confirmed "
        "character, location, or the central story), set clarificationQuestion instead of "
        "guessing. Never invent targets."
    )
    user = {
        "instruction": instruction,
        "wikiPages": toc,
        "matchedRecords": matched,
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
    ]


def _parse_llm_payload(reply: str) -> dict[str, Any] | None:
    if not reply:
        return None
    m = _JSON_RE.search(reply)
    raw = m.group(1) if m else None
    if raw is None:
        b = _BRACE_RE.search(reply)
        raw = b.group(0) if b else None
    if raw is None:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001
        return None


async def _llm_classify(
    provider: Any, instruction: str, snapshot: Any
) -> dict[str, Any] | None:
    from ...providers.base import ChatRequest

    compiled = getattr(snapshot, "compiledWiki", None) or {}
    pages = compiled.get("pages") or []
    toc = [str(p.get("title") or p.get("id") or "") for p in pages if isinstance(p, dict)]
    names = _extract_quoted_names(instruction) or _extract_capitalized_names(instruction)
    matched = _find_matching_records(snapshot, names)
    messages = _build_classification_prompt(instruction, toc, matched)
    request = ChatRequest(
        request_id=f"wiki-correction-classify",
        messages=messages,
        model_id=None,
        temperature=0.1,
        mode="chat",
    )
    try:
        result = await asyncio.wait_for(provider.generate(request), timeout=30.0)
        return _parse_llm_payload(result.reply)
    except Exception:  # noqa: BLE001
        return None


def _normalize_classification(data: dict[str, Any]) -> dict[str, Any]:
    """Coerce an LLM/heuristic dict into a clean classification dict."""
    out: dict[str, Any] = {
        "correctionType": str(data.get("correctionType") or "CANON_CORRECTION"),
        "targets": data.get("targets") or [],
        "affectedRecordIds": [str(x) for x in (data.get("affectedRecordIds") or [])],
        "requiresConfirmation": bool(data.get("requiresConfirmation", True)),
        "clarificationQuestion": data.get("clarificationQuestion") or None,
        "learnedRule": str(data.get("learnedRule") or ""),
        "entityReclassifications": data.get("entityReclassifications") or [],
        "aliases": data.get("aliases") or {},
        "summaryRecompile": bool(data.get("summaryRecompile", False)),
    }
    valid_types = {
        "REWRITE", "ADD", "REMOVE", "MERGE", "RENAME", "RECLASSIFY", "MOVE",
        "CANON_CORRECTION", "SUMMARY_CORRECTION", "RELATIONSHIP_CORRECTION",
        "TIMELINE_CORRECTION", "SCRIPT_CORRECTION",
    }
    if out["correctionType"] not in valid_types:
        out["correctionType"] = "CANON_CORRECTION"
    return out


def _build_preview(
    project_id: str,
    preview_id: str,
    instruction: str,
    classification: dict[str, Any],
    target: CorrectionTarget | None,
) -> CorrectionPreview:
    targets: list[CorrectionTarget] = []
    for t in classification.get("targets") or []:
        if isinstance(t, dict):
            targets.append(CorrectionTarget(**{k: v for k, v in t.items() if k in CorrectionTarget.model_fields}))
    if target and not targets:
        targets.append(target)

    reclass = [
        EntityReclassification(**{k: v for k, v in r.items() if k in EntityReclassification.model_fields})
        for r in classification.get("entityReclassifications") or []
        if isinstance(r, dict)
    ]

    proposed: list[ProposedChange] = []
    ctype = classification["correctionType"]
    for r in reclass:
        proposed.append(
            ProposedChange(
                area="Characters",
                description=f"Reclassify “{r.name}” from {r.fromType} to {r.toType}.",
                changeType="Reclassify",
            )
        )
    for alias, canonical in (classification.get("aliases") or {}).items():
        proposed.append(
            ProposedChange(
                area="Characters",
                description=f"Treat “{alias}” and “{canonical}” as the same identity.",
                changeType="Merge",
            )
        )
    if not proposed:
        proposed.append(
            ProposedChange(
                area="Wiki",
                description=f"Apply {ctype.replace('_', ' ').lower()} per your instruction.",
                changeType=ctype.replace("_", " ").title(),
            )
        )
    if classification.get("summaryRecompile"):
        proposed.append(
            ProposedChange(
                area="Story Summary Editor",
                description="Revise the Logline / Short / Long summaries to reflect this correction.",
                changeType="Revise",
            )
        )

    return CorrectionPreview(
        previewId=preview_id,
        projectId=project_id,
        instruction=instruction,
        correctionType=ctype,  # type: ignore[arg-type]
        targets=targets,
        affectedPages=[t.label for t in targets if t.label],
        affectedRecords=classification.get("affectedRecordIds") or [],
        proposedChanges=proposed,
        summaryRecompile=bool(classification.get("summaryRecompile")),
        entityReclassifications=reclass,
        aliases=classification.get("aliases") or {},
        learnedRule=classification.get("learnedRule") or "",
        requiresConfirmation=classification.get("requiresConfirmation", True),
        clarificationQuestion=classification.get("clarificationQuestion"),
    )


async def classify_correction(
    db: Session,
    project_id: str,
    instruction: str,
    *,
    target: CorrectionTarget | None = None,
    provider: Any = None,
    preview_id: str,
) -> CorrectionPreview:
    """Classify an instruction into a CorrectionPreview (LLM with heuristic fallback)."""
    snapshot = load_snapshot(db, project_id)

    classification: dict[str, Any] | None = None
    if provider is not None:
        classification = await _llm_classify(provider, instruction, snapshot)
    if classification is None:
        classification = _heuristic_classify(instruction, snapshot)
    classification = _normalize_classification(classification)

    return _build_preview(project_id, preview_id, instruction, classification, target)


__all__ = ["classify_correction"]
