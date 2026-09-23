"""Bind project character identity onto Timeline Reference-to-Video.

A character name in a prompt is not proof of identity.

LTX 2.5 / generic R2V still attaches the Character Reference Sheet when
prefer_sheet=True. MiniMax H3 Reference-to-Video (J1–J7 proven / J10):
subject identity slots prefer Character Creator Front / hero_identity /
front-comparable single-subject portraits when Front exists. Multi-panel
CRS sheets alone WARN honestly (no silent hope); do not hard-block sheet tests.

LTX 2.3 still uses Ingredients IC-LoRA from hero tiles. LTX 2.5 and MiniMax H3
consume the canonical R2V contract — never ordinary I2V by stuffing one hero
into start.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ...character_identity.service import get_profile, resolve_approved_reference
from ...codirector.entity_resolver import _CHARACTER_TAG_RE, resolve_character
from ...config import settings
from ...db import Asset
from ...references import store as ref_store
from ...references.ic_lora_status import ingredients_status
from ...references.sheet_builder import SheetPanel, build_reference_sheet
from ...references.static_video import still_to_static_video
from ..contracts import BatchBlock
from .contracts import TimelineGenerationRequest

LTX_ADAPTER_IDS = frozenset(
    {
        "ltx-2.5-full",
        "ltx-2.5-distilled",
        "ltx-2.5-comfy",
    }
)
LTX_25_ADAPTER_IDS = frozenset({"ltx-2.5-full", "ltx-2.5-distilled", "ltx-2.5-comfy"})
H3_ADAPTER_IDS = frozenset(
    {
        "minimax-h3-i2v-local",
        "minimax-h3-i2v",
        "minimax-h3-t2v-local",
        "minimax-h3-local",
        "minimax-h3",
    }
)
H3_I2V_ADAPTER_IDS = H3_ADAPTER_IDS

# J10 Front-form preference (live path + unit tests)
from .h3_front_identity import (  # noqa: E402
    apply_h3_front_identity_to_request,
    apply_h3_front_identity_to_r2v_slots,
    is_multi_panel_crs_asset,
    resolve_h3_front_character_asset,
)


def product_generator_id(request: TimelineGenerationRequest, adapter_id: str) -> str:
    """Timeline product id, not the shared adapter alias.

    LTX 2.5 shares one adapter across its product rows. Identity must follow
    the selected product row or it silently routes through the wrong contract.
    """
    opts = request.providerOptions or {}
    return str(
        opts.get("originalGeneratorId")
        or opts.get("selectedGenerator")
        or request.generatorId
        or adapter_id
        or ""
    ).strip()


_SHEET_SUFFIXES = ("CRS", "ERS", "PRS", "Sheet", "ReferenceSheet", "Reference")


def _strip_sheet_suffix(token: str) -> str:
    """Strip a trailing sheet-designation suffix so @KorriCRS → Korri.

    The suffix is a reference-sheet designation, not part of the character name.
    """
    clean = (token or "").strip()
    for suffix in _SHEET_SUFFIXES:
        if len(clean) > len(suffix) and clean.endswith(suffix):
            base = clean[: -len(suffix)].rstrip(" -_")
            if base:
                return base
    return clean


def mentioned_character_names(text: str, known_names: list[str]) -> list[str]:
    """Resolve @tags and whole-word project character names from creator text.

    @KorriCRS is a reference token, not a separate character named "KorriCRS".
    When the suffix-stripped token (Korri) matches a known character name, the
    full token is dropped so the known name resolves normally — it is not
    reported as a missing character.
    """
    found: list[str] = []
    seen: set[str] = set()
    known_lower = {n.lower() for n in known_names if n and n.strip()}

    def _add(name: str) -> None:
        clean = (name or "").strip()
        key = clean.lower()
        if not clean or key in seen:
            return
        seen.add(key)
        found.append(clean)

    for match in _CHARACTER_TAG_RE.finditer(text or ""):
        token = match.group(1).strip()
        stripped = _strip_sheet_suffix(token)
        # If the suffix-stripped token matches a known character name, the
        # full token is a reference-sheet designation (e.g. @KorriCRS → Korri),
        # not a separate character. Add the base name so it resolves; never
        # add the full suffixed token as a phantom missing character.
        if stripped.lower() != token.lower() and stripped.lower() in known_lower:
            _add(stripped)
        else:
            _add(token)

    blob = text or ""
    for name in known_names:
        if len(name.strip()) < 3:
            continue
        if re.search(rf"\b{re.escape(name)}\b", blob, flags=re.IGNORECASE):
            _add(name)
    return found


def _known_names(db: Session, project_id: str) -> list[str]:
    from ...character_identity.service import list_profiles

    try:
        return [str(p.name).strip() for p in list_profiles(db, project_id) if str(p.name or "").strip()]
    except Exception as exc:
        # Partial test schemas omit character tables. Live DBs must still raise.
        if "no such table" in str(exc).lower():
            return []
        raise


def _appearance_from_profile(db: Session, project_id: str, character_id: str) -> str:
    token = str(character_id or "").strip()
    if not token:
        return ""
    try:
        profile = get_profile(db, project_id, token)
    except Exception:
        return ""
    parts: list[str] = []
    hair = profile.hair if isinstance(profile.hair, dict) else {}
    skin = profile.skin if isinstance(profile.skin, dict) else {}
    style = str(hair.get("canonical_style") or "").strip()
    tone = str(skin.get("skin_tone") or "").strip()
    if style:
        parts.append(style)
    if tone:
        parts.append(tone)
    species = str(profile.species_or_type or "").strip()
    if species and species.lower() not in {"human", "person"}:
        parts.append(species)
    desc = str(profile.visual_description or profile.description or "").strip()
    if desc:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", desc) if s.strip()]
        picked: list[str] = []
        for sentence in sentences:
            low = sentence.lower()
            wardrobe = any(
                word in low
                for word in (
                    "suit",
                    "attire",
                    "wardrobe",
                    "clothes",
                    "outfit",
                    "tattoo",
                    "hair",
                    "eyes",
                    "armor",
                )
            )
            if wardrobe or not picked:
                picked.append(sentence[:180])
            if len(picked) >= 2:
                break
        for sentence in picked:
            if sentence not in parts:
                parts.append(sentence)
    return "; ".join(parts)[:420]


def _is_front_still_asset(db: Session, project_id: str, asset_id: str) -> bool:
    aid = str(asset_id or "").strip()
    if not aid:
        return False
    asset = db.get(Asset, aid)
    if asset is None:
        return False
    if asset.project_id != project_id:
        try:
            from ...creator_scope.service import resolve_readable_asset

            if resolve_readable_asset(db, project_id, aid) is None:
                return False
        except Exception:
            return False
    from ...scene_references.sheet_tags import classify_asset

    return classify_asset(asset).kind == "front_still"


def _drop_front_still_character_refs(db: Session, project_id: str, batch: BatchBlock) -> None:
    """R2V must not keep hero Front.png slots next to a CRS."""
    kept: list[Any] = []
    for ref in batch.references or []:
        if not isinstance(ref, dict):
            kept.append(ref)
            continue
        kind = str(ref.get("kind") or "")
        role = str(ref.get("role") or "")
        if kind == "characterIdentity":
            assets = [
                aid
                for aid in (ref.get("identityAssetIds") or [])
                if not _is_front_still_asset(db, project_id, str(aid))
            ]
            if assets:
                next_ref = dict(ref)
                next_ref["identityAssetIds"] = assets
                kept.append(next_ref)
            continue
        aid = str(ref.get("assetId") or "").strip()
        if aid and ("character" in f"{kind} {role}".lower()) and _is_front_still_asset(
            db, project_id, aid
        ):
            continue
        kept.append(ref)
    batch.references = kept


def _order_characters_by_bindings(
    characters: list[dict[str, Any]],
    bound_assets: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Keep CRS Picture order stable from typed @ bindings, not mention order."""
    if not characters or not bound_assets:
        return characters
    index: dict[str, int] = {}
    cursor = 0
    for item in bound_assets:
        ident = str(item.get("identityId") or item.get("characterId") or "").strip()
        role = str(item.get("role") or item.get("kind") or "").lower()
        if not ident or ident in index:
            continue
        if "character" in role or role in {"crs", "entity"}:
            index[ident] = cursor
            cursor += 1
    if not index:
        return characters
    return sorted(characters, key=lambda row: index.get(str(row.get("characterId") or ""), 999))


