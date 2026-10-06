"""Live Production Readiness from current Timeline scene bindings.

The scene is the truth. This evaluator reuses SceneReferenceBinding,
resolve_binding_id, and PromptNameBinding — it does not invent a second
resolver and does not treat Co-Director chat / upsert flags as primary.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from .contracts import ReadinessDepartment

_CAMEL = re.compile(r"([a-z])([A-Z])")


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _pretty_name(raw: str) -> str:
    token = (raw or "").strip().lstrip("@#%")
    token = re.sub(r"\d+$", "", token)
    token = _CAMEL.sub(r"\1 \2", token)
    token = token.replace("_", " ").replace("-", " ")
    return " ".join(token.split()) or (raw or "").strip()


def _join_names(names: list[str]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{', '.join(names[:-1])}, and {names[-1]}"


def _advisory_reason(category: str, missing: list[str]) -> str:
    joined = _join_names(missing)
    if category == "location":
        if len(missing) == 1:
            return f"{joined} is not explicitly bound as an environment."
        return f"{joined} are not explicitly bound as environments."
    if category == "references":
        return (
            "Some named scene elements do not currently have explicit reference bindings: "
            + ", ".join(missing)
        )
    if category == "cast":
        if len(missing) == 1:
            return f"{joined} is mentioned but is not explicitly bound as a cast reference."
        return f"{joined} are mentioned but are not explicitly bound as cast references."
    return f"Missing {joined}"


def _dept(
    category: str,
    *,
    status: str,
    reason: str = "",
    resolved: int = 0,
    required: int = 0,
    items: list[str] | None = None,
    missing: list[str] | None = None,
) -> ReadinessDepartment:
    return ReadinessDepartment(
        category=category,
        status=status,  # type: ignore[arg-type]
        reason=reason,
        resolved=resolved,
        required=required,
        items=list(items or []),
        missing=list(missing or []),
    )


def _kind_of(reference_type: str | None, prompt_type: str | None = None) -> str:
    raw = str(reference_type or prompt_type or "").strip().lower()
    if raw in {"environment", "location", "place", "scene"}:
        return "environment"
    if raw in {"prop", "vehicle"}:
        return "prop"
    if raw in {"character", "wardrobe", "creature"}:
        return "character"
    return raw or "reference"


def _collect_timeline(db: Session, project_id: str, scene_id: str) -> tuple[Any, Any, Any]:
    scene_row = None
    master = None
    try:
        from app.db import Scene as SceneModel

        scene_row = db.get(SceneModel, scene_id)
    except Exception:  # noqa: BLE001
        scene_row = None
    if scene_row is not None:
        try:
            from app.director_timeline_w46.service import load_timeline_bundle

            bundle = load_timeline_bundle(db, project_id, scene_id)
            if bundle.get("ok"):
                master = bundle.get("master")
        except Exception:  # noqa: BLE001
            master = None
    return scene_row, master


def _master_segments(master: Any) -> list[Any]:
    segs: list[Any] = []
    for batch in getattr(master, "batchBlocks", None) or []:
        segs.extend(getattr(batch, "promptSegments", None) or [])
    return segs


def _prompt_texts(scene_row: Any, master: Any) -> list[str]:
    texts: list[str] = []
    if scene_row is not None:
        texts.append(str(getattr(scene_row, "prompt", "") or ""))
    for seg in _master_segments(master):
        for field in ("text", "userDirection", "productionPrompt", "dialogue"):
            texts.append(str(getattr(seg, field, "") or ""))
    return [t for t in texts if t.strip()]


def _name_hint_index(master: Any) -> dict[str, str]:
    from app.director_timeline_bindings import dump_prompt_name_bindings

    hints: dict[str, str] = {}
    for seg in _master_segments(master):
        for row in dump_prompt_name_bindings(getattr(seg, "referenceNameBindings", None)):
            name = str(row.get("prompt_name") or "").strip()
            if not name:
                continue
            for raw in (row.get("binding_id"), row.get("tag"), row.get("prompt_name")):
                key = _norm(str(raw or ""))
                if key:
                    hints[key] = name
    return hints


def _collect_binding_ids(scene_row: Any, master: Any) -> list[str]:
    from app.director_timeline_bindings import binding_ids_from_name_bindings

    ids: list[str] = []
    seen: set[str] = set()

    def add(token: str | None) -> None:
        bid = str(token or "").strip()
        if bid and bid not in seen:
            seen.add(bid)
            ids.append(bid)

    for seg in _master_segments(master):
        for bid in getattr(seg, "referenceBindingIds", None) or []:
            add(bid)
        for bid in binding_ids_from_name_bindings(getattr(seg, "referenceNameBindings", None)):
            add(bid)
    return ids


def _voice_required(scene_row: Any, timeline: Any, master: Any = None) -> bool:
    """Same speech authority as generation — never infer Voice not required from omission."""
    if scene_row is not None:
        if str(getattr(scene_row, "audio_asset_id", "") or "").strip():
            return True
        if str(getattr(scene_row, "lipsync_audio_asset_id", "") or "").strip():
            return True
        if int(getattr(scene_row, "lipsync_enabled", 0) or 0):
            return True
    lipsync = getattr(timeline, "lipsync", None)
    for track in getattr(lipsync, "tracks", None) or []:
        for clip in getattr(track, "clips", None) or []:
            if str(getattr(clip, "audio_asset_id", "") or "").strip():
                return True

    def _seg_requires_voice(seg: Any) -> bool:
        if str(getattr(seg, "dialogue", "") or "").strip():
            return True
        intents = [str(x).lower() for x in (getattr(seg, "audio_intent", None) or [])]
        if any(token in {"speech", "dialogue", "voice", "line"} for token in intents):
            return True
        text_val = str(getattr(seg, "text", "") or getattr(seg, "promptText", "") or "")
        if not text_val.strip():
            return False
        try:
            from app.director_timeline_w46.generation.speech_compile import (
                extract_dialogue_cues,
                prompt_text_implies_speech,
            )
        except Exception:
            if '"' in text_val or "\u201c" in text_val or "\u201d" in text_val:
                return True
            return bool(
                re.search(
                    r"\b(says|said|asks|asked|whispers|shouts|yells)\b",
                    text_val,
                    re.I,
                )
            )
        if prompt_text_implies_speech(text_val):
            return True
        try:
            if extract_dialogue_cues(seg, db=None, project_id=None):
                return True
        except Exception:
            pass
        return False

    for seg in getattr(timeline, "prompt_segments", None) or []:
        if _seg_requires_voice(seg):
            return True
    for batch in getattr(master, "batchBlocks", None) or []:
        for seg in getattr(batch, "promptSegments", None) or []:
            if _seg_requires_voice(seg):
                return True
    return False


def _display_name(resolved: dict[str, Any], hints: dict[str, str], fallback: str = "") -> str:
    for raw in (
        hints.get(_norm(str(resolved.get("bindingId") or ""))),
        hints.get(_norm(str(resolved.get("alias") or ""))),
        resolved.get("alias"),
        fallback,
    ):
        name = str(raw or "").strip()
        if name:
            pretty = _pretty_name(name) if name.startswith(("@", "#", "%")) or " " not in name else name
            if pretty:
                return pretty
    return _pretty_name(fallback) or "Reference"


def _timeline_bindings(db: Session, project_id: str, scene_id: str) -> list[dict[str, Any]]:
    """Bindings the Timeline References pane can use on this scene.

    Timeline stores @ / % / # tags on the project. Scene rows are the same
    store. Inheritance is the one catalog — not a second scene-only list.
    """
    from app.scene_references.service import list_for_scope

    try:
        return list_for_scope(
            db,
            project_id,
            "scene",
            scene_id,
            include_inherited=True,
        )
    except Exception:  # noqa: BLE001
        return []


def _scene_catalog(db: Session, project_id: str, scene_id: str, master: Any) -> list[dict[str, Any]]:
    """Catalog for this scene — inherited Timeline bindings, not a prompt-name fork."""
    from app.director_timeline_bindings import dump_prompt_name_bindings

    catalog: list[dict[str, Any]] = []
    for data in _timeline_bindings(db, project_id, scene_id):
        if data.get("broken"):
            continue
        catalog.append(data)
    for seg in _master_segments(master):
        for row in dump_prompt_name_bindings(getattr(seg, "referenceNameBindings", None)):
            bid = str(row.get("binding_id") or "").strip()
            if not bid:
                continue
            catalog.append(
                {
                    "id": bid,
                    "alias": row.get("prompt_name") or row.get("tag"),
                    "asset_name": row.get("prompt_name"),
                    "display_token": row.get("tag"),
                    "reference_type": row.get("type") or "character",
                    "media_kind": row.get("type"),
                }
            )
    return catalog


def _covers_token(token: dict[str, str], records: dict[str, dict[str, Any]]) -> bool:
    needle = _norm(str(token.get("name") or token.get("tag") or ""))
    wanted = _kind_of(None, str(token.get("type") or ""))
    if not needle:
        return False
    for row in records.values():
        if row.get("broken"):
            continue
        if wanted and row.get("kind") not in {wanted, "reference"}:
            if not (wanted == "environment" and row.get("kind") == "environment"):
                if row.get("kind") != wanted:
                    continue
        key = _norm(str(row.get("name") or ""))
        if needle == key or key.endswith(needle) or needle.endswith(key):
            return True
    return False


def compute_live_scene_readiness(db: Session, project_id: str, scene_id: str) -> dict[str, Any]:
    """Compute Location / References / Cast / Voice from the current scene."""
    from app.director_timeline_w46.generation.prompt_token_bindings import (
        extract_prompt_tokens,
        match_token_to_catalog,
    )
    from app.director_timeline_w46.generation.reference_compile import resolve_binding_id

    scene_row, master = _collect_timeline(db, project_id, scene_id)
    hints = _name_hint_index(master)
    texts = _prompt_texts(scene_row, master)
    tokens = []
    seen_tokens: set[str] = set()
    for text in texts:
        for token in extract_prompt_tokens(text):
            key = str(token.get("tag") or "").lower()
            if key in seen_tokens:
                continue
            seen_tokens.add(key)
            tokens.append(token)

    catalog = _scene_catalog(db, project_id, scene_id, master)
    records: dict[str, dict[str, Any]] = {}

    def upsert(key: str, *, kind: str, name: str, broken: bool, reason: str = "") -> None:
        existing = records.get(key)
        if existing is None:
            records[key] = {
                "key": key,
                "kind": kind,
                "name": name,
                "broken": broken,
                "reason": reason,
            }
            return
        if name and (not existing["name"] or len(name) > len(str(existing["name"]))):
            existing["name"] = name
        if broken:
            existing["broken"] = True
            existing["reason"] = reason or existing["reason"]
        if kind and existing.get("kind") in {"", "reference"}:
            existing["kind"] = kind

    for bid in _collect_binding_ids(scene_row, master):
        resolved = resolve_binding_id(db, project_id, bid)
        kind = _kind_of(str(resolved.get("referenceType") or ""))
        name = _display_name(resolved, hints)
        upsert(
            bid,
            kind=kind or "reference",
            name=name,
            broken=bool(resolved.get("broken")),
            reason=str(resolved.get("brokenReason") or "broken_reference"),
        )

    for data in _timeline_bindings(db, project_id, scene_id):
        bid = str(data.get("id") or "")
        if not bid:
            continue
        resolved = resolve_binding_id(db, project_id, bid)
        kind = _kind_of(str(data.get("reference_type") or resolved.get("referenceType") or ""))
        alias = str(data.get("alias") or "")
        name = hints.get(_norm(bid)) or hints.get(_norm(alias)) or _pretty_name(alias) or _display_name(resolved, hints)
        upsert(
            bid,
            kind=kind,
            name=name,
            broken=bool(resolved.get("broken") or data.get("broken")),
            reason=str(resolved.get("brokenReason") or data.get("broken_reason") or "broken_reference"),
        )

    for token in tokens:
        if _covers_token(token, records):
            continue
        matched = match_token_to_catalog(token, catalog)
        token_name = hints.get(_norm(token.get("name") or "")) or hints.get(_norm(token.get("tag") or "")) or _pretty_name(
            str(token.get("name") or token.get("tag") or "")
        )
        kind = _kind_of(None, str(token.get("type") or ""))
        if matched:
            bid = str(matched.get("id") or "").strip()
            resolved = resolve_binding_id(db, project_id, bid) if bid else {"broken": True, "brokenReason": "missing_binding"}
            name = (
                hints.get(_norm(bid))
                or str(matched.get("asset_name") or "").strip()
                or token_name
                or _display_name(resolved, hints, token_name)
            )
            if name in {"environment_reference", "advanced_prop_reference_sheet", "character_reference"}:
                name = token_name or _pretty_name(str(matched.get("alias") or bid))
            upsert(
                bid or f"token:{kind}:{_norm(token.get('tag') or '')}",
                kind=kind,
                name=name,
                broken=bool(resolved.get("broken")),
                reason=str(resolved.get("brokenReason") or ""),
            )
            continue
        upsert(
            f"token:{kind}:{_norm(token.get('tag') or token.get('name') or '')}",
            kind=kind,
            name=token_name or _pretty_name(str(token.get("name") or "")),
            broken=True,
            reason=f"Missing {token_name or token.get('tag') or 'reference'}",
        )

    items = list(records.values())
    locations = [row for row in items if row["kind"] == "environment"]
    characters = [row for row in items if row["kind"] == "character"]
    refs = items

    def summarize(category: str, rows: list[dict[str, Any]], empty_reason: str) -> ReadinessDepartment:
        if not rows:
            return _dept(category, status="not_required", reason=empty_reason)
        missing = [str(row["name"]) for row in rows if row.get("broken")]
        ready_names = [str(row["name"]) for row in rows if not row.get("broken")]
        if missing:
            return _dept(
                category,
                status="advisory",
                reason=_advisory_reason(category, missing),
                resolved=len(ready_names),
                required=len(rows),
                items=ready_names,
                missing=missing,
            )
        return _dept(
            category,
            status="ready",
            reason="",
            resolved=len(ready_names),
            required=len(rows),
            items=ready_names,
        )

    location = summarize("location", locations, "No environment binding on this scene")
    if location.status == "ready" and location.items:
        location.reason = location.items[0]
    references = summarize("references", refs, "No references attached to this scene")
    if references.status == "ready":
        references.reason = f"{references.resolved}/{references.required} resolved"
    cast = summarize("cast", characters, "No character performance required")
    if _voice_required(scene_row, None, master=master):
        speaking = [row for row in characters if not row.get("broken")]
        if not speaking:
            voice = _dept(
                "voice",
                status="advisory",
                reason="Dialogue is present without an explicit voice assignment.",
            )
        else:
            voice = _dept(
                "voice",
                status="ready",
                reason="",
                resolved=len(speaking),
                required=len(speaking),
                items=[row["name"] for row in speaking],
            )
    else:
        voice = _dept("voice", status="not_required", reason="No dialogue or speaking character in current scene")

    departments = [location, references, cast, voice]
    blocked = [d for d in departments if d.status == "blocked"]
    advisories = [d for d in departments if d.status == "advisory"]
    generation_plan_ready = bool(
        any(texts)
        or (scene_row is not None and getattr(scene_row, "engine", None))
    )
    if blocked:
        status = "BLOCKED"
        blocker = "; ".join(d.reason for d in blocked if d.reason)
    elif advisories:
        status = "PARTIAL"
        blocker = f"Ready with {len(advisories)} advisories"
    else:
        status = "READY"
        blocker = ""

    return {
        "ok": True,
        "sceneId": scene_id,
        "status": status,
        "blockerSummary": blocker,
        "liveComputed": True,
        "castRequired": cast.status != "not_required",
        "voiceRequired": voice.status != "not_required",
        "locationRequired": location.status != "not_required",
        "referencesRequired": references.status != "not_required",
        "castReady": cast.status != "blocked",
        "locationReady": location.status != "blocked",
        "wardrobeReady": True,
        "propsReady": references.status != "blocked",
        "imageReferencesReady": references.status != "blocked",
        "voiceReady": voice.status != "blocked",
        "audioPlanReady": voice.status != "blocked",
        "generationPlanReady": generation_plan_ready,
        "requiredCharacters": [row["name"] for row in characters],
        "departments": [d.model_dump(mode="json") for d in departments],
        "location": location.model_dump(mode="json"),
        "references": references.model_dump(mode="json"),
        "cast": cast.model_dump(mode="json"),
        "voice": voice.model_dump(mode="json"),
    }
