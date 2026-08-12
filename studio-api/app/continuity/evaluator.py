"""Honest continuity evaluation against frozen packets (no fake scores)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from . import SCHEMA_VERSIONS
from .constants import (
    CHARACTER_DIMENSIONS,
    ENVIRONMENT_DIMENSIONS,
    EVALUATOR_KEY,
    EVALUATOR_VERSION,
    FACE_DEPENDENT_DIMENSIONS,
)


def evaluator_capability(evaluator_key: str | None = None) -> dict[str, Any]:
    key = evaluator_key or EVALUATOR_KEY
    return {
        "evaluator_key": key,
        "evaluator_version": EVALUATOR_VERSION,
        "evaluatorCapabilitySchemaVersion": SCHEMA_VERSIONS["evaluatorCapabilitySchemaVersion"],
        "supported_identity_types": [
            "character",
            "environment",
            "location",
            "prop",
            "vehicle",
            "creature",
            "wardrobe",
            "object",
            "graphic_element",
        ],
        "supported_dimensions": list(CHARACTER_DIMENSIONS) + list(ENVIRONMENT_DIMENSIONS),
        "requires_regions": False,
        "requires_reference_roles": [],
        "deterministic": True,
        "limitations": [
            "Rule-based metadata and constraint checks only.",
            "No biometric identity verification.",
            "No face embeddings in Wave 5 v1.",
            "Dimensions without evidence are not_assessable.",
        ],
    }


def _visibility_blocks(dimension: str, visibility: str) -> bool:
    v = (visibility or "fully_visible").lower()
    if v in ("offscreen", "not_expected"):
        return True
    if v in ("occluded", "background") and dimension in FACE_DEPENDENT_DIMENSIONS:
        return True
    if v == "partially_visible" and dimension in ("eyes", "markings", "jewelry"):
        return True
    # Rear / back shots: face dims not assessable when expected_view says rear
    return False


def _dimensions_for_type(identity_type: str) -> list[str]:
    if identity_type in ("environment", "location"):
        return list(ENVIRONMENT_DIMENSIONS)
    return list(CHARACTER_DIMENSIONS)


def evaluate_binding(
    *,
    binding: dict[str, Any],
    capability: dict[str, Any],
) -> list[dict[str, Any]]:
    identity_type = str(binding.get("identity_type") or "character")
    visibility = str(binding.get("expected_visibility") or "fully_visible")
    expected_view = binding.get("expected_view") or {}
    view_angle = str(expected_view.get("angle") or expected_view.get("shotType") or "").lower()
    traits = binding.get("traits_frozen") or {}
    constraints = binding.get("constraint_snapshot") or []
    refs = binding.get("references_frozen") or []
    supported = set(capability.get("supported_dimensions") or [])

    results: list[dict[str, Any]] = []
    for dim in _dimensions_for_type(identity_type):
        if dim not in supported:
            results.append(
                {
                    "dimension": dim,
                    "score": None,
                    "status": "not_assessable",
                    "severity": "informational",
                    "confidence": None,
                    "evidence": [],
                    "explanation": f"Dimension '{dim}' is outside evaluator capabilities.",
                    "evaluator_key": capability["evaluator_key"],
                }
            )
            continue

        if _visibility_blocks(dim, visibility) or (
            dim in FACE_DEPENDENT_DIMENSIONS and ("rear" in view_angle or "back" in view_angle)
        ):
            results.append(
                {
                    "dimension": dim,
                    "score": None,
                    "status": "not_assessable",
                    "severity": "informational",
                    "confidence": None,
                    "evidence": [{"kind": "visibility", "expected_visibility": visibility, "view": view_angle}],
                    "explanation": f"Dimension '{dim}' is not visually assessable given visibility '{visibility}'.",
                    "evaluator_key": capability["evaluator_key"],
                }
            )
            continue

        # Rule-based: locked constraints present → review required (cannot claim pass without pixels)
        locked = [
            c
            for c in constraints
            if c.get("dimension") == dim and c.get("policy") == "lock" and c.get("enabled", True)
        ]
        trait = traits.get(dim) or traits.get(dim.replace("_", ""))
        if not refs and not locked and trait is None:
            results.append(
                {
                    "dimension": dim,
                    "score": None,
                    "status": "not_assessable",
                    "severity": "informational",
                    "confidence": None,
                    "evidence": [],
                    "explanation": "No frozen references or locked constraints for this dimension.",
                    "evaluator_key": capability["evaluator_key"],
                }
            )
            continue

        if locked:
            results.append(
                {
                    "dimension": dim,
                    "score": None,
                    "status": "review",
                    "severity": str(locked[0].get("severity") or "critical"),
                    "confidence": 0.4,
                    "evidence": [
                        {
                            "kind": "constraint",
                            "expected": locked[0].get("expected_value"),
                            "limitation": "Pixel comparison not available; human review required.",
                        }
                    ],
                    "explanation": (
                        f"Locked constraint on '{dim}' requires human review. "
                        f"Expected: {locked[0].get('expected_value')}. "
                        "Automated pass is not claimed."
                    ),
                    "evaluator_key": capability["evaluator_key"],
                }
            )
            continue

        # Reference presence check only — not a continuity quality score
        role_hint = {
            "eyes": "eyes",
            "hair": "hair",
            "wardrobe": "wardrobe_front",
            "face_structure": "canonical_front",
            "layout": "environment_layout",
        }.get(dim)
        has_ref = True
        if role_hint:
            has_ref = any(role_hint in (r.get("roles") or []) for r in refs) or bool(refs)

        results.append(
            {
                "dimension": dim,
                "score": None if not has_ref else 0.5,
                "status": "review" if has_ref else "not_assessable",
                "severity": "minor",
                "confidence": 0.35 if has_ref else None,
                "evidence": [{"kind": "reference_presence", "has_reference": has_ref}],
                "explanation": (
                    "Reference metadata present; pixel drift not measured. Human review recommended."
                    if has_ref
                    else "No suitable reference role for this dimension."
                ),
                "evaluator_key": capability["evaluator_key"],
            }
        )
    return results


def evaluate_packet(*, packet: dict[str, Any], asset_id: str, project_id: str) -> dict[str, Any]:
    capability = evaluator_capability()
    all_dims: list[dict[str, Any]] = []
    critical_review = False
    for binding in packet.get("bindings") or []:
        dims = evaluate_binding(binding=binding, capability=capability)
        for d in dims:
            d["identity_id"] = binding.get("identity_id")
            d["binding_id"] = binding.get("binding_id")
            if d["status"] == "review" and d.get("severity") == "critical":
                critical_review = True
            all_dims.append(d)

    statuses = {d["status"] for d in all_dims}
    if "error" in statuses:
        overall = "error"
    elif "drift" in statuses:
        overall = "drift"
    elif "review" in statuses or critical_review:
        overall = "review"
    elif statuses and statuses <= {"pass", "not_applicable"}:
        overall = "pass"
    else:
        overall = "not_assessable"

    # Never invent an overall numeric score that conceals critical review
    numeric = [d["score"] for d in all_dims if isinstance(d.get("score"), (int, float))]
    overall_score = None
    if numeric and overall not in ("not_assessable", "error") and not critical_review:
        overall_score = sum(numeric) / len(numeric)

    return {
        "id": str(uuid4()),
        "project_id": project_id,
        "asset_id": asset_id,
        "packet_id": packet["id"],
        "continuityEvaluationSchemaVersion": SCHEMA_VERSIONS["continuityEvaluationSchemaVersion"],
        "evaluator_key": capability["evaluator_key"],
        "evaluator_version": capability["evaluator_version"],
        "evaluator_capability": capability,
        "overall_score": overall_score,
        "overall_status": overall,
        "dimensions": all_dims,
        "requires_human_review": overall in ("review", "drift", "error", "not_assessable") or critical_review,
        "identity_ids": [b.get("identity_id") for b in (packet.get("bindings") or [])],
        "variant_ids": [
            vid for b in (packet.get("bindings") or []) for vid in (b.get("variant_ids") or [])
        ],
    }
