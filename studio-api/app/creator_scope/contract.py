"""Shared isGlobal contract for Character, Prop, and Environment entities."""

from __future__ import annotations

import re
from typing import Any, Iterable, Literal

ENTITY_CHARACTER = "character"
ENTITY_PROP = "prop"
ENTITY_ENVIRONMENT = "environment"
CreatorEntityType = Literal["character", "prop", "environment"]

CREATOR_SCOPE_HELP = (
    "Global assets are available in every project. "
    "If Global is off, this asset is available only in the project where it was created."
)

_TAG_RE = re.compile(r"[^A-Za-z0-9_]+")


class CreatorScopeError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, extra: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.extra = extra or {}

    def as_detail(self) -> dict[str, Any]:
        detail = {"code": self.code, "message": self.message}
        detail.update(self.extra)
        return detail


def normalize_is_global(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off", ""}:
        return False
    return bool(default)


def asset_is_global(payload: Any) -> bool:
    if payload is None:
        return False
    if isinstance(payload, dict):
        if "isGlobal" in payload:
            return normalize_is_global(payload.get("isGlobal"))
        if "is_global" in payload:
            return normalize_is_global(payload.get("is_global"))
        return False
    if hasattr(payload, "isGlobal"):
        return normalize_is_global(getattr(payload, "isGlobal"))
    if hasattr(payload, "is_global"):
        return normalize_is_global(getattr(payload, "is_global"))
    return False


def owning_project_id(payload: Any) -> str:
    if payload is None:
        return ""
    if isinstance(payload, dict):
        return str(
            payload.get("owningProjectId")
            or payload.get("owning_project_id")
            or payload.get("project_id")
            or payload.get("projectId")
            or ""
        ).strip()
    return str(
        getattr(payload, "owning_project_id", None)
        or getattr(payload, "project_id", None)
        or getattr(payload, "projectId", None)
        or ""
    ).strip()


def is_visible_to_project(payload: Any, project_id: str) -> bool:
    pid = str(project_id or "").strip()
    owner = owning_project_id(payload)
    if not pid:
        return False
    if owner == pid:
        return True
    return asset_is_global(payload)


def canonical_tag(raw: str | None, *, prefix: str = "") -> str:
    token = str(raw or "").strip()
    if token[:1] in {"@", "%", "#", "~", "*"}:
        token = token[1:]
    token = _TAG_RE.sub("", token.replace(" ", ""))
    if prefix and token.startswith(prefix):
        token = token[len(prefix) :]
    return token


PROFILE_NAME_ALREADY_EXISTS = "PROFILE_NAME_ALREADY_EXISTS"
OWNER_REQUIRED = "OWNER_REQUIRED"
PLACEHOLDER_CHARACTER_NAMES = frozenset({"new character", "untitled character"})
PLACEHOLDER_CHARACTER_SLUGS = frozenset({"newcharacter", "new-character", "untitledcharacter", "untitled-character"})
_MACHINE_NOTE_RE = re.compile(
    r"\b(?:prsAssetId|adeptWorkingProp|universalAdeptProp)=\S+",
    re.IGNORECASE,
)
_FIXTURE_NAME_RE = re.compile(
    r"wiringsmoke|characterglobaltest|environmentglobaltest|propglobaltestlive",
    re.IGNORECASE,
)


def is_placeholder_character_name(name: str | None) -> bool:
    return normalize_profile_name(name) in PLACEHOLDER_CHARACTER_NAMES


def is_placeholder_character_slug(slug: str | None) -> bool:
    token = canonical_tag(slug).lower()
    raw = str(slug or "").strip().lower()
    return token in PLACEHOLDER_CHARACTER_SLUGS or raw in PLACEHOLDER_CHARACTER_SLUGS


def strip_machine_notes(text: str | None) -> str:
    """Human description must never carry PRS / working-prop markers."""
    cleaned = _MACHINE_NOTE_RE.sub("", str(text or ""))
    return re.sub(r"\s+", " ", cleaned).strip()


def is_ephemeral_creator_fixture(name: str | None) -> bool:
    """Last-resort list filter for leftover WiringSmoke / GlobalTest rows."""
    return bool(_FIXTURE_NAME_RE.search(str(name or "")))


def owner_required_message(kind: str) -> str:
    label = TYPE_LABELS.get(kind, kind or "asset")
    return f"Global {label.lower()}s can only be edited from the project that created them."

TYPE_LABELS = {
    ENTITY_CHARACTER: "Character",
    ENTITY_PROP: "Prop",
    ENTITY_ENVIRONMENT: "Environment",
}


def normalize_profile_name(name: str | None) -> str:
    """Comparison key only. Display names keep the creator's capitalization."""
    return " ".join(str(name or "").split()).casefold()


def display_profile_name(name: str | None) -> str:
    return str(name or "").strip()


def profile_name_conflict_message(
    *,
    entity_type: str,
    existing_name: str,
    is_global: bool,
) -> str:
    label = TYPE_LABELS.get(entity_type, "profile")
    shown = display_profile_name(existing_name) or f"this {label}"
    if is_global:
        return (
            f"{shown} already exists as a Global {label}. "
            "Open the existing profile or choose another name."
        )
    return (
        f"{shown} already exists in this project. "
        "Open the existing profile or choose another name."
    )


ENVIRONMENT_NAME_ALREADY_EXISTS_MESSAGE = (
    "An environment with this name already exists in this project. "
    "Open the existing one or choose a different name."
)


def group_scope_items(
    items: Iterable[Any],
    project_id: str,
    *,
    owner_of=owning_project_id,
    global_of=asset_is_global,
) -> dict[str, list[Any]]:
    """PROJECT = owned by current project (even if also global). GLOBAL = other owners."""
    pid = str(project_id or "").strip()
    project: list[Any] = []
    global_items: list[Any] = []
    seen: set[str] = set()
    for item in items:
        ident = str(
            getattr(item, "id", None)
            or getattr(item, "sheetId", None)
            or (item.get("id") if isinstance(item, dict) else "")
            or (item.get("sheetId") if isinstance(item, dict) else "")
            or ""
        )
        if ident and ident in seen:
            continue
        if ident:
            seen.add(ident)
        owner = owner_of(item)
        if owner == pid:
            project.append(item)
        elif global_of(item):
            global_items.append(item)
    return {"project": project, "global": global_items}
