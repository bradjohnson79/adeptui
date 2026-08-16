"""Vision Validation Engine — orchestrates QA checks and produces ValidationResult."""

from __future__ import annotations

import time
from typing import Any, Optional

from . import ValidationCheck, ValidationResult, ValidationStatus


class VisionValidationEngine:
    """Orchestrates the full vision validation pipeline for a media asset.

    Runs available QA checks (image, video, frame, continuity, lip-sync)
    based on the asset type and available dependencies.
    Returns a structured ValidationResult that is advisory only —
    human authority is absolute.
    """

    def __init__(self) -> None:
        self._feature_enabled = False

    @property
    def enabled(self) -> bool:
        return self._feature_enabled

    def set_enabled(self, enabled: bool) -> None:
        self._feature_enabled = enabled

    def validate_image(
        self,
        asset_id: str,
        asset_path: str,
        *,
        project_id: Optional[str] = None,
    ) -> ValidationResult:
        """Run Image QA against a single image asset."""
        checks: list[ValidationCheck] = []
        start = time.monotonic()

        if not self._feature_enabled:
            return ValidationResult(
                asset_id=asset_id,
                overall_status=ValidationStatus.SKIPPED,
                checks=[],
                asset_type="image",
                errors=["Vision Validation feature flag is off"],
            )

        # Image QA checks
        checks.append(ValidationCheck(
            name="prompt_adherence",
            status=ValidationStatus.NOT_APPLICABLE,
            confidence=0.0,
            details="Requires prompt reference — available in Timeline context",
            category="adherence",
        ))
        checks.append(ValidationCheck(
            name="composition",
            status=ValidationStatus.NOT_APPLICABLE,
            confidence=0.0,
            details="Composition analysis requires VLM model — not yet wired",
            category="quality",
        ))
        checks.append(ValidationCheck(
            name="generation_artifacts",
            status=ValidationStatus.NOT_APPLICABLE,
            confidence=0.0,
            details="Artifact detection requires VLM model — not yet wired",
            category="quality",
        ))

        elapsed = int((time.monotonic() - start) * 1000)
        return ValidationResult(
            asset_id=asset_id,
            overall_status=ValidationStatus.NOT_APPLICABLE,
            overall_confidence=1.0,
            checks=checks,
            asset_type="image",
            duration_ms=elapsed,
        )

    def validate_video(
        self,
        asset_id: str,
        asset_path: str,
        *,
        project_id: Optional[str] = None,
    ) -> ValidationResult:
        """Run Video QA against a video asset, including frame-by-frame checks."""
        checks: list[ValidationCheck] = []
        start = time.monotonic()

        if not self._feature_enabled:
            return ValidationResult(
                asset_id=asset_id,
                overall_status=ValidationStatus.SKIPPED,
                checks=[],
                asset_type="video",
                errors=["Vision Validation feature flag is off"],
            )

        checks.append(ValidationCheck(
            name="frame_continuity",
            status=ValidationStatus.NOT_APPLICABLE,
            confidence=0.0,
            details="Frame continuity requires frame extraction — not yet wired",
            category="quality",
        ))
        checks.append(ValidationCheck(
            name="generation_artifacts",
            status=ValidationStatus.NOT_APPLICABLE,
            confidence=0.0,
            details="Artifact detection requires VLM model — not yet wired",
            category="quality",
        ))

        elapsed = int((time.monotonic() - start) * 1000)
        return ValidationResult(
            asset_id=asset_id,
            overall_status=ValidationStatus.NOT_APPLICABLE,
            overall_confidence=1.0,
            checks=checks,
            asset_type="video",
            duration_ms=elapsed,
        )

    def validate_continuity(
        self,
        asset_id: str,
        asset_path: str,
        *,
        project_id: Optional[str] = None,
        character_ids: Optional[list[str]] = None,
    ) -> ValidationResult:
        """Run continuity analysis against Production Bible / character data."""
        checks: list[ValidationCheck] = []
        start = time.monotonic()

        if not self._feature_enabled:
            return ValidationResult(
                asset_id=asset_id,
                overall_status=ValidationStatus.SKIPPED,
                checks=[],
                asset_type="image",
                errors=["Vision Validation feature flag is off"],
            )

        checks.append(ValidationCheck(
            name="character_continuity",
            status=ValidationStatus.NOT_APPLICABLE,
            confidence=0.0,
            details="Character continuity requires VLM + Bible data — not yet wired",
            category="continuity",
        ))
        checks.append(ValidationCheck(
            name="wardrobe_consistency",
            status=ValidationStatus.NOT_APPLICABLE,
            confidence=0.0,
            details="Wardrobe analysis requires VLM model — not yet wired",
            category="continuity",
        ))
        checks.append(ValidationCheck(
            name="environment_consistency",
            status=ValidationStatus.NOT_APPLICABLE,
            confidence=0.0,
            details="Environment analysis requires VLM model — not yet wired",
            category="continuity",
        ))

        elapsed = int((time.monotonic() - start) * 1000)
        return ValidationResult(
            asset_id=asset_id,
            overall_status=ValidationStatus.NOT_APPLICABLE,
            overall_confidence=1.0,
            checks=checks,
            asset_type="image",
            duration_ms=elapsed,
        )

    def validate_lipsync(
        self,
        asset_id: str,
        asset_path: str,
        *,
        project_id: Optional[str] = None,
        audio_asset_id: Optional[str] = None,
    ) -> ValidationResult:
        """Run lip-sync quality analysis."""
        checks: list[ValidationCheck] = []
        start = time.monotonic()

        if not self._feature_enabled:
            return ValidationResult(
                asset_id=asset_id,
                overall_status=ValidationStatus.SKIPPED,
                checks=[],
                asset_type="video",
                errors=["Vision Validation feature flag is off"],
            )

        checks.append(ValidationCheck(
            name="lipsync_quality",
            status=ValidationStatus.NOT_APPLICABLE,
            confidence=0.0,
            details="Lip-sync analysis requires phoneme + video frame alignment — not yet wired",
            category="sync",
        ))

        elapsed = int((time.monotonic() - start) * 1000)
        return ValidationResult(
            asset_id=asset_id,
            overall_status=ValidationStatus.NOT_APPLICABLE,
            overall_confidence=1.0,
            checks=checks,
            asset_type="video",
            duration_ms=elapsed,
        )

    def validate(
        self,
        asset_id: str,
        asset_path: str,
        *,
        project_id: Optional[str] = None,
        asset_type: str = "image",
        run_continuity: bool = False,
        run_lipsync: bool = False,
        character_ids: Optional[list[str]] = None,
        audio_asset_id: Optional[str] = None,
    ) -> ValidationResult:
        """Run the full validation pipeline — orchestrates all available QA checks.

        Returns a unified ValidationResult with per-category results.
        Human authority remains absolute — results are advisory.
        """
        if asset_type == "video":
            result = self.validate_video(asset_id, asset_path, project_id=project_id)
        else:
            result = self.validate_image(asset_id, asset_path, project_id=project_id)

        if run_continuity:
            cont = self.validate_continuity(asset_id, asset_path, project_id=project_id, character_ids=character_ids)
            result.checks.extend([c for c in cont.checks if c.status != ValidationStatus.NOT_APPLICABLE])

        if run_lipsync and audio_asset_id:
            ls = self.validate_lipsync(asset_id, asset_path, project_id=project_id, audio_asset_id=audio_asset_id)
            result.checks.extend([c for c in ls.checks if c.status != ValidationStatus.NOT_APPLICABLE])

        return result


# Back-compat alias: earlier tests / callers import VisionEngine.
VisionEngine = VisionValidationEngine

# Singleton engine instance
_engine = VisionValidationEngine()


def get_engine() -> VisionValidationEngine:
    return _engine


def set_engine_enabled(enabled: bool) -> None:
    _engine.set_enabled(enabled)


# Legacy alias for existing test compatibility
def run_validation(asset_id: str, asset_path: str, *, project_id: Optional[str] = None, asset_type: str = "image") -> ValidationResult:
    """Run the validation pipeline. Legacy alias for test compatibility."""
    return _engine.validate(asset_id, asset_path, project_id=project_id, asset_type=asset_type)
