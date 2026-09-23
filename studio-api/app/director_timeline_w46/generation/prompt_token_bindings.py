"""Resolve @ / # / % Prompt Name tokens in authored prose to scene-reference IDs.

Compile remains ID-only. Tokens in the prompt are a write-path hint: when a
registered Timeline reference matches, persist a PromptNameBinding so Modal,
Inspector, and the compiler share one clip object.

Do not invent bindings for unmatched tokens. Do not replace authored prose.
"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from ...director_timeline import DirectorTimeline, PromptSegment
from ...director_timeline_bindings import (
    PromptNameBinding,
    binding_ids_from_name_bindings,
    dump_prompt_name_binding,
    dump_prompt_name_bindings,
    normalize_prompt_binding_type,
    parse_prompt_name_bindings,
)

_TOKEN_RE = re.compile(
    r"(?P<tag>[@#%])(?P<name>[A-Za-z][A-Za-z0-9_-]*)"
)


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def extract_prompt_tokens(text: str | None) -> list[dict[str, str]]:
    """Unique @/#/% tokens in authored prompt order."""
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for match in _TOKEN_RE.finditer(text or ""):
        tag = f"{match.group('tag')}{match.group('name')}"
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        prefix = match.group("tag")
        kind = "character" if prefix == "@" else "environment" if prefix == "#" else "prop"
        out.append({"tag": tag, "name": match.group("name"), "type": kind})
    return out


