"""Universal @Character and #ERS reference parser.

Resolves structured production references from text input.

Product Law:
  @Character = UNIVERSAL CHARACTER CANON REFERENCE
  #ERS = UNIVERSAL ENVIRONMENT REFERENCE SHEET REFERENCE
  REFERENCE TAGS ARE NOT PROMPT DECORATION. THEY ARE STRUCTURED PRODUCTION POINTERS.

Usage:
  result = parse_production_references("Create a shot of @Korri in #SchnickCoffee")
  # result.plain_text = "Create a shot of  in "
  # result.character_refs = [ParsedCharacterRef(tag="@Korri", name="Korri", ...)]
  # result.ers_refs = [ParsedErsRef(tag="#SchnickCoffee", ...)]
"""

from __future__ import annotations

import re
from typing import Any, Optional

# ── Parsed Reference Types ────────────────────────────────────────────────


class ParsedCharacterRef:
    """A resolved @Character reference."""
    def __init__(
        self,
        tag: str,
        name: str,
        character_id: str | None = None,
        crs_revision: int = 0,
        resolved: bool = False,
        error: str = "",
    ):
        self.tag = tag
        self.name = name
        self.character_id = character_id
        self.crs_revision = crs_revision
        self.resolved = resolved
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag": self.tag,
            "name": self.name,
            "characterId": self.character_id,
            "crsRevision": self.crs_revision,
            "resolved": self.resolved,
            "error": self.error,
        }


class ParsedErsRef:
    """A resolved #ERS reference."""
    def __init__(
        self,
        tag: str,
        label: str,
        ers_id: str | None = None,
        ers_revision: int = 0,
        resolved: bool = False,
        error: str = "",
    ):
        self.tag = tag
        self.label = label
        self.ers_id = ers_id
        self.ers_revision = ers_revision
        self.resolved = resolved
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag": self.tag,
            "label": self.label,
            "ersId": self.ers_id,
            "ersRevision": self.ers_revision,
            "resolved": self.resolved,
            "error": self.error,
        }


class ProductionReferenceResult:
    """Result of parsing production references from text."""
    def __init__(
        self,
        plain_text: str,
        character_refs: list[ParsedCharacterRef],
        ers_refs: list[ParsedErsRef],
    ):
        self.plain_text = plain_text
        self.character_refs = character_refs
        self.ers_refs = ers_refs

    def to_dict(self) -> dict[str, Any]:
        return {
            "plainText": self.plain_text,
            "characterRefs": [r.to_dict() for r in self.character_refs],
            "ersRefs": [r.to_dict() for r in self.ers_refs],
        }

    @property
    def has_any(self) -> bool:
        return bool(self.character_refs or self.ers_refs)


# ── Parser ────────────────────────────────────────────────────────────────

# Pattern for @CharacterName - alphanumeric, underscores, hyphens
# Must NOT match email addresses (@ preceded by word char)
_CHARACTER_PATTERN = re.compile(r"(?<![\w@])@([A-Za-z][A-Za-z0-9_-]*)")

# Pattern for #ERSTag - alphanumeric, underscores, hyphens
_ERS_PATTERN = re.compile(r"(?<![\w#])#([A-Za-z][A-Za-z0-9_-]*)")

# Escape pattern: backslash + @ or backslash + # to produce literal text
_ESCAPE_PATTERN = re.compile(r"\[@#]")


def parse_production_references(
    text: str,
    *,
    project_id: str = "",
    resolve_characters: bool = False,
    resolve_ers: bool = False,
    db: Any = None,
) -> ProductionReferenceResult:
    """Parse production references from text.
    
    Args:
        text: The input text to parse.
        project_id: Required for resolution.
        resolve_characters: If True, resolve @Character refs against the DB.
        resolve_ers: If True, resolve #ERS refs against the DB.
        db: SQLAlchemy session (required for resolution).
    
    Returns:
        ProductionReferenceResult with plain text and resolved references.
    """
    if not text:
        return ProductionReferenceResult("", [], [])
    
    # Handle escapes first: replace backslash-tag with tag
    unescaped = _ESCAPE_PATTERN.sub(lambda m: m.group(0)[1:], text)
    
    # Find all @Character references
    char_refs: list[ParsedCharacterRef] = []
    char_matches = list(_CHARACTER_PATTERN.finditer(unescaped))
    
    for match in char_matches:
        name = match.group(1)
        tag = f"@{name}"
        ref = ParsedCharacterRef(tag=tag, name=name)
        
        if resolve_characters and project_id and db is not None:
            try:
                from .service import resolve_character_by_name
                profile = resolve_character_by_name(db, project_id, name)
                if profile:
                    ref.character_id = str(profile.id)
                    ref.resolved = True
                    # Estimate CRS revision from active version
                    if profile.active_version_id:
                        try:
                            import uuid
                            ref.crs_revision = int(uuid.UUID(profile.active_version_id).version) if profile.active_version_id else 0
                        except Exception:
                            ref.crs_revision = 1
                else:
                    ref.error = f"Character '{name}' not found in project"
            except Exception as e:
                ref.error = str(e)
        
        char_refs.append(ref)
    
    # Find all #ERS references
    ers_refs: list[ParsedErsRef] = []
    ers_matches = list(_ERS_PATTERN.finditer(unescaped))
    
    for match in ers_matches:
        label = match.group(1)
        tag = f"#{label}"
        ref = ParsedErsRef(tag=tag, label=label)
        
        if resolve_ers and project_id and db is not None:
            try:
                from ..environment_reference_sheet import service as ers_service
                sheets = ers_service.list_sheets(db, project_id)
                for sheet in (sheets or []):
                    sheet_tag = getattr(sheet, "tag", "") or ""
                    sheet_title = getattr(sheet, "title", "") or ""
                    if label.lower() in (sheet_tag.lower(), sheet_title.lower()):
                        ref.ers_id = str(getattr(sheet, "id", "") or "")
                        ref.ers_revision = int(getattr(sheet, "version", 0) or 0)
                        ref.resolved = True
                        break
                if not ref.resolved:
                    ref.error = f"ERS '{label}' not found in project"
            except Exception as e:
                ref.error = str(e)
        
        ers_refs.append(ref)
    
    # Build plain text by removing resolved references
    plain_text = unescaped
    for ref in char_refs:
        if ref.resolved:
            plain_text = plain_text.replace(ref.tag, "", 1)
    for ref in ers_refs:
        if ref.resolved:
            plain_text = plain_text.replace(ref.tag, "", 1)
    plain_text = plain_text.strip()
    plain_text = re.sub(r" +", " ", plain_text)
    
    return ProductionReferenceResult(plain_text, char_refs, ers_refs)


def extract_character_tags(text: str) -> list[str]:
    """Extract @Character names from text without resolving them."""
    if not text:
        return []
    unescaped = _ESCAPE_PATTERN.sub(lambda m: m.group(0)[1:], text)
    return [m.group(1) for m in _CHARACTER_PATTERN.finditer(unescaped)]


def extract_ers_tags(text: str) -> list[str]:
    """Extract #ERS tags from text without resolving them."""
    if not text:
        return []
    unescaped = _ESCAPE_PATTERN.sub(lambda m: m.group(0)[1:], text)
    return [m.group(1) for m in _ERS_PATTERN.finditer(unescaped)]


def escape_reference(text: str) -> str:
    """Escape @ and # in text so they are not treated as references."""
    return text.replace("@", "\@").replace("#", "\#")
