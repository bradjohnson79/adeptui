"""Normalize irregular Comfy/provider events into stable job stages."""

from __future__ import annotations

import time
from typing import Any, Callable, Awaitable

from .job_model import NormalizedStage

ProgressCallback = Callable[[float, str, str], Awaitable[None] | None]


class ProgressNormalizer:
    """Throttle + dedupe raw events into canonical stages."""

    def __init__(self, *, min_interval_sec: float = 0.35) -> None:
        self._min_interval = min_interval_sec
        self._last_emit = 0.0
        self._last_stage: str | None = None
        self._last_msg: str | None = None

    def map_comfy_message(self, raw: str, progress: float) -> tuple[NormalizedStage, float]:
        low = (raw or "").lower()
        if "queued" in low or "pending" in low:
            return NormalizedStage.QUEUED, max(0.05, min(progress, 0.25))
        if "load" in low or "model" in low:
            return NormalizedStage.LOADING_MODELS, max(0.25, min(progress, 0.4))
        if "encod" in low or "clip" in low or "text" in low:
            return NormalizedStage.ENCODING, max(0.35, min(progress, 0.5))
        if "sampl" in low or "running" in low or "execut" in low:
            return NormalizedStage.SAMPLING, max(0.45, min(progress, 0.85))
        if "decod" in low or "vae" in low:
            return NormalizedStage.DECODING, max(0.8, min(progress, 0.9))
        if "writ" in low or "saving" in low or "combine" in low:
            return NormalizedStage.WRITING_OUTPUT, max(0.88, min(progress, 0.95))
        if "done" in low or "complete" in low:
            return NormalizedStage.WRITING_OUTPUT, 0.96
        if progress >= 0.9:
            return NormalizedStage.WRITING_OUTPUT, progress
        if progress >= 0.5:
            return NormalizedStage.SAMPLING, progress
        return NormalizedStage.QUEUED, progress

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
        if (
            not force
            and stage_s == self._last_stage
            and message == self._last_msg
            and (now - self._last_emit) < self._min_interval
        ):
            return False
        if (
            not force
            and stage_s == self._last_stage
            and (now - self._last_emit) < self._min_interval
            and abs(progress - 0) >= 0
        ):
            # allow progress ticks but still throttle duplicates
            if message == self._last_msg and (now - self._last_emit) < self._min_interval:
                return False
        self._last_emit = now
        self._last_stage = stage_s
        self._last_msg = message
        if on_progress is None:
            return True
        result = on_progress(progress, message, stage_s)
        if hasattr(result, "__await__"):
            await result
        return True
