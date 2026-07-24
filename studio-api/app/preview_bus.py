from __future__ import annotations

"""Live generation preview bus + cache (honest intermediates only)."""

import asyncio
import json
import shutil
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from .config import settings

PREVIEW_CACHE = settings.data_dir / "preview_cache"
DEFAULT_CACHE_LIMIT_GB = 5.0


@dataclass
class GenerationPreview:
    jobId: str
    sceneId: str
    engineId: str
    previewId: str
    sequenceNumber: int
    createdAt: str
    stage: str
    progress: Optional[float] = None
    frameIndex: Optional[int] = None
    segmentIndex: Optional[int] = None
    totalSegments: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    mediaType: str = "image"  # image | video
    sourceUrl: Optional[str] = None
    localPath: Optional[str] = None
    temporary: bool = True


@dataclass
class EngineCapabilities:
    supportsLivePreview: bool = False
    previewMode: Optional[str] = None  # frames | partial-video | segments | provider-thumbnail
    supportsPreviewProgress: bool = False
    supportsPreviewStreaming: bool = False


ENGINE_CAPS: dict[str, EngineCapabilities] = {
    "ltx": EngineCapabilities(True, "frames", True, True),
    "wan": EngineCapabilities(True, "frames", True, True),
    "fal_seedance": EngineCapabilities(False, "provider-thumbnail", True, False),
    "fal_kling": EngineCapabilities(False, "provider-thumbnail", True, False),
    "fal_veo": EngineCapabilities(False, "provider-thumbnail", True, False),
    "fal_runway": EngineCapabilities(False, "provider-thumbnail", True, False),
    "auto": EngineCapabilities(False, None, False, False),
}


class PreviewBus:
    def __init__(self) -> None:
        self._latest: dict[str, GenerationPreview] = {}  # jobId -> preview
        self._subscribers: list[asyncio.Queue] = []
        self._lock = asyncio.Lock()

    def capabilities_for(self, engine: str) -> dict[str, Any]:
        caps = ENGINE_CAPS.get(engine, EngineCapabilities())
        return asdict(caps)

    async def publish(self, event: str, preview: GenerationPreview | None, extra: dict | None = None) -> None:
        payload = {
            "event": event,
            "preview": asdict(preview) if preview else None,
            "extra": extra or {},
            "ts": time.time(),
        }
        if preview:
            prev = self._latest.get(preview.jobId)
            if prev and prev.sequenceNumber > preview.sequenceNumber:
                return  # ignore stale
            self._latest[preview.jobId] = preview
        dead: list[asyncio.Queue] = []
        for q in self._subscribers:
            try:
                q.put_nowait(payload)
            except Exception:
                dead.append(q)
        for q in dead:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=64)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    def latest_for_job(self, job_id: str) -> Optional[GenerationPreview]:
        return self._latest.get(job_id)

    def clear_job(self, job_id: str) -> None:
        self._latest.pop(job_id, None)

    def job_dir(self, job_id: str) -> Path:
        d = PREVIEW_CACHE / job_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_bytes(self, job_id: str, data: bytes, ext: str = ".png") -> Path:
        path = self.job_dir(job_id) / f"preview_{uuid.uuid4().hex[:10]}{ext}"
        path.write_bytes(data)
        return path

    def purge_job(self, job_id: str) -> None:
        d = PREVIEW_CACHE / job_id
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
        self.clear_job(job_id)

    def purge_abandoned(self, max_age_sec: float = 86400) -> int:
        PREVIEW_CACHE.mkdir(parents=True, exist_ok=True)
        removed = 0
        now = time.time()
        for child in PREVIEW_CACHE.iterdir():
            if not child.is_dir():
                continue
            try:
                age = now - child.stat().st_mtime
                if age > max_age_sec:
                    shutil.rmtree(child, ignore_errors=True)
                    removed += 1
            except Exception:
                pass
        return removed

    def enforce_cache_limit(self, limit_gb: float = DEFAULT_CACHE_LIMIT_GB) -> None:
        PREVIEW_CACHE.mkdir(parents=True, exist_ok=True)
        dirs = sorted(
            [p for p in PREVIEW_CACHE.iterdir() if p.is_dir()],
            key=lambda p: p.stat().st_mtime,
        )
        total = 0
        sizes: list[tuple[Path, int]] = []
        for d in dirs:
            size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
            sizes.append((d, size))
            total += size
        limit = int(limit_gb * 1024**3)
        while total > limit and sizes:
            d, size = sizes.pop(0)
            shutil.rmtree(d, ignore_errors=True)
            total -= size


preview_bus = PreviewBus()
