"""Local folder copy / link executor."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .base import DownloadCapabilities, DownloadExecutionContext, DownloadExecutionResult


class LocalCopyExecutor:
    provider_id = "local_folder"

    def get_capabilities(self, plan: dict[str, Any]) -> DownloadCapabilities:
        return DownloadCapabilities(
            can_pause=False,
            can_resume=False,
            message="Pause is not supported for local copy operations.",
        )

    def cancel(self, operation: dict[str, Any]) -> None:
        return None

    def execute(
        self, plan: dict[str, Any], context: DownloadExecutionContext
    ) -> DownloadExecutionResult:
        src = Path(str((plan.get("metadata") or {}).get("localPath") or plan.get("destinationRoot") or ""))
        # For link-style: metadata.mode == link_existing → no copy
        mode = (plan.get("metadata") or {}).get("mode") or "copy"
        if mode == "link_existing":
            if not src.is_dir():
                return DownloadExecutionResult(
                    ok=False,
                    phase="failed",
                    message="Linked path is not a directory.",
                    error_category="validation_failed",
                )
            files = []
            for child in list(src.iterdir())[:200]:
                if child.is_file():
                    files.append(
                        {
                            "relativePath": child.name,
                            "size": child.stat().st_size,
                            "ownership": "preexisting",
                            "role": "unknown",
                        }
                    )
            return DownloadExecutionResult(
                ok=True,
                phase="installed",
                message="Linked existing folder.",
                files=files,
            )
        dest = Path(str(plan.get("destinationRoot") or ""))
        if not src.exists():
            return DownloadExecutionResult(
                ok=False, phase="failed", message="Source path missing.", error_category="source_missing"
            )
        dest.mkdir(parents=True, exist_ok=True)
        copied = 0
        files = []
        paths = [src] if src.is_file() else list(src.rglob("*"))
        for path in paths:
            if context.cancel_event.is_set():
                return DownloadExecutionResult(
                    ok=False, phase="cancelled", message="Cancelled", error_category="cancelled"
                )
            if not path.is_file():
                continue
            rel = path.name if src.is_file() else str(path.relative_to(src))
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            size = target.stat().st_size
            copied += size
            if context.on_progress:
                context.on_progress(copied, None)
            files.append(
                {
                    "relativePath": rel,
                    "size": size,
                    "ownership": "installed_by_adept",
                }
            )
        return DownloadExecutionResult(
            ok=True, phase="installed", message="Local copy complete.", files=files, bytes_downloaded=copied
        )
