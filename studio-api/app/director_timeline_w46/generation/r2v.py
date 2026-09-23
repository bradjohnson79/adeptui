"""Canonical Timeline Reference-to-Video contract.

Local Timeline shots already belong to a project. They are never plain
Text-to-Video and never ordinary Image-to-Video. One request carries
character / place / prop / prior-frame / style / video / audio slots.
Each generator maps those slots onto the mechanism it actually has.

Do not fake R2V by stuffing one reference into an I2V start slot and
dropping the rest.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..contracts import BatchBlock
from .contracts import TimelineGenerationRequest, VideoGeneratorCapabilities

R2VRole = Literal[
    "character",
    "place",
    "prior_frame",
    "prop",
    "style",
    "reference",
    "video",
    "audio",
]

H3_MECHANISM = "h3_ref2va"
H3_CANVAS = "864x480"
LTX25_MECHANISM = "ltx25_single_cond"
SEEDANCE_MECHANISM = "seedance_r2v"
KLING_MECHANISM = "kling_i2v"
VEO_MECHANISM = "veo_r2v"

H3_ROLE_CLAUSE = {
    "character": "preserve the supplied visual identity. Do not invent a replacement person",
    "place": "the place - keep this location",
    "prior_frame": "the previous take - continue motion only, do not invent new people",
    "prop": "this object - keep it",
    "style": "the look - keep this style",
    "reference": "a reference picture",
    "audio": "this character's voice - only they speak with this voice",
}

# Same asset can arrive as mapped start (place) and last-frame continuity.
# Continuity wins over place. Character still beats both.
_ROLE_PRIORITY = {
    "character": 0,
    "prior_frame": 1,
    "place": 2,
    "prop": 3,
    "style": 4,
    "reference": 5,
    "video": 6,
    "audio": 7,
}

H3_GENERATOR_IDS = frozenset(
    {
        "minimax-h3-t2v-local",
        "minimax-h3-i2v-local",
        "minimax-h3-local",
        "minimax-h3",
        "minimax-h3-i2v",
    }
)
LTX25_GENERATOR_IDS = frozenset({"ltx-2.5", "ltx-2.5-full", "ltx-2.5-distilled", "ltx-2.5-comfy"})
SEEDANCE_GENERATOR_IDS = frozenset(
    {"seedance-2.0", "seedance-2.0-mini", "seedance-2.5", "seedance-api", "seedance-fal", "fal_seedance", "fal_seedance_25", "fal_seedance_mini", "seedance-mini"}
)
KLING_GENERATOR_IDS = frozenset({"kling-api", "kling-fal", "kling-kie"})
VEO_GENERATOR_IDS = frozenset({"veo-api", "veo-kie"})

TIMELINE_R2V_REQUIRED = (
    "This Timeline shot needs a real project picture — a character, place, "
    "prop, or the previous take. Local generators do not run as plain "
    "text-to-video."
)


class R2VSlot(BaseModel):
    role: R2VRole
    assetId: str
    label: str = ""
    identityId: str | None = None
    pictureIndex: int | None = None
    audioIndex: int | None = None
    appearance: str = ""
    aliases: list[str] = Field(default_factory=list)


class CanonicalR2VRequest(BaseModel):
    slots: list[R2VSlot] = Field(default_factory=list)
    mappedStartAssetId: str | None = None
    mechanism: str = ""
    promptPrefix: str = ""
    disclosures: list[str] = Field(default_factory=list)
    tensorSlotCount: int = 0
    promptOnlyCount: int = 0

    def to_job_dict(self) -> dict[str, Any]:
        return self.model_dump()


def product_generator_id(request: TimelineGenerationRequest | None, fallback: str = "") -> str:
    opts = (request.providerOptions if request is not None else None) or {}
    return str(
        opts.get("originalGeneratorId")
        or opts.get("selectedGenerator")
        or (request.generatorId if request is not None else "")
        or fallback
        or ""
    ).strip()


def knowledge_for_generator(generator_id: str):
    from ...codirector.knowledgebase.video_generators import load_video_generator_knowledge

    return load_video_generator_knowledge(generator_id)


def mechanism_for_generator(generator_id: str) -> str:
    token = (generator_id or "").strip()
    from ...hosted_providers.video_registry import is_retired_local_video

    if is_retired_local_video(token):
        return ""
    kb = knowledge_for_generator(token)
    if kb.loaded and kb.compile.mechanism:
        return kb.compile.mechanism
    if token in H3_GENERATOR_IDS or token.startswith("minimax-h3"):
        return H3_MECHANISM
    if token in LTX25_GENERATOR_IDS or token.startswith("ltx-2.5"):
        return LTX25_MECHANISM
    if token in SEEDANCE_GENERATOR_IDS:
        return SEEDANCE_MECHANISM
    if token in KLING_GENERATOR_IDS:
        return KLING_MECHANISM
    if token in VEO_GENERATOR_IDS:
        return VEO_MECHANISM
    return ""


def _resolve_character_label(db: Any, asset_id: str, identity_id: str | None, label: str) -> str:
    """Fill an empty character label from profile/asset metadata. Never invents identity."""
    if (label or "").strip() and (label or "").strip().lower() not in {"character", "this character"}:
        return label.strip()
    if db is None:
        return (label or "").strip()
    ident = str(identity_id or "").strip()
    if ident:
        try:
            from ...character_identity.models import CharacterProfileRow

            row = db.get(CharacterProfileRow, ident)
            name = str(getattr(row, "name", "") or "").strip()
            if name:
                return name
        except Exception:
            pass
    aid = str(asset_id or "").strip()
    if aid:
        try:
            from ...db import Asset as _Asset

            asset = db.get(_Asset, aid)
            raw = getattr(asset, "prompt_meta_json", None) or ""
            data = json.loads(raw) if isinstance(raw, str) and raw.strip() else (raw if isinstance(raw, dict) else {})
            lineage = data.get("lineage") if isinstance(data, dict) else {}
            tag = ""
            if isinstance(lineage, dict):
                tag = str(lineage.get("atTag") or "").strip()
            if not tag and isinstance(data, dict):
                tag = str(data.get("atTag") or "").strip()
            if tag:
                return tag.lstrip("@")
        except Exception:
            pass
    return (label or "").strip()


def _known_non_image_asset(db: Any, asset_id: str) -> bool:
    """True only when the DB row exists and is not an image.

    Missing schema, missing row, or lookup failure cannot prove a Timeline
    reference is a voice file — keep the slot so identity is not silently dropped.
    """
    if db is None:
        return False
    try:
        from ...db import Asset as _Asset

        asset = db.get(_Asset, asset_id)
    except Exception:
        return False
    if asset is None:
        return False
    return str(getattr(asset, "kind", "") or "").lower() != "image"


def _norm_role(raw: str, *, kind: str = "") -> R2VRole:
    token = f"{raw or ''} {kind or ''}".strip().lower().replace("-", "_")
    if "voice" in token or token.strip() == "audio":
        return "audio"
    if "character" in token or token in {"hero", "identity"}:
        return "character"
    if any(part in token for part in ("place", "environment", "location", "scene", "set")):
        return "place"
    if any(part in token for part in ("prior", "last_frame", "continuity", "previous")):
        return "prior_frame"
    if "prop" in token:
        return "prop"
    if "style" in token or "look" in token:
        return "style"
    if "video" in token or "motion" in token:
        return "video"
    if "audio" in token:
        return "audio"
    if token in {"start", "start_frame", "opening"}:
        return "place"
    return "reference"


def _character_slot_aliases(
    db: Any,
    asset_id: str,
    identity_id: str | None,
    *names: str,
) -> list[str]:
    """Profile name + @tag + checkbox label. No hard-coded character names."""
    out: list[str] = []
    seen: set[str] = set()

    def _add(token: str) -> None:
        item = str(token or "").strip()
        key = item.lower()
        if not item or key in seen:
            return
        seen.add(key)
        out.append(item)

    for name in names:
        _add(name)
    ident = str(identity_id or "").strip()
    if db is not None and ident:
        try:
            from ...character_identity.models import CharacterProfileRow

            row = db.get(CharacterProfileRow, ident)
            _add(str(getattr(row, "name", "") or ""))
        except Exception:
            pass
    aid = str(asset_id or "").strip()
    if db is not None and aid:
        try:
            from ...db import Asset as _Asset

            asset = db.get(_Asset, aid)
            raw = getattr(asset, "prompt_meta_json", None) or ""
            data = json.loads(raw) if isinstance(raw, str) and raw.strip() else (raw if isinstance(raw, dict) else {})
            lineage = data.get("lineage") if isinstance(data, dict) else {}
            tag = ""
            if isinstance(lineage, dict):
                tag = str(lineage.get("atTag") or "").strip()
            if not tag and isinstance(data, dict):
                tag = str(data.get("atTag") or "").strip()
            _add(tag)
        except Exception:
            pass
    return out


def _add_slot(
    slots: list[R2VSlot],
    *,
    asset_id: str | None,
    role: R2VRole,
    label: str = "",
    identity_id: str | None = None,
    appearance: str = "",
    aliases: list[str] | None = None,
) -> None:
    aid = str(asset_id or "").strip()
    if not aid:
        return
    look = (appearance or "").strip()
    extra = [str(item).strip() for item in (aliases or []) if str(item or "").strip()]
    for existing in slots:
        if existing.assetId == aid and existing.role == role:
            if label and not existing.label:
                existing.label = label
            if identity_id and not existing.identityId:
                existing.identityId = identity_id
            if look and not existing.appearance:
                existing.appearance = look
            for item in extra:
                if item.lower() not in {a.lower() for a in existing.aliases}:
                    existing.aliases.append(item)
            return
    slots.append(
        R2VSlot(
            role=role,
            assetId=aid,
            label=(label or "").strip(),
            identityId=identity_id,
            appearance=look,
            aliases=extra,
        )
    )


def _open_on_prior_frame(payload: CanonicalR2VRequest) -> None:
    """Bridge last frame is picture 1 so the next window begins on that still."""
    visuals = [slot for slot in payload.slots if slot.pictureIndex]
    prior = next((slot for slot in visuals if slot.role == "prior_frame"), None)
    if prior is None or prior.pictureIndex == 1:
        return
    rest = sorted(
        (slot for slot in visuals if slot is not prior),
        key=lambda slot: int(slot.pictureIndex or 0),
    )
    for index, slot in enumerate((prior, *rest), start=1):
        slot.pictureIndex = index


def _add_bridge_prior_frame_slot(slots: list[R2VSlot], request: TimelineGenerationRequest) -> None:
    # OWNER-PROTECTED (Timeline Batch Architecture Guard). prior_frame = Batch N
    # ACTUAL last frame via the continuity bridge — the certified H3 extension
    # contract (TL-12). Removing/restriping this slot breaks visual continuation.
    """Append the ContinuityBridge last frame as an H3 prior_frame picture slot.

    Distinguishes a bridge-sourced continuation input (orchestrator set
    request.continuityBridgeId from an Applied/Ready bridge AND a real
    lastFrameAssetId) from an arbitrary request.lastFrameAssetId. Only the
    bridge-sourced case is the certified H3 extension contract (TL-12); an
    unchecked lastFrameAssetId without a bridge is NOT a continuation and must
    stay excluded by the Wave 2A fence. The prior_frame role wins over a
    duplicate place slot (same assetId) via _ROLE_PRIORITY in _rank_visual_slots,
    so a corridor start image is not double-counted.
    """
    bridge_id = str(getattr(request, "continuityBridgeId", None) or "").strip()
    last_frame = str(getattr(request, "lastFrameAssetId", None) or "").strip()
    if not bridge_id or not last_frame:
        return
    # If the same asset already appears as a place/character (e.g. the corridor
    # start image was reused as the last frame), promote it to prior_frame so the
    # continue-motion clause wins, rather than appending a duplicate.
    for slot in slots:
        if slot.assetId == last_frame and slot.role in {"place", "reference", "prop"}:
            slot.role = "prior_frame"
            slot.label = slot.label or "Previous take"
            return
    _add_slot(slots, asset_id=last_frame, role="prior_frame", label="Previous take")


def _is_bound_visual_reference(ref: dict[str, Any]) -> bool:
    """Creator-bound Master visual (@/%/#) even when consumed is False."""
    if not isinstance(ref, dict):
        return False
    aid = str(ref.get("assetId") or "").strip()
    if not aid:
        return False
    kind = str(ref.get("kind") or "").lower()
    if kind in {"charactervoice", "voice", "audio", "motion", "video"}:
        return False
    rtype = str(
        ref.get("referenceType") or ref.get("bindingType") or ref.get("reference_type") or ""
    ).lower()
    role = str(ref.get("role") or "").lower()
    if rtype in {"character", "crs", "prop", "vehicle", "environment", "location", "entity"}:
        return True
    if role in {"character", "crs", "prop", "place", "environment", "entity", "entity_reference"}:
        return True
    if kind in {"entity", "image"} and (
        ref.get("identityId") or ref.get("characterId") or ref.get("bindingId")
    ):
        return True
    return False


def _consumed_timeline_cast(batch: BatchBlock) -> tuple[set[str], set[str]]:
    """Character ids/assets the creator actually checked on the Timed Prompt.

    Stale characterIdentity / leftover voices must not expand this cast.
    Bound entity rows stay in the cast even when consumed is False.
    """
    ids: set[str] = set()
    assets: set[str] = set()
    for ref in batch.references or []:
        if not isinstance(ref, dict):
            continue
        if ref.get("consumed") is False and not _is_bound_visual_reference(ref):
            continue
        kind = str(ref.get("kind") or "").lower()
        if kind in {"characteridentity", "charactervoice", "voice", "audio", "motion"}:
            continue
        role = str(ref.get("role") or "").lower()
        rtype = str(ref.get("referenceType") or ref.get("bindingType") or "").lower()
        if (
            role not in {"character", "crs", "entity", "entity_reference"}
            and "character" not in role
            and rtype not in {"character", "crs"}
        ):
            continue
        aid = str(ref.get("assetId") or "").strip()
        ident = str(ref.get("identityId") or ref.get("characterId") or "").strip()
        if aid:
            assets.add(aid)
        if ident:
            ids.add(ident)
    return ids, assets


def collect_slots_from_batch(
    batch: BatchBlock,
    request: TimelineGenerationRequest,
    *,
    db: Any = None,
    auto_continuity_slots: bool = True,
) -> list[R2VSlot]:
    """Collect R2V slots from batch references.

    Visual slots (character/place/prop/prior_frame/reference/style) require IMAGE
    assets. Voice/audio/video assets are never visual slots — they are routed to
    the audio/video slot path below. When ``db`` is provided, non-image assets
    in visual roles are skipped with a warning emitted via ``warnings`` on the
    returned slots' metadata.
    """
    slots: list[R2VSlot] = []
    cast_ids, cast_assets = _consumed_timeline_cast(batch)
    # Kinds that produce audio/video slots, never visual slots.
    _AUDIO_VIDEO_KINDS = {"charactervoice", "voice", "audio", "motion"}
    from ...scene_references.sheet_tags import r2v_role_for_reference

    for ref in batch.references or []:
        if not isinstance(ref, dict):
            continue
        if ref.get("consumed") is False and not _is_bound_visual_reference(ref):
            continue
        kind = str(ref.get("kind") or "")
        # Voice/audio/motion references are handled by the audio slot loop below.
        if kind.lower() in _AUDIO_VIDEO_KINDS:
            continue
        if kind.lower() == "characteridentity":
            names = list(ref.get("identityNames") or [])
            ids = list(ref.get("identityIds") or [])
            assets = list(ref.get("identityAssetIds") or [])
            for idx, asset_id in enumerate(assets):
                name = str(names[idx] if idx < len(names) else "")
                ident = str(ids[idx] if idx < len(ids) else "") or None
                aid = str(asset_id).strip()
                if not aid:
                    continue
                if cast_assets and aid not in cast_assets:
                    continue
                if cast_ids and ident and ident not in cast_ids:
                    continue
                if _known_non_image_asset(db, aid):
                    continue
                resolved = _resolve_character_label(db, aid, ident, name)
                _add_slot(
                    slots,
                    asset_id=aid,
                    role="character",
                    label=resolved,
                    identity_id=ident,
                    aliases=_character_slot_aliases(db, aid, ident, name, resolved),
                )
            continue
        aid = str(ref.get("assetId") or "").strip()
        if not aid:
            continue
        sheet_role = r2v_role_for_reference(
            ref.get("referenceType") or ref.get("bindingType"),
            role=str(ref.get("role") or ""),
            kind=kind,
        )
        role = _norm_role(str(sheet_role or ref.get("role") or ""), kind=kind)
        if role == "video" or "video" in kind.lower() or kind == "motion":
            _add_slot(
                slots,
                asset_id=aid,
                role="video",
                label=str(ref.get("label") or ref.get("name") or "Motion"),
                identity_id=str(ref.get("identityId") or ref.get("entityId") or "") or None,
            )
            continue
        if role not in {"audio", "video"} and _known_non_image_asset(db, aid):
            continue
        ident = str(ref.get("identityId") or ref.get("entityId") or "") or None
        raw_label = str(ref.get("label") or ref.get("promptName") or ref.get("name") or "")
        aliases: list[str] = []
        if role == "character":
            aliases = _character_slot_aliases(db, aid, ident, raw_label)
            raw_label = _resolve_character_label(db, aid, ident, raw_label)
            aliases = _character_slot_aliases(db, aid, ident, *aliases, raw_label)
        _add_slot(
            slots,
            asset_id=aid,
            role=role,
            label=raw_label,
            identity_id=ident,
            aliases=aliases,
        )
    if auto_continuity_slots:
        for anchor in batch.sourceAnchors or []:
            aid = str(getattr(anchor, "assetId", None) or "").strip()
            if not aid:
                continue
            kind = str(getattr(anchor, "kind", "") or "")
            if kind == "audio":
                continue
            if kind == "video":
                _add_slot(slots, asset_id=aid, role="video", label=str(getattr(anchor, "label", "") or "Motion"))
                continue
            label = str(getattr(anchor, "label", "") or "")
            role = _norm_role(label, kind=kind)
            if kind == "end_frame":
                role = "reference"
            _add_slot(slots, asset_id=aid, role=role, label=label)
        last_id = str(request.lastFrameAssetId or "").strip()
        start_id = str(request.startImageAssetId or "").strip()
        if start_id and start_id != last_id:
            if not any(slot.assetId == start_id and slot.role == "character" for slot in slots):
                _add_slot(slots, asset_id=start_id, role="place", label="Opening picture")
        if last_id:
            _add_slot(slots, asset_id=last_id, role="prior_frame", label="Previous take")
        end_id = str(request.endImageAssetId or "").strip()
        if end_id:
            _add_slot(slots, asset_id=end_id, role="reference", label="End picture")
        planning = str((request.providerOptions or {}).get("planningStartImageAssetId") or "").strip()
        if planning and planning != last_id:
            _add_slot(slots, asset_id=planning, role="place", label="Opening picture")
    for ref in batch.references or []:
        if not isinstance(ref, dict) or ref.get("consumed") is False:
            continue
        if str(ref.get("kind") or "") not in {"characterVoice", "voice"}:
            continue
        aid = str(ref.get("assetId") or "").strip()
        if not aid:
            continue
        ident = str(ref.get("identityId") or "") or None
        if cast_ids and ident and ident not in cast_ids:
            continue
        _add_slot(
            slots,
            asset_id=aid,
            role="audio",
            label=str(ref.get("label") or ref.get("identityName") or "voice"),
            identity_id=ident,
        )
    return slots


def _preferred_slot(existing: R2VSlot | None, incoming: R2VSlot) -> R2VSlot:
    if existing is None:
        return incoming
    if _ROLE_PRIORITY.get(incoming.role, 99) < _ROLE_PRIORITY.get(existing.role, 99):
        return incoming
    return existing


def _rank_visual_slots(slots: list[R2VSlot]) -> list[R2VSlot]:
    order = ("character", "place", "prop", "prior_frame", "style", "reference")
    visual = [slot for slot in slots if slot.role not in {"video", "audio"}]
    winners: dict[str, R2VSlot] = {}
    for slot in visual:
        winners[slot.assetId] = _preferred_slot(winners.get(slot.assetId), slot)
    ranked: list[R2VSlot] = []
    seen: set[str] = set()
    for role in order:
        for slot in winners.values():
            if slot.role != role or slot.assetId in seen:
                continue
            seen.add(slot.assetId)
            ranked.append(slot)
    extras = [slot for slot in slots if slot.role in {"video", "audio"}]
    return ranked + extras


def _assign_picture_indices(
    slots: list[R2VSlot],
    *,
    skip_prior_frame: bool = False,
) -> list[R2VSlot]:
    ranked = _rank_visual_slots(slots)
    index = 1
    for slot in ranked:
        if slot.role in {"video", "audio"}:
            slot.pictureIndex = None
            continue
        if skip_prior_frame and slot.role == "prior_frame":
            slot.pictureIndex = None
            continue
        slot.pictureIndex = index
        index += 1
    audio_index = 1
    for slot in ranked:
        if slot.role != "audio":
            continue
        slot.audioIndex = audio_index
        audio_index += 1
    return ranked


def compile_h3_prompt(
    authored: str,
    slots: list[R2VSlot],
    *,
    style_key: str = "",
) -> tuple[str, list[str]]:
    """Compile H3 promptPrefix (diagnostics / fallback only).

    Phase B Direct Line: when the creator already authored ``<subject N>``
    bindings (Timed Prompt dialect), pass the text through unchanged. Do not
    lift style, strip live-action language, reinject registry style, or mutate
    subject lines. Callers must not copy this onto Comfy Input Text when
    request.prompt already holds the Timed Prompt (Phase A).
    """
    import re

    from .semantic_contract import build_contract, render_h3

    authored_text = authored or ""
    # Phase N: any non-empty Timed Prompt is verbatim. Do not synthesize
    # <subject N>, lift/reinject style, or append place/audio extras.
    if authored_text.strip():
        return authored_text, []

    contract = build_contract(
        slots=slots,
        authored=authored_text,
        style_key=style_key,
        for_h3=True,
    )
    compiled = render_h3(contract, inject_registry_style=False)
    extras: list[str] = []
    places = [slot for slot in slots if slot.pictureIndex is not None and slot.role == "place"]
    if places:
        extras.append(
            "They are in "
            + " and ".join(f"<Picture {slot.pictureIndex}>" for slot in places)
            + "."
        )
    audios = [slot for slot in slots if slot.role == "audio" and slot.audioIndex]
    if audios:
        from .semantic_contract import match_audio_subject

        parts: list[str] = []
        for slot in audios:
            subject = match_audio_subject(
                identity_id=str(slot.identityId or ""),
                label=slot.label,
                characters=contract.characters,
            )
            if subject:
                parts.append(f"<Audio {slot.audioIndex}> for <subject {subject}> (S{subject})")
            else:
                parts.append(f"<Audio {slot.audioIndex}> for {slot.label or 'this speaker'}")
        extras.append("Speak only with " + " and ".join(parts) + ".")
    if extras:
        compiled = "\n".join(part for part in (compiled, " ".join(extras)) if part)
    return compiled, []



def sanitize_ltx_creative_prompt(authored: str) -> str:
    """Strip Adept impl / binding prose from LTX creative Timed Prompts.

    LTX 2.5 Prompt Cleanup Law: creative prompt = style + shot/camera +
    subjects/action + continuity + preservation + dialogue.
    Binding stays structural (Visual / start-end frames). Diagnostics != creative.
    """
    import re

    raw = authored or ""
    if not raw.strip():
        return raw
    drop_line = re.compile(
        r"(?i)^\s*("
        r"\[R2V\].*"
        r"|Opening picture is\b.*"
        r"|.*approved front still.*"
        r"|.*Named in prompt only.*"
        r"|.*not extra reference tensors.*"
        r"|LTX conditioning\b.*"
        r"|.*no MiniMax multi-reference.*"
        r"|.*not silently dropped.*"
        r"|Co-Director pose continuity.*"
        r"|Co-Director temporal continuity.*"
        r")\s*$"
    )
    cleaned_lines: list[str] = []
    for line in raw.splitlines():
        if drop_line.match(line):
            continue
        line = re.sub(r"(?i)\[R2V\]\s*", "", line)
        line = re.sub(r"(?i)\bOpening picture is\b[^.]*\.\s*", "", line)
        cleaned_lines.append(line)
    out: list[str] = []
    blank = 0
    for line in cleaned_lines:
        if not line.strip():
            blank += 1
            if blank <= 1:
                out.append(line)
            continue
        blank = 0
        out.append(line)
    return "\n".join(out).strip()


def compile_single_cond_prompt(
    authored: str,
    slots: list[R2VSlot],
    *,
    start_id: str | None,
    mechanism: str,
    style_key: str = "",
) -> tuple[str, list[str]]:
    from .semantic_contract import build_contract, render_ltx

    start = str(start_id or "").strip()
    start_slot = next((s for s in slots if s.assetId == start), None)
    extras = [s for s in slots if s.assetId != start and s.role not in {"video", "audio"}]
    disclosures: list[str] = []
    start_line = ""
    extras_line = ""
    creative = authored or ""

    # LTX 2.5 Prompt Cleanup Law: never inject Adept [R2V]/binding prose into
    # the creative prompt. Start image binding stays structural (startImageAssetId /
    # Visual). Extras disclosure is diagnostics-only, not creative text.
    if mechanism == LTX25_MECHANISM:
        creative = sanitize_ltx_creative_prompt(creative)
        if start_slot:
            disclosures.append(
                f"Structural start frame: {start_slot.label or start_slot.role} ({start_slot.role})."
            )
        if extras:
            names = ", ".join(f"{slot.label or slot.role} ({slot.role})" for slot in extras)
            disclosures.append(
                f"LTX 2.5 conditions one start picture; extras named for diagnostics only: {names}."
            )
    else:
        if start_slot:
            start_line = (
                f"[R2V] Opening picture is {start_slot.label or start_slot.role} ({start_slot.role})."
            )
        if extras:
            names = ", ".join(
                f"{slot.label or slot.role} ({slot.role})" for slot in extras
            )
            extras_line = f"[R2V] Also in this shot: {names}."

    contract = build_contract(slots=slots, authored=creative, style_key=style_key)
    return render_ltx(contract, start_line=start_line, extras_line=extras_line), disclosures

def compile_named_extras_prompt(
    authored: str,
    slots: list[R2VSlot],
    *,
    start_id: str | None = None,
    disclose_unuploaded: bool = True,
) -> tuple[str, list[str]]:
    start = str(start_id or "").strip()
    extras = [s for s in slots if s.assetId != start and s.role not in {"video", "audio"}]
    videos = [s for s in slots if s.role == "video"]
    disclosures: list[str] = []
    lines: list[str] = []
    if extras and disclose_unuploaded:
        names = ", ".join(f"{slot.label or slot.role} ({slot.role})" for slot in extras)
        lines.append(f"Also in this shot (named only, not extra uploaded refs): {names}.")
        disclosures.append(
            "This generator conditions at most one picture. Extra project sheets stay named."
        )
    if videos:
        names = ", ".join(slot.label or "motion" for slot in videos)
        lines.append(f"Motion reference named only (not uploaded as a video tensor): {names}.")
    body = (authored or "").strip()
    return "\n".join(part for part in (*lines, body) if part), disclosures


def compile_seedance_prompt(
    authored: str,
    slots: list[R2VSlot],
    *,
    max_images: int = 4,
    max_videos: int = 1,
) -> tuple[str, list[str]]:
    videos = [slot for slot in slots if slot.role == "video"][: max(0, max_videos)]
    visuals = [slot for slot in slots if slot.role not in {"video", "audio"}][: max(0, max_images)]
    if not videos:
        return (authored or "").strip(), [
            "Seedance I2V/T2V — extras stay on image_url / referenceAssetIds. No @Image/@Video tokens."
        ]
    lines: list[str] = []
    for index, slot in enumerate(visuals, start=1):
        lines.append(f"@Image{index} {slot.label or slot.role} ({slot.role})")
    for index, slot in enumerate(videos, start=1):
        lines.append(f"@Video{index} {slot.label or 'motion'} (motion)")
    body = (authored or "").strip()
    return "\n".join(part for part in (*lines, body) if part), [
        "Seedance R2V tokens match uploaded image_urls / video_urls. Adept sends at most 4 images and 1 video. No @Audio."
    ]


def map_canonical_r2v(
    *,
    slots: list[R2VSlot],
    generator_id: str,
    mapped_start: str | None,
    authored_prompt: str,
    joining: bool = False,
    style_key: str = "",
) -> CanonicalR2VRequest:
    from ...hosted_providers.video_registry import is_retired_local_video

    start_id = str(mapped_start or "").strip() or None
    if is_retired_local_video(generator_id):
        return CanonicalR2VRequest(
            slots=slots,
            mappedStartAssetId=start_id,
            mechanism="",
            promptPrefix=authored_prompt,
            disclosures=[
                f"Local video generator '{generator_id}' is retired. "
                "Adept UI uses MiniMax H3 and LTX 2.5 only. No substitute was selected."
            ],
            tensorSlotCount=0,
            promptOnlyCount=len(slots),
        )
    kb = knowledge_for_generator(generator_id)
    mechanism = mechanism_for_generator(generator_id)
    skip_prior = bool(joining and mechanism == H3_MECHANISM)
    ranked = _assign_picture_indices(slots, skip_prior_frame=skip_prior)
    dialect = kb.compile.dialect if kb.loaded else ""
    if mechanism == H3_MECHANISM or dialect == "h3_picture_tokens":
        prompt, disclosures = compile_h3_prompt(
            authored_prompt, ranked, style_key=style_key
        )
        tensor_count = len([s for s in ranked if s.pictureIndex])
        prompt_only = len(
            [s for s in ranked if s.role == "prior_frame" and s.pictureIndex is None]
        )
        notes = list(disclosures) or [
            "MiniMax H3 uses MiniMaxH3ReferenceToVideo with LoadImage ref_images and "
            "lowercase <subject n> is Name. bindings. This is not first-frame I2V."
        ]
        if skip_prior and prompt_only:
            notes.append(
                "A new character is joining, so the previous take stays named "
                "but is not sent as a MiniMax picture. That last frame is often "
                "occupied or an Ingredients leak."
            )
        return CanonicalR2VRequest(
            slots=ranked,
            mappedStartAssetId=start_id,
            mechanism=mechanism,
            promptPrefix=prompt,
            disclosures=notes,
            tensorSlotCount=tensor_count,
            promptOnlyCount=prompt_only,
        )
    if mechanism == SEEDANCE_MECHANISM or dialect == "seedance_at_tokens":
        prompt, disclosures = compile_seedance_prompt(
            authored_prompt,
            ranked,
            max_images=int(kb.compile.max_images or 4),
            max_videos=int(kb.compile.max_videos or 1),
        )
        image_n = min(kb.compile.max_images or 4, len([s for s in ranked if s.role not in {"video", "audio"}]))
        video_n = min(kb.compile.max_videos or 1, len([s for s in ranked if s.role == "video"]))
        return CanonicalR2VRequest(
            slots=ranked,
            mappedStartAssetId=start_id,
            mechanism=mechanism or SEEDANCE_MECHANISM,
            promptPrefix=prompt,
            disclosures=disclosures,
            tensorSlotCount=image_n + video_n,
            promptOnlyCount=max(0, len(ranked) - image_n - video_n),
        )
    if mechanism in {KLING_MECHANISM, VEO_MECHANISM} or dialect in {"kling_named", "veo_named"}:
        prompt, disclosures = compile_named_extras_prompt(
            authored_prompt,
            ranked,
            start_id=start_id,
            disclose_unuploaded=True,
        )
        if dialect == "veo_named":
            disclosures = [
                "Official Veo 3.1 allows up to 3 reference images of one subject. Adept Timeline currently sends 1 start image.",
                *disclosures,
            ]
        return CanonicalR2VRequest(
            slots=ranked,
            mappedStartAssetId=start_id,
            mechanism=mechanism or ("veo_r2v" if dialect == "veo_named" else "kling_i2v"),
            promptPrefix=prompt,
            disclosures=disclosures,
            tensorSlotCount=1 if start_id else 0,
            promptOnlyCount=max(0, len([s for s in ranked if s.role not in {"video", "audio"}]) - (1 if start_id else 0)),
        )
    if dialect == "unavailable":
        return CanonicalR2VRequest(
            slots=ranked,
            mappedStartAssetId=start_id,
            mechanism="",
            promptPrefix=authored_prompt,
            disclosures=["This Production Control row is not a Timeline execution path."],
            tensorSlotCount=0,
            promptOnlyCount=len(ranked),
        )
    if not mechanism:
        return CanonicalR2VRequest(
            slots=ranked,
            mappedStartAssetId=start_id,
            mechanism="unmapped",
            promptPrefix=authored_prompt,
            disclosures=[
                "This generator is not a mapped Timeline R2V dialect. "
                "The authored prompt was left unchanged. No H3, LTX, or Seedance grammar was invented."
            ],
            tensorSlotCount=0,
            promptOnlyCount=len(ranked),
        )
    prompt, disclosures = compile_single_cond_prompt(
        authored_prompt,
        ranked,
        start_id=start_id,
        mechanism=mechanism,
        style_key=style_key,
    )
    extras = max(0, len([s for s in ranked if s.role not in {"video", "audio"}]) - (1 if start_id else 0))
    return CanonicalR2VRequest(
        slots=ranked,
        mappedStartAssetId=start_id,
        mechanism=mechanism or "unmapped",
        promptPrefix=prompt,
        disclosures=disclosures,
        tensorSlotCount=1 if start_id else 0,
        promptOnlyCount=extras,
    )


def _refuse_dropped_bound_visuals(batch: BatchBlock, payload: CanonicalR2VRequest) -> None:
    """Fail closed when a bound @/%/# image never reached an H3 picture slot."""
    slotted = {
        str(slot.assetId or "").strip()
        for slot in (payload.slots or [])
        if str(slot.assetId or "").strip() and slot.pictureIndex
    }
    for ref in batch.references or []:
        if not _is_bound_visual_reference(ref if isinstance(ref, dict) else {}):
            continue
        aid = str(ref.get("assetId") or "").strip()
        if aid and aid not in slotted:
            tag = str(ref.get("tag") or ref.get("promptName") or ref.get("label") or aid)
            rtype = str(ref.get("referenceType") or ref.get("role") or "reference")
            raise ValueError(
                f"BOUND_REFERENCE_DROPPED: {rtype} {tag} ({aid}) did not reach an H3 picture slot"
            )


def attach_canonical_r2v(
    request: TimelineGenerationRequest,
    batch: BatchBlock,
    caps: VideoGeneratorCapabilities,
    *,
    db: Any = None,
) -> CanonicalR2VRequest:
    """Write the canonical R2V payload onto the request. Never drop slots."""
    product = product_generator_id(request, request.generatorId or caps.id)
    from .direct_reference import payload_from_request, payload_to_r2v_slots

    is_h3 = mechanism_for_generator(product) == H3_MECHANISM or product.startswith("minimax-h3")
    direct = payload_from_request(request)
    # Wave 2A: H3 sockets are DR-only when a Direct Reference payload is attached.
    # Never invent place/prior from sourceAnchors / lastFrame on H3 (R3/R7 fence).
    # Extension exception: a bridge-sourced prior_frame (request.continuityBridgeId
    # set by the orchestrator from an Applied/Ready ContinuityBridge, with a real
    # lastFrameAssetId extracted from the previous segment) is the certified H3
    # extension contract (TL-12: "H3 last-frame → prompt_context + prior_frame").
    # It is NOT an invented place/prior — it is the actual continuation input and
    # must reach the H3 ref_image_N picture list so Segment B knows where Segment A
    # ended. Without this, an extension batch regenerates the root scene (the
    # Timeline Extension Duplication regression).
    if direct is not None and (direct.sockets or direct.visual_items()):
        slots = payload_to_r2v_slots(direct)
        if is_h3:
            _add_bridge_prior_frame_slot(slots, request)
    else:
        slots = collect_slots_from_batch(
            batch,
            request,
            db=db,
            auto_continuity_slots=not is_h3,
        )
        # REBUILD LAW (TL-12 completeness): the bridge prior_frame exception is
        # independent of the Direct Reference payload. An extension batch with
        # no checked identity refs (pure environment continuation) must still
        # receive the bridge last frame — otherwise the certified H3 extension
        # contract silently degrades to prompt-only continuation. Without a
        # bridge this is a no-op (Wave 2A fence preserved).
        if is_h3:
            _add_bridge_prior_frame_slot(slots, request)
    video_id = str(request.videoReferenceAssetId or "").strip()
    if video_id and not is_h3:
        _add_slot(slots, asset_id=video_id, role="video", label="Motion reference")
    authored = str((request.providerOptions or {}).get("authoredPrompt") or request.prompt or "")
    mapped = str(request.startImageAssetId or "").strip() or None
    joining = bool((request.providerOptions or {}).get("identityJoining"))
    style_key = str((request.providerOptions or {}).get("visualStyle") or "")
    # LTX 2.5 / single-cond: one start picture must reach LTXVImgToVideo. If the
    # Timeline request still has no startImageAssetId (e.g. only role=start_image
    # or entity refs after maxReferenceImages=0 clear), promote the first visual
    # slot so mappedStartAssetId is not left null with prompt-only leftovers.
    if not mapped and mechanism_for_generator(product) in {
        LTX25_MECHANISM,
    }:
        for slot in _rank_visual_slots(slots):
            if slot.role in {"video", "audio"}:
                continue
            aid = str(slot.assetId or "").strip()
            if aid:
                mapped = aid
                request.startImageAssetId = aid
                break
    payload = map_canonical_r2v(
        slots=slots,
        generator_id=product,
        mapped_start=mapped,
        authored_prompt=authored or request.prompt,
        joining=joining,
        style_key=style_key,
    )
    if payload.mechanism == H3_MECHANISM and str(getattr(request, "continuityBridgeId", None) or "").strip():
        _open_on_prior_frame(payload)
    request.providerOptions = dict(request.providerOptions or {})
    request.providerOptions["r2v"] = payload.to_job_dict()
    kb = knowledge_for_generator(product)
    request.providerOptions["r2vKnowledge"] = {
        "loaded": kb.loaded,
        "spec": kb.spec_path.name if kb.loaded else "",
        "dialect": kb.compile.dialect,
        "mechanism": payload.mechanism,
    }
    try:
        from .semantic_contract import build_contract

        request.providerOptions["semanticContract"] = build_contract(
            slots=payload.slots,
            authored=authored or request.prompt,
            style_key=style_key,
        ).to_ledger()
    except Exception:
        pass
    if payload.mechanism == H3_MECHANISM:
        if not str(request.resolution or "").strip():
            request.resolution = H3_CANVAS
        # Wave 2A / Phase A Direct Line: Timed Prompt on request.prompt is Comfy
        # Input Text authority. promptPrefix is diagnostics-only — residual H3
        # overwrite authority DELETED (never request.prompt = promptPrefix on H3).
        request.providerOptions["h3PromptAuthority"] = "timed_prompt_direct_line"
        # Additive subject/picture binds after slots exist. authoredPrompt stays.
        from .semantic_contract import apply_bound_reference_tokens

        request.prompt = apply_bound_reference_tokens(request.prompt, payload.slots)
        prior = next(
            (slot for slot in payload.slots if slot.role == "prior_frame" and slot.pictureIndex),
            None,
        )
        if prior is not None and str(getattr(request, "continuityBridgeId", None) or "").strip():
            opener = (
                f"<Picture {int(prior.pictureIndex)}> is the last frame of the previous window. "
                "Begin this shot on that exact picture. "
                "Keep the same people, distance, and light at the cut."
            )
            if opener.lower() not in (request.prompt or "").lower():
                request.prompt = opener + "\n\n" + (request.prompt or "").strip()
        request.providerOptions["h3ReferenceTokensApplied"] = True
        _refuse_dropped_bound_visuals(batch, payload)
    elif direct is None and payload.promptPrefix and payload.mechanism in {
        LTX25_MECHANISM,
        SEEDANCE_MECHANISM,
        KLING_MECHANISM,
        VEO_MECHANISM,
    }:
        request.prompt = payload.promptPrefix
    return payload


def merge_identity_slots(
    request: TimelineGenerationRequest,
    *,
    characters: list[dict[str, Any]],
    place_asset_id: str | None = None,
    method: str,
    joining: bool = False,
    batch: BatchBlock | None = None,
) -> CanonicalR2VRequest:
    raw = ((request.providerOptions or {}).get("r2v") or {}) if request.providerOptions else {}
    slots = [R2VSlot.model_validate(item) for item in (raw.get("slots") or [])]
    incoming_ids = {str(c.get("assetId") or "").strip() for c in characters if c.get("assetId")}
    if incoming_ids:
        slots = [slot for slot in slots if slot.role != "character" or slot.assetId in incoming_ids]
    tagged_place = next(
        (
            slot
            for slot in slots
            if slot.role == "place" and slot.label and slot.label not in {"Opening picture", "Scene"}
        ),
        None,
    )
    if tagged_place is not None:
        slots = [slot for slot in slots if slot.role != "place" or slot.assetId == tagged_place.assetId]
        place_asset_id = tagged_place.assetId
    elif place_asset_id:
        slots = [
            slot
            for slot in slots
            if slot.role != "place" or slot.assetId == str(place_asset_id)
        ]
    for character in characters:
        _add_slot(
            slots,
            asset_id=str(character.get("assetId") or ""),
            role="character",
            label=str(character.get("name") or ""),
            identity_id=str(character.get("characterId") or "") or None,
            appearance=str(character.get("appearance") or ""),
            aliases=[str(character.get("name") or "")],
        )
    last_id = str(request.lastFrameAssetId or "").strip()
    if last_id:
        _add_slot(slots, asset_id=last_id, role="prior_frame", label="Previous take")
    if place_asset_id and place_asset_id != last_id:
        _add_slot(slots, asset_id=place_asset_id, role="place", label="Scene")
    product = product_generator_id(request, request.generatorId or "")
    authored = str((request.providerOptions or {}).get("authoredPrompt") or request.prompt or "")
    payload = map_canonical_r2v(
        slots=slots,
        generator_id=product,
        mapped_start=str(request.startImageAssetId or "").strip() or None,
        authored_prompt=authored,
        joining=joining or bool((request.providerOptions or {}).get("identityJoining")),
        style_key=str((request.providerOptions or {}).get("visualStyle") or ""),
    )
    request.generationMode = "reference"
    request.providerOptions = dict(request.providerOptions or {})
    request.providerOptions["r2v"] = payload.to_job_dict()
    request.providerOptions["reference_method"] = method
    request.providerOptions["identityJoining"] = bool(
        joining or request.providerOptions.get("identityJoining")
    )
    if payload.mechanism == H3_MECHANISM and not str(request.resolution or "").strip():
        request.resolution = H3_CANVAS
    if payload.mechanism == H3_MECHANISM:
        from .semantic_contract import apply_bound_reference_tokens

        request.prompt = apply_bound_reference_tokens(request.prompt, payload.slots)
        request.providerOptions["h3ReferenceTokensApplied"] = True
        if batch is not None:
            _refuse_dropped_bound_visuals(batch, payload)
    # Wave 2A / Phase A: H3 Timed Prompt stays on request.prompt; promptPrefix is
    # diagnostics only. Residual H3 overwrite authority deleted.
    if payload.promptPrefix and payload.mechanism != H3_MECHANISM:
        request.prompt = payload.promptPrefix
    return payload


def r2v_from_request(request: TimelineGenerationRequest) -> CanonicalR2VRequest | None:
    raw = (request.providerOptions or {}).get("r2v")
    if not isinstance(raw, dict) or not raw.get("slots"):
        return None
    return CanonicalR2VRequest.model_validate(raw)


def visual_slot_asset_ids(payload: CanonicalR2VRequest | dict[str, Any] | None) -> list[str]:
    if payload is None:
        return []
    data = payload.to_job_dict() if isinstance(payload, CanonicalR2VRequest) else payload
    ids: list[str] = []
    for item in data.get("slots") or []:
        if not isinstance(item, dict):
            continue
        if item.get("role") in {"video", "audio"}:
            continue
        aid = str(item.get("assetId") or "").strip()
        if aid and aid not in ids:
            ids.append(aid)
    return ids


def copy_r2v_into_job_params(params: dict[str, Any], request: TimelineGenerationRequest) -> None:
    payload = (request.providerOptions or {}).get("r2v")
    if isinstance(payload, dict) and payload:
        params["r2v"] = payload
        mapped = str(payload.get("mappedStartAssetId") or "").strip()
        if mapped and not str(params.get("startImageAssetId") or "").strip():
            params["startImageAssetId"] = mapped
    direct = (request.providerOptions or {}).get("directReferences")
    if isinstance(direct, dict) and direct:
        params["directReferences"] = direct
    if request.generationMode:
        params["generationMode"] = request.generationMode
    deps = (request.providerOptions or {}).get("runtimeDependencies")
    if isinstance(deps, dict) and deps:
        params["runtimeDependencies"] = deps
    if request.providerOptions and request.providerOptions.get("fast_generation") is not None:
        params["fast_generation"] = bool(request.providerOptions.get("fast_generation"))
    # Pass MiniMax H3 duration-contract fields so the queue worker can:
    # 1. Use legalFrameCount for the MiniMax generation (294 for 12.0s)
    # 2. Trim the generated excess back to requestedDurationSec (12.0s)
    po = request.providerOptions or {}
    if po.get("requestedDurationSec") is not None:
        params["requestedDurationSec"] = po["requestedDurationSec"]
    if po.get("legalDurationSec") is not None:
        params["legalDurationSec"] = po["legalDurationSec"]
    if po.get("legalFrameCount") is not None:
        params["legalFrameCount"] = po["legalFrameCount"]
    # Native MiniMax audio: when Timeline has no audio override, request_builder
    # sets generate_audio=True (caps.audio_generation). Pass both names so the
    # queue worker / Comfy path can honor generator-native audio.
    if po.get("generate_audio") is not None:
        params["generate_audio"] = bool(po.get("generate_audio"))
        params["audio_generation"] = bool(po.get("generate_audio"))
    elif po.get("audio_generation") is not None:
        params["audio_generation"] = bool(po.get("audio_generation"))
        params["generate_audio"] = bool(po.get("audio_generation"))
    aa = po.get("audioAuthority")
    if isinstance(aa, dict):
        params["audioAuthority"] = aa
    cv = po.get("characterVoices")
    if isinstance(cv, dict) and cv:
        params["characterVoices"] = cv
    # Co-Director Dialogue Authority: structured spoken language + Manifest
    # must reach the job ledger for Omni QC / Re-Take. Does NOT rewrite
    # Timed Prompt bytes (H3 Direct Line) and does NOT invent Comfy language widgets.
    da = po.get("dialogueAuthority")
    if isinstance(da, dict) and da:
        params["dialogueAuthority"] = da
    sl = po.get("spokenLanguage")
    if isinstance(sl, dict) and sl:
        params["spokenLanguage"] = sl
    elif isinstance(sl, str) and sl.strip():
        params["spokenLanguage"] = sl.strip()
    mid = po.get("dialogueManifestId")
    if mid:
        params["dialogueManifestId"] = mid
    dp = po.get("dialoguePreflight")
    if isinstance(dp, dict) and dp:
        params["dialoguePreflight"] = dp
    h3sa = po.get("h3SpeechAuthority")
    if isinstance(h3sa, dict) and h3sa:
        params["h3SpeechAuthority"] = h3sa
    ref_size = po.get("refImageSize") or po.get("ref_image_size")
    if ref_size:
        from ...workflows.h3_ref2v_builder import resolve_h3_ref_image_size

        params["refImageSize"] = resolve_h3_ref_image_size(ref_size)
    gen_id = str(
        params.get("generatorId")
        or params.get("adapterId")
        or params.get("engine")
        or ""
    ).lower()
    if gen_id in H3_GENERATOR_IDS or "minimax-h3" in gen_id:
        r2v = params.get("r2v") if isinstance(params.get("r2v"), dict) else {}
        r2v = dict(r2v)
        r2v.setdefault("mechanism", H3_MECHANISM)
        r2v.setdefault("runtime", "adept-comfy-8188")
        params["r2v"] = r2v
        params.setdefault("mechanism", H3_MECHANISM)
        params.setdefault("runtime", "adept-comfy-8188")
