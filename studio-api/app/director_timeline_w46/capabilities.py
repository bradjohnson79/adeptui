"""Honest generator capability registry for Timeline Master."""

from __future__ import annotations

from typing import Any

from .contracts import GeneratorCapability, InPaintStrategy


def list_generators() -> list[GeneratorCapability]:
    """View of Production Control + adapter join. Not a second catalog."""
    from ..production_control.generator_authority import timeline_generator_snapshot

    return timeline_generator_snapshot()


def get_generator(generator_id: str | None) -> GeneratorCapability | None:
    if not generator_id:
        return None
    from ..production_control.generator_authority import canonical_product_id, timeline_adapter_for

    token = str(generator_id).strip()
    canonical = canonical_product_id(token)
    adapter = timeline_adapter_for(token)
    for gen in list_generators():
        if gen.id == token:
            return gen
        if gen.id == canonical or gen.id == adapter:
            return gen
        if canonical_product_id(gen.id) == canonical:
            return gen
        if gen.timelineAdapterId and gen.timelineAdapterId in {token, canonical, adapter}:
            return gen
    return None


def registry_snapshot() -> dict[str, Any]:
    gens = list_generators()
    return {
        "ok": True,
        "generators": [g.model_dump() for g in gens],
        "nativeVideoInPaintCertified": False,
        "defaultInPaintStrategy": "range_replacement",
        "mock": False,
    }


def validate_duration(generator_id: str | None, planned: float) -> dict[str, Any]:
    from ..video_runtime.legal_canvas import is_minimax_h3_generator, snap_h3_timeline_duration

    if is_minimax_h3_generator(generator_id):
        snap = snap_h3_timeline_duration(planned)
        if not snap.get("ok"):
            return {
                "ok": False,
                "action": "choose",
                "plannedDuration": planned,
                "maxDurationSec": snap.get("maxDurationSec"),
                "legalDurationSec": None,
                "snapped": False,
                "options": ["split", "shorten", "keep", "cancel"],
                "message": snap.get("message")
                or f"Planned duration {planned}s exceeds MiniMax H3 max 15s — no silent truncate.",
            }
        return {
            "ok": True,
            "action": "snap" if snap.get("snapped") else "keep",
            "plannedDuration": planned,
            "legalDurationSec": snap.get("legalDurationSec"),
            "maxDurationSec": snap.get("maxDurationSec"),
            "snapped": bool(snap.get("snapped")),
            "frames": snap.get("frames"),
            "message": snap.get("message") or "",
        }

    gen = get_generator(generator_id)
    if not gen or gen.maxDurationSec is None:
        return {"ok": True, "action": "keep", "plannedDuration": planned, "maxDurationSec": None}
    if planned <= gen.maxDurationSec + 1e-6:
        return {"ok": True, "action": "keep", "plannedDuration": planned, "maxDurationSec": gen.maxDurationSec}
    return {
        "ok": False,
        "action": "choose",
        "plannedDuration": planned,
        "maxDurationSec": gen.maxDurationSec,
        "options": ["split", "shorten", "keep", "cancel"],
        "message": f"Planned duration {planned}s exceeds {gen.label} max {gen.maxDurationSec}s — no silent truncate.",
    }


def disclose_inpaint_strategy(generator_id: str | None, requested: InPaintStrategy | None) -> dict[str, Any]:
    gen = get_generator(generator_id)
    requested = requested or "range_replacement"
    if requested == "native":
        # ok=False means nativeRequestSatisfied=False — not an overall Inpaint failure.
        return {
            "ok": False,
            "nativeRequestSatisfied": False,
            "fallbackAccepted": True,
            "executionReady": True,
            "strategy": "range_replacement",
            "requested": "native",
            "disclosed": True,
            "message": "Native video InPaint is not certified. Using range_replacement.",
            "mock": False,
        }
    supported = list(gen.inPaintStrategies) if gen else ["complete_batch_retake"]
    if requested not in supported:
        fallback = supported[0] if supported else "complete_batch_retake"
        return {
            "ok": True,
            "nativeRequestSatisfied": None,
            "fallbackAccepted": True,
            "executionReady": True,
            "strategy": fallback,
            "requested": requested,
            "disclosed": True,
            "message": f"{requested} unsupported for generator; using {fallback}.",
            "mock": False,
        }
    return {
        "ok": True,
        "nativeRequestSatisfied": None,
        "fallbackAccepted": False,
        "executionReady": True,
        "strategy": requested,
        "requested": requested,
        "disclosed": True,
        "mock": False,
    }


def timeline_visual_sufficient(caps: Any) -> bool:
    """Image-frame / Visual-ref sufficiency: R2V or I2V.

    supportsImageToVideo=False is NOT a Timeline refuse when
    supportsReferenceToVideo is True (MiniMax H3).
    """
    if caps is None:
        return False
    return bool(
        getattr(caps, "supportsReferenceToVideo", False)
        or getattr(caps, "supportsImageToVideo", False)
    )


def can_timeline_generate(caps: Any) -> bool:
    """Timeline generate sufficiency.

    R2V is sufficient. Do not treat supportsImageToVideo as the only
    Timeline capability gate (H3 is I2V=false / R2V=true).
    """
    if caps is None:
        return False
    if getattr(caps, "executable", True) is False:
        return False
    if getattr(caps, "supportsTimelineGeneration", True) is False:
        return False
    return bool(
        getattr(caps, "supportsReferenceToVideo", False)
        or getattr(caps, "supportsImageToVideo", False)
        or getattr(caps, "supportsTextToVideo", False)
    )


def can_timeline_retake(caps: Any) -> bool:
    """Timeline Re-Take sufficiency — same visual law as generate.

    R2V is sufficient. Image-frame still requires timeline_visual_sufficient
    at the retake_range gate (I2V or R2V); T2V-only engines refuse image-frame
    honestly and do not fall back.
    """
    if not can_timeline_generate(caps):
        return False
    return getattr(caps, "supportsRetake", True) is not False

