"""Resolve implied CRS / ERS / PRS from creator language.

Typed @ / # / % / * tags remain the authority when present.
Natural names and phrases ('both characters', 'this corridor') may point at
those same project bindings. Never invent a missing sheet.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from sqlalchemy.orm import Session


_BOTH_CHARACTERS_RE = re.compile(
    r"\b(?:both\s+characters|the\s+(?:two\s+)?characters|both\s+people|both\s+of\s+them|"
    r"both\s+(?:girls|women|leads)|the\s+(?:two\s+)?(?:girls|women|leads))\b",
    re.I,
)
_CORRIDOR_RE = re.compile(
    r"\b(?:this|the|current)\s+(?:corridor|hallway|hall|environment|place|location|ers)\b"
    r"|\b(?:corridor|hallway)\b",
    re.I,
)
_PROP_RE = re.compile(r"\b(?:this|the|current)\s+prop\b|\bthe\s+prs\b", re.I)
_THESE_REFS_RE = re.compile(
    r"\b(?:these|the\s+(?:current\s+)?(?:scene\s+)?)references\b|\bcurrent\s+refs\b",
    re.I,
)
_KEEP_EXCEPT_ENV_RE = re.compile(
    r"\bkeep\s+everything\s+except\s+(?:the\s+)?(?:environment|corridor|place|ers)\b",
    re.I,
)
_CHANGE_ONLY_RE = re.compile(r"\bchange\s+only\s+([A-Za-z][A-Za-z0-9_-]*)\b", re.I)
_BIND_ONLY_RE = re.compile(
    r"^\s*(?:please\s+)?(?:use|bind|keep|with)\b.+\b(?:character|corridor|environment|place|prop|reference)",
    re.I,
)
_GENERATE_RE = re.compile(
    r"\b(?:create|generate|render|run|enqueue|make|add)\b.+\b"
    r"(?:shot|clip|video|take|image|crs|sheet|footsteps?|footfalls?|sfx|sound|music|ambience|foley|audio)\b"
    r"|\bgenerate\s+(?:this|the|that|next)\b",
    re.I,
)


@dataclass(frozen=True)
class AvailableRef:
    kind: str  # crs | ers | prs | video
    token: str
    name: str
    alias: str = ""
    asset_id: str = ""
    character_id: str = ""
    labels: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ImpliedResolution:
    requested: list[str] = field(default_factory=list)
    resolved: list[AvailableRef] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    ambiguous: list[str] = field(default_factory=list)
    inventory: list[AvailableRef] = field(default_factory=list)
    bind_only: bool = False

    @property
    def tokens(self) -> list[str]:
        return [item.token for item in self.resolved]

    @property
    def has_question(self) -> bool:
        return bool(self.missing or self.ambiguous)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _labels_for(*parts: str) -> tuple[str, ...]:
    out: list[str] = []
    for part in parts:
        token = _norm(part)
        if token and token not in out:
            out.append(token)
    return tuple(out)


def load_reference_inventory(
    db: Session,
    project_id: str,
    scene_id: str | None = None,
) -> list[AvailableRef]:
    """Project characters plus real scene-reference bindings. No invented sheets."""

    inventory: list[AvailableRef] = []
    seen: set[tuple[str, str]] = set()

    def _add(item: AvailableRef) -> None:
        key = (item.kind, _norm(item.token) or _norm(item.alias) or item.asset_id)
        if key in seen or not item.token:
            return
        seen.add(key)
        inventory.append(item)

    profiles: list[Any] = []
    try:
        from ...character_identity.service import list_profiles

        profiles = list(list_profiles(db, project_id) or [])
    except Exception:
        profiles = []
    by_id = {str(getattr(p, "id", "") or ""): p for p in profiles}

    for profile in profiles:
        name = str(getattr(profile, "name", "") or "").strip()
        if not name:
            continue
        _add(
            AvailableRef(
                kind="crs",
                token=f"@{re.sub(r'[^A-Za-z0-9]+', '', name)}",
                name=name,
                alias=re.sub(r"[^A-Za-z0-9]+", "", name),
                character_id=str(getattr(profile, "id", "") or ""),
                labels=_labels_for(name, getattr(profile, "slug", "") or ""),
            )
        )

    rows: list[Any] = []
    try:
        from ...scene_references.models import SceneReferenceBinding
        from ...scene_references.sheet_tags import display_sheet_token, prefix_for_reference

        query = db.query(SceneReferenceBinding).filter(
            SceneReferenceBinding.project_id == project_id,
            SceneReferenceBinding.deleted_at.is_(None),
            SceneReferenceBinding.enabled.is_(True),
        )
        rows = list(query.all())
    except Exception:
        rows = []
        display_sheet_token = None  # type: ignore[assignment]
        prefix_for_reference = None  # type: ignore[assignment]

    for row in rows:
        ref_type = str(getattr(row, "reference_type", "") or "")
        media = str(getattr(row, "media_kind", "") or "")
        alias = str(getattr(row, "alias", "") or "")
        identity_id = str(getattr(row, "identity_id", "") or "")
        asset_name = ""
        try:
            asset = getattr(row, "asset", None)
            asset_name = str(getattr(asset, "tag", "") or getattr(asset, "filename", "") or "")
        except Exception:
            asset_name = ""
        prefix = ""
        if prefix_for_reference is not None:
            prefix = prefix_for_reference(ref_type, media)
        kind = {"@": "crs", "#": "ers", "%": "prs", "*": "video"}.get(prefix, "ers")
        profile = by_id.get(identity_id)
        name = str(getattr(profile, "name", "") or alias or asset_name or "Reference").strip()
        if kind == "crs" and profile is not None:
            token = f"@{re.sub(r'[^A-Za-z0-9]+', '', name)}"
        elif display_sheet_token is not None and alias:
            token = display_sheet_token(alias, ref_type, media)
        else:
            token = f"{prefix or '#'}{alias or name}"
        _add(
            AvailableRef(
                kind=kind,
                token=token,
                name=name,
                alias=alias,
                asset_id=str(getattr(row, "asset_id", "") or ""),
                character_id=identity_id,
                labels=_labels_for(name, alias, asset_name, ref_type),
            )
        )

    del scene_id  # inventory is project-scoped; scene only scopes later filters
    return inventory


def _of_kind(inventory: Iterable[AvailableRef], kind: str) -> list[AvailableRef]:
    return [item for item in inventory if item.kind == kind]


def _match_named(inventory: Iterable[AvailableRef], raw: str) -> list[AvailableRef]:
    needle = _norm(raw)
    if not needle or len(needle) < 3:
        return []
    exact = [
        item
        for item in inventory
        if needle in item.labels or needle == _norm(item.name) or needle == _norm(item.alias)
    ]
    if exact:
        return exact
    return [item for item in inventory if any(needle in label or label in needle for label in item.labels)]


def resolve_against_inventory(text: str, inventory: list[AvailableRef]) -> ImpliedResolution:
    message = text or ""
    resolution = ImpliedResolution(inventory=list(inventory))
    if _BOTH_CHARACTERS_RE.search(message):
        resolution.requested.append("both_characters")
        chars = _of_kind(inventory, "crs")
        if not chars:
            resolution.missing.append("No character reference sheets are bound on this project.")
        elif len(chars) > 2:
            names = ", ".join(item.name for item in chars)
            resolution.ambiguous.append(
                f"This project has more than two characters ({names}). Which two should I use?"
            )
        else:
            resolution.resolved.extend(chars)
            if len(chars) == 1:
                resolution.missing.append(
                    f"Only one character is bound ({chars[0].name}). There is no second character to pair."
                )

    if _CORRIDOR_RE.search(message) and "except" not in message.lower():
        resolution.requested.append("this_corridor")
        places = _of_kind(inventory, "ers")
        corridorish = [
            item
            for item in places
            if any(token in item.labels for token in ("corridor", "venturecorridor", "venturecorridorscene"))
            or "corridor" in _norm(item.name)
            or "corridor" in _norm(item.alias)
        ]
        chosen = corridorish or (places if len(places) == 1 else [])
        if not chosen:
            if not places:
                resolution.missing.append("No environment reference is bound on this project.")
            else:
                names = ", ".join(item.token for item in places)
                resolution.ambiguous.append(
                    f"More than one environment is bound ({names}). Which place should I use?"
                )
        elif len(chosen) > 1:
            names = ", ".join(item.token for item in chosen)
            resolution.ambiguous.append(f"Several corridor bindings match ({names}). Which one?")
        else:
            resolution.resolved.append(chosen[0])

    if _PROP_RE.search(message):
        resolution.requested.append("this_prop")
        props = _of_kind(inventory, "prs")
        if not props:
            resolution.missing.append("No prop reference sheet is bound on this project.")
        elif len(props) > 1:
            names = ", ".join(item.token for item in props)
            resolution.ambiguous.append(f"Several props are bound ({names}). Which prop?")
        else:
            resolution.resolved.append(props[0])

    if _THESE_REFS_RE.search(message):
        resolution.requested.append("these_references")
        current = [item for item in inventory if item.kind in {"crs", "ers", "prs"}]
        if not current:
            resolution.missing.append("This project has no CRS, ERS, or PRS bindings to use.")
        else:
            resolution.resolved.extend(current)

    if _KEEP_EXCEPT_ENV_RE.search(message):
        resolution.requested.append("keep_except_environment")
        resolution.resolved.extend(_of_kind(inventory, "crs"))
        resolution.resolved.extend(_of_kind(inventory, "prs"))

    only = _CHANGE_ONLY_RE.search(message)
    if only:
        resolution.requested.append("change_only")
        hits = _match_named(inventory, only.group(1))
        if not hits:
            resolution.missing.append(
                f"I do not have a project binding named {only.group(1)}. I will not invent one."
            )
        else:
            resolution.resolved.extend(hits)

    named_hits: list[AvailableRef] = []
    for item in inventory:
        if item.kind != "crs":
            continue
        if re.search(rf"\b{re.escape(item.name)}\b", message, re.I):
            named_hits.append(item)
    for item in named_hits:
        if item not in resolution.resolved:
            resolution.resolved.append(item)

    # Dedup resolved while preserving order.
    seen: set[str] = set()
    unique: list[AvailableRef] = []
    for item in resolution.resolved:
        key = f"{item.kind}:{item.token}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    resolution.resolved = unique
    resolution.bind_only = bool(
        resolution.requested
        and not _GENERATE_RE.search(message)
        and (
            _BIND_ONLY_RE.search(message)
            or any(
                item in resolution.requested
                for item in ("both_characters", "this_corridor", "these_references", "this_prop")
            )
        )
    )
    return resolution


def resolve_implied_references(
    db: Session,
    project_id: str,
    text: str,
    *,
    scene_id: str | None = None,
) -> ImpliedResolution:
    inventory = load_reference_inventory(db, project_id, scene_id)
    return resolve_against_inventory(text, inventory)


def spoken_implied_resolution(resolution: ImpliedResolution) -> str:
    if resolution.ambiguous:
        return " ".join(resolution.ambiguous)
    if resolution.missing and not resolution.resolved:
        return " ".join(resolution.missing) + " I will not invent a CRS, ERS, or PRS."
    if not resolution.requested and not resolution.resolved:
        return ""
    bits: list[str] = []
    if resolution.resolved:
        bits.append(
            "I'll use the real bindings on this project: "
            + ", ".join(item.token + f" ({item.name})" for item in resolution.resolved)
            + "."
        )
    if resolution.missing:
        bits.append(" ".join(resolution.missing))
    if "keep_except_environment" in resolution.requested:
        bits.append("The environment binding is left out.")
    if "change_only" in resolution.requested and resolution.resolved:
        who = resolution.resolved[0].name
        others = [
            item.name
            for item in resolution.inventory
            if item.kind in {"crs", "ers"} and item.token not in resolution.tokens
        ]
        bits.append(f"I'll change only {who}.")
        if others:
            bits.append(f"{', '.join(others)} stay as they are.")
        bits.append(f"What should change about {who}?")
    if resolution.bind_only:
        bits.append("I will not invent a prop. I have not started a generation.")
    return " ".join(bits).strip()
