"""Evidence-based workflow reconciliation — multi-stage assessment, not a single step number."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .definitions import (
    WorkflowDefinition,
    WorkflowRequirement,
    WorkflowRequirementType,
    get_workflow_for_format,
)


class StageMaturity(BaseModel):
    stage_id: str
    label: str
    maturity: float  # 0.0 = not started, 1.0 = complete
    evidence_hits: list[str] = Field(default_factory=list)
    blockers: list[WorkflowRequirement] = Field(default_factory=list)


class WorkflowAssessment(BaseModel):
    applicable_workflow: str
    evidenced_stages: list[StageMaturity]
    active_stage_candidates: list[str] = Field(default_factory=list)
    completed_evidence: list[str] = Field(default_factory=list)
    partial_evidence: list[str] = Field(default_factory=list)
    blockers: list[WorkflowRequirement] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: float = 0.0


def _assess_stage_maturity(
    stage_id: str,
    label: str,
    evidence_rules: list[str],
    readiness_rules: list[WorkflowRequirement],
    project_info: dict[str, Any],
) -> StageMaturity:
    """Evaluate maturity of a single workflow stage against project evidence."""
    hits: list[str] = []
    blockers: list[WorkflowRequirement] = []

    for rule in evidence_rules:
        if _check_evidence_rule(rule, project_info):
            hits.append(rule)

    for req in readiness_rules:
        if not _check_evidence_rule(req.evidence_rule, project_info):
            blockers.append(req)

    if not evidence_rules:
        maturity = 0.0
    elif len(hits) >= len(evidence_rules) and not blockers:
        maturity = 1.0
    elif len(hits) > 0:
        maturity = min(0.3 + 0.3 * (len(hits) / len(evidence_rules)), 0.8) if evidence_rules else 0.0
    else:
        maturity = 0.0

    return StageMaturity(
        stage_id=stage_id,
        label=label,
        maturity=maturity,
        evidence_hits=hits,
        blockers=blockers,
    )


def _check_evidence_rule(rule: str, info: dict[str, Any]) -> bool:
    """Check evidence rules against project info. Deterministic only — no LLM calls."""
    lower = rule.lower()

    if "project exists" in lower:
        return bool(info.get("project_id"))
    if "title" in lower:
        return bool(info.get("title"))
    if "format" in lower:
        return bool(info.get("format"))
    if "primary character" in lower or "character" in rule.lower():
        return bool(info.get("characters"))
    if "script" in lower:
        return bool(info.get("script_exists"))
    if "shot plan" in lower or "shot planning" in lower:
        return bool(info.get("shot_plans"))
    if "generated" in lower or "asset" in lower:
        return bool(info.get("generated_assets"))
    if "timeline" in lower or "clip" in lower or "magi" in lower:
        return bool(info.get("timeline_clips"))
    if "audio" in lower:
        return bool(info.get("audio_assets"))
    if "bible" in lower:
        return bool(info.get("bible_entities"))
    if "scene" in lower:
        return bool(info.get("scene_records"))
    if "post" in lower or "finishing" in lower or "qc" in lower:
        return bool(info.get("post_production"))
    if "concept" in lower:
        return bool(info.get("concept_data"))
    # Default: skip unknown rules (not evidence of readiness)
    return False


def _gather_project_info(db: Session, project_id: str) -> dict[str, Any]:
    """Gather project evidence from authoritative Phase 2+ sources. All try/except wrapped."""
    info: dict[str, Any] = {"project_id": project_id}

    try:
        from app.db import Project
        proj = db.get(Project, project_id)
        if proj:
            info["title"] = getattr(proj, "name", None)
            info["format"] = getattr(proj, "primary_project_type", None)
    except Exception:
        pass

    try:
        from app.codirector.production_state.stage_evidence import get_authoritative_stage
        info["authoritative_stage"] = get_authoritative_stage(db, project_id)
    except Exception:
        pass

    try:
        from app.scriptwriter.store import list_documents
        docs = list_documents(db, project_id)
        info["script_exists"] = bool(docs)
        if docs:
            info["script_draft"] = True
    except Exception:
        pass

    try:
        from app.codirector.character_identity import list_character_profiles
        chars = list_character_profiles(db, project_id)
        info["characters"] = bool(chars)
    except Exception:
        pass

    try:
        from app.codirector.multi_shot import list_plans
        plans = list_plans(db, project_id)
        info["shot_plans"] = bool(plans)
    except Exception:
        pass

    try:
        from app.codirector.image_pipeline.store import list_plans
        plans = list_plans(db, project_id)
        info["generated_assets"] = bool(plans)
    except Exception:
        pass

    try:
        from app.codirector.magi.sequence.store import get_sequence
        seq = get_sequence(project_id)
        info["timeline_clips"] = bool(seq)
    except Exception:
        pass

    try:
        from app.codirector.bible.service import get_bible
        bible = get_bible(db, project_id)
        info["bible_entities"] = bool(bible and getattr(bible, "current_version_id", None))
    except Exception:
        pass

    return info


def reconcile_workflow(
    db: Session,
    project_id: str,
    *,
    workflow_def: Optional[WorkflowDefinition] = None,
    active_workspace: Optional[str] = None,
    active_task: Optional[str] = None,
) -> WorkflowAssessment:
    """Reconcile project evidence against a workflow definition.

    Returns a multi-stage assessment — NEVER a single step number.
    Real productions overlap multiple stages simultaneously.
    """
    project_info = _gather_project_info(db, project_id)

    fmt = project_info.get("format") or "unknown"
    wf = workflow_def or get_workflow_for_format(fmt)

    stages: list[StageMaturity] = []
    all_blockers: list[WorkflowRequirement] = []
    completed: list[str] = []
    partial: list[str] = []

    for stage_def in wf.stages:
        maturity = _assess_stage_maturity(
            stage_def.id, stage_def.label, stage_def.evidence_rules, stage_def.readiness_rules, project_info
        )
        stages.append(maturity)
        all_blockers.extend(maturity.blockers)
        if maturity.maturity >= 1.0:
            completed.append(stage_def.id)
        elif maturity.maturity > 0.0:
            partial.append(stage_def.id)

    # Determine active stage candidates (highest maturity stage that isn't complete)
    sorted_stages = sorted(stages, key=lambda s: s.maturity, reverse=True)
    active_candidates = [s.stage_id for s in sorted_stages if s.maturity < 1.0][:3]

    warnings_list: list[str] = []
    # If later stages have evidence but earlier required stages don't, warn
    for s in stages:
        if s.maturity > 0.0 and any(
            r.type in ("BLOCKING", "REQUIRED") and not _check_evidence_rule(r.evidence_rule, project_info)
            for r in next(
                (sd.readiness_rules for sd in wf.stages if sd.id == s.stage_id), []
            )
        ):
            warnings_list.append(f"{s.label}: some prerequisites may be unmet")

    confidence = 0.5 + 0.05 * len(completed) + 0.03 * len(partial)
    confidence = min(confidence, 1.0)

    return WorkflowAssessment(
        applicable_workflow=wf.id,
        evidenced_stages=stages,
        active_stage_candidates=active_candidates,
        completed_evidence=completed,
        partial_evidence=partial,
        blockers=[b for b in all_blockers if b.type in ("BLOCKING", "REQUIRED")][:5],
        warnings=warnings_list[:3],
        confidence=confidence,
    )
