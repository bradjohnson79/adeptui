"""One advisory VRAM viability evaluator.

Never mutates the creator request. Coarse 8/16/24/32+ buckets are display-only.
"""

from __future__ import annotations

from typing import Any, Literal

from .legal_canvas import (
    TIERS,
    SpecFidelityError,
    alignment_for,
    check_canvas,
    exact_frame_count,
    list_legal_canvases,
    resolve_legal_canvas,
)

Viability = Literal["VIABLE", "VIABLE WITH MODEL UNLOAD", "MARGINAL", "NOT VIABLE"]


def _canonical(product_id: str) -> str:
    token = str(product_id or "").strip()
    if token in {"ltx-2.5", "ltx_2_5"}:
        return "ltx-2.5-distilled"
    if token in {"minimax-h3-local", "minimax-h3-t2v-local"}:
        return "minimax-h3"
    return token


def _family(product_id: str) -> str:
    product = _canonical(product_id)
    if product.startswith("ltx-2.5"):
        return "ltx-2.5"
    if product.startswith("minimax-h3"):
        return "minimax-h3"
    if product.startswith("seedance"):
        return "seedance"
    return product


def _acceleration_profile(product_id: str) -> dict[str, Any] | None:
    """The certified acceleration profile for a product, or None.

    MiniMax H3 v1.1 ships with the ONE shared certified authority
    (SageAttention via MiniMaxH3SpeedCache, residual cache OFF). Recording
    it here feeds the precise VRAM evaluator the acceleration profile so the
    verdict is honest about what is running. The peak estimate itself is
    kept conservative (pre-SageAttention-savings upper bound) — no invented
    VRAM reduction is applied without a measured peak delta.
    """
    if _family(product_id) != "minimax-h3":
        return None
    try:
        from ..minimax_h3.acceleration import ACCELERATOR_PROVENANCE

        return dict(ACCELERATOR_PROVENANCE)
    except Exception:
        return None


def _base_weight_gb(family: str) -> float:
    if family == "ltx-2.5":
        return 10.5
    if family == "minimax-h3":
        return 14.0
    if family == "seedance":
        return 0.0
    return 8.0


def estimate_peak_gb(
    product_id: str,
    *,
    width: int,
    height: int,
    frames: int,
    generate_audio: bool = True,
    surface: str = "t2v",
) -> float:
    family = _family(product_id)
    if family == "seedance":
        return 0.0
    pixels = max(1, int(width) * int(height))
    count = max(1, int(frames))
    # Working-set scale vs published 720p class 1280×704 × 121.
    scale = (pixels / (1280.0 * 704.0)) * (count / 121.0)
    activations = 6.2 * max(0.35, min(scale, 4.5))
    audio = 1.4 if generate_audio else 0.0
    i2v = 0.8 if surface in {"i2v", "multiFrame", "r2v"} else 0.0
    return round(_base_weight_gb(family) + activations + audio + i2v, 2)


def _telemetry() -> dict[str, Any]:
    from ..vram_profiles import query_gpu_stats

    stats = query_gpu_stats()
    gpus = list(stats.get("gpus") or [])
    primary = {}
    if gpus:
        primary = max(gpus, key=lambda g: float(g.get("memory_total_mib") or 0))
    total_mib = float(primary.get("memory_total_mib") or 0)
    used_mib = float(primary.get("memory_used_mib") or 0)
    free_mib = float(primary.get("memory_free_mib") or 0)
    total_gb = round(total_mib / 1024.0, 2) if total_mib else None
    used_gb = round(used_mib / 1024.0, 2) if total_mib else None
    free_gb = round(free_mib / 1024.0, 2) if total_mib else None
    return {
        "ok": bool(stats.get("ok")),
        "gpuName": primary.get("name") or "",
        "driverVersion": primary.get("driver_version") or "",
        "memoryTotalMib": total_mib or None,
        "memoryUsedMib": used_mib or None,
        "memoryFreeMib": free_mib or None,
        "memoryTotalGb": total_gb,
        "memoryUsedGb": used_gb,
        "memoryFreeGb": free_gb,
        "utilizationGpuPct": primary.get("utilization_gpu_pct"),
        "residentNote": (
            f"{used_gb} GB currently allocated on this GPU"
            if used_gb is not None
            else "Residency unknown"
        ),
    }


def _verdict(peak: float, free_gb: float | None, total_gb: float | None, used_gb: float | None) -> tuple[Viability, str]:
    if peak <= 0:
        return "VIABLE", "Hosted path does not consume local GPU memory."
    if free_gb is None or total_gb is None:
        return "MARGINAL", f"Estimated peak {peak} GB, but live VRAM could not be read."
    unloadable = max(0.0, (used_gb or 0.0) - 1.6)
    if peak <= free_gb * 0.88:
        return "VIABLE", f"Estimated peak {peak} GB fits in {free_gb} GB free."
    if peak <= (free_gb + unloadable) * 0.88:
        return (
            "VIABLE WITH MODEL UNLOAD",
            f"Estimated peak {peak} GB needs about {round(peak - free_gb, 2)} GB more than the "
            f"{free_gb} GB free now. Unloading idle models may make room.",
        )
    if peak <= total_gb * 0.94:
        return (
            "MARGINAL",
            f"Estimated peak {peak} GB is close to this GPU’s {total_gb} GB total. "
            "A run may work or may run out of memory.",
        )
    return (
        "NOT VIABLE",
        f"Estimated peak {peak} GB exceeds this GPU’s {total_gb} GB. Adept will not shrink your canvas.",
    )


