"""Image Generator prompt-token compile (@Character %Prop #Environment ~GenericImage).

Creator-facing tags stay in the prompt. This module resolves them to Library
asset ids for referenceAssetIds / provenance. Timeline R2V binding grammar is
unchanged (@ # % *); ~ is Image Generator Other Image References authority.

Also compiles typed CIS-shaped authority packs (character / environment / prop)
so Co-Director image.generate preserves asset IDs — not text-only identity.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from ..scene_references.sheet_tags import (
    GENERIC_IMAGE_REFERENCE_TYPE,
    PREFIX_CRS,
    PREFIX_ERS,
    PREFIX_GENERIC_IMAGE,
    PREFIX_PRS,
    pascal_alias,
)

_TOKEN_RE = re.compile(r"(?P<tag>[@#%~])(?P<name>[A-Za-z][A-Za-z0-9_-]*)")

_KIND_BY_TAG = {
    PREFIX_CRS: "character",
    PREFIX_PRS: "prop",
    PREFIX_ERS: "environment",
    PREFIX_GENERIC_IMAGE: GENERIC_IMAGE_REFERENCE_TYPE,
}

# CisAuthorityKind: character | prop | environment | posecraft | other
_CIS_KINDS = frozenset({"character", "prop", "environment", "posecraft", "other"})


def extract_image_prompt_tokens(text: str | None) -> list[dict[str, str]]:
    """Unique creator tokens in authored order."""
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for match in _TOKEN_RE.finditer(text or ""):
        tag = match.group("tag")
        name = pascal_alias(match.group("name"))
        if not name:
            continue
        token = f"{tag}{name}"
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        kind = _KIND_BY_TAG.get(tag, "unknown")
        out.append({"tag": tag, "name": name, "token": token, "kind": kind})
    return out


def _alias_norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _bindings_by_alias(db: Session, project_id: str) -> dict[str, Any]:
    from ..scene_references.models import SceneReferenceBinding

    rows = (
        db.query(SceneReferenceBinding)
        .filter(
            SceneReferenceBinding.project_id == project_id,
            SceneReferenceBinding.deleted_at.is_(None),
            SceneReferenceBinding.enabled.is_(True),
        )
        .all()
    )
    out: dict[str, Any] = {}
    for row in rows:
        alias = pascal_alias(str(getattr(row, "alias", "") or ""))
        if not alias:
            continue
        out[_alias_norm(alias)] = row
    return out


def approved_ers_composite_id(db: Session, project_id: str) -> str:
    """Hard-default place lock: approved canonical ERS composite ONLY.

    Draft sheets with a composite must NEVER promote. Authority is the project
    approvedCanonicalSheetId pointer (set only by creator Approve), with
    fallback to newest status==approved sheet.
    """
    try:
        from ..environment_reference_sheet.versioning import resolve_canonical_sheet
    except Exception:
        try:
            from ..environment_reference_sheet.store import list_sheets
        except Exception:
            return ""
        sheets = [s for s in (list_sheets(project_id) or []) if getattr(s, "status", "") == "approved"]
        pick = sheets[0] if sheets else None
        if pick is None:
            return ""
        return str(getattr(pick, "ers_composite_asset_id", "") or "").strip()

    sheet = resolve_canonical_sheet(project_id)
    if sheet is None:
        return ""
    cid = str(getattr(sheet, "ers_composite_asset_id", "") or "").strip()
    if cid:
        return cid
    rendered = getattr(getattr(sheet, "composition", None), "renderedAssetIds", None) or {}
    if isinstance(rendered, dict):
        for key in ("composite", "png", "sheet"):
            val = str(rendered.get(key) or "").strip()
            if val:
                return val
    return ""


def resolve_image_prompt_tokens(
    db: Session | None,
    project_id: str,
    text: str | None,
    *,
    hard_default_approved_ers: bool = True,
) -> dict[str, Any]:
    """Compile creator tokens to reference asset ids."""
    tokens = extract_image_prompt_tokens(text)
    if db is None:
        return {
            "tokens": tokens,
            "reference_asset_ids": [],
            "unresolved": [t["token"] for t in tokens],
            "approved_ers_asset_id": None,
            "applied_default_ers": False,
        }

    bindings = _bindings_by_alias(db, project_id)
    asset_ids: list[str] = []
    unresolved: list[str] = []
    resolved_tokens: list[dict[str, Any]] = []

    def _push(aid: str) -> None:
        aid = str(aid or "").strip()
        if aid and aid not in asset_ids:
            asset_ids.append(aid)

    for item in tokens:
        tag = item["tag"]
        name = item["name"]
        token = item["token"]
        row = bindings.get(_alias_norm(name))
        asset_id = ""
        source = ""

        if row is not None:
            asset_id = str(getattr(row, "asset_id", "") or "").strip()
            source = "scene_reference_binding"

        if not asset_id and tag == PREFIX_CRS:
            try:
                from ..codirector.entity_resolver import resolve_character

                hit = resolve_character(db, project_id, name)
                if hit:
                    asset_id = str(hit.get("approved_casting_asset_id") or "").strip()
                    source = "character_approved"
            except Exception:
                pass

        if not asset_id and tag == PREFIX_PRS:
            try:
                from ..codirector.entity_resolver import resolve_prop

                prop = resolve_prop(db, project_id, name)
                if prop is not None:
                    asset_id = str(
                        getattr(prop, "approved_asset_id", None)
                        or getattr(prop, "library_asset_id", None)
                        or ""
                    ).strip()
                    source = "prop_approved"
            except Exception:
                pass

        if not asset_id and tag == PREFIX_ERS:
            asset_id = approved_ers_composite_id(db, project_id)
            source = "approved_ers_alias" if _alias_norm(name) in {"environment", "place", "ers"} else "approved_ers_fallback"

        if not asset_id and tag == PREFIX_GENERIC_IMAGE:
            source = "unresolved_generic"

        entry = {
            **item,
            "assetId": asset_id or None,
            "source": source or ("unresolved" if not asset_id else source),
        }
        resolved_tokens.append(entry)
        if asset_id:
            _push(asset_id)
        else:
            unresolved.append(token)

    approved_ers = approved_ers_composite_id(db, project_id)
    applied_default = False
    has_env_token = any(t.get("tag") == PREFIX_ERS for t in tokens)
    if hard_default_approved_ers and approved_ers and not has_env_token:
        if approved_ers not in asset_ids:
            asset_ids.append(approved_ers)
            applied_default = True
            resolved_tokens.append(
                {
                    "tag": PREFIX_ERS,
                    "name": "Environment",
                    "token": "#Environment",
                    "kind": "environment",
                    "assetId": approved_ers,
                    "source": "approved_ers_hard_default",
                }
            )

    return {
        "tokens": resolved_tokens,
        "reference_asset_ids": asset_ids,
        "unresolved": unresolved,
        "approved_ers_asset_id": approved_ers or None,
        "applied_default_ers": applied_default,
    }


def merge_token_reference_ids(
    existing: list[str] | None,
    compiled: dict[str, Any] | None,
) -> list[str]:
    """Creator/UI refs first; compiled token ids appended uniquely."""
    out: list[str] = []
    for aid in list(existing or []) + list((compiled or {}).get("reference_asset_ids") or []):
        s = str(aid or "").strip()
        if s and s not in out:
            out.append(s)
    return out


def cis_kind(raw: object) -> str:
    """Normalize to CisAuthorityKind (character|prop|environment|posecraft|other)."""
    kind = str(raw or "").strip().lower()
    if kind in {"generic_image", "generic", "other_image", "image"}:
        return "other"
    if kind in {"env", "place", "ers"}:
        return "environment"
    if kind in {"crs", "char", "character_ref"}:
        return "character"
    if kind in {"prs"}:
        return "prop"
    if kind in {"pose", "pose_craft", "posecraft"}:
        return "posecraft"
    if kind in _CIS_KINDS:
        return kind
    return "other"


def make_authority_ref(
    *,
    kind: str,
    asset_id: str,
    name: str = "",
    chip: str = "",
    key: str = "",
) -> dict[str, str] | None:
    """Build one CisAuthorityRef-shaped dict. Requires a non-empty assetId."""
    aid = str(asset_id or "").strip()
    if not aid:
        return None
    k = cis_kind(kind)
    nm = str(name or "").strip()
    ch = str(chip or "").strip()
    if not ch:
        prefix = {
            "character": PREFIX_CRS,
            "prop": PREFIX_PRS,
            "environment": PREFIX_ERS,
            "other": PREFIX_GENERIC_IMAGE,
        }.get(k, "")
        ch = f"{prefix}{nm}" if prefix and nm else (nm or aid)
    stable = str(key or "").strip() or f"{k}:{aid}"
    return {
        "key": stable,
        "kind": k,
        "assetId": aid,
        "name": nm or aid[:8],
        "chip": ch,
    }


def _ref_row(ref: dict[str, Any]) -> dict[str, Any]:
    kind = cis_kind(ref.get("kind"))
    aid = str(ref.get("assetId") or "").strip()
    name = str(ref.get("name") or "").strip()
    token = str(ref.get("chip") or ref.get("token") or "").strip()
    return {
        "kind": kind,
        "role": str(ref.get("role") or kind).strip() or kind,
        "assetId": aid,
        "name": name,
        "label": str(ref.get("label") or name or token or aid or "?").strip(),
        "token": token,
    }


def partition_authority_refs(refs: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Match FE serializeImageGeneratorPlan selected* + references + referenceAssetIds."""
    authority: list[dict[str, str]] = []
    seen_keys: set[str] = set()
    for raw in refs or []:
        if not isinstance(raw, dict):
            continue
        built = make_authority_ref(
            kind=str(raw.get("kind") or "other"),
            asset_id=str(raw.get("assetId") or raw.get("asset_id") or raw.get("id") or ""),
            name=str(raw.get("name") or ""),
            chip=str(raw.get("chip") or raw.get("token") or ""),
            key=str(raw.get("key") or ""),
        )
        if built is None:
            continue
        if built["key"] in seen_keys:
            continue
        seen_keys.add(built["key"])
        authority.append(built)

    selected_characters = [r for r in authority if r["kind"] == "character"]
    selected_props = [r for r in authority if r["kind"] == "prop"]
    selected_environment = next((r for r in authority if r["kind"] == "environment"), None)
    selected_pose = next((r for r in authority if r["kind"] == "posecraft"), None)
    selected_generic = [r for r in authority if r["kind"] == "other"]
    asset_ids: list[str] = []
    for r in authority:
        aid = r["assetId"]
        if aid and aid not in asset_ids:
            asset_ids.append(aid)
    pose_craft = {"attached": False}
    if selected_pose:
        pose_craft = {
            "attached": True,
            "imageAssetId": selected_pose["assetId"] or None,
            "name": selected_pose.get("name") or None,
            "chip": selected_pose.get("chip") or None,
        }
    return {
        "authorityRefs": authority,
        "selectedCharacters": selected_characters,
        "selectedProps": selected_props,
        "selectedEnvironment": selected_environment,
        "selectedPoseCraft": selected_pose,
        "selectedGeneric": selected_generic,
        "references": [_ref_row(r) for r in authority],
        "referenceAssetIds": asset_ids,
        "poseCraft": pose_craft,
    }