def _catalog_keys(row: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for raw in (
        row.get("display_token"),
        row.get("displayToken"),
        row.get("alias"),
        row.get("asset_name"),
        row.get("assetName"),
        row.get("identity_name"),
        row.get("identityName"),
    ):
        token = str(raw or "").strip()
        if not token:
            continue
        keys.append(_norm(token))
        keys.append(_norm(token.lstrip("@#%")))
    return [k for k in keys if k]


def _binding_type(row: dict[str, Any]) -> str:
    kind = str(row.get("media_kind") or row.get("mediaKind") or "").lower()
    ref = str(row.get("reference_type") or row.get("referenceType") or "").lower()
    if ref in {"prop", "vehicle"} or kind == "prop":
        return "prop"
    if ref in {"environment", "location", "place", "scene"} or kind in {"environment", "video"}:
        if ref in {"environment", "location", "place", "scene"}:
            return "environment"
    if kind == "video" and ref not in {"character", "wardrobe", "creature"}:
        return "environment"
    return normalize_prompt_binding_type(ref or "character")


def load_project_prompt_name_index(db: Session | None, project_id: str | None) -> list[dict[str, Any]]:
    """Prompt Names already persisted on any Timeline clip in this project.

    Dialogue stores @Korri → binding_id even when the Scene Reference alias is
    still @CharacterSheet. Walk compile must reuse that mapping.
    """
    if not db or not project_id:
        return []
    try:
        from app.db import Scene

        extra: list[dict[str, Any]] = []
        seen: set[str] = set()
        scenes = db.query(Scene).filter(Scene.project_id == project_id).all()
        from app.director_timeline_w46.migration import extract_master_from_director_dict

        for scene in scenes:
            raw = getattr(scene, "director_json", None)
            if not raw:
                continue
            try:
                parsed = json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                continue
            master = extract_master_from_director_dict(parsed if isinstance(parsed, dict) else None)
            if master is None:
                continue
            for batch in getattr(master, "batchBlocks", None) or []:
                for seg in getattr(batch, "promptSegments", None) or []:
                    bindings = getattr(seg, "referenceNameBindings", None) or getattr(
                        seg, "reference_name_bindings", None
                    )
                    for row in dump_prompt_name_bindings(bindings):
                        bid = row.get("binding_id") or ""
                        name = row.get("prompt_name") or ""
                        tag = row.get("tag") or ""
                        key = f"{bid}:{_norm(name)}:{_norm(tag)}"
                        if not bid or key in seen:
                            continue
                        seen.add(key)
                        extra.append(
                            {
                                "id": bid,
                                "alias": name,
                                "asset_name": name,
                                "display_token": tag,
                                "reference_type": row.get("type") or "character",
                                "media_kind": "entity" if row.get("type") == "character" else row.get("type"),
                            }
                        )
        return extra
    except Exception:
        return []


def load_character_name_catalog(db: Session | None, project_id: str | None) -> list[dict[str, Any]]:
    """Character profile names → CRS bindings that already exist on the project."""
    if not db or not project_id:
        return []
    try:
        from app.character_identity.models import CharacterProfileRow
        from app.scene_references import repository as repo
        from app.scene_references.service import _enrich

        rows = (
            db.query(CharacterProfileRow)
            .filter(CharacterProfileRow.project_id == project_id)
            .all()
        )
        bindings = repo.list_bindings(db, project_id)
        extra: list[dict[str, Any]] = []
        for profile in rows:
            name = str(getattr(profile, "name", "") or "").strip()
            if not name:
                continue
            crs = str(getattr(profile, "crs_asset_id", "") or getattr(profile, "approved_still_asset_id", "") or "").strip()
            matched = None
            for binding in bindings:
                data = _enrich(db, repo.binding_to_dict(binding))
                if data.get("broken"):
                    continue
                if str(data.get("identity_id") or "") == str(profile.id):
                    matched = data
                    break
                if crs and str(data.get("asset_id") or "") == crs:
                    matched = data
                    break
            if not matched:
                continue
            extra.append(
                {
                    **matched,
                    "alias": name,
                    "asset_name": name,
                    "display_token": f"@{name.replace(' ', '')}",
                    "reference_type": "character",
                    "media_kind": "entity",
                }
            )
        return extra
    except Exception:
        return []


def load_scene_reference_catalog(db: Session | None, project_id: str | None, scene_id: str | None) -> list[dict[str, Any]]:
    if not db or not project_id:
        return []
    try:
        from app.scene_references import repository as repo
        from app.scene_references.service import _enrich

        rows = repo.list_bindings(db, project_id, scope_type="scene", scope_id=scene_id) if scene_id else []
        if not rows:
            rows = repo.list_bindings(db, project_id)
        catalog: list[dict[str, Any]] = []
        for row in rows:
            data = _enrich(db, repo.binding_to_dict(row))
            if data.get("broken"):
                continue
            catalog.append(data)
        catalog.extend(load_project_prompt_name_index(db, project_id))
        catalog.extend(load_character_name_catalog(db, project_id))
        return catalog
    except Exception:
        return []


def match_token_to_catalog(token: dict[str, str], catalog: list[dict[str, Any]]) -> dict[str, Any] | None:
    needle = _norm(token.get("name") or token.get("tag") or "")
    if not needle:
        return None
    wanted = str(token.get("type") or "character")
    typed: list[dict[str, Any]] = []
    for row in catalog:
        if _binding_type(row) != wanted:
            continue
        keys = _catalog_keys(row)
        if needle in keys or any(needle == k or k.endswith(needle) or needle.endswith(k) for k in keys if k):
            typed.append(row)
    if len(typed) == 1:
        return typed[0]
    exact = [row for row in typed if needle in _catalog_keys(row)]
    ids = {str(row.get("id") or "") for row in (exact or typed)}
    ids.discard("")
    if len(ids) == 1:
        return (exact or typed)[0]
    if len(exact) == 1:
        return exact[0]
    return None


def _grammar_tag(alias: str, reference_type: str, fallback_type: str = "") -> str:
    from app.creator_scope.identity_tag import sanitize_generator_tag

    kind = str(reference_type or fallback_type or "").lower()
    if kind in {"environment", "location", "place", "scene"}:
        entity = "environment"
    elif kind in {"prop", "vehicle"}:
        entity = "prop"
    else:
        entity = "character"
    return sanitize_generator_tag(entity, alias)


def backfill_name_binding_identities(
    rows: list[Any] | None,
    db: Session | None,
    project_id: str | None,
) -> list[PromptNameBinding]:
    """Fill empty tag/asset_id from the binding row once. Never name-match here."""
    parsed = parse_prompt_name_bindings(rows)
    if not db or not project_id:
        return parsed
    from .reference_compile import resolve_binding_id

    out: list[PromptNameBinding] = []
    for row in parsed:
        data = dump_prompt_name_binding(row)
        if not data["binding_id"]:
            out.append(PromptNameBinding.model_validate(data))
            continue
        resolved = resolve_binding_id(db, project_id, data["binding_id"])
        if resolved.get("broken"):
            out.append(PromptNameBinding.model_validate(data))
            continue
        if not data["asset_id"]:
            data["asset_id"] = str(resolved.get("assetId") or "").strip()
        if not data["identity_id"]:
            data["identity_id"] = str(resolved.get("identityId") or "").strip()
        if not data["reference_sheet_id"]:
            data["reference_sheet_id"] = str(resolved.get("approvedSheetAssetId") or "").strip()
        live_tag = _grammar_tag(
            str(resolved.get("canonicalTag") or resolved.get("displayToken") or resolved.get("alias") or ""),
            str(resolved.get("referenceType") or ""),
            data["type"],
        )
        if live_tag:
            data["tag"] = live_tag
        elif not data["tag"]:
            data["tag"] = _grammar_tag(
                str(resolved.get("alias") or ""),
                str(resolved.get("referenceType") or ""),
                data["type"],
            )
        out.append(PromptNameBinding.model_validate(data))
    return out


def resolve_prompt_tokens_to_bindings(
    text: str | None,
    catalog: list[dict[str, Any]],
    existing: list[Any] | None = None,
) -> list[PromptNameBinding]:
    """Union existing name-bindings with tokens that resolve to registered refs."""
    rows = parse_prompt_name_bindings(existing)
    seen = {row.binding_id for row in rows if row.binding_id}
    for token in extract_prompt_tokens(text):
        matched = match_token_to_catalog(token, catalog)
        if not matched:
            continue
        binding_id = str(matched.get("id") or "").strip()
        if not binding_id or binding_id in seen:
            continue
        seen.add(binding_id)
        alias = str(matched.get("alias") or matched.get("asset_name") or token["name"]).strip()
        rows.append(
            PromptNameBinding(
                binding_id=binding_id,
                prompt_name=str(matched.get("asset_name") or token["name"]).strip(),
                type=normalize_prompt_binding_type(token["type"]),
                tag=token["tag"] if token["tag"].startswith(("@", "#", "%")) else f"{token['tag'][:1]}{alias}",
            )
        )
    return rows


def hydrate_segment_prompt_tokens(
    segment: Any,
    catalog: list[dict[str, Any]],
    *,
    db: Session | None = None,
    project_id: str | None = None,
) -> bool:
    """Fill empty/partial Prompt Name arrays from registered tokens in `text`. Returns True if changed.

    Works on both legacy PromptSegment (reference_name_bindings /
    reference_binding_ids) and Master TimelinePromptSegment
    (referenceNameBindings / referenceBindingIds).
    """
    names_attr = "referenceNameBindings" if hasattr(segment, "referenceNameBindings") else "reference_name_bindings"
    ids_attr = "referenceBindingIds" if hasattr(segment, "referenceBindingIds") else "reference_binding_ids"
    existing = backfill_name_binding_identities(
        getattr(segment, names_attr, None),
        db,
        project_id,
    )
    resolved = backfill_name_binding_identities(
        resolve_prompt_tokens_to_bindings(
            getattr(segment, "text", "") or "",
            catalog,
            existing,
        ),
        db,
        project_id,
    )
    ids = binding_ids_from_name_bindings(resolved)
    before_ids = list(getattr(segment, ids_attr, None) or [])
    for existing in before_ids:
        if existing and existing not in ids:
            ids.append(existing)
    before_names = dump_prompt_name_bindings(getattr(segment, names_attr, None))
    after_names = dump_prompt_name_bindings(resolved)
    if before_ids == ids and before_names == after_names:
        return False
    setattr(segment, names_attr, resolved)
    setattr(segment, ids_attr, ids)
    return True


def hydrate_timeline_prompt_tokens(
    timeline: DirectorTimeline,
    catalog: list[dict[str, Any]],
    *,
    db: Session | None = None,
    project_id: str | None = None,
    master: Any = None,
) -> bool:
    """Hydrate @/#/% tokens on Master promptSegments (single store).

    Master is required. The legacy Director adapter is never walked.
    """
    if master is None:
        return False
    changed = False
    for batch in getattr(master, "batchBlocks", None) or []:
        for seg in getattr(batch, "promptSegments", None) or []:
            if hydrate_segment_prompt_tokens(seg, catalog, db=db, project_id=project_id):
                changed = True
    return changed
