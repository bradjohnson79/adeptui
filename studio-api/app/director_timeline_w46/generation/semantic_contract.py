"""Semantic generation contract — identity and style are separate authorities.

Law:
  The reference image is identity authority.
  Project / scene style is rendering authority.
  Text reinforces action and context. It must not redescribed a character
  into existence, and a style change must not recast the referenced people.

Generator adapters translate this contract into MiniMax / LTX surface syntax.
They must not collapse the layers back into one undifferentiated prose blob.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from pydantic import BaseModel, Field

IDENTITY_PRESERVE = (
    "Preserve the supplied visual identity. "
    "Do not invent a replacement person. "
    "Keep the face, hair, body, wardrobe, and distinguishing marks from the reference picture. "
    "The setting must not redesign their clothes or recast them as generic extras."
)
STYLE_PRESERVE = (
    "Apply this style to the entire scene while preserving reference identity. "
    "A style change is a rendering treatment of the same referenced characters, not a recast."
)

# Global photographic / live-action language that must not ride on every style.
_LIVE_ACTION_BIAS = re.compile(
    r"(?i)\b("
    r"photorealistic(?:\s+environment)?"
    r"|cinematic photography"
    r"|real actors?"
    r"|natural skin"
    r"|DSLR"
    r"|film still"
    r"|hyperreal(?:istic)?"
    r"|premium live-action(?:\s+cinematic\s+production)?"
    r"|look like a scene from a premium live-action"
    r"|exceptionally high-quality realistic anime characters physically inhabit"
    r")\b"
)

# Text that tries to reconstruct a character from prose instead of the sheet.
_IDENTITY_REDESCRIBE = re.compile(
    r"(?i)("
    # Heavy identity essays only. Do NOT match owner-dialect
    # ``<subject N> is Name.`` / ``<subject N> @Tag = Name`` bindings —
    # those must survive Timed Prompt → Comfy Input Text.
    r"use\s+<subject\s+\d+>\s+as the absolute character identity"
    r"|preserve (?:her|his|their) exact face"
    r"|absolute character identity and appearance reference"
    r")"
)

_SUBJECT_TAG = re.compile(r"<subject\s+\d+>", re.IGNORECASE)
_SUBJECT_ASSIGNMENT = re.compile(
    r"(?i)^\s*(?:<subject\s+\d+>\s+)?is\s+\S+.*\(@[^)]+\)\.?\s*$"
)
_OFFICIAL_MEDIA_TOKEN = re.compile(
    r"<(?:Subject|Picture|Audio|Video)\s+\d+>",
    re.IGNORECASE,
)
_GENERIC_NAME_TOKS = frozenset(
    {"years", "year", "old", "the", "this", "character", "person", "yearsold"}
)

_STYLE_LINE = re.compile(r"(?i)\bvisual style:\s*([^\n.]+)")

_PLANNING_NOISE = re.compile(
    r"(?i)^("
    r"unchanged facts:"
    r"|starting state \(m\d+\):"
    r"|ending state \(m\d+\):"
    r"|timed prompt:"
    r")"
)
_PRIMARY_PLACEHOLDER = re.compile(r"(?i)\bprimary (?:beat|direction|line)\b")

_PHOTOGRAPHIC_STYLES = frozenset({"live_action", "documentary_realism"})


class CharacterIdentityLayer(BaseModel):
    tag: str = ""
    label: str = ""
    picture_index: int | None = None
    asset_id: str = ""
    role: str = "character"
    identity_id: str = ""
    aliases: list[str] = Field(default_factory=list)


class SemanticGenerationContract(BaseModel):
    """Shared semantic plan. Adapters render this; they do not invent identity."""

    characters: list[CharacterIdentityLayer] = Field(default_factory=list)
    style_key: str = ""
    style_display: str = ""
    style_rendering: str = ""
    style_camera: str = ""
    environment: str = ""
    action: str = ""
    camera: str = ""
    dialogue_audio: list[str] = Field(default_factory=list)
    continuity: str = ""
    identity_authority: str = "reference_image"

    def to_ledger(self) -> dict[str, Any]:
        return {
            "identityAuthority": self.identity_authority,
            "characters": [c.model_dump() for c in self.characters],
            "style": {
                "key": self.style_key,
                "display": self.style_display,
                "rendering": self.style_rendering,
            },
            "environment": self.environment,
            "action": self.action,
            "camera": self.camera,
            "dialogueAudio": list(self.dialogue_audio),
            "continuity": self.continuity,
        }


def resolve_style_profile(style_key: str) -> Any | None:
    token = (style_key or "").strip()
    if not token:
        return None
    try:
        from ...style_intelligence.registry import STYLE_REGISTRY, REQUIRED_STYLE_KEYS

        if token in STYLE_REGISTRY:
            return STYLE_REGISTRY[token]
        lowered = token.lower()
        for key in REQUIRED_STYLE_KEYS:
            profile = STYLE_REGISTRY[key]
            display = str(getattr(profile, "displayName", "") or "").strip().lower()
            key_name = str(getattr(profile, "key", "") or key).strip().lower()
            if lowered == display or lowered == key_name:
                return profile
            if display and (lowered.startswith(display + " ") or lowered.startswith(display + ",")):
                return profile
    except Exception:
        return None
    return None


def style_rendering_phrase(style_key: str) -> str:
    profile = resolve_style_profile(style_key)
    if profile is not None and getattr(profile, "renderingLanguage", ""):
        return str(profile.renderingLanguage).strip()
    fallbacks = {
        "realistic_anime": (
            "Hybrid realistic-anime illustration with refined line control, "
            "grounded shading, believable depth, and stylized clarity."
        ),
        "anime": "Anime illustration with clean line work and stylized shading.",
        "live_action": "Cinematic live-action photography with realistic lighting and natural detail.",
        "3d": "3D rendered animation with volumetric lighting and material detail.",
        "claymation": (
            "Expressive claymation with hand-sculpted forms, tactile fingerprints, "
            "and staged animation appeal."
        ),
    }
    return fallbacks.get((style_key or "").strip().lower(), "")


def style_camera_phrase(style_key: str) -> str:
    """Cinematography that is legal for this style — not a recast into actors."""
    profile = resolve_style_profile(style_key)
    if profile is None:
        return ""
    camera = str(getattr(profile, "cameraLanguage", "") or "").strip()
    if not camera:
        return ""
    key = str(getattr(profile, "key", "") or style_key).strip().lower()
    if key not in _PHOTOGRAPHIC_STYLES:
        # Keep composition / movement; drop actor / photographic-recast cues.
        if re.search(r"(?i)\b(actor|performer|casting|photographic face)\b", camera):
            return ""
    return camera


def allows_live_action_language(style_key: str) -> bool:
    profile = resolve_style_profile(style_key)
    key = str(getattr(profile, "key", "") or style_key or "").strip().lower()
    return key in _PHOTOGRAPHIC_STYLES


def resolve_style_key(token: str) -> str:
    profile = resolve_style_profile(token)
    if profile is not None:
        return str(getattr(profile, "key", "") or token).strip()
    return (token or "").strip()


def lift_style_from_text(text: str, *, remove_from_text: bool = True) -> tuple[str, str]:
    """Resolve a creator/Co-Director 'Visual style: X' line into the style layer.

    Phase B: when ``remove_from_text`` is False (H3 Timed Prompt path), return the
    resolved key but leave the authored Visual style line intact so Comfy Input
    Text stays byte-faithful. Also fix the period-merge bug that glued a leftover
    ``.`` onto the previous line (``Korri\n\n.`` → ``Korri.``).
    """
    raw = text or ""
    match = _STYLE_LINE.search(raw)
    key = resolve_style_key(match.group(1).strip()) if match else ""
    if not remove_from_text:
        return key, raw
    # Consume the trailing period of the style sentence with the match so it is
    # not left behind to be merged onto the prior line.
    cleaned = re.sub(
        r"(?i)\bvisual style:\s*([^\n.]+)(?:\.)?",
        "",
        raw,
        count=1,
    )
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"^\s*\.\s*", "", cleaned)
    # Only collapse spaces/tabs before a period — never newlines (period-merge bug).
    cleaned = re.sub(r"[ \t]+\.", ".", cleaned)
    cleaned = re.sub(r"\.{2,}", ".", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return key, cleaned


def expand_name_aliases(*parts: str) -> list[str]:
    """Generic mention aliases from a Timeline label / @tag / profile name.

    No character-specific constants. ``Korri40YearsOld`` also yields ``Korri``
    so creator prose can use the given name while the checkbox tag stays long.
    """
    raw: list[str] = []
    for part in parts:
        token = str(part or "").strip()
        if not token:
            continue
        raw.append(token)
        bare = token[1:] if token.startswith("@") else token
        if bare:
            raw.append(bare)
            raw.append(f"@{bare}")
            collapsed = re.sub(r"[^A-Za-z0-9]+", "", bare)
            if collapsed and collapsed.lower() not in _GENERIC_NAME_TOKS:
                raw.append(collapsed)
                raw.append(f"@{collapsed}")
        for piece in re.findall(r"[A-Za-z]+", token):
            if len(piece) >= 3 and piece.lower() not in _GENERIC_NAME_TOKS:
                raw.append(piece)
                raw.append(f"@{piece}")
                break
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        key = item.lower()
        if not item.strip("@") or key in seen:
            continue
        seen.add(key)
        out.append(item)
    out.sort(key=len, reverse=True)
    return out


def character_aliases(char: CharacterIdentityLayer) -> list[str]:
    return expand_name_aliases(char.label, char.tag, *list(char.aliases or []))


def bind_subjects_in_text(text: str, characters: Iterable[CharacterIdentityLayer]) -> str:
    """Rewrite creator names / @tags to owner-dialect ``<subject N>`` after sanitize."""
    raw = text or ""
    cast = [c for c in characters if c.picture_index]
    if not raw or not cast:
        return raw
    held: list[str] = []

    def _hold(match: re.Match[str]) -> str:
        held.append(match.group(0))
        return f"\x00H{len(held) - 1}\x00"

    work = _OFFICIAL_MEDIA_TOKEN.sub(_hold, raw)
    pairs: list[tuple[str, int]] = []
    for char in cast:
        index = int(char.picture_index or 0)
        for alias in character_aliases(char):
            pairs.append((alias, index))
    pairs.sort(key=lambda item: len(item[0]), reverse=True)
    for alias, index in pairs:
        if alias.startswith("@"):
            continue
        work = re.sub(
            rf"(?im)^(\s*){re.escape(alias)}\s*:",
            rf"\1<subject {index}> (S{index}):",
            work,
        )
    for alias, index in pairs:
        if alias.startswith("@"):
            pattern = re.compile(re.escape(alias), re.IGNORECASE)
        else:
            pattern = re.compile(rf"(?<![\w<@]){re.escape(alias)}(?![\w>])", re.IGNORECASE)
        work = pattern.sub(f"<subject {index}>", work)

    def _restore(match: re.Match[str]) -> str:
        return held[int(match.group(1))]

    return re.sub(r"\x00H(\d+)\x00", _restore, work)


def subject_definition_line(char: CharacterIdentityLayer) -> str:
    """Owner Comfy dialect: lowercase ``<subject N> is Name.`` bound to LoadImage order."""
    name = (char.label or "this character").strip().lstrip("@").strip() or "this character"
    index = int(char.picture_index or 0)
    return f"<subject {index}> is {name}."


def _slot_field(slot: Any, *names: str) -> Any:
    for name in names:
        if isinstance(slot, dict):
            if name in slot:
                return slot.get(name)
            continue
        if hasattr(slot, name):
            return getattr(slot, name)
    return None


def compile_h3_av_natural_tags(prompt: str, slots: Iterable[Any]) -> str:
    """Rewrite Adept natural @VideoN / @AudioN tags to MiniMax <Video N> / <Audio N>.

    Only rewrites indices that have a wired Library asset on the matching R2V
    slot. Never invents media from bare strings. Does not rewrite @Character /
    #Environment / %Prop sheet tags.
    """
    text = prompt or ""
    if not text:
        return text
    video_ok: set[int] = set()
    audio_ok: set[int] = set()
    for slot in slots or []:
        role = str(_slot_field(slot, "role") or "").strip().lower()
        asset_id = str(_slot_field(slot, "assetId", "asset_id") or "").strip()
        if not asset_id:
            continue
        if role == "video":
            raw = _slot_field(slot, "videoIndex", "video_index")
            try:
                idx = int(raw) if raw is not None else 0
            except (TypeError, ValueError):
                idx = 0
            if idx > 0:
                video_ok.add(idx)
        elif role == "audio":
            raw = _slot_field(slot, "audioIndex", "audio_index")
            try:
                idx = int(raw) if raw is not None else 0
            except (TypeError, ValueError):
                idx = 0
            if idx > 0:
                audio_ok.add(idx)

    def _video_sub(match: re.Match[str]) -> str:
        idx = int(match.group(1))
        return f"<Video {idx}>" if idx in video_ok else match.group(0)

    def _audio_sub(match: re.Match[str]) -> str:
        idx = int(match.group(1))
        return f"<Audio {idx}>" if idx in audio_ok else match.group(0)

    # Natural Adept tags used in Timed Prompt. Word-boundary style; case-insensitive.
    text = re.sub(r"@Video\s*([1-9]\d*)\b", _video_sub, text, flags=re.IGNORECASE)
    text = re.sub(r"@Audio\s*([1-9]\d*)\b", _audio_sub, text, flags=re.IGNORECASE)
    return text


def apply_bound_reference_tokens(prompt: str, slots: Iterable[Any]) -> str:
    """Prepend missing H3 picture/subject binds. Never overwrite creator action.

    Maps @/%/# tags to the slot that owns that assetId. Does not invent a
    second person or swap identities. Compiles @VideoN/@AudioN natural tags to
    MiniMax <Video N>/<Audio N> when those slots carry Library assets.
    """
    text = compile_h3_av_natural_tags((prompt or "").strip(), slots)
    defs: list[str] = []
    characters: list[CharacterIdentityLayer] = []
    for slot in slots or []:
        idx_raw = _slot_field(slot, "pictureIndex", "picture_index")
        try:
            idx = int(idx_raw) if idx_raw is not None else 0
        except (TypeError, ValueError):
            idx = 0
        if idx <= 0:
            continue
        role = str(_slot_field(slot, "role") or "").strip().lower()
        label = str(
            _slot_field(slot, "label", "promptName", "tag") or ""
        ).strip()
        name = label.lstrip("@#%*~").strip() or "this character"
        asset_id = str(_slot_field(slot, "assetId", "asset_id") or "").strip()
        identity_id = str(
            _slot_field(slot, "identityId", "identity_id") or ""
        ).strip()
        subject_pat = re.compile(rf"<subject\s+{idx}\s*>", re.IGNORECASE)
        picture_pat = re.compile(rf"<Picture\s+{idx}\s*>", re.IGNORECASE)
        if role == "character":
            layer = CharacterIdentityLayer(
                tag=label if label.startswith("@") else f"@{name}" if name else "",
                label=name,
                picture_index=idx,
                asset_id=asset_id,
                identity_id=identity_id,
                aliases=[label, name] if label else [name],
            )
            characters.append(layer)
            line = subject_definition_line(layer)
            if not subject_pat.search(text) and line.lower() not in text.lower():
                defs.append(line)
        elif role == "place":
            line = f"<Picture {idx}> is {name} (environment)."
            if not picture_pat.search(text) and not subject_pat.search(text):
                defs.append(line)
        elif role == "prop":
            line = f"<Picture {idx}> is {name} (prop)."
            if not picture_pat.search(text) and not subject_pat.search(text):
                defs.append(line)
    if not defs:
        return text
    return "\n".join(defs) + "\n\n" + text


def match_audio_subject(
    *,
    identity_id: str = "",
    label: str = "",
    characters: Iterable[CharacterIdentityLayer],
) -> int | None:
    ident = str(identity_id or "").strip()
    token = str(label or "").strip().lower().lstrip("@")
    for char in characters:
        if ident and char.identity_id and ident == char.identity_id and char.picture_index:
            return int(char.picture_index)
    if not token:
        return None
    for char in characters:
        names = {item.lower().lstrip("@") for item in character_aliases(char)}
        if token in names and char.picture_index:
            return int(char.picture_index)
    return None


def sanitize_action_text(
    text: str,
    *,
    style_key: str = "",
    strip_live_action_bias: bool | None = None,
) -> str:
    """Keep behavior/context. Drop identity redescribes and illegal style bias.

    Timeline H3: preserve owner-dialect ``<subject N>`` tags from Timed Prompt.
    Never strip them on the path to Comfy MiniMaxH3ReferenceToVideo Input Text.

    Phase B: when ``strip_live_action_bias`` is False (H3 Timed Prompt / creator
    text under realistic_anime for MiniMaxH3ReferenceToVideo), do not apply
    ``_LIVE_ACTION_BIAS`` stripping — owner live-action / photoreal cinematic
    language must reach Comfy Input Text.
    """
    raw = (text or "").strip()
    if not raw:
        return ""
    if strip_live_action_bias is None:
        strip_live_action_bias = not allows_live_action_language(style_key)
    kept: list[str] = []
    for block in re.split(r"\n{2,}", raw):
        chunk = block.strip()
        if not chunk:
            continue
        if _IDENTITY_REDESCRIBE.search(chunk) and not _looks_like_action(chunk):
            continue
        lines = []
        for line in chunk.splitlines():
            stripped = line.strip()
            if not stripped:
                lines.append(line)
                continue
            if _PRIMARY_PLACEHOLDER.search(stripped):
                continue
            if _PLANNING_NOISE.search(stripped):
                remainder = _PLANNING_NOISE.sub("", stripped).strip(" :-")
                if remainder and _looks_like_action(remainder):
                    stripped = remainder
                else:
                    continue
            # Owner subject binding lines are not identity-essay noise — never mutate.
            if _SUBJECT_TAG.search(stripped):
                lines.append(stripped)
                continue
            if _IDENTITY_REDESCRIBE.search(stripped) or _SUBJECT_ASSIGNMENT.search(stripped):
                continue
            if strip_live_action_bias and _LIVE_ACTION_BIAS.search(stripped):
                cleaned_bias = _LIVE_ACTION_BIAS.sub("", stripped).strip(" .,-")
                if not cleaned_bias or not _looks_like_action(cleaned_bias):
                    continue
                stripped = cleaned_bias
            # Preserve owner ``<subject N>`` tags — never strip on H3 Timed Prompt path.
            if _SUBJECT_TAG.search(stripped):
                lines.append(stripped)
                continue
            if stripped:
                lines.append(stripped)
        joined = "\n".join(lines).strip()
        if joined:
            kept.append(joined)
    unique: list[str] = []
    seen: set[str] = set()
    for part in kept:
        token = re.sub(r"\s+", " ", part).strip()
        if token in seen:
            continue
        seen.add(token)
        unique.append(part)
    return "\n\n".join(unique).strip()


def _looks_like_action(text: str) -> bool:
    low = text.lower()
    return any(
        token in low
        for token in (
            "sits",
            "walk",
            "walks",
            "stands",
            "enters",
            "looks",
            "says",
            "shot",
            "master shot",
            "couch",
            "room",
            "greeting",
            "facing",
            "exchange",
            "sit",
            "wave",
            "points",
            "answers",
            "hold",
            "hands",
            "smile",
        )
    )


def build_contract(
    *,
    slots: Iterable[Any],
    authored: str,
    style_key: str = "",
    for_h3: bool = False,
) -> SemanticGenerationContract:
    # Phase B H3: resolve style key for metadata but do not remove creator
    # Visual style lines from text destined for MiniMax H3 Input Text.
    lifted, authored = lift_style_from_text(authored, remove_from_text=not for_h3)
    style_key = (style_key or "").strip() or lifted
    profile = resolve_style_profile(style_key)
    characters: list[CharacterIdentityLayer] = []
    environment = ""
    continuity = ""
    audio_slots: list[Any] = []
    for slot in slots or []:
        role = str(getattr(slot, "role", "") or "")
        label = str(getattr(slot, "label", "") or "").strip()
        tag = (
            label
            if label.startswith(("@", "#", "%", "*", "~"))
            else (f"@{label}" if label else "")
        )
        picture = getattr(slot, "pictureIndex", None)
        asset_id = str(getattr(slot, "assetId", "") or "")
        extra_aliases = [
            str(item).strip()
            for item in (getattr(slot, "aliases", None) or [])
            if str(item or "").strip()
        ]
        if role == "character":
            characters.append(
                CharacterIdentityLayer(
                    tag=tag or "",
                    label=label or "this character",
                    picture_index=int(picture) if picture is not None else 0,
                    asset_id=asset_id,
                    role="character",
                    identity_id=str(getattr(slot, "identityId", "") or ""),
                    aliases=extra_aliases,
                )
            )
        elif role == "place" and picture is not None:
            environment = f"<Picture {picture}> {label or 'this place'} — keep this location."
        elif role == "prior_frame" and picture is not None:
            continuity = (
                f"<Picture {picture}> {label or 'Previous take'} — "
                "continues the previous take only."
            )
        elif role == "audio" and getattr(slot, "audioIndex", None):
            audio_slots.append(slot)
    audio: list[str] = []
    for slot in audio_slots:
        subject = match_audio_subject(
            identity_id=str(getattr(slot, "identityId", "") or ""),
            label=str(getattr(slot, "label", "") or ""),
            characters=characters,
        )
        if subject:
            audio.append(
                f"<Audio {slot.audioIndex}> is the voice-timbre reference for "
                f"<subject {subject}> (S{subject})."
            )
        else:
            name = str(getattr(slot, "label", "") or "").strip() or "this speaker"
            audio.append(
                f"<Audio {slot.audioIndex}> {name} (this character's voice - only they speak with this voice)"
            )
    action = sanitize_action_text(
        authored,
        style_key=style_key,
        strip_live_action_bias=False if for_h3 else None,
    )
    return SemanticGenerationContract(
        characters=characters,
        style_key=str(getattr(profile, "key", "") or style_key or ""),
        style_display=str(getattr(profile, "displayName", "") or style_key or ""),
        style_rendering=style_rendering_phrase(style_key),
        style_camera=style_camera_phrase(style_key),
        environment=environment,
        action=action,
        camera=style_camera_phrase(style_key),
        dialogue_audio=audio,
        continuity=continuity,
        identity_authority="reference_image",
    )


def render_h3(
    contract: SemanticGenerationContract,
    *,
    inject_registry_style: bool = True,
) -> str:
    """MiniMax H3 Timeline adapter — owner Comfy dialect.

    Timeline Timed Prompt maps to the Comfy Input Text (Prompt) node.
    Character refs map to LoadImage → ref_image_0..ref_image_8 (max 9).
    Subject index N is 1-based and matches ref_image_(N-1).

    Prefer verbatim Timed Prompt when it already carries owner ``<subject N>``
    tags. Only synthesize ``<subject N> is Name.`` bindings when missing.
    Do not emit wardrobe essays or trailing orphan ``<Picture N>`` lists.

    Phase B: when authored text already has Visual style, or when
    ``inject_registry_style`` is False (H3 Timed Prompt path), never reinject
    registry Project Style boilerplate over the creator's language.
    """
    raw_action = contract.action or ""
    # Phase N H3: non-empty Timed Prompt is never rewritten by subject synthesis
    # or registry style. Diagnostics-only callers still pass inject_registry_style=False.
    if raw_action.strip() and not inject_registry_style:
        return raw_action
    has_owner_subjects = bool(re.search(r"<subject\s+\d+>", raw_action, re.IGNORECASE))
    sections: list[str] = []
    ordered_chars = sorted(
        (c for c in contract.characters if c.picture_index),
        key=lambda c: int(c.picture_index or 0),
    )

    def _maybe_style(action_text: str) -> None:
        if not inject_registry_style:
            return
        if re.search(r"(?i)\bvisual style\s*:", action_text or ""):
            return
        style_bits = []
        if contract.style_display:
            style_bits.append(str(contract.style_display).strip())
        if contract.style_rendering:
            style_bits.append(str(contract.style_rendering).strip())
        if style_bits:
            style_line = ". ".join(b.rstrip(".") for b in style_bits if b)
            if style_line:
                sections.append("Visual style: " + style_line + ".")

    if has_owner_subjects:
        # Verbatim Timed Prompt path: keep owner tags / @alias bindings as Input Text.
        # Do not mutate creator ``<subject N>`` lines.
        action = raw_action
        sections.append(action)
        _maybe_style(action)
        if contract.environment:
            sections.append(contract.environment)
    else:
        action = bind_subjects_in_text(raw_action, contract.characters)
        for char in ordered_chars:
            sections.append(subject_definition_line(char))
        _maybe_style(action)
        if contract.environment:
            sections.append(contract.environment)
        if action:
            sections.append(action)
    if contract.camera and not has_owner_subjects:
        sections.append(contract.camera)
    if contract.dialogue_audio:
        sections.append("\n".join(contract.dialogue_audio))
    if contract.continuity:
        sections.append(contract.continuity)
    return "\n\n".join(part for part in sections if part).strip()

def _strip_minimax_tokens(text: str) -> str:
    cleaned = _OFFICIAL_MEDIA_TOKEN.sub("", text or "")
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip(" \t-—")


def render_ltx(contract: SemanticGenerationContract, *, start_line: str = "", extras_line: str = "") -> str:
    """LTX 2.5 adapter — one start cond; extras named; same semantic layers."""
    sections: list[str] = []
    identity_lines = ["CHARACTER IDENTITY"]
    if start_line:
        identity_lines.append(start_line)
    for char in contract.characters:
        identity_lines.append(
            f"{char.label or char.tag or 'Reference character'} — {IDENTITY_PRESERVE}"
        )
    if extras_line:
        identity_lines.append(extras_line)
    identity_lines.append(
        "These are the characters. Preserve them. The reference pictures are identity authority."
    )
    sections.append("\n".join(identity_lines))
    if contract.style_display or contract.style_rendering:
        style_lines = ["VISUAL STYLE"]
        if contract.style_display:
            style_lines.append(contract.style_display)
        if contract.style_rendering:
            style_lines.append(contract.style_rendering)
        style_lines.append(STYLE_PRESERVE)
        sections.append("\n".join(style_lines))
    if contract.environment:
        env = _strip_minimax_tokens(contract.environment)
        if env:
            sections.append("ENVIRONMENT\n" + env)
    if contract.action:
        sections.append("ACTION\n" + contract.action)
    if contract.camera:
        sections.append("CAMERA\n" + contract.camera)
    if contract.continuity:
        cont = _strip_minimax_tokens(contract.continuity)
        if cont:
            sections.append("CONTINUITY\n" + cont)
    return "\n\n".join(part for part in sections if part).strip()
