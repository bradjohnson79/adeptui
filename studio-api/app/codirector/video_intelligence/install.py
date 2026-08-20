"""Hugging Face snapshot install for video-understanding models. Download once."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .paths import (
    INTERNVIDEO3_HF_ID,
    INTERNVIDEO3_REVISION,
    VIDEOCHAT3_HF_ID,
    VIDEOCHAT3_REPO_FILES,
    VIDEOCHAT3_REVISION,
    VIDEOCHAT3_WEIGHT_BYTES,
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


def _download_repo_sequential(
    *,
    repo: str,
    revision: str,
    dest: Path,
    on_progress: ProgressCb | None,
    cancel_check: CancelCb | None,
) -> None:
    """Download one file at a time. Parallel snapshot_download resets this host's HF connections."""
    from huggingface_hub import HfApi, hf_hub_download

    files: list[str] = []
    if repo == VIDEOCHAT3_HF_ID:
        files = list(VIDEOCHAT3_REPO_FILES)
    else:
        try:
            files = [
                name
                for name in HfApi().list_repo_files(repo_id=repo, revision=revision)
                if name and not name.endswith("/")
            ]
        except Exception:
            files = []
    if not files:
        raise RuntimeError("HF_REPO_FILE_LIST_EMPTY")
    total = len(files)
    for index, name in enumerate(files, start=1):
        if cancel_check and cancel_check():
            raise RuntimeError("Cancelled")
        target = dest / name
        expected_size = VIDEOCHAT3_WEIGHT_BYTES.get(name)
        if target.is_file() and target.stat().st_size > 0:
            if expected_size is None or target.stat().st_size == expected_size:
                if on_progress:
                    on_progress("download", index / total, f"Reused {name} ({index}/{total})")
                continue
        last_error: Exception | None = None
        for attempt in range(6):
            try:
                hf_hub_download(
                    repo_id=repo,
                    filename=name,
                    revision=revision,
                    local_dir=str(dest),
                )
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                time.sleep(min(30.0, 1.5 * (2**attempt)))
        if last_error is not None:
            raise last_error
        if on_progress:
            on_progress("download", index / total, f"Downloaded {name} ({index}/{total})")


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
        reuse_evidence: dict[str, Any] = {"localDir": str(dest), "reused": True, "revision": spec["revision"]}
        if component_id == "videochat3_4b":
            from .paths import poll_safe_integrity

            integrity = poll_safe_integrity(dest)
            reuse_evidence["integrity"] = integrity
            if not integrity.get("ok"):
                reuse_evidence["reused"] = False
            else:
                if on_progress:
                    on_progress("verify", 1.0, "Existing weights reused")
                return InstallResult(
                    True,
                    "Existing video-understanding weights reused.",
                    reuse_evidence,
                )
        else:
            if on_progress:
                on_progress("verify", 1.0, "Existing weights reused")
            return InstallResult(
                True,
                "Existing video-understanding weights reused.",
                reuse_evidence,
            )
    if cancel_check and cancel_check():
        return InstallResult(False, "Cancelled")
    try:
        import huggingface_hub  # noqa: F401
    except Exception as exc:
        return InstallResult(False, f"huggingface_hub unavailable: {exc}")
    if on_progress:
        on_progress("download", 0.02, f"Listing {spec['repo']}")
    try:
        _download_repo_sequential(
            repo=spec["repo"],
            revision=spec["revision"],
            dest=dest,
            on_progress=on_progress,
            cancel_check=cancel_check,
        )
    except Exception as exc:
        return InstallResult(False, str(exc)[:800], {"localDir": str(dest)})
    if not model_present(dest, spec["markers"]):
        return InstallResult(False, "Download finished but required weight files are missing.", {"localDir": str(dest)})
    evidence: dict[str, Any] = {"localDir": str(dest), "reused": False, "revision": spec["revision"]}
    if component_id == "videochat3_4b":
        from .paths import poll_safe_integrity, verify_weight_sha256

        integrity = poll_safe_integrity(dest)
        evidence["integrity"] = integrity
        if not integrity.get("ok"):
            return InstallResult(False, f"Integrity check failed: {integrity.get('reason')}", evidence)
        if on_progress:
            on_progress("verify", 0.7, "Hashing weight shards")
        evidence["weightSha"] = verify_weight_sha256(dest)
        if not evidence["weightSha"].get("ok"):
            return InstallResult(False, f"Weight SHA failed: {evidence['weightSha'].get('reason')}", evidence)
    if on_progress:
        on_progress("verify", 1.0, "Weights verified")
    return InstallResult(
        True,
        f"{component_id} installed.",
        evidence,
    )
