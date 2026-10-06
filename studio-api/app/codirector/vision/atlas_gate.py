"""Blocking Atlas visual gate — three questions, all must pass.

Unlike ERS, this gate blocks Spatial Map assignment.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Literal

from ...codirector.routing.atlas_classify import classify_pixels

logger = logging.getLogger(__name__)

AtlasFailCode = Literal[
    "FAIL_CORRUPTION",
    "FAIL_TOP_DOWN",
    "FAIL_TOPOLOGY",
    "FAIL_SOURCE_IDENTITY",
    "FAIL_UNRELATED_SCENE",
    "PASS",
]

ATLAS_GATE_INSTRUCTIONS = """You are a strict reviewer for a Spatial Map Atlas Shot.

You are given up to three images. Answer about the CANDIDATE only for Q1.
1. CANDIDATE — the generated Atlas under review (this is the image Q1 judges)
2. SOURCE — the original location photograph (Q3 identity only; may be eye-level)
3. GUIDE — the structural layout the Atlas must follow (Q2), if provided

Answer ALL three questions. Every answer must be YES for a pass.

Q1: Is the candidate genuinely overhead / roofless (not eye-level, not cinematic, not the unchanged source)?
Q2: Does the candidate topology correspond to the GUIDE (same rooms/corridor shape, openings in corresponding places)?
Q3: Does the candidate visual identity correspond to the SOURCE (same place, materials, architecture — not an unrelated facility)?

Q1 is camera only. Shared silver, metal, or corridor materials with SOURCE is a Q3 identity question, not a Q1 fail.
A painted roofless top-down Atlas of the same place is Q1 YES even when SOURCE is an eye-level photograph.
Q1 is NO only for eye-level, first-person, cinematic vanishing-point, splat/point-cloud, photo-plus-grid, or the unchanged source photograph.
If no GUIDE image is provided, judge Q2 from the candidate being a readable overhead layout (corridor/rooms/openings), not from matching a missing guide.

A pretty sci-fi map that ignores the guide fails Q2.
A guide-perfect map with no visual relationship to the source fails Q3.
Source plus a grid overlay fails Q1 and is not an Atlas.