def _bound_ers_asset(bound_assets: list[dict[str, Any]] | None) -> str:
    fallback = ""
    for item in bound_assets or []:
        role = str(item.get("role") or item.get("kind") or "").lower()
        aid = str(item.get("assetId") or "").strip()
        if not aid or role not in {"place", "environment", "ers"}:
            continue
        source = str(item.get("source") or "")
        label = str(item.get("label") or "")
        if source == "prompt_clip" or (label and label not in {"Opening picture", "Scene"}):
            return aid
        fallback = fallback or aid
    return fallback



def _asset_is_image(db: Session, asset_id: str | None) -> bool:
    """True only when the asset exists and is kind=image. Fail-closed for audio/voice/video."""
    aid = str(asset_id or "").strip()
    if not aid:
        return False
    asset = db.get(Asset, aid)
    if asset is None:
        return False
    kind = str(getattr(asset, "kind", "") or "").lower().strip()
    return kind == "image"


def _bound_crs_asset(
    character_id: str,
    bound_assets: list[dict[str, Any]] | None,
    db: Session | None = None,
) -> str:
    """Resolve the approved Character Reference Sheet (CRS) image asset for a character.

    A CRS is always an IMAGE. Voice/audio/video/motion assets are NEVER CRS images.
    The role must match exactly (`character`, `crs`, `entity`) — not a substring
    match, so `charactervoice` does not match `character`.
    When `db` is provided, Asset.kind must be `image` (fail-closed).
    """
    token = str(character_id or "").strip()
    if not token or not bound_assets:
        return ""
    # Kinds that are never CRS images — exclude before any role matching.
    _NON_IMAGE_KINDS = {"charactervoice", "voice", "audio", "video", "motion", "charactervoice"}
    _CRS_ROLES = {"character", "crs", "entity", "entity_reference"}
    for item in bound_assets:
        kind = str(item.get("kind") or "").lower()
        if kind in _NON_IMAGE_KINDS:
            continue  # Voice/video/audio are NEVER CRS images
        # Also reject characterIdentity/characterVoice rows — they are not CRS pictures.
        if kind in {"characteridentity", "charactervoice"}:
            continue
        ident = str(item.get("identityId") or item.get("characterId") or "").strip()
        role = str(item.get("role") or item.get("kind") or "").lower()
        aid = str(item.get("assetId") or "").strip()
        if aid and ident == token and role in _CRS_ROLES:
            if db is not None and not _asset_is_image(db, aid):
                continue  # Bound asset is not an image (e.g. voice WAV mis-tagged)
            return aid
    return ""

def _find_library_character_sheet(db: Session, project_id: str, character_id: str) -> str:
    """Resolve a composed CRS already in the project Library. Never invent one."""
    token = str(character_id or "").strip()
    prefix = token[:8]
    if not prefix:
        return ""
    try:
        rows = (
            db.query(Asset)
            .filter(Asset.project_id == project_id, Asset.kind == "image")
            .all()
        )
    except Exception:
        return ""
    hits: list[Asset] = []
    for asset in rows:
        labels = str(getattr(asset, "labels_json", "") or "")
        meta = str(getattr(asset, "prompt_meta_json", "") or "")
        blob = f"{asset.filename or ''} {asset.tag or ''} {labels} {meta}".lower()
        if "character_sheet" not in blob:
            continue
        if prefix.lower() in blob or token.lower() in blob:
            hits.append(asset)
    if not hits:
        return ""
    hits.sort(key=lambda a: str(getattr(a, "updated_at", "") or getattr(a, "filename", "")), reverse=True)
    return str(hits[0].id)


