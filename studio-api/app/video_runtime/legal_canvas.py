"""One legal-canvas + duration-fidelity authority for v1.1 video.

Creator tiers resolve to exact published pixels. Execution never snaps,
clamps, or pads. Illegal requests fail before GPU/API spend.
"""

from __future__ import annotations

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
_SEEDANCE_PRODUCTS = frozenset({"seedance-2.0", "seedance-2.5"})


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

    if product not in _ALIGN32_PRODUCTS:
        raise SpecFidelityError(
            f"{product} is not an active v1.1 local or hosted video family for canvas resolution.",
            suggestions=["minimax-h3", "ltx-2.5", "seedance-2.0", "seedance-2.5"],
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
    if abs(raw - frames) > 1e-6:
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
    if token in {"ltx", "ltx-local", "ltx2.5", "ltx-2.5"}:
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


#: Canonical MiniMax H3 megapixel → pixel grid for 16:9 /32 canvases.
#: Width and height are multiples of 32 (VAE /16 then DiT patch 2).
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


def _format_h3_megapixels(value: float) -> str:
    """Stable label like '0.7 MP' or '1.0 MP'."""
    if value == int(value):
        return f"{int(value)}.0 MP"
    return f"{value} MP"


H3_MEGAPIXEL_LABELS: list[str] = [_format_h3_megapixels(mp) for mp, _ in H3_MEGAPIXEL_GRID]


#: Auto Fast = 0.4 MP (864×480) — the certified Scene5 release-gate H3
#: template canvas. ``docs/release-gate/minimax-h3-comfy-parity/Scene5_H3_CanonicalTemplate_API.json``
#: used megapixels 0.4.
H3_AUTO_MEGAPIXEL_FAST = 0.4

#: Auto Quality = 0.7 MP (1152×640) — the FM4/FM5 certified Timeline default
#: (adapter ``finalResolution``). This preserves today's default behavior.
H3_AUTO_MEGAPIXEL_QUALITY = 0.7


def resolve_h3_megapixel_canvas(mp: float | int | str) -> tuple[str, int, int]:
    """Return (label, width, height) for a canonical H3 megapixel value.

    Unknown or unsupported MP raises :class:`SpecFidelityError` with honest
    suggestions. Never snaps to a nearest value.
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
    dims = _H3_MEGAPIXEL_BY_VALUE.get(key)
    if dims is None:
        raise SpecFidelityError(
            f"{mp_val} MP is not a supported MiniMax H3 canvas.",
            suggestions=H3_MEGAPIXEL_LABELS,
            code="H3_ILLEGAL_MEGAPIXELS",
        )
    return _format_h3_megapixels(mp_val), dims[0], dims[1]


def resolve_h3_timeline_canvas(
    batch_h3_resolution: dict[str, Any] | None,
    *,
    draft_mode: bool,
) -> dict[str, Any]:
    """Resolve a BatchBlock's H3 resolution intent to a canonical canvas.

    Manual mode always uses the stored megapixel value. Auto or absent uses
    the policy constant by draft_mode. Returns a provenance dict carrying
    the resolved mode, megapixels, label, width, height, and whether the
    choice was auto-derived.
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

    label, width, height = resolve_h3_megapixel_canvas(mp)
    return {
        "mode": mode,
        "megapixels": mp,
        "label": label,
        "width": width,
        "height": height,
        "auto": auto,
    }
