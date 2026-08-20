"""Dedicated stills-perception installer. Never Hunyuan. Never VideoChat3 dest."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .paths import COMPONENT_SPECS, STILLS_COMPONENT_IDS, stills_root

ProgressCb = Callable[[str, float, str], None]
CancelCb = Callable[[], bool]


@dataclass
class InstallResult:
    ok: bool
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)


def _download_repo(
    *,
    repo: str,
    revision: str,
    dest: Path,
    on_progress: ProgressCb | None,
    cancel_check: CancelCb | None,
) -> None:
    from huggingface_hub import HfApi, snapshot_download

    dest.mkdir(parents=True, exist_ok=True)
    if cancel_check and cancel_check():
        raise RuntimeError("Cancelled")
    if on_progress:
        on_progress("download", 0.05, f"Starting {repo}")
    try:
        files = [
            name
            for name in HfApi().list_repo_files(repo_id=repo, revision=revision)
            if name and not name.endswith("/")
        ]
    except Exception:
        files = []
    if on_progress:
        on_progress("download", 0.1, f"{len(files) or 'unknown'} files")
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            snapshot_download(
                repo_id=repo,
                revision=revision,
                local_dir=str(dest),
            )
            last_error = None
            break
        except Exception as exc:
            last_error = exc
            time.sleep(min(20.0, 1.5 * (2**attempt)))
    if last_error is not None:
        raise last_error
    if on_progress:
        on_progress("download", 1.0, f"Installed {repo}")


def install_component(
    component_id: str,
    *,
    on_progress: ProgressCb | None = None,
    cancel_check: CancelCb | None = None,
) -> InstallResult:
    if component_id not in STILLS_COMPONENT_IDS:
        return InstallResult(ok=False, message=f"Unsupported stills perception component: {component_id}")
    spec = COMPONENT_SPECS[component_id]
    dest_fn = spec["dest"]
    dest = dest_fn() if callable(dest_fn) else Path(str(dest_fn))
    stills_root().mkdir(parents=True, exist_ok=True)
    try:
        from .paths import ensure_stills_perception_venv

        venv_py = ensure_stills_perception_venv()
        if on_progress:
            on_progress("venv", 0.02, f"Isolated worker python {venv_py}")
    except Exception as exc:
        return InstallResult(ok=False, message=f"Could not create the isolated scene-perception environment: {exc}"[:300])
    try:
        _download_repo(
            repo=str(spec["repo"]),
            revision=str(spec["revision"]),
            dest=dest,
            on_progress=on_progress,
            cancel_check=cancel_check,
        )
    except Exception as exc:
        return InstallResult(ok=False, message=str(exc)[:300], evidence={"dest": str(dest)})
    markers = tuple(spec["markers"])  # type: ignore[arg-type]
    missing = [name for name in markers if not (dest / name).is_file()]
    if missing:
        return InstallResult(
            ok=False,
            message=f"Install finished but marker files are missing: {', '.join(missing)}",
            evidence={"dest": str(dest), "missing": missing},
        )
    return InstallResult(ok=True, message=f"{component_id} installed", evidence={"dest": str(dest)})