def _collect_planning_refs(planning: object | None) -> list[dict[str, Any]]:
    """Pull typed refs from a CIS planning snapshot (any partial shape)."""
    if not isinstance(planning, dict) or not planning:
        return []
    collected: list[dict[str, Any]] = []

    def _extend(items: object, default_kind: str) -> None:
        rows = items if isinstance(items, list) else ([items] if isinstance(items, dict) else [])
        for item in rows:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind") or default_kind)
            collected.append({**item, "kind": kind})

    auth = planning.get("authorityRefs")
    if isinstance(auth, list) and auth:
        _extend(auth, "other")
        return collected

    _extend(planning.get("selectedCharacters"), "character")
    _extend(planning.get("selectedProps"), "prop")
    env = planning.get("selectedEnvironment")
    if env is not None:
        _extend(env, "environment")
    pose = planning.get("selectedPoseCraft")
    if pose is not None:
        _extend(pose, "posecraft")
    _extend(planning.get("selectedGeneric"), "other")
    refs = planning.get("references")
    if isinstance(refs, list):
        for item in refs:
            if isinstance(item, dict):
                collected.append(item)

    # Flat ids only — no invented identity; kind stays other until typed elsewhere.
    flat = planning.get("referenceAssetIds")
    if isinstance(flat, list):
        known = {
            str(r.get("assetId") or r.get("asset_id") or r.get("id") or "").strip()
            for r in collected
            if isinstance(r, dict)
        }
        for aid in flat:
            s = str(aid or "").strip()
            if s and s not in known:
                collected.append({"kind": "other", "assetId": s, "name": "", "chip": ""})
                known.add(s)
    return collected


