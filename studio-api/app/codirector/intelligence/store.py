"""Persistence for specialist findings, synthesis records, and production plans."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from ...db import CoDirectorProductionPlan, CoDirectorSpecialistFinding, CoDirectorSynthesisRecord
from .schemas import ProductionPlan, SpecialistFinding, SynthesisResult


class IntelligenceStore:
    @staticmethod
    def save_finding(
        db: Session,
        *,
        project_id: str,
        request_id: str,
        finding: SpecialistFinding,
        context_hash: str,
        prompt_version: Optional[str] = None,
        model_id: Optional[str] = None,
        status: str = "validated",
    ) -> CoDirectorSpecialistFinding:
        row = CoDirectorSpecialistFinding(
            id=str(uuid.uuid4()),
            project_id=project_id,
            request_id=request_id,
            specialist_id=finding.specialistId,
            prompt_version=prompt_version or finding.promptVersion or "",
            model_id=model_id or finding.modelId or "",
            context_hash=context_hash,
            output_json=json.dumps(finding.model_dump(mode="json"), default=str),
            validation_status=status,
            confidence=finding.confidence,
            created_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def save_synthesis(
        db: Session,
        *,
        project_id: str,
        request_id: str,
        synthesis: SynthesisResult,
        specialist_ids: Iterable[str],
        prompt_versions_json: dict[str, str],
        plan_id: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> CoDirectorSynthesisRecord:
        row = CoDirectorSynthesisRecord(
            id=str(uuid.uuid4()),
            project_id=project_id,
            request_id=request_id,
            specialist_ids_json=json.dumps(list(specialist_ids)),
            synthesis_json=json.dumps(synthesis.model_dump(mode="json"), default=str),
            prompt_versions_json=json.dumps(prompt_versions_json, default=str),
            plan_id=plan_id,
            model_id=model_id or "",
            created_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def save_plan(
        db: Session,
        *,
        plan: ProductionPlan,
        status: str = "draft",
    ) -> CoDirectorProductionPlan:
        row = CoDirectorProductionPlan(
            id=plan.planId,
            project_id=plan.projectId,
            request_id=plan.requestId or "",
            playbook_id=plan.playbookId or "",
            title=plan.title,
            status=status,
            plan_json=json.dumps(plan.model_dump(mode="json"), default=str),
            visual_validation_pending=1 if plan.visualValidationPending else 0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def load_plan(db: Session, plan_id: str) -> ProductionPlan | None:
        row = db.get(CoDirectorProductionPlan, plan_id)
        if not row:
            return None
        data = json.loads(row.plan_json or "{}")
        return ProductionPlan.model_validate(data)

    @staticmethod
    def list_findings(db: Session, project_id: str, *, request_id: Optional[str] = None) -> list[dict[str, Any]]:
        query = db.query(CoDirectorSpecialistFinding).filter(CoDirectorSpecialistFinding.project_id == project_id)
        if request_id:
            query = query.filter(CoDirectorSpecialistFinding.request_id == request_id)
        rows = query.order_by(CoDirectorSpecialistFinding.created_at.desc()).limit(100).all()
        out: list[dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "id": row.id,
                    "specialistId": row.specialist_id,
                    "validationStatus": row.validation_status,
                    "confidence": row.confidence,
                    "requestId": row.request_id,
                    "createdAt": row.created_at.isoformat() if row.created_at else None,
                }
            )
        return out
