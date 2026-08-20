"""Dedicated stills-perception HF installer. Never Hunyuan. Never VideoChat3."""

from __future__ import annotations

from typing import Any

from .base import DownloadCapabilities, DownloadExecutionContext, DownloadExecutionResult


class StillsPerceptionExecutor:
    provider_id = "stills_perception_hf"

    def get_capabilities(self, plan: dict[str, Any]) -> DownloadCapabilities:
        return DownloadCapabilities(
            can_pause=False,
            can_resume=True,
            can_cancel=True,
            supports_range_requests=True,
            message="Official Hugging Face install into the isolated stills-perception directory.",
        )

    def cancel(self, operation: dict[str, Any]) -> None:
        return None

    def execute(
        self, plan: dict[str, Any], context: DownloadExecutionContext
    ) -> DownloadExecutionResult:
        component_id = str(plan.get("componentId") or (plan.get("metadata") or {}).get("componentId") or "")
        from ....codirector.perception.paths import STILLS_COMPONENT_IDS
        from ....codirector.perception.install import install_component

        if component_id not in STILLS_COMPONENT_IDS:
            return DownloadExecutionResult(
                ok=False,
                phase="failed",
                message=f"stills_perception_hf does not support {component_id!r}",
                error_category="unsupported_component",
            )

        def on_progress(phase: str, frac: float, message: str) -> None:
            if context.on_progress:
                total = int(plan.get("estimatedDownloadBytes") or 1_500_000_000)
                context.on_progress(int(max(0.0, min(1.0, frac)) * total), total)

        result = install_component(
            component_id,
            on_progress=on_progress,
            cancel_check=lambda: context.cancel_event.is_set(),
        )
        if context.cancel_event.is_set() and not result.ok:
            return DownloadExecutionResult(ok=False, phase="cancelled", message="Cancelled", error_category="cancelled")
        if not result.ok:
            return DownloadExecutionResult(
                ok=False,
                phase="failed",
                message=result.message,
                error_category="install_failed",
            )
        return DownloadExecutionResult(ok=True, phase="completed", message=result.message)
