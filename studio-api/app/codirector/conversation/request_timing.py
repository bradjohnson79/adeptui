"""Per-request stage timing ledger for Co-Director (sanitized for SSE/diagnostics)."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field


class StageTiming(BaseModel):
    stageId: str
    startedAtMs: float
    endedAtMs: float | None = None
    elapsedMs: float | None = None
    cacheHit: bool | None = None
    inputBytes: int | None = None
    outputBytes: int | None = None
    failed: bool = False
    error: str | None = None


class TokenBuckets(BaseModel):
    system: int = 0
    relationship: int = 0
    projectCache: int = 0
    targetedRetrieval: int = 0
    conversation: int = 0
    toolSchemas: int = 0
    total: int = 0


class CoDirectorRequestTiming(BaseModel):
    requestId: str
    projectId: str | None = None
    startedAtMs: float = Field(default_factory=lambda: time.perf_counter() * 1000)
    stages: list[StageTiming] = Field(default_factory=list)
    tokenBuckets: TokenBuckets = Field(default_factory=TokenBuckets)
    firstProviderTokenMs: float | None = None
    firstSseTokenMs: float | None = None
    cacheHit: bool | None = None
    complexity: str | None = None
    deferEnrichment: bool = False
    streamed: bool = False

    def start_stage(self, stage_id: str) -> None:
        now = time.perf_counter() * 1000
        self.stages.append(StageTiming(stageId=stage_id, startedAtMs=now))

    def end_stage(
        self,
        stage_id: str,
        *,
        cache_hit: bool | None = None,
        input_bytes: int | None = None,
        output_bytes: int | None = None,
        failed: bool = False,
        error: str | None = None,
    ) -> None:
        now = time.perf_counter() * 1000
        for stage in reversed(self.stages):
            if stage.stageId == stage_id and stage.endedAtMs is None:
                stage.endedAtMs = now
                stage.elapsedMs = round(now - stage.startedAtMs, 1)
                if cache_hit is not None:
                    stage.cacheHit = cache_hit
                if input_bytes is not None:
                    stage.inputBytes = input_bytes
                if output_bytes is not None:
                    stage.outputBytes = output_bytes
                stage.failed = failed
                stage.error = (error or "")[:200] or None
                return
        # Stage never started — record closed sample.
        self.stages.append(
            StageTiming(
                stageId=stage_id,
                startedAtMs=now,
                endedAtMs=now,
                elapsedMs=0.0,
                cacheHit=cache_hit,
                inputBytes=input_bytes,
                outputBytes=output_bytes,
                failed=failed,
                error=(error or "")[:200] or None,
            )
        )

    def mark_first_token(self) -> None:
        if self.firstSseTokenMs is None:
            self.firstSseTokenMs = round(time.perf_counter() * 1000 - self.startedAtMs, 1)
            self.firstProviderTokenMs = self.firstSseTokenMs

    def to_public_dict(self) -> dict[str, Any]:
        """Sanitized timings — never includes prompt text."""
        return {
            "requestId": self.requestId,
            "projectId": self.projectId,
            "complexity": self.complexity,
            "deferEnrichment": self.deferEnrichment,
            "streamed": self.streamed,
            "cacheHit": self.cacheHit,
            "firstSseTokenMs": self.firstSseTokenMs,
            "tokenBuckets": self.tokenBuckets.model_dump(mode="json"),
            "stages": [
                {
                    "stageId": s.stageId,
                    "elapsedMs": s.elapsedMs,
                    "cacheHit": s.cacheHit,
                    "failed": s.failed,
                }
                for s in self.stages
                if s.elapsedMs is not None or s.failed
            ],
        }


def estimate_tokens(text: str) -> int:
    return max(1, len(text or "") // 4) if (text or "").strip() else 0
