"""Additive localization envelopes — never overwrite canonical text."""

from __future__ import annotations

from typing import Any, Optional


def wrap_localized_field(
    *,
    field_id: str,
    canonical_language: str,
    canonical_text: str,
    localized_text: Optional[dict[str, str]] = None,
    translation_status: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    return {
        "fieldId": field_id,
        "canonicalLanguage": canonical_language,
        "canonicalText": canonical_text,
        "localizedText": dict(localized_text or {}),
        "translationStatus": dict(translation_status or {}),
    }


def merge_localization(
    existing: dict[str, Any],
    *,
    locale: str,
    text: str,
    status: str = "draft",
) -> dict[str, Any]:
    out = dict(existing)
    # Never overwrite canonical
    canon = out.get("canonicalText", "")
    localized = dict(out.get("localizedText") or {})
    statuses = dict(out.get("translationStatus") or {})
    if statuses.get(locale) == "locked":
        return out
    localized[locale] = text
    statuses[locale] = status
    out["localizedText"] = localized
    out["translationStatus"] = statuses
    out["canonicalText"] = canon
    return out


def display_text(field: dict[str, Any], locale: str) -> str:
    localized = field.get("localizedText") or {}
    if locale in localized and localized[locale]:
        return localized[locale]
    return field.get("canonicalText") or ""
