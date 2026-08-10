"""Persistence for specialist findings, synthesis records, and production plans."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from ...db import CoDirectorProductionPlan, CoDirectorSpecialistFinding, CoDirectorSynthesisRecord
from ..plans.service import PlanService
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
        """Route intelligence drafts through the canonical Wave 4 PlanService.

        Always persists as an unapproved `draft` regardless of the legacy `status` argument —
        authoritative transitions require propose → approve.
        """

        _ = status  # legacy callers may pass status; Wave 4 ignores it for authority
        steps = [
            {
                "stepId": s.stepId,
                "title": s.title,
                "description": s.description,
                "proposedToolId": s.toolId,
                "requiresApproval": s.requiresApproval,
                "requiredCapabilities": [s.capability] if s.capability else [],
                "order": i + 1,
            }
            for i, s in enumerate(plan.steps or [])
        ]
        result = PlanService.create_draft(
            db,
            project_id=plan.projectId,
            request_id=plan.requestId or str(uuid.uuid4()),
            title=plan.title or "Intelligence draft plan",
            objective=plan.summary or "",
            description=plan.summary or "",
            steps=steps,
            source_type="intelligence",
            source_id=plan.playbookId,
            actor_type="codirector",
            plan_id=plan.planId,
        )
        row = db.get(CoDirectorProductionPlan, result.plan.planId)
        if row is None:
            raise RuntimeError("PlanService.create_draft did not persist a plan head")
        return row

    @staticmethod
    def load_plan(db: Session, plan_id: str) -> ProductionPlan | None:
        row = db.get(CoDirectorProductionPlan, plan_id)
        if not row:
            return None
        data = json.loads(row.plan_json or "{}")
        # Wave 4 schema may be richer; map back to intelligence ProductionPlan shape.
        try:
            return ProductionPlan.model_validate(
                {
                    "planId": data.get("planId") or row.id,
                    "projectId": data.get("projectId") or row.project_id,
                    "playbookId": data.get("playbookId") or row.playbook_id,
                    "title": data.get("title") or row.title,
                    "summary": data.get("objective") or data.get("summary") or "",
                    "steps": [
                        {
                            "stepId": s.get("stepId"),
                            "title": s.get("title"),
                            "description": s.get("description") or "",
                            "toolId": s.get("proposedToolId") or s.get("toolId"),
                            "requiresApproval": s.get("requiresApproval", True),
                            "capability": (s.get("requiredCapabilities") or [None])[0],
                            "status": s.get("state") or s.get("status") or "pending",
                        }
                        for s in (data.get("steps") or [])
                        if isinstance(s, dict)
                    ],
                    "blockers": [
                        b.get("title") if isinstance(b, dict) else str(b) for b in (data.get("blockers") or [])
                    ],
                    "approvalRequired": True,
                    "requestId": data.get("requestId") or row.request_id,
                }
            )
        except Exception:
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