def resolve_r2v_character_asset(
    db: Session,
    project_id: str,
    hit: dict[str, Any],
    *,
    bound_assets: list[dict[str, Any]] | None = None,
) -> str:
    """CRS first. hero_identity is I2V only and is not a fallback here.

    Every candidate must be an IMAGE asset. Voice/audio/video IDs are skipped.
    Returns "" when no image CRS can be resolved (caller fail-closed).
    """
    character_id = str(hit.get("character_id") or "").strip()
    candidates: list[str] = []
    bound = _bound_crs_asset(character_id, bound_assets, db=db)
    if bound:
        candidates.append(bound)
    for role in ("character_sheet", "composed_sheet"):
        sheet = str(resolve_approved_reference(db, character_id, role) or "").strip()
        if sheet:
            candidates.append(sheet)
    # Persisted CRS approval authority (manual "Approve as Character" from
    # Preview Monitor) takes priority over the CC v2 sheetAssetId fallback.
    # The creator explicitly chose this image as the character reference sheet.
    try:
        from ...character_identity.crs_service import load_persisted_crs

        persisted = load_persisted_crs(db, character_id)
        persisted_sheet = str(persisted.get("approved_sheet_asset_id") or "").strip()
        if persisted_sheet:
            candidates.append(persisted_sheet)
    except Exception:
        pass
    sheet = str(hit.get("approved_sheet_asset_id") or "").strip()
    if sheet:
        candidates.append(sheet)
    lib = _find_library_character_sheet(db, project_id, character_id)
    if lib:
        candidates.append(lib)
    seen: set[str] = set()
    for aid in candidates:
        if not aid or aid in seen:
            continue
        seen.add(aid)
        if _asset_is_image(db, aid):
            return aid
    return ""




_CRS_AUTHORITY_ROLES = frozenset({"character", "crs", "entity", "entity_reference"})
_NON_CRS_IMAGE_KINDS = frozenset(
    {"charactervoice", "voice", "audio", "video", "motion", "characteridentity"}
)


def _normalize_ref_token(token: str) -> str:
    """Compact lower token for @alias / profile-name equality checks."""
    return re.sub(r"[^a-z0-9]", "", (token or "").lower())


def _bound_ref_name_tokens(item: dict[str, Any]) -> set[str]:
    """Collect alias/label/tag tokens that identify a Timeline Reference @tag."""
    tokens: set[str] = set()
    for key in (
        "alias",
        "label",
        "promptName",
        "prompt_name",
        "tag",
        "display_token",
        "displayToken",
    ):
        raw = str(item.get(key) or "").strip()
        if not raw:
            continue
        raw = raw.lstrip("@").strip()
        if not raw:
            continue
        tokens.add(_normalize_ref_token(raw))
        stripped = _strip_sheet_suffix(raw)
        if stripped:
            tokens.add(_normalize_ref_token(stripped))
    return {t for t in tokens if t}


def _is_character_crs_ref(item: dict[str, Any]) -> bool:
    """True when a batch reference is a Character / CRS Timeline Reference."""
    kind = str(item.get("kind") or "").lower()
    if kind in _NON_CRS_IMAGE_KINDS:
        return False
    role = str(item.get("role") or "").lower()
    ref_type = str(
        item.get("referenceType")
        or item.get("bindingType")
        or item.get("reference_type")
        or ""
    ).lower()
    if role in _CRS_AUTHORITY_ROLES or "character" in role:
        return True
    if ref_type in {"character", "crs", "entity", "wardrobe", "creature"}:
        return True
    if item.get("identityId") or item.get("characterId"):
        # Bound identity rows without an explicit role still count as CRS authority
        # when they carry an image asset (entity compile path).
        if kind in {"entity", "image", ""} and str(item.get("assetId") or "").strip():
            return True
    return False


