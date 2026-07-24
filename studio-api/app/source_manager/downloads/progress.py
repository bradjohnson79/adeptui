"""Rolling-window speed and ETA (real bytes only — never simulated)."""

from __future__ import annotations

import time
from collections import deque
from typing import Any


class ProgressTracker:
    """Track bytes with a rolling window for smoothed speed/ETA."""

    def __init__(self, window_seconds: float = 8.0, min_samples: int = 3) -> None:
        self.window_seconds = window_seconds
        self.min_samples = min_samples
        self._samples: deque[tuple[float, int]] = deque()
        self.bytes_downloaded = 0
        self.bytes_total: int | None = None
        self._paused = False

    def set_total(self, total: int | None) -> None:
        if total is not None and total >= 0:
            self.bytes_total = int(total)

    def reset_samples(self) -> None:
        self._samples.clear()

    def pause(self) -> None:
        self._paused = True
        self.reset_samples()

    def resume(self) -> None:
        self._paused = False
        self.reset_samples()

    def update(self, bytes_downloaded: int, *, now: float | None = None) -> dict[str, Any]:
        if self._paused:
            return self.snapshot()
        ts = time.monotonic() if now is None else now
        self.bytes_downloaded = max(0, int(bytes_downloaded))
        self._samples.append((ts, self.bytes_downloaded))
        cutoff = ts - self.window_seconds
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()
        return self.snapshot()

    def speed(self) -> float | None:
        if len(self._samples) < self.min_samples:
            return None
        t0, b0 = self._samples[0]
        t1, b1 = self._samples[-1]
        dt = t1 - t0
        if dt <= 0.25:
            return None
        delta = b1 - b0
        if delta < 0:
            return None
        return delta / dt

    def eta_seconds(self) -> float | None:
        if self.bytes_total is None or self.bytes_total <= 0:
            return None
        spd = self.speed()
        if spd is None or spd <= 0:
            return None
        remaining = self.bytes_total - self.bytes_downloaded
        if remaining <= 0:
            return 0.0
        eta = remaining / spd
        return max(0.0, eta)

    def percent(self) -> float:
        if self.bytes_total and self.bytes_total > 0:
            return max(0.0, min(100.0, (self.bytes_downloaded / self.bytes_total) * 100.0))
        return 0.0

    def snapshot(self) -> dict[str, Any]:
        spd = self.speed()
        eta = self.eta_seconds()
        return {
            "bytesDownloaded": self.bytes_downloaded,
            "bytesTotal": self.bytes_total,
            "percent": round(self.percent(), 2),
            "speedBytesPerSecond": None if spd is None else round(spd, 2),
            "etaSeconds": None if eta is None else int(round(eta)),
        }


def format_speed(bps: float | None) -> str | None:
    if bps is None:
        return None
    if bps < 1024:
        return f"{bps:.0f} B/s"
    if bps < 1024**2:
        return f"{bps / 1024:.1f} KB/s"
    if bps < 1024**3:
        return f"{bps / (1024**2):.1f} MB/s"
    return f"{bps / (1024**3):.2f} GB/s"


def format_eta(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    sec = int(seconds)
    if sec < 60:
        return "Less than a minute"
    minutes = sec // 60
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    hours = minutes // 60
    rem = minutes % 60
    if rem:
        return f"{hours} hour{'s' if hours != 1 else ''} {rem} minutes"
    return f"{hours} hour{'s' if hours != 1 else ''}"
