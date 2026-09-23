"""Normalize irregular Comfy/provider events into stable job stages.

Live Comfy step fractions (value/max, progress_state) are the progress authority.
Stage labels stay human-friendly but must not clamp away a live fraction for
multi-minute MiniMax / Desktop runs.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Awaitable

from .job_model import NormalizedStage

ProgressCallback = Callable[[float, str, str], Awaitable[None] | None]


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def live_fraction_from_comfy(value: float, max_value: float) -> float:
    """Comfy WS progress / progress_state value÷max → 0..1."""
    mx = float(max_value) if float(max_value or 0) > 0 else 1.0
    return clamp01(float(value or 0) / mx)


def extract_progress_state_fraction(data: dict[str, Any]) -> tuple[float, str] | None:
    """Best live fraction + label from a Comfy ``progress_state`` payload."""
    if not isinstance(data, dict):
        return None
    nodes = data.get("nodes")
    if not isinstance(nodes, dict) or not nodes:
        # Some builds put value/max on the root.
        if "value" in data and "max" in data:
            frac = live_fraction_from_comfy(data.get("value") or 0, data.get("max") or 0)
            return frac, f"Sampling step {int(float(data.get('value') or 0))}/{int(float(data.get('max') or 0) or 1)}"
        return None

    best: tuple[float, str] | None = None
    for node_id, meta in nodes.items():
        if not isinstance(meta, dict):
            continue
        state = str(meta.get("state") or meta.get("status") or "").lower()
        value = meta.get("value")
        max_v = meta.get("max")
        if value is None or max_v is None:
            continue
        try:
            frac = live_fraction_from_comfy(value, max_v)
        except Exception:
            continue
        label = f"Node {node_id} {int(float(value))}/{int(float(max_v) or 1)}"
        if state in {"running", "executing", "active", ""} or best is None:
            best = (frac, label)
            if state in {"running", "executing", "active"}:
                return best
    return best


# MiniMax Route A graph node → (progress floor, friendly label).
# Floors are minima when entering a node; live value/max fills upward and must
# never be clamped back down to these constants.
ROUTE_A_NODE_FLOOR: dict[str, tuple[float, str]] = {
    "15": (0.10, "Reading first frame"),
    "1": (0.12, "Loading MiniMax transformer"),
    "2": (0.14, "Loading MiniMax text encoder"),
    "3": (0.16, "Loading video decoder"),
    "4": (0.18, "Loading audio decoder"),
    "5": (0.22, "Encoding motion from the first frame"),
    "90": (0.24, "Applying Fast cache"),
    "10": (0.30, "Sampling video"),
    "11": (0.88, "Decoding video frames"),
    "12": (0.92, "Decoding audio"),
    "13": (0.95, "Muxing video and audio"),
    "14": (0.97, "Saving clip"),
}


def route_a_progress_from_executing(node: str | None, *, last_live: float) -> tuple[float, str]:
    """Map an executing node to a floor progress without freezing a higher live value."""
    key = str(node or "").strip()
    floor, label = ROUTE_A_NODE_FLOOR.get(key, (max(0.16, float(last_live or 0)), f"Running node {key or '?'}"))
    return max(float(last_live or 0), float(floor)), label


def route_a_progress_from_step(
    value: float,
    max_value: float,
    *,
    last_live: float,
    node: str | None = None,
) -> tuple[float, str]:
    """Map Comfy step progress into the Adept 0..1 gauge.

    Sampling (node 10 / unknown) owns the bulk of the bar. Other nodes keep the
    last live value but still advance monotonically with the step fraction when
    Comfy reports one.
    """
    frac = live_fraction_from_comfy(value, max_value)
    key = str(node or "").strip()
    if key in {"10", ""} or key not in ROUTE_A_NODE_FLOOR:
        # Primary sampling band: leave headroom for decode/mux.
        mapped = 0.30 + 0.55 * frac
    else:
        floor, _ = ROUTE_A_NODE_FLOOR[key]
        # Within-node advance up to the next known floor (approx).
        mapped = floor + (0.30 - min(floor, 0.30)) * frac if floor < 0.30 else floor + 0.05 * frac
    mapped = clamp01(max(float(last_live or 0), mapped))
    label = f"Sampling step {int(float(value or 0))}/{int(float(max_value or 0) or 1)}"
    return mapped, label


class ProgressNormalizer:
    """Throttle + dedupe raw events into canonical stages."""

    def __init__(self, *, min_interval_sec: float = 0.35) -> None:
        self._min_interval = min_interval_sec
        self._last_emit = 0.0
        self._last_stage: str | None = None
        self._last_msg: str | None = None
        self._last_progress: float = 0.0

    def _infer_stage(self, raw: str, progress: float) -> NormalizedStage:
        low = (raw or "").lower()
        if "queued" in low or "pending" in low:
            return NormalizedStage.QUEUED
        if "load" in low or "model" in low:
            return NormalizedStage.LOADING_MODELS
        if "encod" in low or "clip" in low or "text" in low:
            return NormalizedStage.ENCODING
        if "sampl" in low or "running" in low or "execut" in low or "step" in low:
            return NormalizedStage.SAMPLING
        if "decod" in low or "vae" in low:
            return NormalizedStage.DECODING
        if "writ" in low or "saving" in low or "combine" in low or "done" in low or "complete" in low:
            return NormalizedStage.WRITING_OUTPUT
        if progress >= 0.9:
            return NormalizedStage.WRITING_OUTPUT
        if progress >= 0.45:
            return NormalizedStage.SAMPLING
        return NormalizedStage.QUEUED

    def map_comfy_message(
        self,
        raw: str,
        progress: float,
        *,
        live: bool = False,
    ) -> tuple[NormalizedStage, float]:
        """Map a status message to a stage.

        When ``live=True`` (Comfy WS value/max or progress_state), the numeric
        fraction is preserved — stage ceilings must not pin e.g. 22% through a
        long encode/sample. Coarse queue-only messages still use soft bands.
        """
        stage = self._infer_stage(raw, progress)
        p = clamp01(progress)
        if live or "step" in (raw or "").lower():
            return stage, p

        low = (raw or "").lower()
        # Soft bands for coarse queue presence only — floors, not hard ceilings
        # that freeze a higher live value already stored by the caller.
        if "queued" in low or "pending" in low:
            return NormalizedStage.QUEUED, p
        if "waiting for comfy" in low:
            return NormalizedStage.QUEUED, p
        if "running in comfy" in low:
            # Keep the last grounded fraction — never invent a mid-bar percent.
            return NormalizedStage.SAMPLING, p
        if "done" in low or "complete" in low:
            return NormalizedStage.WRITING_OUTPUT, max(p, 1.0) if p >= 1.0 else p
        return stage, p

    async def emit(
        self,
        on_progress: Any,
        *,
        progress: float,
        message: str,
        stage: NormalizedStage | str,
        force: bool = False,
    ) -> bool:
        stage_s = stage.value if isinstance(stage, NormalizedStage) else str(stage)
        now = time.monotonic()
        progress = clamp01(progress)
        # Allow live % ticks even when stage/message are unchanged.
        same_text = stage_s == self._last_stage and message == self._last_msg
        tiny_delta = abs(progress - self._last_progress) < 0.002
        if (
            not force
            and same_text
            and tiny_delta
            and (now - self._last_emit) < self._min_interval
        ):
            return False
        if (
            not force
            and same_text
            and not tiny_delta
            and (now - self._last_emit) < 0.15
        ):
            # Still throttle very chatty WS floods, but keep % moving.
            return False
        self._last_emit = now
        self._last_stage = stage_s
        self._last_msg = message
        self._last_progress = progress
        if on_progress is None:
            return True
        result = on_progress(progress, message, stage_s)
        if hasattr(result, "__await__"):
            await result
        return True
