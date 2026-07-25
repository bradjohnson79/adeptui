"""Vision validation engine orchestrator."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from ...db import Asset
from ..bible.context_retrieval import ContextRetrievalService
from .comparison import build_comparison
from .config import DEFAULT_VISION_CONFIG
from .providers import get_provider
from .reports import compute_report
from .schemas import ValidateRequest, ValidationReport, ValidationSession, ValidatorFinding
from .store import VisionStore
from .validators import IMAGE_VALIDATOR_IDS, VALIDATOR_BY_ID, VIDEO_VALIDATOR_IDS


class VisionEngine:
    """Inspect assets against generation-package requirements; never auto-approve or regenerate."""

    def __init__(self, config=DEFAULT_VISION_CONFIG):
        self.config = config

    def build_requirements(
        self,
        db: Session,
        *,
        project_id: str,
        scene_id: Optional[str],
        media_kind: str = "image",
        fixture_profile: Optional[str] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        package = ContextRetrievalService.generation_package(db, project_id, scene_id=scene_id)
        requirements: dict[str, Any] = {
            **package,
            "mediaKind": media_kind,
            "minWidth": 256,
            "minHeight": 256,
        }
        if fixture_profile:
            requirements["fixtureProfile"] = fixture_profile
        if extra:
            requirements.update(extra)
        return requirements

    def run(self, db: Session, request: ValidateRequest) -> dict[str, Any]:
        asset = db.get(Asset, request.assetId) if request.assetId else None
        media_kind = "video" if asset and str(asset.kind).lower() == "video" else "image"
        if request.fixtureProfile and "video" in request.fixtureProfile:
            media_kind = "video"

        requirements = self.build_requirements(
            db,
            project_id=request.projectId,
            scene_id=request.sceneId,
            media_kind=media_kind,
            fixture_profile=request.fixtureProfile,
        )

        validator_ids = list(request.validators or (VIDEO_VALIDATOR_IDS if media_kind == "video" else IMAGE_VALIDATOR_IDS))
        # Technical always first.
        if "technical" in validator_ids:
            validator_ids = ["technical"] + [v for v in validator_ids if v != "technical"]
        else:
            validator_ids = ["technical"] + validator_ids

        session = VisionStore.create_session(
            db,
            project_id=request.projectId,
            asset_id=request.assetId,
            plan_id=request.planId,
            scene_id=request.sceneId,
            reference_asset_id=request.referenceAssetId,
            provider=request.provider,
            validator_set=validator_ids,
            requirements=requirements,
        )

        if request.assetId:
            VisionStore.update_asset_validation(db, request.assetId, lifecycle="running", result="unreviewed")

        VisionStore.update_session_status(db, session.sessionId, "running")

        asset_path = asset.path if asset else None
        ref_asset = db.get(Asset, request.referenceAssetId) if request.referenceAssetId else None
        reference_path = ref_asset.path if ref_asset else None

        provider = get_provider(request.provider)
        try:
            context = provider.prepare_asset_context(
                asset_path=asset_path,
                reference_path=reference_path,
                requirements=requirements,
                fixture_profile=request.fixtureProfile,
            )
            findings = self._run_validators(
                validator_ids=validator_ids,
                context=context,
                requirements=requirements,
                provider_id=provider.provider_id,
            )
            report = compute_report(
                session_id=session.sessionId,
                project_id=request.projectId,
                findings=findings,
                provider=provider.provider_id,
                include_motion=media_kind == "video",
                config=self.config,
            )
            VisionStore.save_report(db, report)

            comparison = build_comparison(
                db,
                session_id=session.sessionId,
                project_id=request.projectId,
                reference_asset_id=request.referenceAssetId,
                generated_asset_id=request.assetId,
                context=context,
            )
            VisionStore.save_comparison(db, comparison)

            session = VisionStore.update_session_status(
                db,
                session.sessionId,
                "completed",
                report_id=report.reportId,
                comparison_id=comparison.comparisonId,
            ) or session

            result_label = "passed" if report.passed else ("warnings" if report.band in ("review", "corrections_required") else "failed")
            if request.assetId:
                VisionStore.update_asset_validation(
                    db,
                    request.assetId,
                    lifecycle="completed",
                    result=result_label,
                )

            if request.planId:
                VisionStore.clear_visual_validation_pending(db, request.planId)

            self._maybe_write_derivative(request.projectId, session.sessionId, report)

            return {
                "session": session.model_dump(mode="json") if session else None,
                "report": report.model_dump(mode="json"),
                "comparison": comparison.model_dump(mode="json"),
            }
        except Exception as exc:
            VisionStore.update_session_status(
                db,
                session.sessionId,
                "failed",
                error_message=str(exc),
            )
            if request.assetId:
                VisionStore.update_asset_validation(db, request.assetId, lifecycle="failed", result="failed")
            if request.planId:
                VisionStore.clear_visual_validation_pending(db, request.planId)
            raise

    def _run_validators(
        self,
        *,
        validator_ids: list[str],
        context: dict[str, Any],
        requirements: dict[str, Any],
        provider_id: str,
    ) -> list[ValidatorFinding]:
        findings: list[ValidatorFinding] = []
        for vid in validator_ids:
            validator = VALIDATOR_BY_ID.get(vid)
            if not validator:
                continue
            findings.append(
                validator.validate(context=context, requirements=requirements, provider_id=provider_id)
            )
            # Hard stop after blocking technical fail is still recorded; remaining validators still run
            # so the report stays informative, but technical/identity blocking is enforced in scoring.
        return findings

    def _maybe_write_derivative(self, project_id: str, session_id: str, report: ValidationReport) -> None:
        try:
            from ...config import settings

            root = Path(settings.data_dir) / "projects" / project_id / "validation"
            root.mkdir(parents=True, exist_ok=True)
            (root / f"{session_id}.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
        except Exception:
            pass


def run_validation(db: Session, request: ValidateRequest) -> dict[str, Any]:
    return VisionEngine().run(db, request)