def _match_bound_character_sheet_by_tag(
    name: str,
    bound_assets: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """Owner law: a bound Timeline Reference @tag IS the Character Reference Sheet.

    Match the prompt @token against alias/label/tag on Character/CRS bindings.
    Returns the first matching binding that has an assetId, else None.
    """
    needle = _normalize_ref_token(name)
    needle_stripped = _normalize_ref_token(_strip_sheet_suffix(name))
    if not needle or not bound_assets:
        return None
    for item in bound_assets:
        if not isinstance(item, dict) or not _is_character_crs_ref(item):
            continue
        aid = str(item.get("assetId") or "").strip()
        if not aid:
            continue
        tags = _bound_ref_name_tokens(item)
        if needle in tags or (needle_stripped and needle_stripped in tags):
            return item
    return None


def _hit_from_bound_crs_ref(
    db: Session,
    project_id: str,
    name: str,
    bound_match: dict[str, Any],
) -> dict[str, Any]:
    """Synthesize a resolve_character-compatible hit from a bound CRS Reference."""
    ident = str(
        bound_match.get("identityId") or bound_match.get("characterId") or ""
    ).strip()
    asset_id = str(bound_match.get("assetId") or "").strip()
    display = name
    if ident:
        try:
            profile = get_profile(db, project_id, ident)
            if profile is not None and str(getattr(profile, "name", "") or "").strip():
                display = str(profile.name).strip()
        except Exception:
            pass
    return {
        "character_id": ident or None,
        "name": display or name,
        "approved_sheet_asset_id": asset_id,
        "approved_reference_asset_id": asset_id,
        "visual_reference": asset_id,
    }


def _crs_authority_bound_assets(
    references: list[Any] | None,
) -> list[dict[str, Any]]:
    """Timeline References that may clear the missing-CRS warning.

    Consumed image refs are included as today. Unconsumed Character/CRS entity
    rows are also included — binding authority does not depend on whether the
    selected generator consumes the image reference slot.
    """
    out: list[dict[str, Any]] = []
    for ref in references or []:
        if not isinstance(ref, dict):
            continue
        if ref.get("consumed") is not False:
            out.append(ref)
            continue
        if _is_character_crs_ref(ref):
            out.append(ref)
    return out


def resolve_shot_characters(
    db: Session,
    project_id: str,
    texts: list[str],
    *,
    prefer_sheet: bool = False,
    prefer_front: bool = False,
    bound_assets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Resolve named @characters to identity image assets.

    prefer_sheet=True: CRS first (LTX 2.5 / H3 Timeline default). prefer_front=True: Front first (opt-in).

    Authority for the missing-CRS warning is Timeline Reference / CRS binding:
    if the prompt @tag matches a bound Character Reference sheet, the warning
    must not fire — even when Character Creator profile name differs from the
    Reference alias (e.g. profile "Korri" vs tag @Korri40YearsOld).
    Truly unbound @tags still fail closed.
    """
    names = mentioned_character_names("\n".join(t for t in texts if t), _known_names(db, project_id))
    resolved: list[dict[str, Any]] = []
    missing: list[str] = []
    crs_only: list[str] = []
    for name in names:
        hit = resolve_character(db, project_id, name)
        bound_match = _match_bound_character_sheet_by_tag(name, bound_assets)
        if not hit and bound_match is not None:
            # Bound Reference @tag is the CRS sheet for this identity.
            hit = _hit_from_bound_crs_ref(db, project_id, name, bound_match)
        if not hit:
            missing.append(name)
            continue
        asset_id = ""
        identity_form = ""
        if prefer_front:
            front_id, form = resolve_h3_front_character_asset(
                db, project_id, hit, bound_assets=bound_assets
            )
            if front_id:
                asset_id = front_id
                identity_form = form or "front"
            else:
                sheet_id = resolve_r2v_character_asset(
                    db, project_id, hit, bound_assets=bound_assets
                )
                if (not sheet_id) and bound_match is not None:
                    sheet_id = str(bound_match.get("assetId") or "").strip()
                if sheet_id and is_multi_panel_crs_asset(db, project_id, sheet_id):
                    # Warn path: still attach CRS so sheet tests are not hard-blocked,
                    # but mark crs_only for honest pre-generate warning.
                    asset_id = sheet_id
                    identity_form = "crs_sheet_only"
                    crs_only.append(str(hit.get("name") or name))
                elif sheet_id and _asset_is_image(db, sheet_id):
                    asset_id = sheet_id
                    identity_form = "front_comparable"
        elif prefer_sheet:
            asset_id = resolve_r2v_character_asset(
                db, project_id, hit, bound_assets=bound_assets
            )
            if (not asset_id) and bound_match is not None:
                asset_id = str(bound_match.get("assetId") or "").strip()
        else:
            hero = str(
                resolve_approved_reference(db, str(hit.get("character_id") or ""), "hero_identity") or ""
            ).strip()
            asset_id = str(
                hero
                or hit.get("approved_reference_asset_id")
                or hit.get("visual_reference")
                or hit.get("approved_casting_asset_id")
                or hit.get("approved_sheet_asset_id")
                or ""
            ).strip()
            if (not asset_id) and bound_match is not None:
                asset_id = str(bound_match.get("assetId") or "").strip()
        if not asset_id or not _asset_is_image(db, asset_id):
            # Fail-closed: voice/audio/video must never occupy CRS visual slots.
            # Bound non-image refs do not clear the visual CRS warning.
            missing.append(hit.get("name") or name)
            continue
        character_id = str(hit.get("character_id") or "").strip()
        # Collapse alias @tag + profile whole-word mentions of the same identity
        # (e.g. @Korri40YearsOld and "Korri") into one CRS slot.
        if character_id and any(
            str(row.get("characterId") or "").strip() == character_id for row in resolved
        ):
            continue
        if (not character_id) and any(
            str(row.get("name") or "").strip().lower() == str(hit.get("name") or name).strip().lower()
            and str(row.get("assetId") or "") == asset_id
            for row in resolved
        ):
            continue
        row = {
            "characterId": hit.get("character_id"),
            "name": hit.get("name") or name,
            "assetId": asset_id,
            "appearance": _appearance_from_profile(
                db, project_id, character_id
            ),
        }
        if identity_form:
            row["identityForm"] = identity_form
        resolved.append(row)
    resolved = _order_characters_by_bindings(resolved, bound_assets)
    return {
        "characters": resolved,
        "missing": missing,
        "mentioned": names,
        "crs_only": crs_only,
    }


def _union_bound_crs_into_shot(
    shot: dict[str, Any],
    bound_assets: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Master-bound CRS rows are cast even when prompt-name match missed."""
    characters = list(shot.get("characters") or [])
    have_ids = {str(row.get("characterId") or "").strip() for row in characters}
    have_ids.discard("")
    have_assets = {str(row.get("assetId") or "").strip() for row in characters}
    have_assets.discard("")
    for item in bound_assets or []:
        if not isinstance(item, dict) or not _is_character_crs_ref(item):
            continue
        cid = str(item.get("identityId") or item.get("characterId") or "").strip()
        aid = str(item.get("assetId") or "").strip()
        if not aid:
            continue
        if cid and cid in have_ids:
            continue
        if not cid and aid in have_assets:
            continue
        if aid in have_assets and cid:
            continue
        name = str(
            item.get("promptName")
            or item.get("label")
            or item.get("tag")
            or "character"
        ).strip().lstrip("@#%*~")
        characters.append(
            {
                "characterId": cid or None,
                "name": name or "character",
                "assetId": aid,
            }
        )
        if cid:
            have_ids.add(cid)
        have_assets.add(aid)
    out = dict(shot)
    out["characters"] = characters
    return out


def _bound_characters_missing_from_shot(
    bound_assets: list[dict[str, Any]] | None,
    shot: dict[str, Any],
) -> list[str]:
    have_ids = {
        str(row.get("characterId") or "").strip()
        for row in (shot.get("characters") or [])
    }
    have_assets = {
        str(row.get("assetId") or "").strip()
        for row in (shot.get("characters") or [])
    }
    missing: list[str] = []
    for item in bound_assets or []:
        if not isinstance(item, dict) or not _is_character_crs_ref(item):
            continue
        cid = str(item.get("identityId") or item.get("characterId") or "").strip()
        aid = str(item.get("assetId") or "").strip()
        tag = str(item.get("tag") or item.get("promptName") or item.get("label") or aid)
        if cid and cid not in have_ids:
            missing.append(tag or cid)
        elif (not cid) and aid and aid not in have_assets:
            missing.append(tag or aid)
    return missing

def _asset_file(db: Session, project_id: str, asset_id: str) -> Path | None:
    asset = db.get(Asset, asset_id)
    if not asset or asset.project_id != project_id:
        return None
    raw = str(getattr(asset, "path", "") or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if path.is_file():
        return path
    alt = Path(settings.data_dir) / raw
    if alt.is_file():
        return alt
    return None


def _identity_layout(character_count: int, has_environment: bool) -> str:
    if character_count >= 2:
        return "two_heroes_place"
    return "character_focus"


def _existing_sheet(
    project_id: str,
    source_asset_ids: list[str],
    *,
    layout: str | None = None,
) -> dict[str, Any] | None:
    wanted = [str(item) for item in source_asset_ids if str(item).strip()]
    wanted_set = set(wanted)
    if not wanted_set:
        return None
    for sheet in ref_store.list_sheets(project_id):
        have = [str(item) for item in (sheet.get("source_asset_ids") or []) if str(item).strip()]
        if set(have) != wanted_set:
            continue
        if layout and str(sheet.get("layout") or "") != str(layout):
            continue
        image = Path(str(sheet.get("image_path") or sheet.get("composite_path") or ""))
        if image.is_file():
            return sheet
    return None


def ensure_identity_sheet(
    db: Session,
    project_id: str,
    *,
    characters: list[dict[str, Any]],
    environment_asset_id: str | None,
) -> dict[str, Any]:
    """Build or reuse an Ingredients sheet from hero pictures + optional environment."""
    source_ids: list[str] = []
    panels: list[SheetPanel] = []
    for character in characters:
        asset_id = str(character.get("assetId") or "").strip()
        path = _asset_file(db, project_id, asset_id)
        if not path:
            raise ValueError(f"CHARACTER_ASSET_MISSING:{character.get('name') or asset_id}")
        if asset_id not in source_ids:
            source_ids.append(asset_id)
        panels.append(
            SheetPanel(
                path=path,
                role="character",
                subject_name=str(character.get("name") or ""),
                priority="primary",
            )
        )
        ref_store.upsert_ingredient(
            project_id,
            {
                "id": f"char_{character.get('characterId')}",
                "asset_id": asset_id,
                "role": "character",
                "subject_name": character.get("name"),
                "label": character.get("name"),
                "priority": "primary",
                "include": True,
            },
        )

    env_id = str(environment_asset_id or "").strip()
    if env_id and env_id not in source_ids:
        env_path = _asset_file(db, project_id, env_id)
        if env_path:
            source_ids.append(env_id)
            panels.append(
                SheetPanel(
                    path=env_path,
                    role="environment",
                    subject_name="Scene",
                    priority="secondary",
                )
            )
            ref_store.upsert_ingredient(
                project_id,
                {
                    "id": f"env_{env_id[:8]}",
                    "asset_id": env_id,
                    "role": "environment",
                    "subject_name": "Scene",
                    "label": "Scene",
                    "priority": "secondary",
                    "include": True,
                },
            )

    layout = _identity_layout(len(characters), bool(env_id and env_id in source_ids))
    existing = _existing_sheet(project_id, source_ids, layout=layout)
    if existing:
        return existing
    sheet_id = str(uuid.uuid4())
    root = ref_store.project_refs_root(project_id) / "sheets" / sheet_id
    root.mkdir(parents=True, exist_ok=True)
    png_path = root / "composite.png"
    built = build_reference_sheet(panels, layout=layout, width=768, height=448, out_path=png_path)
    video_path = root / "composite_static.mp4"
    still_to_static_video(png_path, video_path, fps=24, frames=121, width=768, height=448)

    from ...db import Project

    project = db.get(Project, project_id)
    if not project:
        raise ValueError("SCENE_NOT_FOUND")
    png_asset = Asset(
        id=str(uuid.uuid4()),
        project_id=project_id,
        filename="reference_sheet.png",
        path=str(png_path),
        kind="image",
        tag="reference_sheet",
    )
    vid_asset = Asset(
        id=str(uuid.uuid4()),
        project_id=project_id,
        filename="reference_sheet_static.mp4",
        path=str(video_path),
        kind="video",
        tag="reference_sheet_video",
    )
    db.add(png_asset)
    db.add(vid_asset)
    db.commit()
    sheet = {
        "id": sheet_id,
        "version": 1,
        "layout": built["layout"],
        "composite_path": str(png_path),
        "static_video_path": str(video_path),
        "image_path": str(png_path),
        "video_path": str(video_path),
        "image_asset_id": png_asset.id,
        "video_asset_id": vid_asset.id,
        "composite_asset_id": png_asset.id,
        "static_video_asset_id": vid_asset.id,
        "source_asset_ids": source_ids,
        "source_references": [
            {"asset_id": c["assetId"], "role": "character", "subject_name": c.get("name")}
            for c in characters
        ],
        "panels": built.get("panels") or [],
        "width": 768,
        "height": 448,
        "identitySheet": True,
    }
    return ref_store.save_sheet(project_id, sheet)


def _prior_identity_ids(batch: BatchBlock) -> set[str]:
    ids: set[str] = set()
    for ref in batch.references or []:
        if not isinstance(ref, dict):
            continue
        if str(ref.get("kind") or "") != "characterIdentity":
            continue
        for item in ref.get("identityIds") or []:
            token = str(item or "").strip()
            if token:
                ids.add(token)
    return ids


def _is_continuity_frame(db: Session, asset_id: str) -> bool:
    token = str(asset_id or "").strip()
    if not token:
        return False
    asset = db.get(Asset, token)
    return bool(asset and str(getattr(asset, "tag", "") or "") == "continuity_last_frame")


def _place_environment_id(
    db: Session,
    request: TimelineGenerationRequest,
    batch: BatchBlock,
    hero_ids: set[str],
    *,
    batches: list[BatchBlock] | None = None,
) -> str | None:
    """When a new character joins, condition the place — not the previous take's occupied last frame."""
    anchors = list(batch.sourceAnchors or [])
    for earlier in batches or []:
        if earlier.id == batch.id:
            break
        anchors.extend(earlier.sourceAnchors or [])
    for anchor in anchors:
        aid = str(getattr(anchor, "assetId", None) or "").strip()
        if aid and aid not in hero_ids and not _is_continuity_frame(db, aid):
            return aid
    from ...db import Scene

    scene = db.get(Scene, request.sceneId)
    start = str(getattr(scene, "start_asset_id", None) or "").strip() if scene is not None else ""
    if start and start not in hero_ids and not _is_continuity_frame(db, start):
        return start
    fallback = str(request.startImageAssetId or request.lastFrameAssetId or "").strip()
    if fallback and fallback not in hero_ids and not _is_continuity_frame(db, fallback):
        return fallback
    return start or None


def prior_identity_ids(batches: list[BatchBlock] | None, current_batch_id: str | None) -> set[str]:
    """Characters already established in earlier approved takes — not this batch's leftover refs."""
    ids: set[str] = set()
    for batch in batches or []:
        if current_batch_id and batch.id == current_batch_id:
            break
        ids |= _prior_identity_ids(batch)
    return ids


def _bind_identity_ref(
    batch: BatchBlock,
    characters: list[dict[str, Any]],
    *,
    method: str,
    extra: dict[str, Any] | None = None,
) -> None:
    kept = [
        ref
        for ref in (batch.references or [])
        if not (isinstance(ref, dict) and str(ref.get("kind") or "") == "characterIdentity")
    ]
    row = {
        "kind": "characterIdentity",
        "method": method,
        "identityIds": [c["characterId"] for c in characters],
        "identityNames": [str(c.get("name") or "") for c in characters],
        "identityAssetIds": [c["assetId"] for c in characters],
        "consumed": True,
        "source": "project_character",
    }
    if extra:
        row.update(extra)
    batch.references = kept + [row]


def _apply_i2v_start_identity(
    db: Session,
    request: TimelineGenerationRequest,
    batch: BatchBlock,
    *,
    characters: list[dict[str, Any]],
    prior_identity: set[str] | None,
    batches: list[BatchBlock] | None,
    method: str,
    bound_assets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Condition identity through the existing I2V start frame — not Ingredients."""
    current_ids = {str(c["characterId"]) for c in characters if c.get("characterId")}
    prior_ids = set(prior_identity or ())
    extending = (
        request.continuityStrategy == "last_frame_i2v"
        and bool(request.lastFrameAssetId)
        and current_ids
        and current_ids.issubset(prior_ids)
    )
    if extending:
        return {
            "ok": True,
            "applied": False,
            "reason": "continuity_already_has_identity",
            "characters": characters,
            "method": method,
        }

    hero_ids = {str(c["assetId"]) for c in characters}
    joining = bool(current_ids - prior_ids) and bool(prior_ids)
    request.providerOptions = dict(request.providerOptions or {})
    request.providerOptions["identityJoining"] = joining
    last_id = str(request.lastFrameAssetId or "").strip()
    from .r2v import H3_MECHANISM, mechanism_for_generator

    is_h3 = mechanism_for_generator(product_generator_id(request, method)) == H3_MECHANISM
    bound_place = _bound_ers_asset(bound_assets)
    if bound_place and bound_place not in hero_ids and bound_place != last_id:
        start_id = bound_place
    elif joining:
        start_id = _place_environment_id(db, request, batch, hero_ids, batches=batches)
    else:
        start_id = request.startImageAssetId or request.lastFrameAssetId
        # Validate start_id is an image — never use a voice/video/audio asset as I2V start.
        if start_id and not _asset_is_image(db, start_id):
            start_id = ""  # Non-image start — clear it, don't use it
        if start_id and start_id in hero_ids:
            start_id = start_id
        elif not start_id:
            start_id = next((str(c["assetId"]) for c in characters if c.get("assetId")), None)
            # Validate the fallback character asset is also an image.
            if start_id and not _asset_is_image(db, start_id):
                start_id = None  # Non-image fallback — don't use it
        bridge_open = bool(str(getattr(request, "continuityBridgeId", None) or "").strip() and last_id)
        if is_h3 and bridge_open:
            # Continuation begins on the previous window's last frame.
            # Character and place sheets stay as later pictures.
            start_id = last_id
        elif is_h3 and last_id and start_id == last_id:
            start_id = _place_environment_id(db, request, batch, hero_ids, batches=batches)
    if not start_id and not (is_h3 and last_id):
        start_id = next((str(c["assetId"]) for c in characters if c.get("assetId")), None)
    if not start_id and not (is_h3 and last_id):
        names = ", ".join(c["name"] for c in characters)
        return {
            "ok": False,
            "error": "CHARACTER_IDENTITY_MISSING",
            "message": (
                f"{names} is named in this shot but Adept has no opening picture to send. "
                "Choose a start picture or approve their character picture first."
            ),
            "missing": [c["name"] for c in characters],
            "mock": False,
        }

    # Final CRS honesty: identity slots are images only. Fail-closed if any
    # named character resolved to a non-image (voice/audio/video).
    image_chars: list[dict[str, Any]] = []
    dropped: list[str] = []
    for c in characters:
        if _asset_is_image(db, c.get("assetId")):
            image_chars.append(c)
        else:
            dropped.append(str(c.get("name") or c.get("characterId") or "?"))
    if dropped:
        return {
            "ok": False,
            "error": "CHARACTER_IDENTITY_MISSING",
            "message": (
                f"{', '.join(dropped)} resolved to a non-image asset for CRS. "
                "Voice or audio assets cannot fill visual CRS slots. "
                "Approve a Character Reference Sheet image before generating."
            ),
            "missing": dropped,
            "mock": False,
        }
    characters = image_chars
    hero_ids = {str(c["assetId"]) for c in characters}
    if start_id and not _asset_is_image(db, start_id):
        start_id = next((str(c["assetId"]) for c in characters if c.get("assetId")), None)

    request.startImageAssetId = start_id
    request.generationMode = "reference"
    if request.lastFrameAssetId and start_id != request.lastFrameAssetId:
        request.continuityStrategy = "prompt_context"
    request.providerOptions = dict(request.providerOptions or {})
    request.providerOptions.update(
        {
            "ingredients_ic_lora": False,
            "reference_method": method,
            "source_asset_ids": [str(c["assetId"]) for c in characters if c.get("assetId")],
            "characterIdentity": {
                "applied": True,
                "method": method,
                "startImageAssetId": start_id,
                "characters": characters,
            },
        }
    )
    from .r2v import merge_identity_slots

    merge_identity_slots(
        request,
        characters=characters,
        place_asset_id=start_id if start_id not in hero_ids else None,
        method=method,
        joining=joining,
        batch=batch,
    )
    _bind_identity_ref(
        batch,
        characters,
        method=method,
        extra={"startImageAssetId": start_id},
    )
    return {
        "ok": True,
        "applied": True,
        "method": method,
        "startImageAssetId": start_id,
        "characters": characters,
        "mock": False,
    }



_CONTINUITY_PREFIX_RE = re.compile(
    r"^(?:UNCHANGED FACTS|STARTING STATE|ENDING STATE|ACTION\s*/\s*DIRECTION|DIALOGUE|TIMED PROMPT)\b.*$",
    re.IGNORECASE | re.MULTILINE,
)


def _strip_continuity_boilerplate(text: str) -> str:
    """Remove Spatial Map / temporal continuity lines from a generation prompt.

    Those lines name project-cast characters (e.g. Anadriya keeps walking) and
    must not expand CRS Picture/Audio slots beyond creator Timed Prompt bindings.
    """
    cleaned = _CONTINUITY_PREFIX_RE.sub("", text or "")
    # Drop empty lines left by stripping.
    return "\n".join(line for line in cleaned.splitlines() if line.strip()).strip()


def _creator_cast_texts(request: TimelineGenerationRequest, batch: BatchBlock) -> list[str]:
    """Texts that may expand CRS Picture/Audio cast.

    Creator Spec Fidelity: Timed Prompt segments + authoredPrompt, plus
    request.prompt with Spatial Map / temporal continuity boilerplate stripped.
    Never let movement-layer speakers expand cast.
    """
    opts = request.providerOptions or {}
    texts: list[str] = [str(opts.get("authoredPrompt") or "").strip()]
    for seg in batch.promptSegments or []:
        texts.append(str(getattr(seg, "text", "") or ""))
        texts.append(str(getattr(seg, "productionPrompt", "") or ""))
        texts.append(str(getattr(seg, "userDirection", "") or ""))
        for nb in getattr(seg, "referenceNameBindings", None) or []:
            if not isinstance(nb, dict):
                continue
            tag = str(nb.get("tag") or "").strip()
            name = str(nb.get("prompt_name") or "").strip()
            if tag:
                texts.append(tag if tag.startswith(("@", "#", "%", "*", "~")) else f"@{tag}")
            if name:
                texts.append(name)
    raw_prompt = str(request.prompt or "").strip()
    if raw_prompt:
        texts.append(_strip_continuity_boilerplate(raw_prompt))
    return texts


def _restrict_to_creator_bound_cast(
    shot: dict[str, Any],
    bound_assets: list[dict[str, Any]] | None,
    creator_texts: list[str],
) -> dict[str, Any]:
    """When Timeline CRS bindings exist, they are cast authority.

    Drop characters that were only introduced via Spatial Map / project cast
    whole-word matching and were never creator-bound on the Timed Prompt.
    """
    characters = list(shot.get("characters") or [])
    if not characters:
        return shot
    bound_ids = {
        str(item.get("identityId") or item.get("characterId") or "").strip()
        for item in (bound_assets or [])
        if isinstance(item, dict) and _is_character_crs_ref(item)
    }
    bound_ids.discard("")
    bound_asset_ids = {
        str(item.get("assetId") or "").strip()
        for item in (bound_assets or [])
        if isinstance(item, dict) and _is_character_crs_ref(item)
    }
    bound_asset_ids.discard("")
    if not bound_ids and not bound_asset_ids:
        return shot
    # Bindings present: Picture/Audio slots may only include bound identities.
    # Keep Master-bound CRS even when the row is asset-only (no identityId).
    kept = [
        row
        for row in characters
        if str(row.get("characterId") or "").strip() in bound_ids
        or str(row.get("assetId") or "").strip() in bound_asset_ids
    ]
    out = dict(shot)
    out["characters"] = kept
    return out


def apply_character_identity(
    db: Session,
    request: TimelineGenerationRequest,
    batch: BatchBlock,
    *,
    adapter_id: str,
    prior_identity: set[str] | None = None,
    batches: list[BatchBlock] | None = None,
) -> dict[str, Any]:
    """Attach canonical character assets. Fail closed if identity cannot be sent."""
    product = product_generator_id(request, adapter_id)
    # Timeline Reference Character/CRS bindings are CRS authority even when
    # the selected generator does not consume the image reference slot.
    bound_assets = _crs_authority_bound_assets(batch.references)
    if product in H3_I2V_ADAPTER_IDS:
        texts = _creator_cast_texts(request, batch)
        shot = resolve_shot_characters(
            db,
            request.projectId,
            texts,
            prefer_sheet=True,
            prefer_front=False,
            bound_assets=bound_assets,
        )
        shot = _union_bound_crs_into_shot(shot, bound_assets)
        shot = _restrict_to_creator_bound_cast(shot, bound_assets, texts)
        dropped = _bound_characters_missing_from_shot(bound_assets, shot)
        if dropped:
            return {
                "ok": False,
                "error": "CHARACTER_REFERENCE_DROPPED",
                "message": (
                    f"{', '.join(dropped)} is bound on Timeline but did not reach "
                    "MiniMax identity slots. Adept did not substitute another person."
                ),
                "dropped": dropped,
                "mock": False,
            }
        # H3 Timeline: creator CRS is authoritative (no silent Front remap). Front stills
        # remain valid when the creator attached Front explicitly; do not call _drop_front_still_character_refs.
        crs_only = list(shot.get("crs_only") or [])
        warn_msgs = []
        if crs_only:
            names = ", ".join(crs_only)
            warn_msgs.append(
                f"{names} only has a multi-panel Character Reference Sheet. "
                "MiniMax H3 identity locks best with Character Creator Front "
                "(or a front-comparable portrait). CRS sheets alone often fail identity."
            )
        if shot["missing"]:
            names = ", ".join(shot["missing"])
            return {
                "ok": False,
                "error": "CHARACTER_IDENTITY_MISSING",
                "message": (
                    f"{names} is named in this shot but has no Character Creator Front "
                    "or Character Reference Sheet for MiniMax H3. "
                    "Open Character Creator and approve Front (preferred) or a sheet."
                ),
                "missing": shot["missing"],
                "mock": False,
            }
        if not shot["characters"]:
            out = {"ok": True, "applied": False, "reason": "no_named_characters"}
            if warn_msgs:
                out["warnings"] = warn_msgs
                out["crsOnly"] = crs_only
            return out
        result = _apply_i2v_start_identity(
            db,
            request,
            batch,
            characters=shot["characters"],
            prior_identity=prior_identity,
            batches=batches,
            method="h3_ref2va",
            bound_assets=bound_assets,
        )
        if warn_msgs:
            result = dict(result)
            result["warnings"] = warn_msgs
            result["crsOnly"] = crs_only
            opts = dict(request.providerOptions or {})
            existing = list(opts.get("warnings") or [])
            for msg in warn_msgs:
                if msg not in existing:
                    existing.append(msg)
            opts["warnings"] = existing
            request.providerOptions = opts
        return result
    if product not in LTX_ADAPTER_IDS and str(adapter_id or request.generatorId or "") not in LTX_ADAPTER_IDS:
        return {"ok": True, "applied": False, "reason": "not_ltx"}

    texts = _creator_cast_texts(request, batch)
    shot = resolve_shot_characters(
        db,
        request.projectId,
        texts,
        prefer_sheet=product in LTX_25_ADAPTER_IDS,
        bound_assets=bound_assets,
    )
    shot = _union_bound_crs_into_shot(shot, bound_assets)
    shot = _restrict_to_creator_bound_cast(shot, bound_assets, texts)
    dropped = _bound_characters_missing_from_shot(bound_assets, shot)
    if dropped:
        return {
            "ok": False,
            "error": "CHARACTER_REFERENCE_DROPPED",
            "message": (
                f"{', '.join(dropped)} is bound on Timeline but did not reach "
                "identity slots. Adept did not substitute another person."
            ),
            "dropped": dropped,
            "mock": False,
        }
    if shot["missing"]:
        names = ", ".join(shot["missing"])
        return {
            "ok": False,
            "error": "CHARACTER_IDENTITY_MISSING",
            "message": (
                f"{names} is named in this shot but has no Character Reference Sheet. "
                "Open the character and approve their sheet before generating."
            ),
            "missing": shot["missing"],
            "mock": False,
        }
    characters = shot["characters"]
    if not characters:
        return {"ok": True, "applied": False, "reason": "no_named_characters"}

    if product in LTX_25_ADAPTER_IDS:
        return _apply_i2v_start_identity(
            db,
            request,
            batch,
            characters=characters,
            prior_identity=prior_identity,
            batches=batches,
            method="ltx25_r2v_single_cond",
        )

    current_ids = {str(c["characterId"]) for c in characters if c.get("characterId")}
    prior_ids = set(prior_identity or ())
    extending = (
        request.continuityStrategy == "last_frame_i2v"
        and bool(request.lastFrameAssetId)
        and current_ids
        and current_ids.issubset(prior_ids)
    )
    if extending:
        return {
            "ok": True,
            "applied": False,
            "reason": "continuity_already_has_identity",
            "characters": characters,
        }

    status = ingredients_status()
    if not status.get("ready"):
        names = ", ".join(c["name"] for c in characters)
        return {
            "ok": False,
            "error": "CHARACTER_IDENTITY_RUNTIME_UNAVAILABLE",
            "message": (
                f"This shot names {names}, but Adept cannot send their pictures to LTX yet. "
                f"{status.get('message') or 'Ingredients identity is not ready.'}"
            ),
            "mock": False,
        }

    hero_ids = {str(c["assetId"]) for c in characters}
    joining = bool(current_ids - prior_ids) and bool(prior_ids)
    if joining:
        env_id = _place_environment_id(db, request, batch, hero_ids, batches=batches)
    else:
        env_id = request.startImageAssetId or request.lastFrameAssetId
        if env_id and env_id in hero_ids:
            env_id = None
    try:
        sheet = ensure_identity_sheet(
            db,
            request.projectId,
            characters=characters,
            environment_asset_id=env_id,
        )
    except Exception as exc:
        return {
            "ok": False,
            "error": "CHARACTER_IDENTITY_SHEET_FAILED",
            "message": (
                "Adept could not prepare the character pictures for this shot. "
                "The original batches were not changed."
            ),
            "detail": str(exc)[:400],
            "mock": False,
        }

    request.generationMode = "reference"
    request.providerOptions = dict(request.providerOptions or {})
    request.providerOptions.update(
        {
            "ingredients_ic_lora": True,
            "reference_method": "ingredients_ic_lora",
            "sheet_id": sheet.get("id"),
            "source_asset_ids": list(sheet.get("source_asset_ids") or []),
            "image_asset_id": sheet.get("image_asset_id"),
            "reference_prompt": ", ".join(c["name"] for c in characters),
            "characterIdentity": {
                "applied": True,
                "method": "ingredients_ic_lora",
                "sheetId": sheet.get("id"),
                "characters": characters,
            },
        }
    )
    _bind_identity_ref(
        batch,
        characters,
        method="ingredients_ic_lora",
        extra={"sheetId": sheet.get("id")},
    )
    return {
        "ok": True,
        "applied": True,
        "sheetId": sheet.get("id"),
        "characters": characters,
        "mock": False,
    }
