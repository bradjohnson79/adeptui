"""Hugging Face snapshot download executor — Qwen voice + Hunyuan video (official repos only)."""

from __future__ import annotations

from typing import Any

from .base import DownloadCapabilities, DownloadExecutionContext, DownloadExecutionResult

_HUNYUAN_COMPONENTS = frozenset({"hunyuan_video_15", "hunyuan_video_13b"})
_VOICE_COMPONENTS = frozenset({"qwen_voice_design_17b", "qwen_voice_clone_17b"})
_VIDEO_UNDERSTANDING_COMPONENTS = frozenset({"videochat3_4b", "internvideo3_8b"})


class HuggingFaceSnapshotExecutor:
    """Runs HF snapshot installs for approved component IDs only."""

    provider_id = "huggingface_snapshot"

    def get_capabilities(self, plan: dict[str, Any]) -> DownloadCapabilities:
        component_id = str(plan.get("componentId") or (plan.get("metadata") or {}).get("componentId") or "")
        resume = component_id in _HUNYUAN_COMPONENTS
        return DownloadCapabilities(
            can_pause=False,
            can_resume=resume,
            can_cancel=True,
            supports_range_requests=resume,
            message=(
                "Official Hugging Face snapshot install. Hunyuan downloads resume from partial local files."
                if resume
                else "Hugging Face snapshot install. Cancel stops the worker; partial downloads are detected on retry."
            ),
        )

    def cancel(self, operation: dict[str, Any]) -> None:
        return None

    def execute(
        self, plan: dict[str, Any], context: DownloadExecutionContext
    ) -> DownloadExecutionResult:
        component_id = str(plan.get("componentId") or (plan.get("metadata") or {}).get("componentId") or "")
        if component_id in _VOICE_COMPONENTS:
            return self._execute_voice(component_id, plan, context)
        if component_id in _HUNYUAN_COMPONENTS:
            return self._execute_hunyuan(component_id, plan, context)
        if component_id in _VIDEO_UNDERSTANDING_COMPONENTS:
            return self._execute_video_understanding(component_id, plan, context)
        return DownloadExecutionResult(
            ok=False,
            phase="failed",
            message=f"huggingface_snapshot executor does not support component {component_id!r}",
            error_category="unsupported_component",
        )

    def _execute_voice(
        self, component_id: str, plan: dict[str, Any], context: DownloadExecutionContext
    ) -> DownloadExecutionResult:
        from ....codirector.m210b.qwen_voice_install import install_component

        def on_progress(phase: str, frac: float, message: str) -> None:
            if context.on_progress:
                total = int((plan.get("estimatedDownloadBytes") or 3_500_000_000))
                downloaded = int(max(0.0, min(1.0, frac)) * total)
                context.on_progress(downloaded, total)

        result = install_component(
            component_id,
            on_progress=on_progress,
            cancel_check=lambda: context.cancel_event.is_set(),
        )
        if context.cancel_event.is_set() and not result.ok:
            return DownloadExecutionResult(
                ok=False,
                phase="cancelled",
                message="Cancelled",
                error_category="cancelled",
            )
        if not result.ok:
            return DownloadExecutionResult(
                ok=False,
                phase="failed",
                message=result.message[:800],
                error_category="provider_error",
                error={"evidence": result.evidence},
            )
        bytes_dl = int((result.evidence.get("weights") or {}).get("diskUsageBytes") or 0)
        return DownloadExecutionResult(
            ok=True,
            phase="completed",
            message="Qwen voice model installed and runtime-ready",
            bytes_downloaded=bytes_dl,
            files=[
                {
                    "path": (result.evidence.get("manifest") or {}).get("modelsDir"),
                    "role": "weights",
                }
            ],
        )

    def _execute_hunyuan(
        self, component_id: str, plan: dict[str, Any], context: DownloadExecutionContext
    ) -> DownloadExecutionResult:
        from ....video_runtime.hunyuan_install import install_component

        def on_progress(phase: str, frac: float, message: str) -> None:
            if context.on_progress:
                total = int((plan.get("estimatedDownloadBytes") or 45_000_000_000))
                downloaded = int(max(0.0, min(1.0, frac)) * total)
                context.on_progress(downloaded, total)

        result = install_component(
            component_id,
            on_progress=on_progress,
            cancel_check=lambda: context.cancel_event.is_set(),
            force=False,
        )
        if context.cancel_event.is_set() and not result.ok:
            return DownloadExecutionResult(
                ok=False,
                phase="cancelled",
                message="Cancelled",
                error_category="cancelled",
            )
        if not result.ok:
            return DownloadExecutionResult(
                ok=False,
                phase="failed",
                message=result.message[:800],
                error_category="provider_error",
                error={"evidence": result.evidence, "fakeSuccess": False},
            )
        bytes_dl = int((result.evidence.get("weights") or {}).get("diskUsageBytes") or 0)
        return DownloadExecutionResult(
            ok=True,
            phase="completed",
            message=result.message,
            bytes_downloaded=bytes_dl,
            files=[{"path": (result.evidence.get("status") or {}).get("localDir"), "role": "weights"}],
        )

    def _execute_video_understanding(
        self, component_id: str, plan: dict[str, Any], context: DownloadExecutionContext
    ) -> DownloadExecutionResult:
        from ....codirector.video_intelligence.install import install_component

        def on_progress(phase: str, frac: float, message: str) -> None:
            if context.on_progress:
                total = int((plan.get("estimatedDownloadBytes") or 9_000_000_000))
                downloaded = int(max(0.0, min(1.0, frac)) * total)
                context.on_progress(downloaded, total)

        result = install_component(
            component_id,
            on_progress=on_progress,
            cancel_check=lambda: context.cancel_event.is_set(),
        )
        if context.cancel_event.is_set() and not result.ok:
            return DownloadExecutionResult(
                ok=False,
                phase="cancelled",
                message="Cancelled",
                error_category="cancelled",
            )
        if not result.ok:
            return DownloadExecutionResult(
                ok=False,
                phase="failed",
                message=result.message[:800],
                error_category="provider_error",
                error={"evidence": result.evidence},
            )
        return DownloadExecutionResult(
            ok=True,
            phase="completed",
            message=result.message,
            files=[{"path": result.evidence.get("localDir"), "role": "weights"}],
        )
