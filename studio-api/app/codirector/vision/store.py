"""SQL persistence for vision validation sessions, reports, and related rows."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from ...db import (
    Asset,
    CoDirectorProductionPlan,
    CoDirectorValidationApproval,
    CoDirectorValidationComparison,
    CoDirectorValidationCorrectionProposal,
    CoDirectorValidationFinding,
    CoDirectorValidationReport,
    CoDirectorValidationSession,
)
from ..intelligence.schemas import ProductionPlan
from .schemas import (
    CorrectionProposalLink,
    ValidationApproval,
    ValidationComparison,
    ValidationReport,
    ValidationSession,
    ValidatorFinding,
)


def _iso(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.isoformat() + ("Z" if not str(dt).endswith("Z") else "")


class VisionStore:
    @staticmethod
    def create_session(
        db: Session,
        *,
        project_id: str,
        asset_id: Optional[str],
        plan_id: Optional[str],
        scene_id: Optional[str],
        reference_asset_id: Optional[str],
        provider: str,
        validator_set: list[str],
        requirements: dict[str, Any],
    ) -> ValidationSession:
        now = datetime.utcnow()
        row = CoDirectorValidationSession(
            id=str(uuid.uuid4()),
            project_id=project_id,
            asset_id=asset_id,
            plan_id=plan_id,
            scene_id=scene_id,
            reference_asset_id=reference_asset_id,
            provider=provider,
            status="pending",
            validator_set_json=json.dumps(validator_set),
            requirements_json=json.dumps(requirements, default=str),
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return VisionStore.session_from_row(row)

    @staticmethod
    def session_from_row(row: CoDirectorValidationSession) -> ValidationSession:
        return ValidationSession(
            sessionId=row.id,
            projectId=row.project_id,
            assetId=row.asset_id,
            planId=row.plan_id,
            sceneId=row.scene_id,
            referenceAssetId=row.reference_asset_id,
            provider=row.provider,
            status=row.status,  # type: ignore[arg-type]
            validatorSet=json.loads(row.validator_set_json or "[]"),
            reportId=row.report_id,
            comparisonId=row.comparison_id,
            errorMessage=row.error_message,
            requirements=json.loads(row.requirements_json or "{}"),
            createdAt=_iso(row.created_at),
            updatedAt=_iso(row.updated_at),
        )

    @staticmethod
    def get_session(db: Session, session_id: str, *, project_id: Optional[str] = None) -> ValidationSession | None:
        row = db.get(CoDirectorValidationSession, session_id)
        if not row:
            return None
        if project_id and row.project_id != project_id:
            return None
        return VisionStore.session_from_row(row)

    @staticmethod
    def update_session_status(
        db: Session,
        session_id: str,
        status: str,
        *,
        report_id: Optional[str] = None,
        comparison_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> ValidationSession | None:
        row = db.get(CoDirectorValidationSession, session_id)
        if not row:
            return None
        row.status = status
        row.updated_at = datetime.utcnow()
        if report_id is not None:
            row.report_id = report_id
        if comparison_id is not None:
            row.comparison_id = comparison_id
        if error_message is not None:
            row.error_message = error_message
        db.commit()
        db.refresh(row)
        return VisionStore.session_from_row(row)

    @staticmethod
    def save_report(db: Session, report: ValidationReport) -> ValidationReport:
        row = CoDirectorValidationReport(
            id=report.reportId,
            session_id=report.sessionId,
            project_id=report.projectId,
            overall_score=report.overallScore,
            passed=1 if report.passed else 0,
            band=report.band,
            strengths_json=json.dumps(report.strengths),
            warnings_json=json.dumps(report.warnings),
            failures_json=json.dumps(report.failures),
            recommendations_json=json.dumps(report.recommendations),
            confidence=report.confidence,
            weights_json=json.dumps(report.weights),
            blocking_failures_json=json.dumps(report.blockingFailures),
            provider=report.provider,
            report_json=json.dumps(report.model_dump(mode="json"), default=str),
            created_at=datetime.utcnow(),
        )
        db.add(row)
        for f in report.findings:
            VisionStore._add_finding(db, report=report, finding=f)
        db.commit()
        return report

    @staticmethod
    def _add_finding(db: Session, *, report: ValidationReport, finding: ValidatorFinding) -> None:
        db.add(
            CoDirectorValidationFinding(
                id=str(uuid.uuid4()),
                session_id=report.sessionId,
                report_id=report.reportId,
                project_id=report.projectId,
                validator_id=finding.validatorId,
                status=finding.status,
                score=finding.score,
                confidence=finding.confidence,
                severity=finding.severity,
                correctable=1 if finding.correctable else 0,
                blocking=1 if finding.blocking else 0,
                issues_json=json.dumps([i.model_dump(mode="json") for i in finding.issues], default=str),
                finding_json=json.dumps(finding.model_dump(mode="json"), default=str),
                created_at=datetime.utcnow(),
            )
        )

    @staticmethod
    def get_report(db: Session, report_id: str, *, project_id: Optional[str] = None) -> ValidationReport | None:
        row = db.get(CoDirectorValidationReport, report_id)
        if not row:
            return None
        if project_id and row.project_id != project_id:
            return None
        data = json.loads(row.report_json or "{}")
        return ValidationReport.model_validate(data)

    @staticmethod
    def save_comparison(db: Session, comparison: ValidationComparison) -> ValidationComparison:
        row = CoDirectorValidationComparison(
            id=comparison.comparisonId,
            session_id=comparison.sessionId,
            project_id=comparison.projectId,
            reference_asset_id=comparison.referenceAssetId,
            generated_asset_id=comparison.generatedAssetId,
            reference_meta_json=json.dumps(comparison.referenceMeta, default=str),
            generated_meta_json=json.dumps(comparison.generatedMeta, default=str),
            differences_json=json.dumps(comparison.differences, default=str),
            created_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()
        return comparison

    @staticmethod
    def get_comparison(
        db: Session, comparison_id: str, *, project_id: Optional[str] = None
    ) -> ValidationComparison | None:
        row = db.get(CoDirectorValidationComparison, comparison_id)
        if not row:
            return None
        if project_id and row.project_id != project_id:
            return None
        return ValidationComparison(
            comparisonId=row.id,
            sessionId=row.session_id,
            projectId=row.project_id,
            referenceAssetId=row.reference_asset_id,
            generatedAssetId=row.generated_asset_id,
            referenceMeta=json.loads(row.reference_meta_json or "{}"),
            generatedMeta=json.loads(row.generated_meta_json or "{}"),
            differences=json.loads(row.differences_json or "[]"),
            createdAt=_iso(row.created_at),
        )

    @staticmethod
    def save_approval(db: Session, approval: ValidationApproval) -> ValidationApproval:
        row = CoDirectorValidationApproval(
            id=approval.approvalId,
            session_id=approval.sessionId,
            report_id=approval.reportId,
            project_id=approval.projectId,
            decision=approval.decision,
            reviewer=approval.reviewer,
            notes=approval.notes,
            override_flag=1 if approval.override else 0,
            created_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()
        return approval

    @staticmethod
    def link_correction_proposal(
        db: Session,
        *,
        session_id: str,
        report_id: Optional[str],
        project_id: str,
        proposal_id: str,
        kind: str = "vision_correction",
    ) -> CorrectionProposalLink:
        link = CorrectionProposalLink(
            linkId=str(uuid.uuid4()),
            sessionId=session_id,
            reportId=report_id,
            projectId=project_id,
            proposalId=proposal_id,
            kind=kind,
            createdAt=datetime.utcnow().isoformat() + "Z",
        )
        db.add(
            CoDirectorValidationCorrectionProposal(
                id=link.linkId,
                session_id=session_id,
                report_id=report_id,
                project_id=project_id,
                proposal_id=proposal_id,
                kind=kind,
                created_at=datetime.utcnow(),
            )
        )
        db.commit()
        return link

    @staticmethod
    def list_correction_links(db: Session, session_id: str) -> list[CorrectionProposalLink]:
        rows = (
            db.query(CoDirectorValidationCorrectionProposal)
            .filter(CoDirectorValidationCorrectionProposal.session_id == session_id)
            .order_by(CoDirectorValidationCorrectionProposal.created_at.desc())
            .all()
        )
        return [
            CorrectionProposalLink(
                linkId=r.id,
                sessionId=r.session_id,
                reportId=r.report_id,
                projectId=r.project_id,
                proposalId=r.proposal_id,
                kind=r.kind,
                createdAt=_iso(r.created_at),
            )
            for r in rows
        ]

    @staticmethod
    def update_asset_validation(
        db: Session,
        asset_id: str,
        *,
        lifecycle: Optional[str] = None,
        result: Optional[str] = None,
        production_approval: Optional[str] = None,
    ) -> None:
        asset = db.get(Asset, asset_id)
        if not asset:
            return
        if lifecycle is not None:
            asset.validation_lifecycle = lifecycle
        if result is not None:
            asset.validation_result = result
        if production_approval is not None:
            asset.production_approval = production_approval
        db.commit()

    @staticmethod
    def clear_visual_validation_pending(db: Session, plan_id: str) -> bool:
        """M2.5: first code path allowed to clear ProductionPlan.visualValidationPending."""

        row = db.get(CoDirectorProductionPlan, plan_id)
        if not row:
            return False
        data = json.loads(row.plan_json or "{}")
        data["visualValidationPending"] = False
        try:
            plan = ProductionPlan.model_validate(data)
            row.plan_json = json.dumps(plan.model_dump(mode="json"), default=str)
        except Exception:
            row.plan_json = json.dumps(data, default=str)
        row.visual_validation_pending = 0
        row.updated_at = datetime.utcnow()
        db.commit()
        return True

    @staticmethod
    def list_sessions_for_project(db: Session, project_id: str, *, limit: int = 50) -> list[ValidationSession]:
        rows = (
            db.query(CoDirectorValidationSession)
            .filter(CoDirectorValidationSession.project_id == project_id)
            .order_by(CoDirectorValidationSession.created_at.desc())
            .limit(limit)
            .all()
        )
        return [VisionStore.session_from_row(r) for r in rows]