Respond with EXACTLY this format:
Q1: <YES|NO>
Q2: <YES|NO>
Q3: <YES|NO>
FAIL_CODE: <PASS|FAIL_TOP_DOWN|FAIL_TOPOLOGY|FAIL_SOURCE_IDENTITY|FAIL_UNRELATED_SCENE>
REASON: <one sentence, plain language>
"""

RETRY_BUDGET = 3


def parse_atlas_gate_verdict(text: str) -> dict[str, Any]:
    raw = str(text or "")
    def _yn(tag: str) -> bool | None:
        match = re.search(rf"{tag}:\s*(YES|NO)", raw, flags=re.IGNORECASE)
        if not match:
            return None
        return match.group(1).upper() == "YES"

    q1, q2, q3 = _yn("Q1"), _yn("Q2"), _yn("Q3")
    code_match = re.search(
        r"FAIL_CODE:\s*(PASS|FAIL_CORRUPTION|FAIL_TOP_DOWN|FAIL_TOPOLOGY|FAIL_SOURCE_IDENTITY|FAIL_UNRELATED_SCENE)",
        raw,
        flags=re.IGNORECASE,
    )
    reason_match = re.search(r"REASON:\s*(.+)", raw, flags=re.IGNORECASE | re.DOTALL)
    reason = reason_match.group(1).strip().splitlines()[0][:400] if reason_match else ""
    if q1 is True and q2 is True and q3 is True:
        return {
            "ok": True,
            "failCode": "PASS",
            "q1": True,
            "q2": True,
            "q3": True,
            "reason": reason or "The Atlas is overhead, follows the layout, and matches the location.",
        }
    code = code_match.group(1).upper() if code_match else ""
    if not code:
        if q1 is False:
            code = "FAIL_TOP_DOWN"
        elif q2 is False:
            code = "FAIL_TOPOLOGY"
        elif q3 is False:
            code = "FAIL_SOURCE_IDENTITY"
        else:
            code = "FAIL_UNRELATED_SCENE"
    if code == "PASS":
        code = "FAIL_UNRELATED_SCENE"
    return {
        "ok": False,
        "failCode": code,
        "q1": q1,
        "q2": q2,
        "q3": q3,
        "reason": reason or "The Atlas did not pass the three-question review.",
    }


def detect_atlas_corruption(arr: Any, width: int, height: int) -> dict[str, Any]:
    """Reject broken-latent Atlas plates: center column + dead/noisy interior.

    The SenseNova Route B failure signature is source-like sides plus a vertical
    white/gray/checkerboard column. That is not a camera problem — it is data
    corruption and must fail before review.
    """
    import numpy as np

    if arr is None or width < 32 or height < 32:
        return {"ok": True, "score": 0.0}
    rgb = arr.astype("float32")
    if rgb.ndim != 3:
        return {"ok": True, "score": 0.0}
    gray = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    x0 = width // 3
    x1 = (2 * width) // 3
    y0 = height // 8
    y1 = height - y0
    center = gray[y0:y1, x0:x1]
    left = gray[y0:y1, : max(8, width // 6)]
    right = gray[y0:y1, width - max(8, width // 6) :]
    if center.size == 0:
        return {"ok": True, "score": 0.0}
    # High-frequency checker / dither: neighbor absolute difference.
    dx = np.abs(np.diff(center, axis=1)).mean() if center.shape[1] > 1 else 0.0
    dy = np.abs(np.diff(center, axis=0)).mean() if center.shape[0] > 1 else 0.0
    hf = float((dx + dy) / 2.0)
    unique_center = int(len(np.unique(np.round(center / 16.0))))
    side_std = float((left.std() + right.std()) / 2.0) if left.size and right.size else float(gray.std())
    # Saturated blue corner blocks from the same failure family.
    corners = [
        rgb[: max(8, height // 10), : max(8, width // 10)],
        rgb[: max(8, height // 10), width - max(8, width // 10) :],
        rgb[height - max(8, height // 10) :, : max(8, width // 10)],
        rgb[height - max(8, height // 10) :, width - max(8, width // 10) :],
    ]
    blue_corners = 0
    for block in corners:
        if block.size and float(block[:, :, 2].mean()) > 140 and float(block[:, :, 2].mean() - block[:, :, 0].mean()) > 35:
            blue_corners += 1
    flat_bar = False
    col_std = center.std(axis=0)
    if col_std.size and float((col_std < 8).mean()) > 0.12 and float(center.std()) > 25:
        flat_bar = True
    score = hf
    if unique_center <= 12 and hf > 18:
        score += 20
    if blue_corners >= 2:
        score += 25
    if flat_bar:
        score += 15
    # Blue corner blocks are the Route B decode signature. High-frequency
    # grids alone stay FAIL_TOP_DOWN, not corruption.
    if blue_corners >= 3 or (blue_corners >= 2 and flat_bar) or (flat_bar and hf > 24):
        return {
            "ok": False,
            "score": score,
            "hf": hf,
            "blueCorners": blue_corners,
            "flatBar": flat_bar,
            "reason": "The Atlas center is corrupted (blocky white/gray or broken latent), not a usable map.",
        }
    return {"ok": True, "score": score, "hf": hf, "blueCorners": blue_corners, "flatBar": flat_bar}


def _grid_overlay_score(arr: Any, width: int, height: int) -> float:
    import numpy as np

    if arr is None or width < 16 or height < 16:
        return 0.0
    if arr.ndim == 3:
        gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    else:
        gray = arr.astype("float32")
    step_y = max(1, height // 96)
    step_x = max(1, width // 96)
    small = gray[::step_y, ::step_x].astype("float32")
    # Periodic line energy: strong regular peaks on both axes.
    col_var = float(np.var(small.mean(axis=0)))
    row_var = float(np.var(small.mean(axis=1)))
    return (col_var + row_var) / 2.0


def pixel_prefilter_candidate(
    arr: Any,
    width: int,
    height: int,
    *,
    source_arr: Any | None = None,
    source_w: int = 0,
    source_h: int = 0,
    guide_arr: Any | None = None,
) -> dict[str, Any]:
    kind, conf = classify_pixels(arr, width, height)
    grid_score = _grid_overlay_score(arr, width, height)
    corruption = detect_atlas_corruption(arr, width, height)
    if not corruption.get("ok"):
        return {
            "ok": False,
            "failCode": "FAIL_CORRUPTION",
            "reason": corruption.get("reason") or "The Atlas image is corrupted.",
            "pixelKind": kind,
            "corruption": {k: corruption.get(k) for k in ("score", "hf", "blueCorners", "flatBar")},
        }
    import numpy as np

    if arr.ndim == 3:
        gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    else:
        gray = arr.astype("float32")
    inset_y = max(2, height // 8)
    inset_x = max(2, width // 8)
    interior = gray[inset_y : height - inset_y, inset_x : width - inset_x]
    if interior.size and float(interior.std()) < 10 and float(gray.std()) > 20:
        return {
            "ok": False,
            "failCode": "FAIL_TOPOLOGY",
            "reason": "This looks like an outline or edge overlay, not a readable Atlas.",
            "pixelKind": kind,
        }
    source_kind = ""
    if source_arr is not None and source_w and source_h:
        source_kind, _ = classify_pixels(source_arr, source_w, source_h)
    # Corridor + grid / perspective + overlay must never assign.
    if kind == "perspective_environment" and grid_score > 80:
        return {
            "ok": False,
            "failCode": "FAIL_TOP_DOWN",
            "reason": "This still looks like the location photo with a grid on top, not a top-down Atlas.",
            "pixelKind": kind,
        }
    if kind == "perspective_environment" and conf >= 0.7:
        return {
            "ok": False,
            "failCode": "FAIL_TOP_DOWN",
            "reason": "This still looks like an eye-level location photo, not a roofless top-down Atlas.",
            "pixelKind": kind,
        }
    if source_kind == "perspective_environment" and kind == "perspective_environment":
        return {
            "ok": False,
            "failCode": "FAIL_TOP_DOWN",
            "reason": "The result is still the original viewpoint.",
            "pixelKind": kind,
        }
    if guide_arr is not None:
        alignment = guide_topology_alignment(arr, guide_arr)
        if not alignment.get("ok"):
            return {
                "ok": False,
                "failCode": "FAIL_TOPOLOGY",
                "reason": alignment.get("reason") or "The Atlas does not follow the structural layout.",
                "pixelKind": kind,
                "guideAlignment": alignment,
            }
    if kind == "non_environment":
        return {
            "ok": False,
            "failCode": "FAIL_TOPOLOGY" if guide_arr is not None else "FAIL_UNRELATED_SCENE",
            "reason": (
                "The Atlas does not follow the structural guide — the result is not a readable layout."
                if guide_arr is not None
                else "The result does not look like a location Atlas."
            ),
            "pixelKind": kind,
        }
    if guide_arr is not None and source_arr is not None:
        from PIL import Image

        def _thumb(a: Any) -> Any:
            img = Image.fromarray(a.astype("uint8") if a.dtype != "uint8" else a)
            return np.asarray(img.resize((32, 32)))

        try:
            delta = float(np.mean(np.abs(_thumb(arr).astype("float32") - _thumb(source_arr).astype("float32"))))
            if delta < 8:
                return {
                    "ok": False,
                    "failCode": "FAIL_TOP_DOWN",
                    "reason": "The Atlas is still the source image.",
                    "pixelKind": kind,
                }
        except Exception:
            pass
    if kind == "atlas" and conf >= 0.7:
        return {"ok": True, "failCode": "PASS", "reason": "", "pixelKind": kind, "needsVlm": True}
    return {
        "ok": False,
        "failCode": "FAIL_TOP_DOWN",
        "reason": "The result is not a clear top-down Atlas yet.",
        "pixelKind": kind,
        "needsVlm": True,
    }


def guide_topology_alignment(candidate: Any, guide: Any) -> dict[str, Any]:
    """Compare major guide regions to the candidate. Detects rearranged layouts."""
    import numpy as np
    from PIL import Image

    if candidate is None or guide is None:
        return {"ok": True, "score": 1.0, "reason": ""}
    try:
        cand_img = Image.fromarray(candidate.astype("uint8") if getattr(candidate, "dtype", None) != "uint8" else candidate)
        guide_img = Image.fromarray(guide.astype("uint8") if getattr(guide, "dtype", None) != "uint8" else guide)
        size = (64, 64)
        cand = np.asarray(cand_img.resize(size)).astype("float32")
        guid = np.asarray(guide_img.resize(size)).astype("float32")
    except Exception:
        return {"ok": True, "score": 1.0, "reason": ""}

    def _region_mask(rgb: Any, target: tuple[int, int, int], tol: float) -> Any:
        delta = np.abs(rgb - np.array(target, dtype="float32"))
        return (delta.sum(axis=2) < tol)

    regions = {
        "floor": ((52, 56, 62), 70),
        "forest": ((28, 72, 36), 80),
        "clearing": ((168, 150, 96), 80),
        "water": ((48, 92, 148), 80),
        "opening": ((64, 168, 96), 70),
        "yellow": ((232, 196, 48), 70),
        "trail": ((150, 112, 64), 70),
        "hill": ((110, 104, 92), 70),
    }
    misses: list[str] = []
    scores: list[float] = []
    for name, (color, tol) in regions.items():
        mask = _region_mask(guid, color, tol)
        if float(mask.mean()) < 0.02:
            continue
        ys, xs = np.where(mask)
        if ys.size < 8:
            continue
        y0, y1 = int(ys.min()), int(ys.max()) + 1
        x0, x1 = int(xs.min()), int(xs.max()) + 1
        g_occ = float(mask[y0:y1, x0:x1].mean())
        c_patch = cand[y0:y1, x0:x1]
        if c_patch.size == 0:
            misses.append(name)
            continue
        c_std = float(c_patch.std())
        c_mean = float(c_patch.mean())
        g_mean = float(guid[y0:y1, x0:x1][mask[y0:y1, x0:x1]].mean()) if mask[y0:y1, x0:x1].any() else 0.0
        # Candidate must keep a distinct region where the guide placed one.
        if c_std < 6 and abs(c_mean - float(cand.mean())) < 8:
            misses.append(name)
            scores.append(0.0)
            continue
        scores.append(min(1.0, c_std / 20.0 + (1.0 - min(1.0, abs(c_mean - g_mean) / 180.0))))
        if name in {"water", "clearing", "opening", "yellow"} and g_occ > 0.08:
            # Strong semantic markers: the candidate region cannot be empty noise.
            if c_std < 8:
                misses.append(name)
    score = float(sum(scores) / len(scores)) if scores else 1.0
    if misses:
        return {
            "ok": False,
            "score": score,
            "misses": misses,
            "reason": "The Atlas moved or dropped major layout features: " + ", ".join(dict.fromkeys(misses)),
        }
    if scores and score < 0.22:
        return {
            "ok": False,
            "score": score,
            "reason": "The Atlas does not preserve the structural guide topology.",
        }
    return {"ok": True, "score": score, "reason": ""}


def retry_adjustment(fail_code: str) -> dict[str, str]:
    if fail_code == "FAIL_TOP_DOWN":
        return {
            "promptSuffix": " Camera is locked directly overhead. Roofless orthographic floor plan. No horizon.",
            "slotOrder": "guide_source",
        }
    if fail_code == "FAIL_TOPOLOGY":
        return {
            "promptSuffix": " Follow the structural layout image exactly. Same corridor or room proportions. Same door placements. The guide is topology authority.",
            "slotOrder": "guide_source",
        }
    if fail_code in {"FAIL_SOURCE_IDENTITY", "FAIL_APPEARANCE"}:
        return {
            "promptSuffix": " Keep the materials, lighting, and architecture of the appearance reference. Same place. Do not copy its camera.",
            "slotOrder": "guide_source",
        }
    return {
        "promptSuffix": " Rebuild from the structural guide. Do not invent a different facility or decorative pattern.",
        "slotOrder": "guide_source",
    }


def evaluate_atlas_candidate_pixels(
    *,
    candidate_path: str,
    source_path: str = "",
    guide_path: str = "",
) -> dict[str, Any]:
    from PIL import Image
    import numpy as np

    cand = Path(candidate_path)
    if not cand.is_file():
        return {
            "ok": False,
            "failCode": "FAIL_UNRELATED_SCENE",
            "reason": "The Atlas image file is missing.",
            "blocking": True,
        }
    img = Image.open(cand).convert("RGB")
    arr = np.asarray(img)
    src_arr = src_w = src_h = None
    if source_path and Path(source_path).is_file():
        src = Image.open(source_path).convert("RGB")
        src_arr = np.asarray(src)
        src_w, src_h = src.size
    guide_arr = None
    if guide_path and Path(guide_path).is_file():
        guide_arr = np.asarray(Image.open(guide_path).convert("RGB"))
    pre = pixel_prefilter_candidate(
        arr,
        int(arr.shape[1]),
        int(arr.shape[0]),
        source_arr=src_arr,
        source_w=int(src_w or 0),
        source_h=int(src_h or 0),
        guide_arr=guide_arr,
    )
    pre["blocking"] = True
    return pre


async def run_atlas_visual_gate(
    *,
    candidate_path: str,
    source_path: str = "",
    guide_path: str = "",
) -> dict[str, Any]:
    """Pixel prefilter, then three-question VLM when configured. No VLM ≠ fake PASS."""
    from .vision_review import chat_vision, data_url_from_path

    pixel = evaluate_atlas_candidate_pixels(
        candidate_path=candidate_path,
        source_path=source_path,
        guide_path=guide_path,
    )
    if not pixel.get("ok") and pixel.get("failCode") in {
        "FAIL_CORRUPTION",
        "FAIL_TOP_DOWN",
        "FAIL_UNRELATED_SCENE",
    }:
        # Hard pixel rejects (perspective, corridor+grid) never wait for a VLM pass.
        if pixel.get("pixelKind") == "perspective_environment" or "grid" in str(pixel.get("reason") or "").lower():
            return {**pixel, "source": "pixel"}
    parts: list[dict[str, Any]] = [{"type": "text", "text": "IMAGE 1 — CANDIDATE ATLAS (judge Q1 on this image only):"}]
    url = data_url_from_path(candidate_path)
    if url:
        parts.append({"type": "image_url", "image_url": {"url": url}})
    parts.append({"type": "text", "text": "IMAGE 2 — SOURCE location (Q3 materials/identity only; may be eye-level):"})
    if source_path:
        url = data_url_from_path(source_path)
        if url:
            parts.append({"type": "image_url", "image_url": {"url": url}})
    parts.append({"type": "text", "text": "IMAGE 3 — STRUCTURAL GUIDE (Q2), if provided:"})
    if guide_path:
        url = data_url_from_path(guide_path)
        if url:
            parts.append({"type": "image_url", "image_url": {"url": url}})
    response = await chat_vision(instructions=ATLAS_GATE_INSTRUCTIONS, parts=parts)
    if not response.get("ok"):
        # No VLM: keep pixel verdict. Never fake PASS on perspective.
        return {**pixel, "source": "pixel", "vlm": str(response.get("reason") or "no_vlm")}
    parsed = parse_atlas_gate_verdict(str(response.get("output") or ""))
    parsed["blocking"] = True
    parsed["source"] = "vlm"
    if pixel.get("failCode") == "FAIL_TOP_DOWN" and parsed.get("ok"):
        # Pixel perspective hard-fail still wins — VLM must not override corridor+grid.
        return {**pixel, "source": "pixel+vlm-overruled"}
    return parsed


def evaluate_atlas_candidate_sync(**kwargs: Any) -> dict[str, Any]:
    """Sync wrapper used by API and unit tests. VLM is best-effort."""
    pixel = evaluate_atlas_candidate_pixels(**kwargs)
    try:
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            return {**pixel, "source": "pixel"}
        return asyncio.run(run_atlas_visual_gate(**kwargs))
    except Exception as exc:
        logger.info("Atlas VLM gate skipped: %s", exc)
        return {**pixel, "source": "pixel"}
