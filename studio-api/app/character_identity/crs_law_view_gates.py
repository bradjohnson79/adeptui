"""Fail-closed CRS law-view gates before Adept compose accepts a tile.

Hard gates (FAIL-CLOSE):
  - one_figure: reject multi-character / collage / turnaround tiles
  - requested_view: reject only when a real detector returns a concrete
    camera that mismatches the requested view
    (front / three_quarter / side / back / closeup).
    Missing / disabled / error / unknown detector is FAIL-OPEN RECOMMEND
    (composeEligible stays true unless one_figure failed). No fake pose CNN.

Soft checks (FAIL-OPEN as RECOMMEND when no existing scorer):
  - identity, wardrobe, domain

Does not auto-approve. Does not call Krea. Does not compose failed tiles.
Reuses this module as the single CRS tile-accept contract; identity/CD
scoring is consulted if already present, never a second scorer stack.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable

# Canonical requested cameras for CRS law views (owner wording).
REQUESTED_VIEWS = ("front", "three_quarter", "side", "back", "closeup")

ROLE_TO_REQUESTED_VIEW: dict[str, str] = {
    "hero_identity": "front",
    "full_body_front": "front",
    "front_full": "front",
    "front": "front",
    "full_body_three_quarter_front": "three_quarter",
    "full_body_three_quarter": "three_quarter",
    "three_quarter_full": "three_quarter",
    "three_quarter": "three_quarter",
    "full_body_side_left": "side",
    "full_body_side_right": "side",
    "side_left": "side",
    "side_right": "side",
    "side": "side",
    "full_body_back": "back",
    "back_full": "back",
    "back": "back",
    "closeup_front": "closeup",
    "face_closeup": "closeup",
    "front_closeup": "closeup",
    "closeup": "closeup",
}

PASS = "PASS"
FAIL = "FAIL"
RECOMMEND = "RECOMMEND"

HARD_CHECKS = ("one_figure", "requested_view")
SOFT_CHECKS = ("identity", "wardrobe", "domain")


def canonical_requested_view(role: str | None) -> str:
    key = str(role or "").strip().lower()
    if key in ROLE_TO_REQUESTED_VIEW:
        return ROLE_TO_REQUESTED_VIEW[key]
    # last token fallback: "crs_view:front" / "view=side"
    for token in reversed(key.replace("-", "_").replace(" ", "_").split("_")):
        if token in REQUESTED_VIEWS:
            return token
        if token in {"3", "34", "3q", "tq"}:
            return "three_quarter"
    raise ValueError(f"unknown CRS law-view role: {role!r}")


@runtime_checkable
class LawViewDetector(Protocol):
    """Pixel / fixture detector. Tests inject a mock. Production may reuse CD."""

    def count_figures(self, path: str | None, *, extras: dict[str, Any] | None = None) -> int | None:
        """Return figure count, or None when unknown (hard-gate fail-close)."""

    def detect_view(self, path: str | None, *, extras: dict[str, Any] | None = None) -> str | None:
        """Return a REQUESTED_VIEWS value, or None when scoring is unavailable."""


@dataclass
class CheckResult:
    name: str
    status: str
    reason: str = ""
    fail_closed: bool = False
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "reason": self.reason,
            "failClosed": self.fail_closed,
            "detail": dict(self.detail),
        }


@dataclass
class LawViewGateVerdict:
    accepted: bool
    checks: list[CheckResult] = field(default_factory=list)
    requested_view: str = ""
    detected_view: str | None = None
    figure_count: int | None = None

    @property
    def reasons(self) -> list[str]:
        return [c.reason for c in self.checks if c.status == FAIL and c.reason]

    @property
    def error(self) -> str:
        return "; ".join(self.reasons) or "CRS law-view gate failed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "composeEligible": self.accepted,
            "autoApproved": False,
            "requestedView": self.requested_view,
            "detectedView": self.detected_view,
            "figureCount": self.figure_count,
            "reasons": list(self.reasons),
            "error": self.error if not self.accepted else "",
            "checks": [c.to_dict() for c in self.checks],
        }


def _try_existing_cd_scorer() -> Any | None:
    """Reuse identity/CD scoring if already wired. Do not invent a second stack."""
    try:
        from ..codirector.vision.engine import get_engine

        engine = get_engine()
        if engine is None or not getattr(engine, "enabled", False):
            return None
        return engine
    except Exception:
        return None


def _heuristic_is_collage(path: str) -> bool:
    """Detect regular multi-panel / turnaround grids from gutter seams."""
    try:
        from PIL import Image
        import statistics
    except Exception:
        return False
    pth = Path(path)
    if not pth.is_file():
        return False
    try:
        with Image.open(pth) as im:
            rgb = im.convert("RGB")
            w, h = rgb.size
            if w < 16 or h < 16:
                return False
            pix = list(rgb.getdata())
    except Exception:
        return False

    def _lum(x: int, y: int) -> float:
        r, g, b = pix[y * w + x]
        return 0.299 * r + 0.587 * g + 0.114 * b

    def _band_mean(xs: range, ys: range) -> float:
        vals = [_lum(x, y) for y in ys for x in xs]
        return sum(vals) / max(1, len(vals))

    def _has_gutters(cols: int, rows: int) -> bool:
        if cols < 2 and rows < 2:
            return False
        cell_w = w // max(1, cols)
        cell_h = h // max(1, rows)
        if cell_w < 8 or cell_h < 8:
            return False
        gutter = max(1, min(cell_w, cell_h) // 16)
        interiors: list[float] = []
        gutters: list[float] = []
        for c in range(cols):
            x0 = c * cell_w + gutter
            x1 = (c + 1) * cell_w - gutter
            for r in range(rows):
                y0 = r * cell_h + gutter
                y1 = (r + 1) * cell_h - gutter
                if x1 <= x0 or y1 <= y0:
                    continue
                interiors.append(_band_mean(range(x0, x1), range(y0, y1)))
        for c in range(1, cols):
            gx0 = c * cell_w - gutter
            gx1 = c * cell_w + gutter
            gutters.append(_band_mean(range(max(0, gx0), min(w, gx1)), range(0, h)))
        for r in range(1, rows):
            gy0 = r * cell_h - gutter
            gy1 = r * cell_h + gutter
            gutters.append(_band_mean(range(0, w), range(max(0, gy0), min(h, gy1))))
        if len(interiors) < 2 or not gutters:
            return False
        try:
            spread = max(interiors) - min(interiors)
            g_mean = sum(gutters) / len(gutters)
            i_mean = sum(interiors) / len(interiors)
            i_var = statistics.pvariance(interiors) if len(interiors) > 1 else 0.0
        except Exception:
            return False
        # Distinct panels + a contrasting gutter (typical Qwen collage / turnaround).
        return spread > 18.0 and abs(g_mean - i_mean) > 12.0 and i_var > 40.0

    return _has_gutters(2, 2) or _has_gutters(2, 3) or _has_gutters(1, 4) or _has_gutters(4, 1)


def _heuristic_figure_count(path: str | None, extras: dict[str, Any] | None) -> int | None:
    extra = extras or {}
    if extra.get("figureCount") is not None:
        try:
            return int(extra["figureCount"])
        except (TypeError, ValueError):
            return None
    if extra.get("isCollage") is True or extra.get("isTurnaround") is True:
        return 2
    if not path:
        return None
    if _heuristic_is_collage(path):
        return 2
    pth = Path(path)
    if not pth.is_file():
        return None
    try:
        from PIL import Image, ImageFilter, ImageOps
    except Exception:
        return None
    try:
        with Image.open(pth) as im:
            gray = ImageOps.grayscale(im)
            w, h = gray.size
            if w < 8 or h < 8:
                return None
            # Downsample for a cheap connected-component count.
            gray = gray.resize((min(w, 96), min(h, 96)))
            gray = gray.filter(ImageFilter.MedianFilter(size=3))
            pixels = list(gray.getdata())
            gw, gh = gray.size
    except Exception:
        return None
    # Background = mode of border pixels.
    border = (
        pixels[0:gw]
        + pixels[(gh - 1) * gw : gh * gw]
        + [pixels[y * gw] for y in range(gh)]
        + [pixels[y * gw + gw - 1] for y in range(gh)]
    )
    bg = sorted(border)[len(border) // 2]
    thresh = 28
    fg = [1 if abs(p - bg) > thresh else 0 for p in pixels]
    seen = [False] * (gw * gh)
    blobs = 0
    min_area = max(12, int(0.04 * gw * gh))
    for i, on in enumerate(fg):
        if not on or seen[i]:
            continue
        stack = [i]
        seen[i] = True
        area = 0
        while stack:
            cur = stack.pop()
            area += 1
            x, y = cur % gw, cur // gw
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if nx < 0 or ny < 0 or nx >= gw or ny >= gh:
                    continue
                ni = ny * gw + nx
                if seen[ni] or not fg[ni]:
                    continue
                seen[ni] = True
                stack.append(ni)
        if area >= min_area:
            blobs += 1
    return blobs if blobs > 0 else None


def _heuristic_view(path: str | None, extras: dict[str, Any] | None) -> str | None:
    extra = extras or {}
    raw = extra.get("detectedView") or extra.get("detected_view")
    if raw:
        key = str(raw).strip().lower().replace("-", "_")
        try:
            return canonical_requested_view(key)
        except ValueError:
            if key in REQUESTED_VIEWS:
                return key
            return None
    if path:
        side = Path(str(path) + ".view.json")
        if side.is_file():
            try:
                import json

                blob = json.loads(side.read_text(encoding="utf-8"))
                return canonical_requested_view(str(blob.get("view") or blob.get("detectedView") or ""))
            except Exception:
                return None
    return None


class DefaultLawViewDetector:
    def count_figures(self, path: str | None, *, extras: dict[str, Any] | None = None) -> int | None:
        return _heuristic_figure_count(path, extras)

    def detect_view(self, path: str | None, *, extras: dict[str, Any] | None = None) -> str | None:
        return _heuristic_view(path, extras)


_default_detector = DefaultLawViewDetector()


def evaluate_crs_law_view_tile(
    *,
    path: str | None = None,
    requested_role: str | None = None,
    requested_view: str | None = None,
    detector: LawViewDetector | None = None,
    extras: dict[str, Any] | None = None,
    identity_scorer: Callable[..., Any] | None = None,
) -> LawViewGateVerdict:
    """Evaluate one completed law-view tile. Hard gates fail-close."""
    extra = dict(extras or {})
    try:
        want = (requested_view or "").strip().lower() or canonical_requested_view(requested_role)
    except ValueError as exc:
        return LawViewGateVerdict(
            accepted=False,
            requested_view=str(requested_view or requested_role or ""),
            checks=[
                CheckResult(
                    name="requested_view",
                    status=FAIL,
                    reason=str(exc),
                    fail_closed=True,
                )
            ],
        )
    if want not in REQUESTED_VIEWS:
        want = canonical_requested_view(want)

    det = detector or _default_detector
    view_scoring_unavailable = False
    view_unavailable_reason = ""
    try:
        figures = det.count_figures(path, extras=extra)
    except Exception:
        figures = None
    try:
        detected = det.detect_view(path, extras=extra)
    except Exception as exc:  # noqa: BLE001
        detected = None
        view_scoring_unavailable = True
        view_unavailable_reason = type(exc).__name__
    if detected:
        try:
            detected = canonical_requested_view(detected)
        except ValueError:
            detected = None
            view_scoring_unavailable = True
            view_unavailable_reason = "non-canonical view label"
    else:
        view_scoring_unavailable = True
        if not view_unavailable_reason:
            view_unavailable_reason = "detector missing, disabled, or returned unknown"

    checks: list[CheckResult] = []

    if figures is None:
        checks.append(
            CheckResult(
                name="one_figure",
                status=FAIL,
                reason="one-figure unknown: detector could not count figures (fail-close)",
                fail_closed=True,
                detail={"figureCount": None},
            )
        )
    elif figures != 1:
        checks.append(
            CheckResult(
                name="one_figure",
                status=FAIL,
                reason=(
                    f"one-figure failed: expected 1 figure, got {figures} "
                    "(multi-character / collage / turnaround tile)"
                ),
                fail_closed=True,
                detail={"figureCount": figures},
            )
        )
    else:
        checks.append(
            CheckResult(
                name="one_figure",
                status=PASS,
                reason="one figure",
                fail_closed=True,
                detail={"figureCount": 1},
            )
        )

    if not detected:
        # No production pose/view scorer: do not fail-close live tiles.
        checks.append(
            CheckResult(
                name="requested_view",
                status=RECOMMEND,
                reason=(
                    f"requested-view scoring unavailable for {want} "
                    f"({view_unavailable_reason}); fail-open RECOMMEND"
                ),
                fail_closed=False,
                detail={
                    "requestedView": want,
                    "detectedView": None,
                    "scoringUnavailable": True,
                    "unavailableReason": view_unavailable_reason,
                },
            )
        )
    elif detected != want:
        checks.append(
            CheckResult(
                name="requested_view",
                status=FAIL,
                reason=f"requested-view failed: wanted {want}, tile is {detected}",
                fail_closed=True,
                detail={"requestedView": want, "detectedView": detected},
            )
        )
    else:
        checks.append(
            CheckResult(
                name="requested_view",
                status=PASS,
                reason=f"view matches {want}",
                fail_closed=True,
                detail={"requestedView": want, "detectedView": detected},
            )
        )

    scorer = identity_scorer if identity_scorer is not None else _try_existing_cd_scorer()
    for name in SOFT_CHECKS:
        if scorer is None:
            checks.append(
                CheckResult(
                    name=name,
                    status=RECOMMEND,
                    reason=f"{name}: no existing scorer wired; fail-open RECOMMEND",
                    fail_closed=False,
                )
            )
            continue
        try:
            score_fn = getattr(scorer, f"score_{name}", None) or getattr(scorer, "validate_image", None)
            if score_fn is None:
                checks.append(
                    CheckResult(
                        name=name,
                        status=RECOMMEND,
                        reason=f"{name}: existing engine has no {name} score; fail-open RECOMMEND",
                        fail_closed=False,
                    )
                )
                continue
            raw = score_fn(path) if score_fn.__code__.co_argcount <= 2 else score_fn
            ok = bool(raw) if not isinstance(raw, dict) else bool(raw.get("ok", True))
            checks.append(
                CheckResult(
                    name=name,
                    status=PASS if ok else RECOMMEND,
                    reason=f"{name}: existing scorer consulted",
                    fail_closed=False,
                    detail={"raw": raw if isinstance(raw, (dict, str, int, float, bool)) else str(type(raw))},
                )
            )
        except Exception as exc:  # noqa: BLE001
            checks.append(
                CheckResult(
                    name=name,
                    status=RECOMMEND,
                    reason=f"{name}: scorer error fail-open ({type(exc).__name__})",
                    fail_closed=False,
                )
            )

    hard_failed = any(c.name in HARD_CHECKS and c.status == FAIL for c in checks)
    return LawViewGateVerdict(
        accepted=not hard_failed,
        checks=checks,
        requested_view=want,
        detected_view=detected,
        figure_count=figures,
    )


def record_slot_gate(slot: dict[str, Any], verdict: LawViewGateVerdict) -> dict[str, Any]:
    """Stamp the pack slot. Never auto-approve. Failed tiles are not compose-eligible."""
    body = verdict.to_dict()
    slot["crsLawViewGate"] = body
    slot["composeEligible"] = bool(verdict.accepted)
    slot["autoApproved"] = False
    if not verdict.accepted:
        slot["gateRejected"] = True
        slot["gateReason"] = verdict.error
        if not slot.get("error"):
            slot["error"] = verdict.error
    else:
        slot["gateRejected"] = False
    return slot


def gate_candidate_law_views(
    view_jobs: list[dict[str, Any]],
    *,
    resolve_path: Callable[[dict[str, Any]], str | None],
    detector: LawViewDetector | None = None,
) -> dict[str, Any]:
    """Gate every completed tile. Any hard failure blocks Adept compose."""
    rejected: list[str] = []
    for vj in view_jobs:
        role = vj.get("role") or vj.get("viewRole") or vj.get("sheetView")
        path = resolve_path(vj)
        extras = {}
        if isinstance(vj.get("gateExtras"), dict):
            extras = dict(vj["gateExtras"])
        verdict = evaluate_crs_law_view_tile(
            path=path,
            requested_role=str(role or ""),
            detector=detector,
            extras=extras,
        )
        record_slot_gate(vj, verdict)
        if not verdict.accepted:
            rejected.append(f"{role}: {verdict.error}")
    accepted = not rejected
    return {
        "accepted": accepted,
        "error": "; ".join(rejected) if rejected else "",
        "rejectedCount": len(rejected),
        "kreaInvoked": False,
        "autoApproved": False,
    }

def stamp_matching_gate_extras(view_jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Test helper: mark slots as one-figure + matching requested view.

    Production compose never calls this. It only lets unit tests that
    already complete dummy PNGs exercise Adept compose without live pixels.
    """
    for vj in view_jobs:
        role = vj.get("role") or vj.get("viewRole") or vj.get("sheetView")
        try:
            view = canonical_requested_view(str(role or ""))
        except ValueError:
            view = "front"
        extra = dict(vj.get("gateExtras") or {})
        extra.setdefault("figureCount", 1)
        extra.setdefault("detectedView", view)
        vj["gateExtras"] = extra
    return view_jobs
