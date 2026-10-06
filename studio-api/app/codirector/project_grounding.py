"""Canonical Co-Director project grounding + @entity resolution.

Composed from existing character / voice / scene stores. Not a second project
database. Used before conversational answers and before model/provider parsing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from .entity_resolver import find_character_names, resolve_character
from .image_route.contracts import RouteLock

# @Character, leftover #prop / #ERS, and %PRS tokens must never reach model parsers.
_ENTITY_TAG_RE = re.compile(
    r"(?:@[A-Z][A-Za-z'\-0-9]+(?:\s+[A-Z][A-Za-z'\-0-9]+)*"
    r"|#[A-Za-z][A-Za-z0-9_-]*"
    r"|%[A-Za-z][A-Za-z0-9_]*)"
)

_GLOBAL_ASSETS_Q = re.compile(
    r"\bglobal\b.+\b(?:characters?|props?|environments?)\b"
    r"|\b(?:characters?|props?|environments?)\b.+\bglobal\b",
    re.I,
)
_CHAR_VIEWS_Q = re.compile(
    r"\b(?:which|what)\b.+\bcharacter\b.+\bviews?\b"
    r"|\bcharacter\b.+\bviews?\b.+\bapproved\b"
    r"|\bapproved\b.+\bcharacter\b.+\bviews?\b",
    re.I,
)
_PROP_VIEWS_Q = re.compile(
    r"\b(?:which|what)\b.+\bprop\b.+\bviews?\b"
    r"|\bprop\b.+\bviews?\b.+\bapproved\b"
    r"|\bapproved\b.+\bprop\b.+\bviews?\b",
    re.I,
)
_PROP_READY_Q = re.compile(
    r"\b(?:is|are)\b.+\bprops?\b.+\bready\b"
    r"|\bprops?\b.+\bready\b"
    r"|\bis this prop ready\b",
    re.I,
)
_PROP_PENDING_PRIMARY_Q = re.compile(
    r"\b(?:which|what)\b.+\bprimary\b.+\bpending\b"
    r"|\bpending\b.+\bprimary\b"
    r"|\bprimary\b.+\bpending\b",
    re.I,
)
_CURRENT_VOICE_Q = re.compile(
    r"\b(?:which|what)\b.+\bvoice\b.+\b(?:current|approved|active|default)\b"
    r"|\b(?:current|approved|active|default)\b.+\bvoice\b",
    re.I,
)
_CHARACTERS_Q = re.compile(
    r"\b(?:who(?:'s| is| are)?|what(?:'s| are)?|list|name)\b.+\b(?:active\s+)?characters?\b"
    r"|\bwho is in this project\b"
    r"|\bwho(?:'s| is| are) (?:in|on) (?:this|the) (?:project|cast|roster)\b",
    re.I,
)
_VOICES_Q = re.compile(
    r"\b(?:what|which|who(?:se)?)\b.+\bvoices?\b"
    r"|\bvoices?\s+assigned\b"
    r"|\bassigned\s+voices?\b",
    re.I,
)
_SCENE_Q = re.compile(
    r"\b(?:what|which)\s+scene\b"
    r"|\bscene are we (?:working on|on|in)\b"
    r"|\bwhat scene are we working on\b",
    re.I,
)
_SHOT_REFS_Q = re.compile(
    r"\bwho is referenced\b"
    r"|\bwho(?:'s| is| are) (?:referenced|in) this (?:shot|clip|batch)\b"
    r"|\bwhich characters? (?:are|is) (?:in|on|bound|referenced)\b"
    r"|\bwho is in this shot\b",
    re.I,
)
_ENV_Q = re.compile(
    r"\bwhat environment\b"
    r"|\benvironment is assigned\b"
    r"|\bwhich environment\b"
    r"|\bwhat (?:location|place|ers)\b",
    re.I,
)
_GEN_Q = re.compile(
    r"\bwhat generator\b"
    r"|\bwhich generator\b"
    r"|\bgenerator is this scene using\b"
    r"|\bwhat(?:'s| is) the (?:selected )?generator\b",
    re.I,
)
# Scene-bound grounding must not swallow Adept-platform identity questions.
_PLATFORM_KNOWLEDGE_Q = re.compile(
    r"\benvironment reference sheet\b|\bers\b"
    r"|\bposecraft\b|\bspatial map\b"
    r"|\bcharacter reference sheet\b|\bcrs\b"
    r"|\bprop reference sheet\b|\bprs\b"
    r"|\broad area network\b|\bwide area network\b"
    r"|\bwhat is wan\b|\bwhat does wan\b",
    re.I,
)
_APPROVAL_Q = re.compile(
    r"\bhow many (?:timeline )?batches?\b.+\b(?:approved|draft)\b"
    r"|\bhow many (?:batches?|shots?) (?:are )?(?:approved|draft)\b"
    r"|\b(?:approved|draft) (?:timeline )?batches\b"
    r"|\btimeline batch(?:es)? (?:are )?(?:approved|draft)\b",
    re.I,
)
_HAPPENS_Q = re.compile(
    r"\bwhat happens\b"
    r"|\bwhat(?:'s| is) (?:going on|happening)\b"
    r"|\bwhat is this scene about\b"
    r"|\bwhat(?:'s| is) the scene (?:about|doing)\b",
    re.I,
)
_TAKE_Q = re.compile(
    r"\bcurrent take\b"
    r"|\bwhat(?:'s| is) the (?:current |active )?take\b"
    r"|\bwhich take\b"
    r"|\bpublished take\b"
    r"|\bwhich take is published\b"
    r"|\bcompare take\b"
    r"|\bshow(?: me)? take\b"
    r"|\bmake take\b",
    re.I,
)
_PRODUCTION_STATUS_Q = re.compile(
    r"\bproduction status\b"
    r"|\bscene(?:'s)? (?:production )?lifecycle\b"
    r"|\bwhat is the (?:production )?status of this scene\b"
    r"|\bscene ready(?:ness)?\b",
    re.I,
)
_SPATIAL_WHERE_Q = re.compile(
    r"\bwhere\b.+\b(?:spatial\s+map|the map|this map)\b"
    r"|\b(?:who|what) is (?:on|placed on) (?:the )?(?:spatial )?map\b"
    r"|\bplacements? on (?:the )?(?:spatial )?map\b"
    r"|\b(?:where is|where are)\b.+\b(?:camera|prop|crate)\b",
    re.I,
)


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _canonical_workspace(workspace: Optional[str]) -> Optional[str]:
    raw = str(workspace or "").strip().lower()
    if raw in {"one", "three", "timeline", "director"}:
        return "timeline"
    return raw or None


@dataclass(frozen=True)
class ResolvedEntity:
    kind: str
    token: str
    name: str
    character_id: str = ""
    crs_asset_id: str = ""
    project_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "token": self.token,
            "name": self.name,
            "characterId": self.character_id,
            "crsAssetId": self.crs_asset_id,
            "projectId": self.project_id,
        }


@dataclass
class EntityResolution:
    project_id: str
    tokens: list[str] = field(default_factory=list)
    characters: list[ResolvedEntity] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "projectId": self.project_id,
            "tokens": list(self.tokens),
            "characters": [item.to_dict() for item in self.characters],
            "unresolved": list(self.unresolved),
        }


def route_parse_surface(text: str, extra_tokens: Iterable[str] = ()) -> str:
    """Remove project entity tokens from the model/provider parsing surface."""

    blob = _ENTITY_TAG_RE.sub(" ", text or "")
    for raw in extra_tokens:
        token = str(raw or "").strip()
        if not token:
            continue
        blob = re.sub(re.escape(token), " ", blob, flags=re.I)
        if token.startswith(("@", "#", "%")):
            blob = re.sub(re.escape(token[1:]), " ", blob, flags=re.I)
    return re.sub(r"\s+", " ", blob).strip()


def forbidden_model_tokens(entities: Iterable[ResolvedEntity | dict[str, Any] | str]) -> set[str]:
    """Normalized names and concatenations that cannot become generator ids."""

    names: list[str] = []
    for item in entities:
        if isinstance(item, ResolvedEntity):
            names.append(_norm(item.name))
            names.append(_norm(item.token.lstrip("@#%")))
        elif isinstance(item, dict):
            names.append(_norm(str(item.get("name") or "")))
            names.append(_norm(str(item.get("token") or "").lstrip("@#%")))
        else:
            names.append(_norm(str(item or "").lstrip("@#%")))
    names = [n for n in dict.fromkeys(names) if len(n) >= 2]
    tokens = set(names)
    for i, left in enumerate(names):
        for right in names[i + 1 :]:
            tokens.add(left + right)
            tokens.add(right + left)
            tokens.add(left + "and" + right)
            tokens.add(right + "and" + left)
            tokens.add(left + "or" + right)
            tokens.add(right + "or" + left)
    return tokens


def snapshot_entity_tokens(snapshot: dict[str, Any] | None) -> list[str]:
    """Project character names that must never be treated as generator ids."""

    names: list[str] = []
    for row in (snapshot or {}).get("characters") or []:
        name = str((row or {}).get("name") or "").strip()
        if name:
            names.append(name)
    return names


def parse_route_lock_excluding_entities(
    text: str,
    entities: Iterable[ResolvedEntity | dict[str, Any] | str] = (),
) -> RouteLock:
    """parse_route_lock after entity tokens are removed from the parse surface."""

    from .image_route.lock import parse_route_lock

    extras = []
    for item in entities:
        if isinstance(item, ResolvedEntity):
            extras.extend([item.token, item.name])
        elif isinstance(item, dict):
            extras.extend([str(item.get("token") or ""), str(item.get("name") or "")])
        else:
            extras.append(str(item or ""))
    surface = route_parse_surface(text, extras)
    lock = parse_route_lock(surface)
    banned = forbidden_model_tokens(entities)
    named = _norm(lock.requested_model_id)
    if named and named in banned:
        return RouteLock(
            level="UNLOCKED" if not lock.requested_provider else lock.level,
            scope="provider" if lock.requested_provider else "",
            requested_provider=lock.requested_provider,
            requested_model_id="",
            restated=bool(lock.requested_provider or lock.level == "STRICT"),
        )
    return lock


def resolve_turn_entities(db: Session, project_id: str, text: str) -> EntityResolution:
    """Resolve every @character mention in this project. Fail closed across projects."""

    pid = str(project_id or "").strip()
    resolution = EntityResolution(project_id=pid)
    if not pid:
        for name in find_character_names(text):
            resolution.tokens.append(f"@{name}")
            resolution.unresolved.append(f"@{name}")
        return resolution
    for name in find_character_names(text):
        token = f"@{name}"
        resolution.tokens.append(token)
        found = resolve_character(db, pid, name)
        if not found:
            resolution.unresolved.append(token)
            continue
        owner = str(found.get("project_id") or pid)
        if owner and owner != pid:
            resolution.unresolved.append(token)
            continue
        crs = (
            str(found.get("approved_sheet_asset_id") or "")
            or str(found.get("sheet_asset_id") or "")
            or str(found.get("approved_reference_asset_id") or "")
            or str(found.get("visual_reference") or "")
            or str(found.get("approved_casting_asset_id") or "")
        )
        resolution.characters.append(
            ResolvedEntity(
                kind="crs",
                token=token,
                name=str(found.get("name") or name),
                character_id=str(found.get("character_id") or ""),
                crs_asset_id=crs,
                project_id=pid,
            )
        )
    return resolution


def _active_scene(db: Session, project_id: str, scene_id: Optional[str]) -> Optional[dict[str, Any]]:
    """Explicit request scene only. Never invent the first scene."""

    from ..db import Scene

    sid = str(scene_id or "").strip()
    pid = str(project_id or "").strip()
    if not sid or not pid:
        return None
    scene = db.get(Scene, sid)
    if scene is None or str(getattr(scene, "project_id", "") or "") != pid:
        return None
    return {"id": scene.id, "name": scene.name or "", "index": int(getattr(scene, "index", 0) or 0)}


def _character_approved_views(db: Session, project_id: str, character_id: str) -> list[dict[str, Any]]:
    """Same Character Creator slots as the UI. Fail open on snapshot."""
    try:
        from ..character_identity.cc_v2 import get_status

        state = get_status(db, project_id, character_id)
    except Exception:  # noqa: BLE001
        return []
    out: list[dict[str, Any]] = []
    front = ((state.get("views") or {}).get("front") or {})
    if front.get("approved") and front.get("assetId"):
        out.append(
            {
                "name": "Front",
                "source": front.get("source") or front.get("sourceType") or front.get("generator") or "",
                "assetId": front.get("assetId"),
            }
        )
    labels = {"side": "Side", "three_quarter": "3/4", "back": "Back"}
    for key, label in labels.items():
        slot = ((state.get("multiView") or {}).get("angles") or {}).get(key) or {}
        if slot.get("approved") and slot.get("assetId"):
            out.append(
                {
                    "name": label,
                    "source": slot.get("source") or "",
                    "assetId": slot.get("assetId"),
                }
            )
    return out


def _prop_approved_views(prop: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if (prop.primary_approved_asset_id or prop.approved_asset_id) and (
        str(prop.primary_phase or "") == "approved" or bool(prop.approved_asset_id)
    ):
        origin = ""
        for cand in reversed(list(prop.candidates or [])):
            if cand.asset_id in {prop.primary_approved_asset_id, prop.approved_asset_id}:
                origin = str(getattr(cand, "origin", "") or "")
                break
        out.append(
            {
                "name": "Primary",
                "source": origin,
                "assetId": prop.primary_approved_asset_id or prop.approved_asset_id,
            }
        )
    raw = prop.angles or {}
    for key in ("front", "back", "left", "right", "top", "bottom", "hero"):
        slot = raw.get(key)
        if slot is None:
            continue
        approved = bool(getattr(slot, "approved", False) if not isinstance(slot, dict) else slot.get("approved"))
        asset_id = getattr(slot, "asset_id", None) if not isinstance(slot, dict) else slot.get("asset_id")
        source = getattr(slot, "source", None) if not isinstance(slot, dict) else slot.get("source")
        if approved and asset_id:
            out.append({"name": key.title(), "source": source or "", "assetId": asset_id})
    return out


def _format_approved_views(slots: list[dict[str, Any]]) -> str:
    if not slots:
        return "none"
    bits = []
    for slot in slots:
        src = str(slot.get("source") or "").strip()
        bits.append(f"{slot.get('name')} ({src})" if src else str(slot.get("name")))
    return ", ".join(bits)


def _match_named_row(rows: list[dict[str, Any]], text: str) -> list[dict[str, Any]]:
    lowered = (text or "").lower()
    full: list[dict[str, Any]] = []
    token_hits: list[dict[str, Any]] = []
    skip = {"the", "and", "for", "upload", "smoke", "test", "global", "basic", "advanced"}
    for row in rows:
        name = str(row.get("name") or "").strip()
        tag = str(row.get("tag") or "").strip()
        tokens = [
            part
            for part in name.lower().replace("'", " ").replace("-", " ").split()
            if len(part) >= 3 and part not in skip
        ]
        if (name and name.lower() in lowered) or (tag and tag.lower() in lowered):
            full.append(row)
        elif tokens and any(part in lowered for part in tokens):
            token_hits.append(row)
    return full or token_hits or list(rows)


def _character_rows(db: Session, project_id: str) -> list[dict[str, Any]]:
    from ..character_identity.service import list_profiles

    pid = str(project_id or "").strip()
    if not pid:
        return []
    out: list[dict[str, Any]] = []
    for row in list_profiles(db, pid):
        if str(row.status or "").upper() == "ARCHIVED":
            continue
        resolved = resolve_character(db, pid, row.name) or {}
        crs = (
            str(resolved.get("approved_sheet_asset_id") or "")
            or str(resolved.get("sheet_asset_id") or "")
            or str(resolved.get("approved_reference_asset_id") or "")
            or str(resolved.get("visual_reference") or "")
            or str(resolved.get("approved_casting_asset_id") or "")
        )
        out.append(
            {
                "id": row.id,
                "name": row.name,
                "status": row.approval_status or row.status,
                "crsAssetId": crs,
                "activeVoiceProfileId": row.active_voice_profile_id or "",
                "isGlobal": bool(getattr(row, "is_global", False)),
                "owningProjectId": row.project_id,
                "approvedViews": _character_approved_views(db, pid, row.id),
            }
        )
    return out


def _prop_rows(db: Session, project_id: str) -> list[dict[str, Any]]:
    from ..prop_creator.service import _prop_is_global, list_props

    pid = str(project_id or "").strip()
    if not pid:
        return []
    try:
        props = list_props(db, pid, approved_only=False)
    except Exception:  # noqa: BLE001 — grounding must not fail closed
        return []
    from ..prop_creator.readiness import (
        approved_primary_asset_id,
        identity_ready,
        readiness_payload,
        valid_primary_candidate_asset_id,
        visible_primary_preview_asset_id,
    )

    out: list[dict[str, Any]] = []
    for prop in props:
        ready = identity_ready(prop)
        payload = readiness_payload(prop)
        approved_primary = approved_primary_asset_id(prop)
        pending_primary = valid_primary_candidate_asset_id(prop)
        out.append(
            {
                "id": prop.id,
                "name": prop.display_label or prop.tag,
                "tag": prop.tag,
                "isGlobal": _prop_is_global(prop),
                "owningProjectId": prop.project_id,
                "approvedViews": _prop_approved_views(prop),
                "identityReady": ready,
                "propReady": ready,
                "approvedPrimaryAssetId": approved_primary or None,
                "pendingPrimaryAssetId": (
                    pending_primary if pending_primary and pending_primary != approved_primary else None
                ),
                "previewPrimaryAssetId": visible_primary_preview_asset_id(prop) or None,
                "readyReason": payload.get("readyReason") or "",
                "missingViewsBlockReadiness": False,
            }
        )
    return out


def _environment_rows(db: Session, project_id: str) -> list[dict[str, Any]]:
    from ..environment_reference_sheet.store import list_visible_sheets, sheet_is_global

    pid = str(project_id or "").strip()
    if not pid:
        return []
    try:
        sheets = list_visible_sheets(db, pid)
    except Exception:  # noqa: BLE001 — grounding must not fail closed
        return []
    return [
        {
            "id": sheet.sheetId,
            "name": sheet.name,
            "isGlobal": sheet_is_global(sheet),
            "owningProjectId": sheet.projectId,
        }
        for sheet in sheets
    ]


def _voice_assignments(db: Session, project_id: str, characters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from ..character_identity.models import VoiceProfileRow

    pid = str(project_id or "").strip()
    assignments: list[dict[str, Any]] = []
    for character in characters:
        cid = str(character.get("id") or "")
        voice_id = str(character.get("activeVoiceProfileId") or "").strip()
        row = db.get(VoiceProfileRow, voice_id) if voice_id else None
        if row is None or str(row.character_profile_id or "") != cid:
            row = (
                db.query(VoiceProfileRow)
                .filter(
                    VoiceProfileRow.project_id == pid,
                    VoiceProfileRow.character_profile_id == cid,
                )
                .order_by(VoiceProfileRow.updated_at.desc())
                .first()
            )
        if row is None and character.get("isGlobal"):
            owner = str(character.get("owningProjectId") or "").strip()
            q = db.query(VoiceProfileRow).filter(VoiceProfileRow.character_profile_id == cid)
            if owner:
                q = q.filter(VoiceProfileRow.project_id == owner)
            row = q.order_by(VoiceProfileRow.updated_at.desc()).first()
        if row is None:
            continue
        if str(row.project_id or "") != pid and not character.get("isGlobal"):
            continue
        engine = str(row.provider or row.model_id or row.source_mode or "").strip()
        ready = str(row.approval_status or "").lower() == "approved" or str(row.status or "").upper() == "APPROVED"
        assignments.append(
            {
                "characterId": cid,
                "characterName": character.get("name") or "",
                "voiceProfileId": row.id,
                "voiceName": row.name or "",
                "engine": engine,
                "approval": row.approval_status or row.status or "",
                "readiness": "ready" if ready else "not_ready",
            }
        )
    return assignments


def _spatial_map_grounding(db: Session, project_id: str) -> Optional[dict[str, Any]]:
    """Read-only planning facts from the project's Spatial Map. Never generates."""

    try:
        from ..spatial_map.service import list_documents, planning_context

        docs = list_documents(db, project_id) or []
        if not docs:
            return {"hasMap": False}
        plan = planning_context(docs[0])
        return {
            "hasMap": True,
            **plan,
        }
    except Exception:
        return {"hasMap": False}


