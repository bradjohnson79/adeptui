"""Production-safe prompt library loader."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .cache import PromptFileCache
from .parser import parse_markdown_prompt
from .types import PromptRecord, PromptType
from .validator import PromptValidationIssue, validate_front_matter_dict

_PACKAGE_ROOT = Path(__file__).resolve().parent
_DEFAULT_SEARCH_DIRS: tuple[str, ...] = ("core", "specialists", "playbooks", "standards")


@dataclass
class PromptLoadDiagnostics:
    loaded: int = 0
    skipped: int = 0
    issues: list[PromptValidationIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "loaded": self.loaded,
            "skipped": self.skipped,
            "issues": [issue.to_dict() for issue in self.issues],
        }


class PromptLibrary:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or _PACKAGE_ROOT
        self._cache = PromptFileCache()
        self._by_id: dict[str, PromptRecord] = {}
        self._by_type: dict[PromptType, list[PromptRecord]] = {
            "core": [],
            "specialist": [],
            "playbook": [],
            "standard": [],
        }
        self._diagnostics = PromptLoadDiagnostics()
        self.reload()

    @property
    def diagnostics(self) -> PromptLoadDiagnostics:
        return self._diagnostics

    def reload(self) -> PromptLoadDiagnostics:
        self._by_id.clear()
        for bucket in self._by_type.values():
            bucket.clear()
        self._cache.invalidate()
        diagnostics = PromptLoadDiagnostics()
        seen_ids: set[str] = set()
        load_order = 0
        for path in self._iter_prompt_files():
            load_order += 1
            try:
                text, checksum = self._cache.read(path)
                raw, body = parse_markdown_prompt(text)
            except Exception as exc:  # noqa: BLE001
                diagnostics.skipped += 1
                diagnostics.issues.append(
                    PromptValidationIssue(str(path), f"Could not parse prompt file: {exc}")
                )
                continue
            front, issues = validate_front_matter_dict(raw, path=path, seen_ids=seen_ids)
            if front is None or issues:
                diagnostics.skipped += 1
                diagnostics.issues.extend(issues)
                continue
            record = PromptRecord(
                front_matter=front,
                body=body,
                source_path=path,
                checksum=checksum,
                load_order=load_order,
            )
            self._by_id[front.id] = record
            self._by_type[front.type].append(record)
            diagnostics.loaded += 1
        for bucket in self._by_type.values():
            bucket.sort(key=lambda r: (r.load_order, r.id))
        self._diagnostics = diagnostics
        return diagnostics

    def _iter_prompt_files(self) -> Iterable[Path]:
        for subdir in _DEFAULT_SEARCH_DIRS:
            base = self.root / subdir
            if not base.is_dir():
                continue
            yield from sorted(base.glob("*.md"))

    def get(self, prompt_id: str) -> PromptRecord | None:
        return self._by_id.get(prompt_id)

    def require(self, prompt_id: str) -> PromptRecord:
        record = self.get(prompt_id)
        if record is None:
            raise KeyError(prompt_id)
        return record

    def by_type(self, prompt_type: PromptType) -> tuple[PromptRecord, ...]:
        return tuple(self._by_type.get(prompt_type, []))

    def all_records(self) -> tuple[PromptRecord, ...]:
        return tuple(sorted(self._by_id.values(), key=lambda r: r.load_order))

    def version_map(self) -> dict[str, str]:
        return {record.id: record.front_matter.version for record in self.all_records()}


_default_library: PromptLibrary | None = None


def get_prompt_library() -> PromptLibrary:
    global _default_library
    if _default_library is None:
        _default_library = PromptLibrary()
    return _default_library