def evaluate(
    product_id: str,
    *,
    width: int,
    height: int,
    fps: int,
    duration_sec: float,
    surface: str = "t2v",
    generate_audio: bool = True,
) -> dict[str, Any]:
    product = _canonical(product_id)
    telemetry = _telemetry()
    canvas = check_canvas(product, width, height)
    try:
        frames = exact_frame_count(duration_sec, fps)
    except SpecFidelityError as exc:
        return {
            "ok": False,
            "verdict": "NOT VIABLE",
            "productId": product,
            "width": width,
            "height": height,
            "fps": fps,
            "durationSec": duration_sec,
            "estimatedPeakGb": None,
            "reason": str(exc),
            "suggestions": exc.suggestions,
            "telemetry": telemetry,
            "canvas": canvas.to_dict(),
            "mutatesRequest": False,
        }
    peak = estimate_peak_gb(
        product,
        width=width,
        height=height,
        frames=frames,
        generate_audio=generate_audio,
        surface=surface,
    )
    verdict, reason = _verdict(
        peak,
        telemetry.get("memoryFreeGb"),
        telemetry.get("memoryTotalGb"),
        telemetry.get("memoryUsedGb"),
    )
    suggestions: list[str] = []
    if not canvas.ok:
        verdict = "NOT VIABLE"
        reason = canvas.message
        suggestions = list(canvas.suggestions)
    elif verdict == "NOT VIABLE":
        suggestions = [
            "Try 1080p or 720p for this generator",
            "Shorten the clip if you still want this canvas",
        ]
    elif verdict == "VIABLE WITH MODEL UNLOAD":
        suggestions = ["Unload idle local models, then generate — Adept will not do that for you automatically"]
    return {
        "ok": canvas.ok and verdict != "NOT VIABLE",
        "verdict": verdict,
        "productId": product,
        "width": width,
        "height": height,
        "fps": fps,
        "durationSec": duration_sec,
        "frames": frames,
        "estimatedPeakGb": peak,
        "reason": reason,
        "suggestions": suggestions,
        "telemetry": telemetry,
        "canvas": canvas.to_dict(),
        "alignment": alignment_for(product),
        "acceleration": _acceleration_profile(product),
        "mutatesRequest": False,
    }


def evaluate_ladder(
    product_id: str,
    *,
    aspect: str = "16:9",
    fps: int = 24,
    duration_sec: float = 5.0,
    surface: str = "t2v",
    generate_audio: bool = True,
) -> dict[str, Any]:
    from .h3_resolution_guidance import (
        decorate_h3_ladder,
        display_product_label,
        is_minimax_h3_product,
    )

    telemetry = _telemetry()
    tiers: list[dict[str, Any]] = []
    for row in list_legal_canvases(product_id, aspect=aspect, surface=surface):  # type: ignore[arg-type]
        if not row.get("available"):
            tiers.append(
                {
                    "tier": row["tier"],
                    "verdict": "NOT VIABLE",
                    "honestyLabel": row.get("honestyLabel") or "Unavailable",
                    "width": None,
                    "height": None,
                    "estimatedPeakGb": None,
                    "reason": row.get("honestyLabel") or "This tier is not available for this workflow.",
                    "suggestions": row.get("suggestions") or [],
                }
            )
            continue
        result = evaluate(
            product_id,
            width=int(row["width"]),
            height=int(row["height"]),
            fps=fps,
            duration_sec=duration_sec,
            surface=surface,
            generate_audio=generate_audio,
        )
        tiers.append(
            {
                "tier": row["tier"],
                "verdict": result["verdict"],
                "honestyLabel": row.get("honestyLabel"),
                "width": row["width"],
                "height": row["height"],
                "estimatedPeakGb": result.get("estimatedPeakGb"),
                "reason": result.get("reason"),
                "suggestions": result.get("suggestions") or [],
            }
        )
    product = _canonical(product_id)
    if is_minimax_h3_product(product):
        # Canonical H3 resolution-fit advice (demonstrated 480/720/1080 on ~32 GB).
        # Instant free-VRAM peak heuristics must not brand 720p/1080p "Not viable".
        tiers = decorate_h3_ladder(tiers, total_gb=telemetry.get("memoryTotalGb"))
    return {
        "productId": product,
        "productLabel": display_product_label(product),
        "aspect": aspect,
        "fps": fps,
        "durationSec": duration_sec,
        "surface": surface,
        "telemetry": telemetry,
        "tiers": tiers,
        "mutatesRequest": False,
    }



def exact_gpu_payload(stats: dict[str, Any] | None = None) -> dict[str, Any]:
    from ..vram_profiles import query_gpu_stats

    raw = dict(stats or query_gpu_stats())
    gpus = list(raw.get("gpus") or [])
    primary = max(gpus, key=lambda g: float(g.get("memory_total_mib") or 0)) if gpus else {}
    total_mib = float(primary.get("memory_total_mib") or 0)
    used_mib = float(primary.get("memory_used_mib") or 0)
    free_mib = float(primary.get("memory_free_mib") or 0)
    raw["memory_total_gb"] = round(total_mib / 1024.0, 2) if total_mib else None
    raw["memory_used_gb"] = round(used_mib / 1024.0, 2) if total_mib else None
    raw["memory_free_gb"] = round(free_mib / 1024.0, 2) if total_mib else None
    raw["gpu_name"] = primary.get("name") or ""
    raw["recommended_tier"] = None
    return raw
