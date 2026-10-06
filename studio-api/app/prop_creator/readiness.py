"""Prop identity readiness — Primary required, additional views optional.

Owner law (2026-09-15):
- PRIMARY is the required identity anchor (generated, uploaded, or library-adopt).
- Front/Back/Left/Right/Top/Bottom/Hero are optional enrichment.
- Approval depends only on a valid candidate asset existing for that slot.
- Missing optional views must not block save, Approve Primary, identity, Library,
  downstream, Co-Director "ready", or a partial Prop Reference Sheet.
"""

from __future__ import annotations

from typing import Any

from ..spatial_map.ers_contracts import PropCandidate, PropEntity

OPTIONAL_VIEWS = ("front", "back", "left", "right", "top", "bottom", "hero")
CANONICAL_PRS_ORDER = ("primary",) + OPTIONAL_VIEWS
FAILED_CANDIDATE_STATUSES = frozenset({"failed", "error", "cancelled", "missing"})


def _aid(value: Any) -> str:
    return str(value or "").strip()


def candidate_has_valid_asset(candidate: PropCandidate | None) -> bool:
    if candidate is None:
        return False
    if not _aid(candidate.asset_id):
        return False
    status = str(getattr(candidate, "status", "") or "").strip().lower()
    return status not in FAILED_CANDIDATE_STATUSES


def valid_primary_candidate(prop: PropEntity | None) -> PropCandidate | None:
    if prop is None:
        return None
    for candidate in reversed(list(prop.candidates or [])):
        if candidate_has_valid_asset(candidate):
            return candidate
    return None


def valid_primary_candidate_asset_id(prop: PropEntity | None) -> str:
    candidate = valid_primary_candidate(prop)
    return _aid(candidate.asset_id) if candidate is not None else ""


def approved_primary_asset_id(prop: PropEntity | None) -> str:
    if prop is None:
        return ""
    advanced = str(getattr(prop, "mode", "standard") or "standard").strip().lower() == "advanced"
    if advanced:
        return _aid(prop.primary_approved_asset_id) or _aid(prop.approved_asset_id)
    return _aid(prop.approved_asset_id)


def can_approve_primary(prop: PropEntity | None) -> bool:
    """True when a valid candidate exists that is not yet the approved identity."""
    candidate_id = valid_primary_candidate_asset_id(prop)
    if not candidate_id:
        return False
    return candidate_id != approved_primary_asset_id(prop)


def visible_primary_preview_asset_id(prop: PropEntity | None) -> str:
    """Preview the pending replacement when it differs from the locked Primary."""
    pending = valid_primary_candidate_asset_id(prop)
    approved = approved_primary_asset_id(prop)
    if pending and pending != approved:
        return pending
    return pending or approved


def identity_ready(prop: PropEntity | None) -> bool:
    """Prop is ready for Library / Timeline / Image Generator / Co-Director."""
    return bool(approved_primary_asset_id(prop))


def approved_optional_views(prop: PropEntity | None) -> list[str]:
    if prop is None:
        return []
    angles = prop.angles or {}
    ready: list[str] = []
    for key in OPTIONAL_VIEWS:
        slot = angles.get(key)
        if slot is None:
            continue
        if bool(getattr(slot, "approved", False)) and _aid(getattr(slot, "asset_id", None)):
            ready.append(key)
    return ready


def missing_optional_views(prop: PropEntity | None) -> list[str]:
    have = set(approved_optional_views(prop))
    return [key for key in OPTIONAL_VIEWS if key not in have]


def view_has_approvable_candidate(prop: PropEntity | None, view: str) -> bool:
    key = str(view or "").strip().lower()
    if key == "primary":
        return can_approve_primary(prop)
    if prop is None:
        return False
    slot = (prop.angles or {}).get(key)
    if slot is None:
        return False
    if bool(getattr(slot, "approved", False)):
        return False
    return bool(_aid(getattr(slot, "asset_id", None)))


def readiness_payload(prop: PropEntity | None) -> dict[str, Any]:
    ready = identity_ready(prop)
    missing = missing_optional_views(prop) if prop is not None else list(OPTIONAL_VIEWS)
    return {
        "propReady": ready,
        "identityReady": ready,
        "canApprovePrimary": can_approve_primary(prop),
        "validPrimaryCandidateAssetId": valid_primary_candidate_asset_id(prop) or None,
        "approvedPrimaryAssetId": approved_primary_asset_id(prop) or None,
        "previewPrimaryAssetId": visible_primary_preview_asset_id(prop) or None,
        "optionalViews": list(OPTIONAL_VIEWS),
        "approvedOptionalViews": approved_optional_views(prop),
        "missingOptionalViews": missing,
        "missingViewsBlockReadiness": False,
        "sheetReady": ready,
        "readyReason": (
            "Primary approved. Additional views are optional."
            if ready
            else "Approve Primary to make this Prop ready. Additional views are optional."
        ),
    }