def compile_typed_image_authority(
    *,
    token_pack: dict[str, Any] | None = None,
    planning: object | None = None,
    authority_refs: list[dict[str, Any]] | None = None,
    reference_asset_ids: list[str] | None = None,
    character_asset_ids: list[str] | None = None,
    environment_asset_id: str = "",
    prop_asset_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Merge planning + tokens + typed ids into ONE CIS-shaped compile authority.

    Adapter-agnostic: does not select workflowKey / generator. Preserves asset
    IDs with kinds so downstream can bind pixels (not prose identity rewrite).
    Precedence: explicit authority_refs, then planning, then token kinds,
    then typed id lists, then leftover flat reference_asset_ids as other.
    """
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(item: dict[str, Any] | None) -> None:
        if not item:
            return
        built = make_authority_ref(
            kind=str(item.get("kind") or "other"),
            asset_id=str(item.get("assetId") or item.get("asset_id") or item.get("id") or ""),
            name=str(item.get("name") or ""),
            chip=str(item.get("chip") or item.get("token") or ""),
            key=str(item.get("key") or ""),
        )
        if built is None:
            return
        # Prefer first typed occurrence; skip duplicate asset ids.
        if built["assetId"] in seen:
            return
        seen.add(built["assetId"])
        merged.append(built)

    for raw in authority_refs or []:
        if isinstance(raw, dict):
            _add(raw)

    for raw in _collect_planning_refs(planning):
        _add(raw)

    for tok in list((token_pack or {}).get("tokens") or []):
        if not isinstance(tok, dict):
            continue
        aid = str(tok.get("assetId") or "").strip()
        if not aid:
            continue
        _add(
            {
                "kind": cis_kind(tok.get("kind")),
                "assetId": aid,
                "name": str(tok.get("name") or ""),
                "chip": str(tok.get("token") or tok.get("chip") or ""),
                "key": f"token:{tok.get('token') or aid}",
            }
        )

    for aid in character_asset_ids or []:
        _add({"kind": "character", "assetId": str(aid), "name": "", "chip": ""})
    if environment_asset_id:
        _add(
            {
                "kind": "environment",
                "assetId": str(environment_asset_id),
                "name": "Environment",
                "chip": "#Environment",
            }
        )
    for aid in prop_asset_ids or []:
        _add({"kind": "prop", "assetId": str(aid), "name": "", "chip": ""})

    # Flat leftovers (attachments / unresolved flat lists) stay typed as other —
    # never invent character/env identity from a bare UUID or display name.
    for aid in list(reference_asset_ids or []) + list(
        (token_pack or {}).get("reference_asset_ids") or []
    ):
        s = str(aid or "").strip()
        if s and s not in seen:
            _add({"kind": "other", "assetId": s, "name": "", "chip": ""})

    pack = partition_authority_refs(merged)
    pack["provenance"] = "codirector_image_authority_compile"
    return pack


def apply_typed_authority_to_body(body: dict[str, Any], pack: dict[str, Any] | None) -> dict[str, Any]:
    """Stamp CIS-shaped typed fields onto generation body + creativeContext."""
    if not isinstance(body, dict) or not isinstance(pack, dict) or not pack:
        return body
    ids = list(pack.get("referenceAssetIds") or [])
    if ids:
        existing = body.get("referenceAssetIds")
        if not isinstance(existing, list) or not existing:
            body["referenceAssetIds"] = list(ids)
        else:
            merged_ids: list[str] = []
            for aid in list(existing) + ids:
                s = str(aid or "").strip()
                if s and s not in merged_ids:
                    merged_ids.append(s)
            body["referenceAssetIds"] = merged_ids
        if not body.get("referenceImage") and not body.get("reference_image"):
            body["referenceImage"] = ids[0]
            body["reference_image"] = ids[0]

    ctx = body.get("creativeContext")
    if not isinstance(ctx, dict):
        ctx = {}
        body["creativeContext"] = ctx
    for key in (
        "authorityRefs",
        "selectedCharacters",
        "selectedProps",
        "selectedEnvironment",
        "selectedPoseCraft",
        "selectedGeneric",
        "references",
        "referenceAssetIds",
        "poseCraft",
    ):
        if key in pack:
            ctx[key] = pack[key]
            body[key] = pack[key]
    ctx["reference_image_ids"] = list(pack.get("referenceAssetIds") or ctx.get("reference_image_ids") or [])
    return body
