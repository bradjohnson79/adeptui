"""Storage classes: core / shared_optional / private with reference counting."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import settings


def _root() -> Path:
    base = Path(getattr(settings, "data_dir", None) or Path(__file__).resolve().parents[3] / "data")
    root = base / "docker_runtime"
    (root / "private").mkdir(parents=True, exist_ok=True)
    (root / "shared_optional").mkdir(parents=True, exist_ok=True)
    (root / "core").mkdir(parents=True, exist_ok=True)
    return root


def private_path(runtime_id: str) -> Path:
    p = _root() / "private" / runtime_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def shared_optional_path() -> Path:
    return _root() / "shared_optional"


def core_path() -> Path:
    return _root() / "core"


def _refs_file() -> Path:
    return _root() / "shared_refs.json"


def load_refs() -> dict[str, int]:
    path = _refs_file()
    if not path.exists():
        return {}
    try:
        return {str(k): int(v) for k, v in json.loads(path.read_text(encoding="utf-8")).items()}
    except Exception:
        return {}


def save_refs(refs: dict[str, int]) -> None:
    _refs_file().write_text(json.dumps(refs, indent=2), encoding="utf-8")


def acquire_shared(artifact_id: str) -> int:
    refs = load_refs()
    refs[artifact_id] = refs.get(artifact_id, 0) + 1
    save_refs(refs)
    return refs[artifact_id]


def release_shared(artifact_id: str) -> int:
    refs = load_refs()
    cur = max(0, refs.get(artifact_id, 0) - 1)
    if cur == 0:
        refs.pop(artifact_id, None)
    else:
        refs[artifact_id] = cur
    save_refs(refs)
    return cur


def can_delete_shared(artifact_id: str) -> bool:
    return load_refs().get(artifact_id, 0) <= 0


def dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def remove_private(runtime_id: str) -> dict[str, Any]:
    import shutil

    p = private_path(runtime_id)
    if p.exists():
        shutil.rmtree(p, ignore_errors=True)
    return {"removed": str(p), "ok": not p.exists()}