def _spatial_placement_lines(spatial: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for item in spatial.get("characters") or []:
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        extra = f", {item['facing']}" if item.get("facing") else ""
        lines.append(f"- {label} is on the Spatial Map at {item.get('summary')}{extra}.")
    for item in spatial.get("props") or []:
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        lines.append(f"- {label} is on the Spatial Map at {item.get('summary')}.")
    for item in spatial.get("cameras") or []:
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        facing = f", facing {item['facing']}" if item.get("facing") else ""
        lines.append(f"- {label} is on the Spatial Map at {item.get('summary')}{facing}.")
    return lines


_SPATIAL_PLACE_CMD = re.compile(
    r"\b(?:put|move|place|drop|set|relocate)\b",
    re.I,
)


def _is_spatial_placement_question(text: str, snap: dict[str, Any]) -> bool:
    spatial = snap.get("spatialMap") or {}
    if not spatial.get("hasMap"):
        return False
    # Planning edits stay on the placement layer. Do not answer them as "where".
    if _SPATIAL_PLACE_CMD.search(text or ""):
        return False
    if _SPATIAL_WHERE_Q.search(text):
        return True
    if snap.get("workspace") == "spatial" and re.search(r"\bwhere (?:is|are)\b", text or "", re.I):
        return True
    return False


def _spatial_placement_reply(snap: dict[str, Any]) -> str:
    spatial = snap.get("spatialMap") or {}
    if not spatial.get("hasMap"):
        return "This project does not have a Spatial Map yet."
    title = str(spatial.get("title") or "Spatial Map").strip()
    lines = [f"{title} is the active Spatial Map."]
    source = str(spatial.get("sourceLine") or "").strip()
    if source:
        lines.append(source)
    placed = _spatial_placement_lines(spatial)
    if placed:
        lines.extend(line.lstrip("- ").rstrip(".") + "." for line in placed)
    else:
        lines.append("No characters, props, or cameras are placed on it yet.")
    if spatial.get("pixelsUnchanged"):
        lines.append("The uploaded atlas was not regenerated.")
    return " ".join(lines)


def _scriptwriter_scene_grounding(
    db: Session,
    project_id: str,
    scriptwriter_scene_id: Optional[str],
) -> dict[str, Any] | None:
    """Live Script Writer current-scene slice, keyed by the canonical
    navigator heading id the Script Writer surface emits. Read-only; never
    raises — grounding must not fail closed."""
    sw_id = str(scriptwriter_scene_id or "").strip()
    if not sw_id:
        return None
    try:
        from ..scriptwriter.service import canonical_elements
        from ..scriptwriter.store import list_documents, load_document

        docs = list_documents(db, project_id)
        if not docs:
            return None
        doc = load_document(db, docs[0].id)
        if doc is None:
            return None
        headings = [e for e in canonical_elements(doc) if e.type == "scene_heading"]
        for idx, heading in enumerate(headings):
            if heading.id == sw_id:
                return {
                    "id": heading.id,
                    "heading": heading.text,
                    "position": idx + 1,
                    "total": len(headings),
                    "documentId": doc.id,
                    "scriptTitle": doc.title or "",
                }
    except Exception:  # noqa: BLE001 — grounding must not fail closed
        return None
    return None


def build_project_grounding_snapshot(
    db: Session,
    project_id: Optional[str],
    scene_id: Optional[str] = None,
    *,
    workspace: Optional[str] = None,
    scriptwriter_scene_id: Optional[str] = None,
) -> dict[str, Any]:
    """Concise live snapshot. Unbound when project_id is missing."""

    from ..db import Project

    pid = str(project_id or "").strip() or None
    empty = {
        "bound": False,
        "sessionStatus": "no_project",
        "project": None,
        "activeScene": None,
        "scriptwriterScene": None,
        "workspace": _canonical_workspace(workspace),
        "characters": [],
        "props": [],
        "environments": [],
        "voiceAssignments": [],
        "spatialMap": None,
    }
    if not pid:
        return empty
    project = db.get(Project, pid)
    if project is None:
        return empty
    characters = _character_rows(db, pid)
    return {
        "bound": True,
        "sessionStatus": "bound",
        "project": {"id": pid, "name": project.name or ""},
        "activeScene": _active_scene(db, pid, scene_id),
        "scriptwriterScene": _scriptwriter_scene_grounding(db, pid, scriptwriter_scene_id),
        "workspace": _canonical_workspace(workspace),
        "characters": [
            {
                "id": row["id"],
                "name": row["name"],
                "status": row["status"],
                "crsAssetId": row["crsAssetId"],
                "isGlobal": bool(row.get("isGlobal")),
                "owningProjectId": row.get("owningProjectId") or pid,
                "approvedViews": row.get("approvedViews") or [],
            }
            for row in characters
        ],
        "props": _prop_rows(db, pid),
        "environments": _environment_rows(db, pid),
        "voiceAssignments": _voice_assignments(db, pid, characters),
        "spatialMap": _spatial_map_grounding(db, pid),
    }


def render_grounding_block(
    db: Session,
    project_id: Optional[str],
    scene_id: Optional[str] = None,
    *,
    workspace: Optional[str] = None,
    max_chars: int = 2200,
) -> str:
    snap = build_project_grounding_snapshot(db, project_id, scene_id, workspace=workspace)
    if not snap.get("bound"):
        return ""
    project = snap.get("project") or {}
    lines = ["PROJECT GROUNDING"]
    lines.append(f"- Project: {project.get('name')} ({project.get('id')})")
    scene = snap.get("activeScene")
    if scene:
        lines.append(f"- Active scene: {scene.get('name')} ({scene.get('id')})")
    elif snap.get("workspace") == "timeline":
        lines.append("- Active scene: (none selected this turn)")
    workspace = snap.get("workspace")
    if workspace:
        lines.append(f"- Workspace: {workspace}")
    chars = snap.get("characters") or []
    if chars:
        labels = ", ".join(f"{c.get('name')} [{c.get('status') or 'draft'}]" for c in chars)
        lines.append(f"- Characters: {labels}")
    else:
        lines.append("- Characters: (none)")
    voices = snap.get("voiceAssignments") or []
    if voices:
        for voice in voices:
            lines.append(
                "- Voice {name}: {engine} ({approval}, {ready})".format(
                    name=voice.get("characterName") or voice.get("characterId"),
                    engine=voice.get("engine") or "unspecified",
                    approval=voice.get("approval") or "draft",
                    ready=voice.get("readiness") or "not_ready",
                )
            )
    else:
        lines.append("- Voice assignments: (none)")
    spatial = snap.get("spatialMap") or {}
    if spatial.get("hasMap"):
        lines.append(f"- Spatial Map: {spatial.get('title') or 'Spatial Map'}")
        if spatial.get("sourceLine"):
            lines.append(f"- {spatial.get('sourceLine')}")
        placed = _spatial_placement_lines(spatial)
        if placed:
            lines.extend(placed)
        else:
            lines.append("- Spatial Map placements: none yet")
    text = "\n".join(lines)
    if len(text) > max_chars:
        return text[:max_chars] + "..."
    return text


def _production_lifecycle_slice(
    db: Session,
    project_id: str,
    scene_id: Optional[str],
) -> dict[str, Any] | None:
    """Read-only lifecycle slice. Does not persist."""
    try:
        from .production_lifecycle.service import _load_life

        _snapshot, life = _load_life(db, project_id)
        match = next((row for row in (life.scenes or []) if row.sceneId == scene_id), None)
        return {
            "projectStage": life.currentStage,
            "productionStatus": life.productionStatus,
            "sceneReadyStatus": match.status if match else None,
            "blockerSummary": match.blockerSummary if match else "",
        }
    except Exception:  # noqa: BLE001 — questions must not fail closed
        return None


def grounding_reply(inspect: dict[str, Any], user_text: str) -> Optional[str]:
    """Deterministic answers for project-state questions. No LLM recollection."""

    text = user_text or ""
    snap = inspect.get("snapshot") or inspect
    if _GLOBAL_ASSETS_Q.search(text):
        if not snap.get("bound"):
            return "No project is selected, so I cannot list global assets."
        chars = [str(c.get("name") or "").strip() for c in (snap.get("characters") or []) if c.get("isGlobal") and c.get("name")]
        props = [str(p.get("name") or "").strip() for p in (snap.get("props") or []) if p.get("isGlobal") and p.get("name")]
        envs = [str(e.get("name") or "").strip() for e in (snap.get("environments") or []) if e.get("isGlobal") and e.get("name")]
        bits: list[str] = []
        if chars:
            bits.append("global characters " + ", ".join(chars))
        if props:
            bits.append("global props " + ", ".join(props))
        if envs:
            bits.append("global environments " + ", ".join(envs))
        if not bits:
            return "No Global characters, props, or environments are visible in this project."
        return "This project can use " + "; ".join(bits) + "."
    if _CHAR_VIEWS_Q.search(text):
        if not snap.get("bound"):
            return "No project is selected, so I cannot list character views."
        rows = _match_named_row(list(snap.get("characters") or []), text)
        if not rows:
            return "This project has no character records yet."
        parts = []
        for row in rows:
            name = str(row.get("name") or "Character").strip()
            parts.append(f"{name} approved views: {_format_approved_views(row.get('approvedViews') or [])}.")
        return " ".join(parts)
    if _PROP_PENDING_PRIMARY_Q.search(text):
        if not snap.get("bound"):
            return "No project is selected, so I cannot name a pending Primary."
        rows = _match_named_row(list(snap.get("props") or []), text)
        if not rows:
            return "This project has no Prop records yet."
        parts = []
        for row in rows:
            name = str(row.get("name") or "Prop").strip()
            pending = str(row.get("pendingPrimaryAssetId") or "").strip()
            preview = str(row.get("previewPrimaryAssetId") or "").strip()
            approved = str(row.get("approvedPrimaryAssetId") or "").strip()
            if pending:
                parts.append(
                    f"{name} has a pending Primary candidate {pending}. "
                    f"The preview uses that candidate. Approved identity is {approved or 'none'}."
                )
            elif approved:
                parts.append(f"{name} has no pending Primary. Approved Primary is {approved}.")
            else:
                parts.append(f"{name} has no Primary candidate yet.")
            if preview and preview != pending and preview != approved:
                parts.append(f"Preview asset is {preview}.")
        return " ".join(parts)
    if _PROP_VIEWS_Q.search(text):
        if not snap.get("bound"):
            return "No project is selected, so I cannot list prop views."
        rows = _match_named_row(list(snap.get("props") or []), text)
        if not rows:
            return "This project has no Prop records yet."
        parts = []
        for row in rows:
            name = str(row.get("name") or "Prop").strip()
            parts.append(f"{name} approved views: {_format_approved_views(row.get('approvedViews') or [])}.")
        return " ".join(parts)
    if _PROP_READY_Q.search(text):
        if not snap.get("bound"):
            return "No project is selected, so I cannot say whether a Prop is ready."
        rows = _match_named_row(list(snap.get("props") or []), text)
        if not rows:
            return "This project has no Prop records yet."
        parts = []
        seen: set[str] = set()
        for row in rows:
            rid = str(row.get("id") or row.get("name") or "")
            if rid in seen:
                continue
            seen.add(rid)
            name = str(row.get("name") or "Prop").strip()
            ready = bool(row.get("identityReady") or row.get("propReady"))
            if ready:
                parts.append(
                    f"{name} is ready. Primary is approved. Additional views are optional."
                )
            else:
                parts.append(
                    f"{name} is not ready. Approve Primary to make this Prop ready. Additional views are optional."
                )
        return " ".join(parts)
    if _CHARACTERS_Q.search(text):
        if not snap.get("bound"):
            return "No project is selected, so I do not have an active cast."
        names = [str(c.get("name") or "").strip() for c in (snap.get("characters") or []) if c.get("name")]
        if not names:
            return "This project has no character records yet."
        if len(names) == 1:
            return f"The active character in this project is {names[0]}."
        if len(names) == 2:
            return f"The active characters in this project are {names[0]} and {names[1]}."
        return f"The active characters in this project are {', '.join(names[:-1])}, and {names[-1]}."
    if _VOICES_Q.search(text):
        if not snap.get("bound"):
            return "No project is selected, so I cannot list assigned voices."
        voices = snap.get("voiceAssignments") or []
        if not voices:
            return "No voices are assigned to the characters in this project."
        bits = []
        for voice in voices:
            engine = voice.get("engine") or "unspecified engine"
            label = voice.get("voiceName") or voice.get("voiceProfileId")
            bits.append(
                f"{voice.get('characterName')} is assigned {label} ({engine}, {voice.get('approval') or 'draft'})"
            )
        return " ".join(bits) + "."
    if _SCENE_Q.search(text):
        if not snap.get("bound"):
            return "No project is selected, so there is no active scene."
        sw_scene = snap.get("scriptwriterScene")
        if sw_scene:
            return (
                f"You are editing {sw_scene.get('heading')} "
                f"(scene {sw_scene.get('position')} of {sw_scene.get('total')} in the script)."
            )
        scene = snap.get("activeScene")
        if not scene:
            return "No scene is selected in this turn."
        return f"We are working on {scene.get('name')}."
    if _HAPPENS_Q.search(text):
        if not snap.get("bound"):
            return "No project is selected, so I cannot describe this scene."
        timeline = snap.get("timelineSnapshot") or {}
        summary = str(timeline.get("sceneSummary") or "").strip()
        prompt = str(timeline.get("scenePrompt") or "").strip()
        scene = snap.get("activeScene") or {}
        name = scene.get("name") or "this scene"
        if summary:
            return f"In {name}: {summary}"
        if prompt:
            return f"The Scene Prompt for {name} is: {prompt[:400]}"
        return f"I have {name} bound, but there is no Scene Prompt or summary on the Timeline yet."
    if _TAKE_Q.search(text):
        timeline = snap.get("timelineSnapshot") or {}
        if not timeline.get("hasTimelineSnapshot"):
            return "No Timeline scene is bound, so I cannot name the current take."
        scene_take = timeline.get("currentSceneTake") or {}
        published = timeline.get("publishedTake") or {}
        takes = timeline.get("sceneTakes") or []
        current_label = (
            scene_take.get("displayLabel")
            or scene_take.get("label")
            or (timeline.get("currentTake") or {}).get("sceneTakeLabel")
        )
        pub_label = published.get("label") or published.get("displayLabel")
        if re.search(r"published", text, re.I):
            if pub_label:
                return f"The published master is {pub_label}."
            return "Nothing is published yet, so there is no published Take."
        if re.search(r"compare", text, re.I) and len(takes) >= 2:
            names = [str(t.get("displayLabel") or t.get("label")) for t in takes[:4]]
            return (
                "I can preview each whole-scene Take on the Timeline Preview Monitor. "
                f"Available Takes: {', '.join(names)}. Preview one, then the other — they stay separate renders."
            )
        if current_label:
            extra = f" The published master is still {pub_label}." if pub_label and pub_label != current_label else ""
            return f"The current whole-scene Take is {current_label}.{extra}"
        take = timeline.get("currentTake") or {}
        take_id = take.get("takeId") or take.get("currentTakeId") or take.get("approvedClipAssetId")
        if not take_id:
            return "This Timeline scene has no current take yet."
        label = take.get("batchLabel") or take.get("batchId") or "the active batch"
        return f"The current take is {take_id} on {label}."
    if _is_spatial_placement_question(text, snap):
        return _spatial_placement_reply(snap)
    timeline = snap.get("timelineSnapshot") or {}
    if _SHOT_REFS_Q.search(text):
        if not timeline.get("hasTimelineSnapshot"):
            names = [str(c.get("name") or "").strip() for c in (snap.get("characters") or []) if c.get("name")]
            if names:
                return (
                    "I can see the project cast ("
                    + ", ".join(names)
                    + ") but this turn has no active Timeline shot bindings."
                )
            return "No Timeline shot is bound, so I cannot list who is referenced in this shot."
        refs = [r for r in (timeline.get("referencedInShot") or []) if r.get("type") == "character"]
        if not refs:
            return "This shot has no character Prompt Name bindings."
        bits = [str(r.get("promptName") or r.get("tag") or "character") for r in refs]
        return "This shot references " + (" and ".join(bits) if len(bits) <= 2 else ", ".join(bits[:-1]) + f", and {bits[-1]}") + "."
    if _ENV_Q.search(text) and not _PLATFORM_KNOWLEDGE_Q.search(text):
        if not timeline.get("hasTimelineSnapshot"):
            return "No Timeline shot is bound, so I cannot name the assigned environment."
        env = timeline.get("environment")
        if not env:
            return "No environment Prompt Name is bound on this shot."
        return f"The assigned environment is {env.get('promptName') or env.get('tag')}."
    if _GEN_Q.search(text) and not _PLATFORM_KNOWLEDGE_Q.search(text):
        if not timeline.get("hasTimelineSnapshot"):
            return "No Timeline scene is bound, so I cannot name the generator."
        gen = timeline.get("generatorId") or "unset"
        ready = timeline.get("generatorReadiness")
        if ready:
            return f"This scene is using {gen}. Runtime state: {ready}."
        return f"This scene is using {gen}."
    if _PRODUCTION_STATUS_Q.search(text):
        if not snap.get("bound"):
            return "No project is selected, so there is no production status."
        life = snap.get("productionLifecycle") or timeline.get("productionLifecycle") or {}
        scene_st = life.get("sceneReadyStatus") or "not recorded"
        prod = life.get("productionStatus") or "unknown"
        stage = life.get("projectStage") or "unknown"
        return (
            f"The production status of this scene is {scene_st}. "
            f"Project production is {prod} at stage {stage}. "
            "That is scene lifecycle, not Timeline batch approval."
        )
    if _APPROVAL_Q.search(text):
        if not timeline.get("hasTimelineSnapshot"):
            return "No Timeline scene is bound, so I cannot count approved Timeline batches."
        counts = timeline.get("batchApproval") or {}
        return (
            f"{counts.get('approved', 0)} Approved / {counts.get('draft', 0)} Draft "
            f"on this Timeline scene (approved means a batch has an approved clip, "
            "not scene production lifecycle)."
        )
    return None


def inspect_turn_grounding(
    db: Session,
    project_id: Optional[str],
    scene_id: Optional[str],
    text: str,
    *,
    workspace: Optional[str] = None,
    scriptwriter_scene_id: Optional[str] = None,
) -> dict[str, Any]:
    """Read-only turn inspect: snapshot, entity resolution, sanitized route lock."""

    snapshot = build_project_grounding_snapshot(
        db, project_id, scene_id, workspace=workspace, scriptwriter_scene_id=scriptwriter_scene_id
    )
    if snapshot.get("bound") and project_id:
        snapshot["productionLifecycle"] = _production_lifecycle_slice(db, str(project_id), scene_id)
    if snapshot.get("bound") and scene_id:
        from .active_timeline_scene_snapshot import build_active_timeline_scene_snapshot

        snapshot["timelineSnapshot"] = build_active_timeline_scene_snapshot(
            db, project_id, scene_id, workspace=workspace
        )
    resolution = resolve_turn_entities(db, str(project_id or ""), text)
    lock = parse_route_lock_excluding_entities(
        text,
        list(resolution.characters) + snapshot_entity_tokens(snapshot),
    )
    return {
        "snapshot": snapshot,
        "entities": resolution.to_dict(),
        "routeLock": {
            "level": lock.level,
            "scope": lock.scope,
            "requestedProvider": lock.requested_provider,
            "requestedModelId": lock.requested_model_id,
            "restated": lock.restated,
        },
        "routeParseSurface": route_parse_surface(
            text,
            [item.token for item in resolution.characters] + [item.name for item in resolution.characters],
        ),
        "sessionStatus": snapshot.get("sessionStatus"),
        "projectId": (snapshot.get("project") or {}).get("id") if snapshot.get("bound") else None,
        "activeSceneId": (snapshot.get("activeScene") or {}).get("id") if snapshot.get("activeScene") else None,
        "scriptwriterSceneId": (snapshot.get("scriptwriterScene") or {}).get("id") or None,
        "workspace": snapshot.get("workspace"),
    }
