"""Checksum cache keyed by prompt file mtime."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class _CacheEntry:
    mtime_ns: int
    checksum: str
    text: str


class PromptFileCache:
    def __init__(self) -> None:
        self._entries: dict[str, _CacheEntry] = {}

    @staticmethod
    def checksum(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def read(self, path: Path) -> tuple[str, str]:
        key = str(path.resolve())
        stat = path.stat()
        mtime_ns = stat.st_mtime_ns
        cached = self._entries.get(key)
        if cached is not None and cached.mtime_ns == mtime_ns:
            return cached.text, cached.checksum
        text = path.read_text(encoding="utf-8")
        digest = self.checksum(text)
        self._entries[key] = _CacheEntry(mtime_ns=mtime_ns, checksum=digest, text=text)
        return text, digest

    def invalidate(self, path: Path | None = None) -> None:
        if path is None:
            self._entries.clear()
            return
        self._entries.pop(str(path.resolve()), None)
