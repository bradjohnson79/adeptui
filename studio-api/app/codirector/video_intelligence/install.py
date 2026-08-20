"""Hugging Face snapshot install for video-understanding models. Download once."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .paths import (
    INTERNVIDEO3_HF_ID,
    INTERNVIDEO3_REVISION,
    VIDEOCHAT3_HF_ID,
    VIDEOCHAT3_REVISION,
    internvideo3_dir,
    model_present,
    videochat3_dir,
)

ProgressCb = Callable[[str, float, str], None]
CancelCb = Callable[[], bool]


@dataclass
class InstallResult:
    ok: bool
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)


_SPECS = {
    "videochat3_4b": {
        "repo": VIDEOCHAT3_HF_ID,
        "revision": VIDEOCHAT3_REVISION,
        "dest": videochat3_dir,
        "markers": ("config.json", "model.safetensors.index.json"),
    },
    "internvideo3_8b": {
        "repo": INTERNVIDEO3_HF_ID,
        "revision": INTERNVIDEO3_REVISION,
        "dest": internvideo3_dir,
        "markers": ("config.json", "model.safetensors.index.json"),
    },
}


def install_component(
    component_id: str,
    *,
    on_progress: ProgressCb | None = None,
    cancel_check: CancelCb | None = None,
    local_dir: str | None = None,
) -> InstallResult:
    spec = _SPECS.get(component_id)
    if spec is None:
        return InstallResult(False, f"unsupported component {component_id}")
    dest = Path(local_dir) if local_dir else spec["dest"]()
    dest.mkdir(parents=True, exist_ok=True)
    if model_present(dest, spec["markers"]):
        if on_progress:
            on_progress("verify", 1.0, "Existing weights reused")
        return InstallResult(
            True,
            "Existing video-understanding weights reused.",
            {"localDir": str(dest), "reused": True, "revision": spec["revision"]},
        )
    if cancel_check and cancel_check():
        return InstallResult(False, "Cancelled")
    try:
        from huggingface_hub import snapshot_download
    except Exception as exc:
        return InstallResult(False, f"huggingface_hub unavailable: {exc}")
    if on_progress:
        on_progress("download", 0.05, f"Downloading {spec['repo']}")
    try:
        try:
            snapshot_download(
                repo_id=spec["repo"],
                revision=spec["revision"],
                local_dir=str(dest),
                resume_download=True,
                local_files_only=True,
            )
        except Exception:
            snapshot_download(
                repo_id=spec["repo"],
                revision=spec["revision"],
                local_dir=str(dest),
                resume_download=True,
            )
    except Exception as exc:
        return InstallResult(False, str(exc)[:800], {"localDir": str(dest)})
    if not model_present(dest, spec["markers"]):
        return InstallResult(False, "Download finished but required weight files are missing.", {"localDir": str(dest)})
    if on_progress:
        on_progress("verify", 1.0, "Weights verified")
    return InstallResult(
        True,
        f"{component_id} installed.",
        {"localDir": str(dest), "reused": False, "revision": spec["revision"]},
    )
