"""Co-Director production memory - queryable projection over authoritative stores.

Mission Parts 3-4, 54, 56: reliable operational memory that is NOT raw
conversation history. Records are projected from:
- codirector_tool_invocations (every CD tool attempt + outcome),
- production_events (production changes incl. manual UI actions),
- jobs (generation lifecycle),
- assets (candidate approvals / library durability),
- timeline state (clips / prompt segments / batches).

Reference resolution (Part 4) handles: C1-A style candidate tags, ordinal
references ("the first C1 shot", "shot frame 1"), and camera labels
("the close-up", "the wide") - never guessing when ambiguous.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from sqlalchemy.orm import Session

_TOOL_LIMIT = 10


def _loads(value: Optional[str], default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def recent_tool_actions(
    db: Session,
    project_id: str,
    *,
    limit: int = _TOOL_LIMIT,
) -> list[dict[str, Any]]:
    """Recent Co-Director tool actions with outcomes (newest first)."""
    try:
        from ...db import CoDirectorToolInvocation

        rows = (
            db.query(CoDirectorToolInvocation)
            .filter(CoDirectorToolInvocation.project_id == project_id)
            .order_by(CoDirectorToolInvocation.created_at.desc())
            .limit(max(1, min(int(limit), 50)))
            .all()
        )
        out: list[dict[str, Any]] = []
        for row in rows:
            args = _loads(row.arguments_json, {})
            result = _loads(row.result_json, None)
            kept_args = {k: v for k, v in (args or {}).items() if k in ("assetId", "candidateId", "clipId", "segmentId", "batchId", "sceneId", "start", "length", "duration", "label", "text", "prompt", "userDirection", "productionPrompt", "generatorId", "frameSize", "aspectRatio", "model")}
            kept_result = {k: v for k, v in (result or {}).items() if k in ("ok", "clipId", "segmentId", "batchId", "assetId", "candidateId", "timelineRevision", "start", "duration", "placement")}
            out.append({
                "toolId": row.tool_id,
                "status": row.status,
                "kind": row.kind,
                "createdBy": row.created_by,
                "errorCode": row.error_code,
                "errorMessage": row.error_message,
                "argumentsSummary": kept_args,
                "resultSummary": kept_result,
            })
        return out
    except Exception:
        return []


def build_production_memory(
    db: Session,
    project_id: str,
    scene_id: Optional[str] = None,
) -> dict[str, Any]:
    """Structured production memory for one project (bounded)."""
    from ...production_events import recent_production_events
    from .snapshot import build_production_snapshot

    events = recent_production_events(db, project_id, scene_id=scene_id, limit=12)
    tool_actions = recent_tool_actions(db, project_id, limit=_TOOL_LIMIT)
    snapshot = build_production_snapshot(db, project_id, scene_id)
    return {
        "events": events,
        "toolActions": tool_actions,
        "snapshot": snapshot,
    }


def production_memory_block(
    db: Session,
    project_id: str,
    scene_id: Optional[str] = None,
    *,
    max_chars: int = 1400,
) -> str:
    """Bounded prompt block of recent CD actions + production events."""
    from ...production_events import recent_production_events_block

    out: list[str] = []
    actions = recent_tool_actions(db, project_id, limit=6)
    if actions:
        out.append("CO-DIRECTOR RECENT ACTIONS")
        for a in actions:
            status = a.get("status") or ""
            err = ""
            if status == "failed":
                err = " (failed: " + str(a.get("errorMessage") or a.get("errorCode") or "") + ")"
            args = a.get("argumentsSummary") or {}
            label = a.get("toolId") or ""
            detail = ", ".join(str(k) + "=" + str(v) for k, v in list(args.items())[:4])
            line = "- " + label + ": " + status + err
            if detail:
                line = line + " [" + detail + "]"
            out.append(line)
    events_block = recent_production_events_block(db, project_id, scene_id=scene_id, limit=6)
    if events_block:
        if out:
            out.append("")
        out.append(events_block)
    text = chr(10).join(out)
    if len(text) > max_chars:
        text = text[:max_chars] + "..."
    return text


# ---------------------------------------------------------------------------
# Reference resolution (mission Part 4)
# ---------------------------------------------------------------------------

_CAMERA_ALIASES: dict[str, list[str]] = {
    "wide": ["wide", "establishing", "master"],
    "closeup": ["close", "close-up", "closeup", "tight", "reaction"],
    "medium": ["medium", "mid", "waist"],
    "over-shoulder": ["over-shoulder", "over shoulder", "os"],
}


def _candidate_catalog(db: Session, project_id: str) -> list[dict[str, Any]]:
    """Ordered candidate list (oldest first) with camera/variant parsing."""
    from ...db import Asset
    from .snapshot import _parse_candidate_tag

    rows = (
        db.query(Asset)
        .filter(Asset.project_id == project_id)
        .order_by(Asset.created_at.asc())
        .all()
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        tag = str(row.tag or "")
        if not any(k in tag for k in ("scene_creator", "multi_shot", "imagegen", "shot")):
            continue
        parsed = _parse_candidate_tag(tag)
        out.append({
            "assetId": row.id,
            "tag": tag,
            "camera": parsed["camera"],
            "variant": parsed["variant"],
            "createdAt": row.created_at,
        })
    return out


def _candidates_by_camera(catalog: list[dict[str, Any]], camera: str) -> list[dict[str, Any]]:
    return [c for c in catalog if c["camera"].upper() == camera.upper()]


def _camera_number_candidates(
    db: Session,
    project_id: str,
    catalog: list[dict[str, Any]],
    aliases: list[str],
) -> tuple[list[dict[str, Any]], str]:
    """Try to pin a camera-label alias to a candidate set via spatial camera labels."""
    try:
        from ...spatial_map.service import list_documents
        import json as _json

        docs = list_documents(db, project_id) or []
        for doc in docs:
            raw = getattr(doc, "document_json", None)
            payload = _json.loads(raw) if isinstance(raw, str) else (doc if isinstance(doc, dict) else {})
            for cam in (payload.get("cameras") or []):
                label = str(cam.get("label") or "").lower()
                if any(alias in label for alias in aliases):
                    num = re.search(r"(\d+)$", str(cam.get("id") or ""))
                    if num:
                        per_camera = _candidates_by_camera(catalog, "C" + num.group(1))
                        if per_camera:
                            return per_camera, "candidates for camera " + str(cam.get("label")) + " (" + str(cam.get("id"))[:8] + ")"
    except Exception:
        pass
    return [], ""


def resolve_reference(
    db: Session,
    project_id: str,
    ref: str,
    *,
    scene_id: Optional[str] = None,
) -> dict[str, Any]:
    """Resolve a conversational production reference to candidate asset(s).

    Handles:
    - exact candidate tags: "C1-A", "c1-a", "scene_creator_mini_8_C2_B"
    - ordinal refs: "the first C1 shot", "shot frame 1", "the second C3 image"
    - camera labels: "the close-up", "the wide", "reaction shot"

    Returns {"matched": [...], "ambiguous": bool, "note": str}. Never raises.
    """
    text = (ref or "").strip()
    if not text:
        return {"matched": [], "ambiguous": False, "note": "empty reference"}
    catalog = _candidate_catalog(db, project_id)
    if not catalog:
        return {"matched": [], "ambiguous": False, "note": "no candidates found in project"}
    matched: list[dict[str, Any]] = []
    note = ""

    # 1. exact tag pattern C<n>-<v> (case-insensitive)
    m = re.search(r"(?i)\b([Cc]\d+)[-_. ]?([A-Za-z])\b", text)
    if m:
        camera = m.group(1).upper()
        variant = m.group(2).upper()
        exact = [c for c in catalog if c["camera"] == camera and c["variant"] == variant]
        if exact:
            return {"matched": exact, "ambiguous": len(exact) > 1, "note": "candidate " + camera + "-" + variant + (" (multiple matches)" if len(exact) > 1 else "")}
        per_camera = _candidates_by_camera(catalog, camera)
        if per_camera:
            return {"matched": per_camera, "ambiguous": len(per_camera) > 1, "note": "camera " + camera + " candidates (no " + variant + " variant)"}
        return {"matched": [], "ambiguous": False, "note": "no candidates for camera " + camera}

    # 2. ordinal references
    ordinals = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5}
    for word, num in ordinals.items():
        mm = re.search(r"(?i)\b" + re.escape(word) + r"\s+(C\d+)", text)
        if mm:
            camera = mm.group(1).upper()
            per_camera = _candidates_by_camera(catalog, camera)
            if len(per_camera) >= num:
                return {"matched": [per_camera[num - 1]], "ambiguous": False, "note": word + " " + camera + " candidate"}
            return {"matched": [], "ambiguous": False, "note": "only " + str(len(per_camera)) + " " + camera + " candidates"}
    m2 = re.search(r"(?i)(?:shot|frame|image)\s*(?:#|number\s*)?(\d+)", text)
    if m2:
        n = int(m2.group(1)) - 1
        if 0 <= n < len(catalog):
            return {"matched": [catalog[n]], "ambiguous": False, "note": "candidate #" + m2.group(1) + " in project order"}
        return {"matched": [], "ambiguous": False, "note": "no candidate #" + m2.group(1)}
    if re.search(r"(?i)\b(?:first|previous|last|latest)\b", text) and re.search(r"(?i)\b(?:shot|candidate|image|frame)\b", text):
        lowered = text.lower()
        if "last" in lowered or "latest" in lowered:
            return {"matched": [catalog[-1]], "ambiguous": False, "note": "latest candidate"}
        return {"matched": [catalog[0]], "ambiguous": False, "note": "first candidate"}

    # 3. camera-label references
    lowered = text.lower()
    for key, aliases in _CAMERA_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            pinned, note = _camera_number_candidates(db, project_id, catalog, aliases)
            if pinned:
                return {"matched": pinned, "ambiguous": len(pinned) > 1, "note": note}
            return {"matched": catalog, "ambiguous": True, "note": "camera-label reference (" + key + "); could not pin to one camera"}

    return {"matched": [], "ambiguous": False, "note": "unrecognized reference"}