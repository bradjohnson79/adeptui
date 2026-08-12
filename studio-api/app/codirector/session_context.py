"""Canonical Co-Director session-context contract (composed; not a duplicate project store)."""

from __future__ import annotations

import os
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.codirector import config_store
from app.db import CoDirectorConversation, Project


def _provider_id() -> str:
    override = os.environ.get("ADEPT_CODIRECTOR_PROVIDER", "").strip().lower()
    e2e = os.environ.get("STUDIO_E2E", "").strip() in {"1", "true", "TRUE", "yes"}
    if override == "mock" and not e2e:
        return "ollama"
    if override in ("ollama", "mock"):
        return override
    if e2e:
        return "mock"
    return "ollama"


def build_session_context(
    db: Session,
    *,
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
    active_document_id: Optional[str] = None,
    active_scene_id: Optional[str] = None,
    active_workspace: Optional[str] = None,
    active_content_tab: Optional[str] = None,
    selected_assets: Optional[list[str]] = None,
    session_status: Optional[str] = None,
    last_successful_tool_action: Optional[str] = None,
    unresolved_blockers: Optional[list[str]] = None,
    active_production_plan: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Assemble session context from existing repositories only."""
    cfg = config_store.load_config()
    provider = _provider_id()
    model = str(cfg.get("selectedModel") or "") or None
    resolved_name = project_name

    if project_id:
        project = db.get(Project, project_id)
        if project is not None and not resolved_name:
            resolved_name = getattr(project, "name", None) or project_id
        row = db.get(CoDirectorConversation, project_id)
        if row is not None:
            if row.model_id:
                model = row.model_id
            if row.provider_id:
                provider = row.provider_id

    blockers = list(unresolved_blockers or [])
    if not project_id:
        blockers = sorted(set([*blockers, "no_project_selected"]))

    status = session_status or ("no_project" if not project_id else "bound")

    plan_fields: dict[str, Any] = {
        "activePlanId": None,
        "activePlanVersion": None,
        "activePlanState": None,
        "activeStepId": None,
        "planReadiness": None,
        "openPlanBlockers": [],
        "lastPlanCommand": None,
    }
    resolved_active_plan = active_production_plan
    if project_id:
        try:
            from app.codirector.plans.service import PlanService

            plan_fields = PlanService.session_fields(db, project_id)
            if resolved_active_plan is None:
                resolved_active_plan = plan_fields.get("activeProductionPlan")
            blockers = sorted(set([*blockers, *list(plan_fields.get("openPlanBlockers") or [])]))
        except Exception:
            pass

    _e2e = os.environ.get("STUDIO_E2E", "").strip() in {"1", "true", "TRUE", "yes"}
    _production = os.environ.get("ADEPT_ENV", "").strip().lower() == "production"
    _allow_mock = (
        _e2e
        and _production
        and (
            bool(cfg.get("allowMockProvider"))
            or os.environ.get("ADEPT_ALLOW_MOCK_PROVIDER", "").strip()
            in ("1", "true", "TRUE", "yes", "YES")
        )
    )

    return {
        "projectId": project_id,
        "projectName": resolved_name,
        "activeDocumentId": active_document_id,
        "activeSceneId": active_scene_id,
        "activeWorkspace": active_workspace,
        "activeContentTab": active_content_tab,
        "selectedAssets": list(selected_assets or []),
        "provider": provider,
        "model": model,
        "allowMock": _allow_mock,
        "activeProductionPlan": resolved_active_plan,
        "sessionStatus": status,
        "lastSuccessfulToolAction": last_successful_tool_action,
        "unresolvedBlockers": blockers,
        "activePlanId": plan_fields.get("activePlanId"),
        "activePlanVersion": plan_fields.get("activePlanVersion"),
        "activePlanState": plan_fields.get("activePlanState"),
        "activeStepId": plan_fields.get("activeStepId"),
        "planReadiness": plan_fields.get("planReadiness"),
        "openPlanBlockers": list(plan_fields.get("openPlanBlockers") or []),
        "lastPlanCommand": plan_fields.get("lastPlanCommand"),
    }
