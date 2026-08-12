"""Compile immutable multi-binding Continuity Packets with frozen snapshots."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from . import SCHEMA_VERSIONS
from .constants import (
    COMPILER_VERSION,
    RESOLVER_VERSION,
    REFERENCE_ROLES,
)
from .validation import require_visibility, sanitize_user_text


def _role_priority_for_shot(shot_type: str | None, required_roles: list[str]) -> list[str]:
    if required_roles:
        return list(required_roles)
    st = (shot_type or "").lower()
    if "rear" in st or "back" in st:
        return ["canonical_back", "canonical_three_quarter", "full_body", "body_proportion", "wardrobe_back", "hair"]
    if "profile" in st:
        return ["canonical_profile", "face_closeup", "hair", "full_body"]
    if "close" in st or "face" in st:
        return ["face_closeup", "canonical_front", "eyes", "hair", "skin"]
    if "environment" in st or "wide" in st:
        return ["environment_wide", "environment_layout", "canonical_front", "full_body"]
    return ["canonical_front", "canonical_three_quarter", "full_body", "face_closeup", "wardrobe_front"]


def select_references(
    *,
    candidates: list[dict[str, Any]],
    preferred_roles: list[str],
    max_references: int,
) -> dict[str, Any]:
    """Deterministic role-aware selection. Only approved, non-revoked, non-rejected."""
    eligible = [
        c
        for c in candidates
        if c.get("approval_status") == "approved"
        and not c.get("archived")
        and c.get("approval_status") not in ("rejected", "revoked", "deprecated")
    ]
    # deprecated excluded from new packets; rejected/revoked never selected
    eligible = [c for c in eligible if c.get("approval_status") == "approved"]

    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    covered: set[str] = set()

    for role in preferred_roles:
        if len(selected) >= max_references:
            break
        match = next(
            (
                c
                for c in eligible
                if role in (c.get("roles") or []) and c["id"] not in {s["id"] for s in selected}
            ),
            None,
        )
        if match:
            selected.append({**match, "selection_reason": f"preferred_role:{role}"})
            covered.add(role)
        else:
            rejected.append({"role": role, "reason": "no_approved_reference"})

    # Fill remaining slots with unused eligible refs (stable by id)
    for c in sorted(eligible, key=lambda x: x["id"]):
        if len(selected) >= max_references:
            break
        if c["id"] in {s["id"] for s in selected}:
            continue
        selected.append({**c, "selection_reason": "fill_remaining"})

    missing = [r for r in preferred_roles if r not in covered]
    return {
        "candidates": [{"id": c["id"], "roles": c.get("roles"), "status": c.get("approval_status")} for c in candidates],
        "selected": selected,
        "rejected": rejected,
        "missing_preferred_roles": missing,
        "resolver_version": RESOLVER_VERSION,
        "max_references": max_references,
    }


def compile_directives(
    *,
    identity_name: str,
    version_number: int,
    traits: dict[str, Any],
    constraints: list[dict[str, Any]],
    variant_names: list[str],
) -> tuple[list[str], list[str]]:
    locked = []
    for key, val in (traits or {}).items():
        if isinstance(val, dict) and val.get("mode") == "locked":
            locked.append(f"{key}={val.get('value', val)}")
        elif not isinstance(val, dict):
            locked.append(f"{key}={val}")
    for c in constraints or []:
        if c.get("policy") == "lock" and c.get("enabled", True):
            locked.append(f"{c.get('dimension')}:{c.get('expected_value')}")

    pos = [
        sanitize_user_text(
            f"Maintain the approved visual identity for {identity_name} "
            f"defined by Identity Version {version_number}."
            + (f" Allowed variants: {', '.join(variant_names)}." if variant_names else "")
        )
    ]
    if locked:
        pos.append(sanitize_user_text("Preserve locked traits: " + "; ".join(locked[:12]) + "."))
    neg = [
        "Do not alter locked facial structure, eye color, hair color, species traits, "
        "or approved wardrobe pattern unless an approved variant explicitly allows it."
    ]
    return pos, neg


def build_binding_snapshot(
    *,
    identity: dict[str, Any],
    version: dict[str, Any],
    variants: list[dict[str, Any]],
    selection: dict[str, Any],
    constraints: list[dict[str, Any]],
    expected_screen_role: str | None,
    expected_visibility: str,
    expected_view: dict[str, Any] | None,
) -> dict[str, Any]:
    selected = selection.get("selected") or []
    trait_freeze = dict(version.get("traits") or {})
    for v in variants:
        trait_freeze.update(v.get("trait_overrides") or {})
    pos, neg = compile_directives(
        identity_name=identity.get("display_name") or identity.get("canonical_name") or "subject",
        version_number=int(version.get("version_number") or 1),
        traits=trait_freeze,
        constraints=constraints,
        variant_names=[v.get("name") or v.get("id") for v in variants],
    )
    return {
        "binding_id": str(uuid4()),
        "identity_id": identity["id"],
        "identity_type": identity.get("identity_type"),
        "display_name": identity.get("display_name"),
        "identity_version_id": version["id"],
        "version_number": version.get("version_number"),
        "traits_frozen": trait_freeze,
        "variant_ids": [v["id"] for v in variants],
        "variants_frozen": [
            {
                "id": v["id"],
                "name": v.get("name"),
                "variant_type": v.get("variant_type"),
                "trait_overrides": v.get("trait_overrides") or {},
                "locked_traits": v.get("locked_traits") or [],
            }
            for v in variants
        ],
        "selected_reference_ids": [s["id"] for s in selected],
        "selected_reference_roles": sorted(
            {r for s in selected for r in (s.get("roles") or []) if r in REFERENCE_ROLES}
        ),
        "reference_approval_states": {s["id"]: s.get("approval_status") for s in selected},
        "references_frozen": [
            {
                "id": s["id"],
                "asset_id": s.get("asset_id"),
                "roles": s.get("roles") or [],
                "approval_status": s.get("approval_status"),
                "selection_reason": s.get("selection_reason"),
            }
            for s in selected
        ],
        "constraint_snapshot": constraints,
        "prompt_directives": pos,
        "negative_directives": neg,
        "expected_screen_role": expected_screen_role,
        "expected_visibility": require_visibility(expected_visibility),
        "expected_view": expected_view,
        "selection_audit": {
            "missing_preferred_roles": selection.get("missing_preferred_roles") or [],
            "rejected": selection.get("rejected") or [],
            "resolver_version": RESOLVER_VERSION,
        },
    }


def assemble_packet(
    *,
    project_id: str,
    request_id: str,
    bindings: list[dict[str, Any]],
    workflow_capability_statement: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "project_id": project_id,
        "request_id": request_id,
        "continuityPacketSchemaVersion": SCHEMA_VERSIONS["continuityPacketSchemaVersion"],
        "bindings": bindings,
        "workflow_capability_statement": workflow_capability_statement,
        "resolver_version": RESOLVER_VERSION,
        "compiler_version": COMPILER_VERSION,
        "frozen": True,
    }


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)
