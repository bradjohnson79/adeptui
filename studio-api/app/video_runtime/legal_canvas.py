"""One legal-canvas + duration-fidelity authority for v1.1 video.

Creator tiers resolve to exact published pixels. Execution never snaps,
clamps, or pads. Illegal requests fail before GPU/API spend.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

ResolutionTier = Literal["480p", "720p", "1080p", "2K", "4K"]
GenerationMode = Literal["native", "upscale", "unavailable"]
Surface = Literal["t2v", "i2v", "multiFrame", "r2v"]

TIERS: tuple[ResolutionTier, ...] = ("480p", "720p", "1080p", "2K", "4K")

ASPECT_RATIOS: dict[str, tuple[int, int]] = {
    "1:1": (1, 1),
    "4:3": (4, 3),
    "3:4": (3, 4),
    "3:2": (3, 2),
    "16:10": (16, 10),
    "16:9": (16, 9),
    "18:9": (18, 9),
    "21:9": (21, 9),
    "9:16": (9, 16),
    "2.39:1": (239, 100),
}

# /32 short-edge class. 4K has no native /32 16:9 (3840×2160 is illegal).
_ALIGN32_SHORT: dict[ResolutionTier, int | None] = {
    "480p": 480,
    "720p": 704,
    "1080p": 1088,
    "2K": 1440,
    "4K": None,
}

# Published 16:9 /32 canvases (H3 + LTX 2.5). Not silent snaps of 1280×720.
_ALIGN32_16_9: dict[ResolutionTier, tuple[int, int] | None] = {
    "480p": (832, 480),
    "720p": (1280, 704),
    "1080p": (1920, 1088),
    "2K": (2560, 1440),
    "4K": None,
}

# Hosted Seedance Adept-implemented sizes (standard broadcast, not /32).
_SEEDANCE_16_9: dict[ResolutionTier, tuple[int, int] | None] = {
    "480p": (854, 480),
    "720p": (1280, 720),
    "1080p": None,
    "2K": None,
    "4K": None,
}

_ALIGN32_PRODUCTS = frozenset(
    {
        "minimax-h3",
        "minimax-h3-i2v-local",
        "ltx-2.5",
        "ltx-2.5-distilled",
        "ltx-2.5-full",
        "ltx-2.5-comfy",
    }
)
_SEEDANCE_PRODUCTS = frozenset({"seedance-2.0", "seedance-2.0-mini", "seedance-2.0-fast", "seedance-2.5"})


class SpecFidelityError(ValueError):
    """Creator specification cannot execute as requested. Never auto-fix."""

    def __init__(self, message: str, *, suggestions: list[str] | None = None, code: str = "SPEC_FIDELITY"):
        super().__init__(message)
        self.code = code
        self.suggestions = list(suggestions or [])

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "suggestions": self.suggestions}


@dataclass(frozen=True)
class LegalCanvas:
    tier: ResolutionTier
    aspect: str
    width: int
    height: int
    alignment: int
    generation_mode: GenerationMode
    honesty_label: str
    product_id: str
    workflow_key: str | None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "aspect": self.aspect,
            "width": self.width,
            "height": self.height,
            "alignment": self.alignment,
            "generationMode": self.generation_mode,
            "honestyLabel": self.honesty_label,
            "productId": self.product_id,
            "workflowKey": self.workflow_key,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class CanvasCheck:
    ok: bool
    width: int
    height: int
    alignment: int
    message: str = ""
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "width": self.width,
            "height": self.height,
            "alignment": self.alignment,
            "message": self.message,
            "suggestions": list(self.suggestions),
        }


def _canonical_product(product_id: str) -> str:
    token = str(product_id or "").strip()
    if token in {"ltx-2.5", "ltx_2_5", "ltx_2_5_distilled"}:
        return "ltx-2.5-distilled"
    if token in {"minimax-h3-local", "minimax-h3-t2v-local"}:
        return "minimax-h3"
    if token in {"seedance-fal", "seedance-api", "fal_seedance"}:
        return "seedance-2.0"
    if token in {"fal_seedance_25"}:
        return "seedance-2.5"
    if token in {"fal_seedance_mini", "seedance-mini", "seedance-2.0-mini"}:
        return "seedance-2.0-mini"
    if token in {"fal_seedance_fast", "seedance-fast", "seedance-2.0-fast"}:
        return "seedance-2.0-fast"
    return token


def _workflow_for(product_id: str, surface: Surface) -> str | None:
    from .workflow_capabilities import workflow_key_for

    return workflow_key_for(product_id, surface)


def alignment_for(product_id: str) -> int:
    product = _canonical_product(product_id)
    if product in _ALIGN32_PRODUCTS:
        return 32
    return 1


def _align_down(value: int, multiple: int) -> int:
    return max(multiple, (int(value) // multiple) * multiple)


def _align_up(value: int, multiple: int) -> int:
    value = max(multiple, int(value))
    rem = value % multiple
    return value if rem == 0 else value + (multiple - rem)


def _nearest_aligned_pair(width: int, height: int, multiple: int) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    for w in (_align_down(width, multiple), width if width % multiple == 0 else _align_up(width, multiple)):
        for h in (_align_down(height, multiple), height if height % multiple == 0 else _align_up(height, multiple)):
            if w > 0 and h > 0 and (w, h) not in pairs:
                pairs.append((w, h))
    return pairs


def _dims_for_aspect_short_edge(aspect: str, short: int, multiple: int) -> tuple[int, int]:
    a, b = ASPECT_RATIOS.get(aspect, (16, 9))
    if a >= b:
        height = _align_down(short, multiple)
        width = _align_down(int(round(height * a / b)), multiple)
        return max(multiple, width), max(multiple, height)
    width = _align_down(short, multiple)
    height = _align_down(int(round(width * b / a)), multiple)
    return max(multiple, width), max(multiple, height)


def infer_tier_from_pixels(width: int, height: int) -> ResolutionTier:
    """Map stored pixels onto a creator tier. Does not change the pixels."""
    short = min(int(width or 0), int(height or 0))
    if short <= 0:
        return "720p"
    if short <= 560:
        return "480p"
    if short <= 896:
        return "720p"
    if short <= 1264:
        return "1080p"
    if short <= 1800:
        return "2K"
    return "4K"


def resolve_legal_canvas(
    product_id: str,
    *,
    tier: str,
    aspect: str = "16:9",
    surface: Surface = "t2v",
) -> LegalCanvas:
    product = _canonical_product(product_id)
    label = str(tier or "720p").strip()
    if label == "1440p":
        label = "2K"
    if label not in TIERS:
        raise SpecFidelityError(
            f"{label} is not a standard Adept video tier. Choose 480p, 720p, 1080p, 2K, or 4K.",
            suggestions=list(TIERS),
            code="UNKNOWN_TIER",
        )
    tier_key: ResolutionTier = label  # type: ignore[assignment]
    aspect_key = str(aspect or "16:9").strip() or "16:9"
    if aspect_key not in ASPECT_RATIOS:
        raise SpecFidelityError(
            f"Aspect {aspect_key} is not a known Adept video aspect.",
            suggestions=list(ASPECT_RATIOS),
            code="UNKNOWN_ASPECT",
        )
    workflow = _workflow_for(product, surface)

    if product in _SEEDANCE_PRODUCTS:
        dims = _SEEDANCE_16_9.get(tier_key) if aspect_key == "16:9" else None
        if dims is None and _SEEDANCE_16_9.get(tier_key) is None:
            raise SpecFidelityError(
                f"{product} in Adept only runs 480p and 720p. {tier_key} is not implemented for this hosted path.",
                suggestions=["480p", "720p"],
                code="HOSTED_TIER_UNAVAILABLE",
            )
        if dims is None:
            short = 480 if tier_key == "480p" else 720
            dims = _dims_for_aspect_short_edge(aspect_key, short, 2)
        return LegalCanvas(
            tier=tier_key,
            aspect=aspect_key,
            width=dims[0],
            height=dims[1],
            alignment=1,
            generation_mode="native",
            honesty_label=f"Native {tier_key}",
            product_id=product,
            workflow_key=workflow,
        )

    if product == "hunyuan-video-1.5-distilled":
        # Staged checkpoints are 480p distilled. A higher requested tier stays
        # 480p-class; Adept does not relabel that output as 720p.
        sizes = {"16:9": (848, 480), "9:16": (480, 848), "1:1": (480, 480)}
        dims = sizes.get(aspect_key)
        if dims is None:
            raise SpecFidelityError(
                "HunyuanVideo 1.5 Distilled supports 16:9, 9:16, and 1:1.",
                suggestions=["16:9", "9:16", "1:1"],
                code="HUNYUAN_ASPECT_UNSUPPORTED",
            )
        return LegalCanvas(
            tier="480p",
            aspect=aspect_key,
            width=dims[0],
            height=dims[1],
            alignment=16,
            generation_mode="native",
            honesty_label="480p-class",
            product_id=product,
            workflow_key=workflow,
            notes="Staged HunyuanVideo 1.5 Distilled checkpoints are 480p-class. The finished video keeps its real size.",
        )

    if product not in _ALIGN32_PRODUCTS:
        raise SpecFidelityError(
            f"{product} is not an active v1.1 local or hosted video family for canvas resolution.",
            suggestions=["minimax-h3", "ltx-2.5", "hunyuan-video-1.5-distilled", "seedance-2.0", "seedance-2.5"],
            code="UNKNOWN_PRODUCT",
        )

    if tier_key == "4K":
        raise SpecFidelityError(
            "Native 4K is not legal for MiniMax H3 / LTX 2.5 (3840×2160 is not /32). "
            "Adept will not pretend an upscale is native 4K, and no 4K upscale graph is wired.",
            suggestions=["480p", "720p", "1080p", "2K"],
            code="NATIVE_4K_UNAVAILABLE",
        )

    if aspect_key == "16:9":
        dims = _ALIGN32_16_9[tier_key]
        assert dims is not None
    else:
        short = _ALIGN32_SHORT[tier_key]
        assert short is not None
        dims = _dims_for_aspect_short_edge(aspect_key, short, 32)

    honesty = {
        "480p": "Native 480p",
        "720p": "Native 720p",
        "1080p": "Native 1080p",
        "2K": "Native 2K",
    }[tier_key]
    notes = ""
    if tier_key == "720p" and aspect_key == "16:9":
        notes = "720p class is 1280×704. 1280×720 is illegal for this workflow."
    if tier_key == "1080p" and aspect_key == "16:9":
        notes = "1080p class is 1920×1088. 1920×1080 is illegal for this workflow."

    return LegalCanvas(
        tier=tier_key,
        aspect=aspect_key,
        width=dims[0],
        height=dims[1],
        alignment=32,
        generation_mode="native",
        honesty_label=honesty,
        product_id=product,
        workflow_key=workflow,
        notes=notes,
    )


def list_legal_canvases(
    product_id: str,
    *,
    aspect: str = "16:9",
    surface: Surface = "t2v",
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for tier in TIERS:
        try:
            canvas = resolve_legal_canvas(product_id, tier=tier, aspect=aspect, surface=surface)
            rows.append({**canvas.to_dict(), "available": True})
        except SpecFidelityError as exc:
            rows.append(
                {
                    "tier": tier,
                    "aspect": aspect,
                    "width": None,
                    "height": None,
                    "alignment": alignment_for(product_id),
                    "generationMode": "unavailable",
                    "honestyLabel": str(exc),
                    "productId": _canonical_product(product_id),
                    "workflowKey": _workflow_for(_canonical_product(product_id), surface),
                    "notes": "",
                    "available": False,
                    "suggestions": exc.suggestions,
                }
            )
    return rows


def check_canvas(product_id: str, width: int, height: int) -> CanvasCheck:
    product = _canonical_product(product_id)
    w, h = int(width or 0), int(height or 0)
    multiple = alignment_for(product)
    if w <= 0 or h <= 0:
        return CanvasCheck(False, w, h, multiple, "Width and height must be positive.", [])
    # Certified H3 routing (gate-removal REPORT 3.1): every minimax-h3* token uses
    # the H3-specific resolution validator, never the generic /32 Scene-canvas gate.
    if product in {"minimax-h3", "minimax-h3-i2v-local"} or product.startswith("minimax-h3"):
        return check_h3_resolution(w, h)
    if product == "hunyuan-video-1.5-distilled":
        if w % 16 == 0 and h % 16 == 0 and max(w, h) <= 848 and min(w, h) <= 480:
            return CanvasCheck(True, w, h, 16, "", [])
        return CanvasCheck(
            False,
            w,
            h,
            16,
            "HunyuanVideo 1.5 Distilled renders at 480p-class sizes (multiples of 16).",
            ["848×480", "480×848", "480×480"],
        )
    if product in _SEEDANCE_PRODUCTS:
        return CanvasCheck(True, w, h, 1, "", [])
    if product not in _ALIGN32_PRODUCTS:
        return CanvasCheck(
            False,
            w,
            h,
            multiple,
            f"{product} is not an active v1.1 video family.",
            ["minimax-h3", "ltx-2.5"],
        )
    if w % 32 == 0 and h % 32 == 0:
        return CanvasCheck(True, w, h, 32, "", [])
    near = _nearest_aligned_pair(w, h, 32)
    suggestions = [f"{nw}×{nh}" for nw, nh in near[:4]]
    if (1280, 704) not in near and {w, h} & {720, 1280}:
        suggestions.insert(0, "1280×704")
    return CanvasCheck(
        False,
        w,
        h,
        32,
        (
            f"This generator needs width and height in multiples of 32 "
            f"(VAE /16 then patch 2). {w}×{h} would make a latent of {w // 16}×{h // 16}, "
            f"which cannot pack. Adept will not change your canvas."
        ),
        suggestions,
    )


def assert_legal_canvas(product_id: str, width: int, height: int) -> tuple[int, int]:
    checked = check_canvas(product_id, width, height)
    if not checked.ok:
        raise SpecFidelityError(checked.message, suggestions=checked.suggestions, code="ILLEGAL_CANVAS")
    return checked.width, checked.height


def exact_frame_count(length_seconds: float, fps: int) -> int:
    seconds = float(length_seconds)
    rate = int(fps)
    if seconds <= 0 or rate <= 0:
        raise SpecFidelityError("Duration and frame rate must be positive.", code="ILLEGAL_DURATION")
    raw = seconds * rate
    frames = int(round(raw))
    # Durations are often persisted to ~4 decimals (8.0417 for 193/24).
    # Allow up to half of 1e-4 seconds of drift in frame space.
    tol = max(1e-6, (0.5 * 1e-4) * rate + 1e-9)
    if abs(raw - frames) > tol:
        raise SpecFidelityError(
            f"{seconds}s at {rate} fps is not a whole number of frames ({raw}).",
            suggestions=[f"{frames / rate:.4g}s ({frames} frames)", f"{(frames + 1) / rate:.4g}s ({frames + 1} frames)"],
            code="ILLEGAL_DURATION",
        )
    return max(1, frames)


def _ltx_legal_frames(frames: int) -> bool:
    return frames >= 9 and (frames - 1) % 8 == 0


# Timeline MiniMax H3: Inspector request is authority. 15s is the requested
# maximum (HARD CAP). Frame-grid snap may disclose a slightly different legal
# length. Timeline MiniMax H3 new-scene default is 15s (MINIMAX_H3_NEW_SCENE_SEC = H3 max); 12s was interim; 8s is legacy.
H3_TIMELINE_MAX_REQUEST_SEC = 15.0
H3_TIMELINE_FPS = 24.0
H3_MAX_FRAMES = 362  # 17*21 + 5; trained ceiling ~15s at 24 fps


def is_minimax_h3_generator(generator_id: str | None) -> bool:
    token = str(generator_id or "").strip().lower()
    return token.startswith("minimax-h3")


#: New-scene / new-batch seed when the creator did not pick a duration and the
#: scene engine resolves to MiniMax H3. Equals the H3 Timeline request max so a
#: fresh H3 scene starts at full creator fidelity (never 12s interim, never 5s legacy).
H3_NEW_SCENE_SEED_SEC = H3_TIMELINE_MAX_REQUEST_SEC
#: LTX 2.5 Timeline new-scene / new-batch seed (creator fidelity — whole seconds).
LTX_NEW_SCENE_SEED_SEC = 20.0
#: Non-H3 / non-LTX seed when the creator did not pick a duration (legacy product default).
LEGACY_NEW_SCENE_SEED_SEC = 5.0


def is_h3_default_engine(engine: str | None) -> bool:
    """Scene/project engine that resolves to MiniMax H3 at generation time.

    Blank/missing is the product default (H3); the legal EngineName "auto"
    also resolves to H3. Seeding those scenes anything shorter than the H3
    envelope was the 12.0s / 5.0s defect.
    """
    token = str(engine or "").strip().lower()
    return token in ("", "auto") or token.startswith("minimax-h3")


def is_ltx_default_engine(engine: str | None) -> bool:
    """Scene/project engine that resolves to LTX 2.5 at generation time."""
    token = str(engine or "").strip().lower().replace("_", "-")
    if token in {"ltx2.5", "ltx-2.5"}:
        return True
    return token.startswith("ltx-2.5") or token.startswith("ltx2.5")


def sanitize_creator_duration_sec(value: float | int | None) -> float | None:
    """Keep creator-facing duration as clean seconds (no frames/fps float noise).

    Whole numbers stay ints-as-float (15.0). Near one-decimal values round to
    one decimal. Does not invent a default — None/invalid stay None.
    """
    if value is None:
        return None
    try:
        sec = float(value)
    except (TypeError, ValueError):
        return None
    if not (sec > 0) or sec != sec:  # NaN guard
        return None
    nearest_int = round(sec)
    if abs(sec - nearest_int) <= 1e-6:
        return float(nearest_int)
    cleaned = round(sec, 1)
    if abs(cleaned - round(cleaned)) <= 1e-9:
        return float(round(cleaned))
    return float(cleaned)


def seed_new_scene_duration_sec(engine: str | None) -> float:
    """Duration seed for a new Scene/Batch when the creator did NOT explicitly
    choose one. Explicit creator choices are never routed through here."""
    if is_h3_default_engine(engine):
        return float(H3_NEW_SCENE_SEED_SEC)
    if is_ltx_default_engine(engine):
        return float(LTX_NEW_SCENE_SEED_SEC)
    return float(LEGACY_NEW_SCENE_SEED_SEC)


def snap_h3_timeline_duration(
    duration_sec: float | None,
    *,
    fps: float = H3_TIMELINE_FPS,
) -> dict[str, Any]:
    """Inspector duration → legal 17k+5 frames. Never silently clamp >15s.

    Snap UP to the next legal frame count (same as Route A ``_h3_frame_count``)
    and disclose the difference. Requests above 15s fail closed.

    Creator contract: ``durationSec`` / ``requestedDurationSec`` stay the clean
    creator request (defaults to H3_NEW_SCENE_SEED_SEC). ``legalDurationSec`` and
    ``frames`` are execution-only — never write frames/fps back as the scene's
    canonical duration.
    """
    fps_val = float(fps) if fps and fps > 0 else H3_TIMELINE_FPS
    if duration_sec is None or float(duration_sec) <= 0:
        requested = float(H3_NEW_SCENE_SEED_SEC)
        defaulted = True
    else:
        requested = float(duration_sec)
        defaulted = False
    if requested > H3_TIMELINE_MAX_REQUEST_SEC + 1e-6:
        return {
            "ok": False,
            "requestedDurationSec": requested,
            "legalDurationSec": None,
            "durationSec": None,
            "frames": None,
            "maxDurationSec": H3_TIMELINE_MAX_REQUEST_SEC,
            "snapped": False,
            "defaulted": defaulted,
            "message": (
                f"This shot is {requested:g}s. MiniMax H3 can run up to "
                f"{H3_TIMELINE_MAX_REQUEST_SEC:g}s. Shorten it or split it into batches."
            ),
        }
    raw = max(5, int(round(requested * fps_val)))
    snapped_frames = ((raw - 5 + 16) // 17) * 17 + 5
    snapped_frames = max(5, min(snapped_frames, H3_MAX_FRAMES))
    legal = snapped_frames / fps_val
    snapped = abs(legal - requested) > 1e-6
    return {
        "ok": True,
        "requestedDurationSec": requested,
        "legalDurationSec": legal,
        # Creator-facing canonical duration — NEVER frames/fps float noise.
        "durationSec": requested,
        "frames": snapped_frames,
        "maxDurationSec": H3_TIMELINE_MAX_REQUEST_SEC,
        "snapped": snapped,
        "defaulted": defaulted,
        "message": (
            f"MiniMax H3 will render {snapped_frames} frames (~{legal:.2f}s) from your {requested:g}s request."
            if snapped
            else ""
        ),
    }


def _h3_legal_frames(frames: int) -> bool:
    return frames >= 5 and frames % 17 == 5


def _nearest_ltx_frames(frames: int) -> list[int]:
    lo = ((max(1, frames) - 1) // 8) * 8 + 1
    hi = lo + 8
    out = [n for n in (lo, hi) if n >= 9]
    return out[:2]


def ltx_execution_frames(length_seconds: float, fps: int = 24) -> int:
    """Nearest legal 8n+1 count for a Timeline whole-second LTX request.

    CREATE and txt2vid stay fail-closed in assert_legal_duration. Timeline keeps
    the creator's whole seconds and renders the nearer legal count, taking the
    longer count when both neighbors are equally far.
    """

    frames = exact_frame_count(length_seconds, fps)
    if _ltx_legal_frames(frames):
        return frames
    near = _nearest_ltx_frames(frames)
    if not near:
        raise SpecFidelityError(
            f"LTX 2.5 cannot render {length_seconds}s at {fps} fps.",
            code="ILLEGAL_DURATION",
        )
    return min(near, key=lambda count: (abs(count - frames), -count))


def _nearest_h3_frames(frames: int) -> list[int]:
    n = max(5, int(frames))
    while n % 17 != 5:
        n -= 1
        if n < 5:
            n = 5
            break
    hi = n + 17 if n % 17 == 5 else 5
    while hi % 17 != 5:
        hi += 1
    return [x for x in dict.fromkeys([n if n % 17 == 5 else 5, hi]) if x >= 5]


def check_duration(product_id: str, length_seconds: float, fps: int, *, surface: Surface = "t2v") -> dict[str, Any]:
    product = _canonical_product(product_id)
    frames = exact_frame_count(length_seconds, fps)
    if product in _SEEDANCE_PRODUCTS:
        if length_seconds < 4 or length_seconds > 12:
            return {
                "ok": False,
                "frames": frames,
                "message": f"Seedance in Adept accepts 4–12 seconds. You asked for {length_seconds}s.",
                "suggestions": ["4s", "8s", "12s"],
            }
        return {"ok": True, "frames": frames, "message": "", "suggestions": []}

    if product.startswith("ltx-2.5") or product == "ltx-2.5":
        if _ltx_legal_frames(frames):
            return {"ok": True, "frames": frames, "message": "", "suggestions": []}
        near = _nearest_ltx_frames(frames)
        suggestions = [f"{n / fps:.4g}s ({n} frames)" for n in near]
        return {
            "ok": False,
            "frames": frames,
            "message": (
                f"LTX 2.5 needs a frame count of 8n+1. {length_seconds}s at {fps} fps is "
                f"{frames} frames. Adept will not pad or shorten the clip."
            ),
            "suggestions": suggestions,
        }

    if product in {"minimax-h3", "minimax-h3-i2v-local"}:
        if surface == "r2v":
            if _h3_legal_frames(frames):
                return {"ok": True, "frames": frames, "message": "", "suggestions": []}
            near = _nearest_h3_frames(frames)
            return {
                "ok": False,
                "frames": frames,
                "message": (
                    f"MiniMax H3 Reference-to-Video needs a frame count where n ≡ 5 (mod 17). "
                    f"{length_seconds}s at {fps} fps is {frames} frames. Adept will not pad the clip."
                ),
                "suggestions": [f"{n / fps:.4g}s ({n} frames)" for n in near],
            }
        return {"ok": True, "frames": frames, "message": "", "suggestions": []}

    return {"ok": True, "frames": frames, "message": "", "suggestions": []}


def assert_legal_duration(product_id: str, length_seconds: float, fps: int, *, surface: Surface = "t2v") -> int:
    checked = check_duration(product_id, length_seconds, fps, surface=surface)
    if not checked["ok"]:
        raise SpecFidelityError(
            str(checked["message"]),
            suggestions=list(checked.get("suggestions") or []),
            code="ILLEGAL_DURATION",
        )
    return int(checked["frames"])


def preflight_spec(
    product_id: str,
    *,
    width: int,
    height: int,
    length_seconds: float,
    fps: int,
    surface: Surface = "t2v",
) -> dict[str, Any]:
    canvas = check_canvas(product_id, width, height)
    duration = check_duration(product_id, length_seconds, fps, surface=surface)
    ok = canvas.ok and bool(duration["ok"])
    messages = [m for m in (canvas.message, duration.get("message")) if m]
    suggestions = list(canvas.suggestions) + list(duration.get("suggestions") or [])
    return {
        "ok": ok,
        "productId": _canonical_product(product_id),
        "width": width,
        "height": height,
        "fps": fps,
        "durationSec": length_seconds,
        "frames": duration.get("frames"),
        "message": " ".join(messages),
        "suggestions": suggestions,
        "canvas": canvas.to_dict(),
        "duration": duration,
    }


#: Canonical MiniMax H3 megapixel tiers (Size Settings Reference values).
#: Pixel dims for any supported aspect come from ResolutionSelector (D1), not a
#: hardcoded per-aspect table. The 16:9 column below matches ResolutionSelector
#: (aspect=16:9, megapixels, multiple=32) exactly — kept as the published
#: Size Settings honesty grid and as the megapixel-tier catalog.
H3_MEGAPIXEL_GRID: tuple[tuple[float, tuple[int, int]], ...] = (
    (0.2, (608, 352)),
    (0.3, (736, 416)),
    (0.4, (864, 480)),
    (0.5, (960, 544)),
    (0.6, (1056, 608)),
    (0.7, (1152, 640)),
    (0.8, (1216, 672)),
    (0.9, (1280, 736)),
    (0.98, (1344, 768)),
    (1.0, (1376, 768)),
    (1.2, (1504, 832)),
    (1.5, (1664, 928)),
    (1.8, (1824, 1024)),
    (2.0, (1920, 1088)),
)

_H3_MEGAPIXEL_BY_VALUE: dict[float, tuple[int, int]] = dict(H3_MEGAPIXEL_GRID)
H3_MEGAPIXEL_VALUES: tuple[float, ...] = tuple(mp for mp, _ in H3_MEGAPIXEL_GRID)

#: Comfy ResolutionSelector aspect combo (node contract). multiple=32 for H3.
H3_RESOLUTION_SELECTOR_ASPECTS: frozenset[str] = frozenset(
    {"1:1", "2:3", "3:2", "3:4", "4:3", "9:16", "16:9", "21:9"}
)

#: Soft aliases that normalize to 16:9 (display tokens from older caps).
H3_ASPECT_ALIASES: frozenset[str] = frozenset({"≈16:9", "~16:9"})


def _format_h3_megapixels(value: float) -> str:
    """Stable label like '0.7 MP' or '1.0 MP'."""
    if value == int(value):
        return f"{int(value)}.0 MP"
    return f"{value} MP"


H3_MEGAPIXEL_LABELS: list[str] = [_format_h3_megapixels(mp) for mp, _ in H3_MEGAPIXEL_GRID]

#: Auto Fast = 0.4 MP (864x480 @16:9) — certified Scene5 release-gate H3 template.
H3_AUTO_MEGAPIXEL_FAST = 0.4

#: Auto Quality = 0.7 MP (1152x640 @16:9) — FM4/FM5 certified Timeline default.
H3_AUTO_MEGAPIXEL_QUALITY = 0.7


def resolve_h3_resolution_selector(
    aspect: str,
    megapixels: float | int | str,
    *,
    multiple: int = 32,
) -> tuple[int, int]:
    """Comfy ResolutionSelector(aspect, megapixels, multiple=32) — Adept D1 authority.

    Independently rounds width and height from megapixel budget x aspect ratio
    onto ``multiple``. Matches published MiniMax Size Settings 16:9 rows exactly.
    Does NOT use Scene / production canvas pixels.
    """
    aspect_key = str(aspect or "").strip() or "16:9"
    if aspect_key in H3_ASPECT_ALIASES:
        aspect_key = "16:9"
    if aspect_key not in ASPECT_RATIOS:
        raise SpecFidelityError(
            f"Aspect {aspect_key} is not a known Adept video aspect.",
            suggestions=sorted(H3_RESOLUTION_SELECTOR_ASPECTS),
            code="UNKNOWN_ASPECT",
        )
    if aspect_key not in H3_RESOLUTION_SELECTOR_ASPECTS:
        raise SpecFidelityError(
            f"Aspect {aspect_key} is not a MiniMax H3 ResolutionSelector shape.",
            suggestions=sorted(H3_RESOLUTION_SELECTOR_ASPECTS),
            code="H3_ASPECT_UNSUPPORTED",
        )
    try:
        mp_val = float(megapixels)
    except (TypeError, ValueError) as exc:
        raise SpecFidelityError(
            f"MiniMax H3 megapixels must be a number (got {megapixels!r}).",
            suggestions=H3_MEGAPIXEL_LABELS,
            code="H3_ILLEGAL_MEGAPIXELS",
        ) from exc
    a, b = ASPECT_RATIOS[aspect_key]
    total = float(mp_val) * 1024.0 * 1024.0
    mult = max(1, int(multiple))
    width = int(round(math.sqrt(total * a / b) / mult)) * mult
    height = int(round(math.sqrt(total * b / a) / mult)) * mult
    width = max(mult, width)
    height = max(mult, height)
    return width, height


def resolve_h3_megapixel_canvas(
    mp: float | int | str,
    *,
    aspect: str = "16:9",
) -> tuple[str, int, int]:
    """Return (label, width, height) for a canonical H3 megapixel x aspect.

    Megapixel must be an exact published tier. Dims come from D1 ResolutionSelector.
    Never snaps to a nearest megapixel value.
    """
    try:
        mp_val = float(mp)
    except (TypeError, ValueError):
        raise SpecFidelityError(
            f"MiniMax H3 megapixels must be a number (got {mp!r}).",
            suggestions=H3_MEGAPIXEL_LABELS,
            code="H3_ILLEGAL_MEGAPIXELS",
        )
    key = round(mp_val, 2)
    if key not in _H3_MEGAPIXEL_BY_VALUE:
        raise SpecFidelityError(
            f"{mp_val} MP is not a supported MiniMax H3 canvas.",
            suggestions=H3_MEGAPIXEL_LABELS,
            code="H3_ILLEGAL_MEGAPIXELS",
        )
    width, height = resolve_h3_resolution_selector(aspect, key, multiple=32)
    return _format_h3_megapixels(mp_val), width, height


def resolve_h3_timeline_canvas(
    batch_h3_resolution: dict[str, Any] | None,
    *,
    draft_mode: bool,
    aspect: str = "16:9",
) -> dict[str, Any]:
    """Resolve a BatchBlock's H3 resolution intent to a canonical canvas.

    Manual mode always uses the stored megapixel value. Auto or absent uses
    the policy constant by draft_mode. Dims are D1 ResolutionSelector outputs
    for the requested creative aspect (never Scene canvas).
    """
    mode = "auto"
    auto = True
    mp = H3_AUTO_MEGAPIXEL_FAST if draft_mode else H3_AUTO_MEGAPIXEL_QUALITY

    if isinstance(batch_h3_resolution, dict):
        stored_mode = str(batch_h3_resolution.get("mode") or "auto").strip().lower()
        if stored_mode == "manual":
            mode = "manual"
            stored_mp = batch_h3_resolution.get("megapixels")
            if stored_mp is None:
                raise SpecFidelityError(
                    "Manual MiniMax H3 resolution requires a megapixel value.",
                    suggestions=H3_MEGAPIXEL_LABELS,
                    code="H3_MANUAL_MISSING_MEGAPIXELS",
                )
            mp = float(stored_mp)
            auto = False

    label, width, height = resolve_h3_megapixel_canvas(mp, aspect=aspect)
    return {
        "mode": mode,
        "megapixels": mp,
        "label": label,
        "width": width,
        "height": height,
        "auto": auto,
        "aspect": aspect if aspect not in H3_ASPECT_ALIASES else "16:9",
    }


def _build_h3_legal_pixels() -> frozenset[tuple[int, int]]:
    """All D1 ResolutionSelector outputs for production intersect selector aspects x MP tiers."""
    shapes = ("1:1", "4:3", "16:9", "9:16", "21:9")
    pixels: set[tuple[int, int]] = set()
    for aspect in shapes:
        for mp in H3_MEGAPIXEL_VALUES:
            pixels.add(resolve_h3_resolution_selector(aspect, mp, multiple=32))
    return frozenset(pixels)


#: Exact legal (width, height) pairs from D1 ResolutionSelector over H3 shapes x MP.
H3_LEGAL_PIXELS: frozenset[tuple[int, int]] = _build_h3_legal_pixels()

H3_LEGAL_RESOLUTION_LABELS: list[str] = sorted(
    f"{w}x{h}" for w, h in H3_LEGAL_PIXELS
)


def h3_megapixels_for_dims(width: int, height: int) -> float | None:
    """Return the megapixel tier that produces (width, height) for some supported shape, else None."""
    target = (int(width), int(height))
    shapes = ("1:1", "4:3", "16:9", "9:16", "21:9")
    for mp in H3_MEGAPIXEL_VALUES:
        for aspect in shapes:
            if resolve_h3_resolution_selector(aspect, mp, multiple=32) == target:
                return float(mp)
    return None


def is_h3_legal_pixels(width: int, height: int) -> bool:
    """True only when (width, height) is an exact D1 ResolutionSelector H3 output."""
    return (int(width), int(height)) in H3_LEGAL_PIXELS


def check_h3_resolution(width: int, height: int) -> CanvasCheck:
    """Authoritative MiniMax H3 canvas check — D1 legal membership, not /32 alone."""
    w, h = int(width or 0), int(height or 0)
    if w <= 0 or h <= 0:
        return CanvasCheck(False, w, h, 32, "Width and height must be positive.", H3_LEGAL_RESOLUTION_LABELS[:6])
    if (w, h) in H3_LEGAL_PIXELS:
        return CanvasCheck(True, w, h, 32, "", [])
    sample = ", ".join(H3_LEGAL_RESOLUTION_LABELS[:8])
    return CanvasCheck(
        False,
        w,
        h,
        32,
        (
            f"MiniMax H3 does not support {w}x{h}. "
            f"Use a legal H3 ResolutionSelector canvas only (not the Scene canvas). "
            f"Examples: {sample}."
        ),
        list(H3_LEGAL_RESOLUTION_LABELS[:14]),
    )


def assert_h3_legal_resolution(width: int, height: int) -> tuple[int, int]:
    checked = check_h3_resolution(width, height)
    if not checked.ok:
        raise SpecFidelityError(
            checked.message,
            suggestions=list(checked.suggestions),
            code="H3_RESOLUTION_UNSUPPORTED",
        )
    return checked.width, checked.height



# Timeline production Picture Shape contract (Scene Creator + Timeline Generator).
# Soft normalize_production_aspect (display) lives in aspect_fps — generate uses these.
TIMELINE_PRODUCTION_ASPECTS: tuple[str, ...] = ("1:1", "4:3", "16:9", "9:16", "21:9")

#: ONE H3 creative-shape capability = Adept production intersect ResolutionSelector aspects.
#: Do not invent shapes outside this intersection (no 3:2 / 2:3 / 3:4 on Timeline H3
#: until they are first-class PRODUCTION_ASPECTS).
H3_SUPPORTED_ASPECTS: tuple[str, ...] = tuple(
    a for a in TIMELINE_PRODUCTION_ASPECTS if a in H3_RESOLUTION_SELECTOR_ASPECTS
)

#: Adapter / authority capability list — single owner reference (not cloned tables).
#: Includes soft 16:9 aliases for older UI tokens; canonical shapes are H3_SUPPORTED_ASPECTS.
H3_CAPABILITY_ASPECT_RATIOS: list[str] = ["≈16:9", *H3_SUPPORTED_ASPECTS]

#: Backward-compat alias (normalize display tokens to 16:9). Prefer H3_SUPPORTED_ASPECTS.
H3_TIMELINE_ASPECTS: frozenset[str] = frozenset({"16:9"}) | H3_ASPECT_ALIASES


def require_timeline_aspect(raw: str | None) -> str:
    """Timeline generate path: refuse empty / custom / unknown. Never silent to 16:9."""
    aspect = (raw or "").strip()
    if not aspect:
        raise SpecFidelityError(
            "Timeline generate requires a picture shape (aspect ratio).",
            suggestions=list(TIMELINE_PRODUCTION_ASPECTS),
            code="ASPECT_REQUIRED",
        )
    if aspect in H3_ASPECT_ALIASES:
        aspect = "16:9"
    if aspect == "custom":
        raise SpecFidelityError(
            "Custom aspect is not allowed on Timeline generate. Choose a production picture shape.",
            suggestions=list(TIMELINE_PRODUCTION_ASPECTS),
            code="ASPECT_CUSTOM_REFUSED",
        )
    if aspect not in TIMELINE_PRODUCTION_ASPECTS:
        raise SpecFidelityError(
            f"Aspect {aspect} is not a Timeline production picture shape.",
            suggestions=list(TIMELINE_PRODUCTION_ASPECTS),
            code="UNKNOWN_ASPECT",
        )
    return aspect


def require_h3_timeline_aspect(raw: str | None) -> str:
    """MiniMax H3 Timeline/Director: aspect must be in H3_SUPPORTED_ASPECTS (D1 unify).

    Soft aliases normalize to 16:9. Unsupported shapes hard-refuse.
    Does not map creative shape onto Scene canvas dims.
    """
    token = (raw or "").strip()
    if not token:
        raise SpecFidelityError(
            "MiniMax H3 requires a picture shape "
            f"({', '.join(H3_SUPPORTED_ASPECTS)}).",
            suggestions=list(H3_SUPPORTED_ASPECTS),
            code="H3_ASPECT_REQUIRED",
        )
    if token in H3_ASPECT_ALIASES:
        return "16:9"
    try:
        aspect = require_timeline_aspect(token)
    except SpecFidelityError:
        aspect = token
    if aspect not in H3_SUPPORTED_ASPECTS:
        raise SpecFidelityError(
            f"MiniMax H3 does not support picture shape {aspect}. "
            f"Supported: {', '.join(H3_SUPPORTED_ASPECTS)}.",
            suggestions=list(H3_SUPPORTED_ASPECTS),
            code="H3_ASPECT_UNSUPPORTED",
        )
    return aspect



def compile_timeline_canvas(
    generator_id: str,
    *,
    aspect_ratio: str | None,
    h3_resolution: dict | None = None,
    ltx_quality: str | None = None,
    seedance_resolution: str | None = None,
    draft_mode: bool = False,
) -> dict:
    """Single Timeline compile entry to dims dict for resolvedGeneration stamping.

    Raises SpecFidelityError on illegal aspect / canvas. Does not use production_pixels.
    """
    product = _canonical_product(generator_id)
    token = (product or "").lower()
    is_h3 = product in {"minimax-h3", "minimax-h3-i2v-local"} or token.startswith("minimax-h3")
    aspect = require_timeline_aspect(aspect_ratio)

    if is_h3:
        h3_aspect = require_h3_timeline_aspect(aspect)
        canvas = resolve_h3_timeline_canvas(
            h3_resolution, draft_mode=bool(draft_mode), aspect=h3_aspect
        )
        return {
            "productId": "minimax-h3",
            "width": int(canvas["width"]),
            "height": int(canvas["height"]),
            "megapixels": canvas.get("megapixels"),
            "label": canvas.get("label"),
            "aspect": h3_aspect,
            "source": "h3_timeline_canvas",
            "tier": None,
            "projectCanvasIgnored": None,
        }

    from .workflow_resolver import is_ltx_25_generator

    if is_ltx_25_generator(generator_id) or is_ltx_25_generator(product):
        raw_tier = (ltx_quality or "720p").strip()
        aliases = {"720p": "720p", "1080p": "1080p", "2k": "2K", "4k": "4K"}
        tier = aliases.get(raw_tier.lower(), raw_tier if raw_tier in {"720p", "1080p", "2K", "4K"} else "720p")
        legal = resolve_legal_canvas(product or generator_id, tier=tier, aspect=aspect)
        return {
            "productId": product or generator_id,
            "width": int(legal.width),
            "height": int(legal.height),
            "megapixels": None,
            "label": legal.honesty_label,
            "aspect": legal.aspect,
            "source": "ltx_quality",
            "tier": tier,
            "projectCanvasIgnored": None,
        }

    tier_token = str(seedance_resolution or ltx_quality or "720p").strip() or "720p"
    aliases = {"720p": "720p", "1080p": "1080p", "2k": "2K", "4k": "4K", "480p": "480p"}
    tier = aliases.get(tier_token.lower(), "720p")
    legal = resolve_legal_canvas(product or generator_id, tier=tier, aspect=aspect)
    return {
        "productId": product or generator_id,
        "width": int(legal.width),
        "height": int(legal.height),
        "megapixels": None,
        "label": legal.honesty_label,
        "aspect": legal.aspect,
        "source": "legal_canvas",
        "tier": legal.tier,
        "projectCanvasIgnored": None,
    }


def resolve_generation_dimensions(
    *,
    model: str,
    requested_quality: str | float | None = None,
    requested_aspect: str | None = "16:9",
    project_canvas: tuple[int, int] | None = None,
    draft_mode: bool = False,
) -> dict[str, Any]:
    """One authoritative resolver for generation output size.

    MiniMax H3 returns ONLY an H3 megapixel-table entry. Scene / project canvas
    is never used as the video output size. LTX and hosted APIs keep their own
    legal tables via resolve_legal_canvas.
    """
    product = _canonical_product(model)
    token = (product or "").lower()
    is_h3 = product in {"minimax-h3", "minimax-h3-i2v-local"} or token.startswith("minimax-h3")

    if requested_aspect is None:
        aspect_raw = "16:9"
    else:
        aspect_raw = str(requested_aspect)

    if is_h3:
        aspect = require_h3_timeline_aspect(aspect_raw)
        if requested_quality is not None and str(requested_quality).strip():
            q = str(requested_quality).strip().lower()
            if "x" in q:
                try:
                    w_s, h_s = q.split("x", 1)
                    w, h = int(w_s), int(h_s)
                except ValueError as exc:
                    raise SpecFidelityError(
                        f"MiniMax H3 resolution {requested_quality!r} is not a WxH pair.",
                        suggestions=H3_LEGAL_RESOLUTION_LABELS[:14],
                        code="H3_RESOLUTION_UNSUPPORTED",
                    ) from exc
                # Raw WxH (often adapter finalResolution 16:9 honesty label) is NOT
                # aspect-blind authority. Infer megapixels, then re-resolve through D1
                # ResolutionSelector for the creative aspect so 21:9 never ships 1152x640.
                assert_h3_legal_resolution(w, h)
                mp = h3_megapixels_for_dims(w, h)
                if mp is None:
                    raise SpecFidelityError(
                        f"MiniMax H3 resolution {w}x{h} is legal-shaped but not a published megapixel tier.",
                        suggestions=H3_MEGAPIXEL_LABELS,
                        code="H3_RESOLUTION_UNSUPPORTED",
                    )
                label, rw, rh = resolve_h3_megapixel_canvas(mp, aspect=aspect)
                return {
                    "productId": "minimax-h3",
                    "width": rw,
                    "height": rh,
                    "megapixels": mp,
                    "label": label,
                    "aspect": aspect,
                    "source": "requested_wxh_reselected",
                    "projectCanvasIgnored": list(project_canvas) if project_canvas else None,
                    "requestedWxH": [w, h],
                }
            label, w, h = resolve_h3_megapixel_canvas(requested_quality, aspect=aspect)
            return {
                "productId": "minimax-h3",
                "width": w,
                "height": h,
                "megapixels": float(requested_quality),
                "label": label,
                "aspect": aspect,
                "source": "requested_megapixels",
                "projectCanvasIgnored": list(project_canvas) if project_canvas else None,
            }
        canvas = resolve_h3_timeline_canvas(None, draft_mode=bool(draft_mode), aspect=aspect)
        return {
            "productId": "minimax-h3",
            "width": int(canvas["width"]),
            "height": int(canvas["height"]),
            "megapixels": canvas["megapixels"],
            "label": canvas["label"],
            "aspect": aspect,
            "source": "h3_auto_policy",
            "projectCanvasIgnored": list(project_canvas) if project_canvas else None,
        }

    aspect = require_timeline_aspect(aspect_raw)
    tier = str(requested_quality or "720p").strip() or "720p"
    if tier.endswith(" mp") or tier.replace(".", "", 1).isdigit():
        tier = "720p"
    legal = resolve_legal_canvas(product, tier=tier, aspect=aspect, surface="i2v")
    return {
        "productId": product,
        "width": int(legal.width),
        "height": int(legal.height),
        "megapixels": None,
        "label": legal.honesty_label,
        "aspect": legal.aspect,
        "source": "legal_canvas",
        "projectCanvasIgnored": list(project_canvas) if project_canvas else None,
    }

