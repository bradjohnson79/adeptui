"""Proposal integration for story field compilation.
Routes compiler outputs through the existing ProposalService create->approve->reject flow,
with creator direct-edit preservation and argument pinning.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..bible.proposals import ProposalService, _raw_payload
from ..bible.schemas import ProposalOut
from ..conversation.snapshot import load_snapshot, save_snapshot
from ...db import CoDirectorExecutionReceipt, CoDirectorProposal
from .story_model import StoryEvidenceModel, build_story_evidence

logger = logging.getLogger(__name__)

STORY_FIELD_PROPOSAL_TYPE = "story_field"

ARTIFACT_TO_COMPILED_KEY: dict[str, str] = {
    "logline": "storySummary.logline",
    "short_summary": "storySummary.shortSummary",
    "long_summary": "storySummary.longSummary",
}


class StoryFieldPayload(BaseModel):
    artifactType: str = ""
    currentValue: Optional[str] = None
    proposedValue: str = ""
    compilerVersion: str = "1.0"
    evidenceHash: str = ""


def create_story_field_proposal(
    db: Session,
    *,
    project_id: str,
    artifact_type: str,
    current_value: Optional[str],
    proposed_value: str,
    compiler_version: str = "1.0",
    evidence_hash: str = "",
    request_id: Optional[str] = None,
) -> ProposalOut:
    payload = StoryFieldPayload(
        artifactType=artifact_type,
        currentValue=current_value,
        proposedValue=proposed_value,
        compilerVersion=compiler_version,
        evidenceHash=evidence_hash,
    )
    return ProposalService.create_proposal(
        db,
        project_id=project_id,
        proposal_type=STORY_FIELD_PROPOSAL_TYPE,
        title=f"Update {artifact_type.replace('_', ' ').title()}",
        summary=f"AI-proposed revision to the project's {artifact_type.replace('_', ' ')}",
        payload=payload,
        request_id=request_id,
    )


def apply_story_field_approval(
    db: Session,
    *,
    project_id: str,
    proposal_id: str,
) -> dict[str, Any]:
    row = db.get(CoDirectorProposal, proposal_id)
    if not row or row.project_id != project_id:
        raise ValueError(f"Proposal {proposal_id} not found for project {project_id}")

    payload = _raw_payload(row.payload_json)
    artifact_type = payload.get("artifactType", "unknown")
    proposed_value = payload.get("proposedValue", "")

    snapshot = load_snapshot(db, project_id)
    compiled = snapshot.compiledWiki
    if "storySummary" not in compiled:
        compiled["storySummary"] = {}
    compiled["storySummary"][artifact_type] = proposed_value
    snapshot.compiledWiki = compiled
    save_snapshot(db, snapshot)

    input_hash = hashlib.sha256(row.payload_json.encode("utf-8")).hexdigest()[:64]
    receipt_row = CoDirectorExecutionReceipt(
        id=str(uuid.uuid4()),
        proposal_id=proposal_id,
        input_hash=input_hash,
        status="success",
        resulting_version_id=None,
        error_json=None,
        executed_at=datetime.utcnow(),
    )
    db.add(receipt_row)
    row.status = "completed"
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(receipt_row)

    return {"ok": True, "artifactType": artifact_type, "proposalId": proposal_id, "appliedProposalId": receipt_row.id}


def reject_story_field_proposal(
    db: Session,
    *,
    project_id: str,
    proposal_id: str,
    note: Optional[str] = None,
    decided_by: str = "creator",
) -> ProposalOut:
    return ProposalService.reject(db, project_id, proposal_id, note=note, decided_by=decided_by)


def get_current_story_field(
    db: Session,
    *,
    project_id: str,
    artifact_type: str,
) -> Optional[str]:
    snapshot = load_snapshot(db, project_id)
    compiled = snapshot.compiledWiki
    story_summary = compiled.get("storySummary", {}) if isinstance(compiled, dict) else {}
    key = ARTIFACT_TO_COMPILED_KEY.get(artifact_type, "").split(".")[-1]
    return story_summary.get(key)


def route_compiler_output(
    db: Session,
    *,
    project_id: str,
    artifact_type: str,
    proposed_value: str,
    evidence: StoryEvidenceModel,
    request_id: Optional[str] = None,
) -> Optional[ProposalOut]:
    if not proposed_value or not proposed_value.strip():
        logger.info("Skipping proposal for %s: empty output (insufficient evidence)", artifact_type)
        return None

    current = get_current_story_field(db, project_id=project_id, artifact_type=artifact_type)
    if current and current.strip() == proposed_value.strip():
        logger.info("Skipping proposal for %s: proposed value matches current", artifact_type)
        return None

    return create_story_field_proposal(
        db,
        project_id=project_id,
        artifact_type=artifact_type,
        current_value=current,
        proposed_value=proposed_value,
        request_id=request_id,
    )


async def trigger_compiler_for_artifact(
    db: Session,
    *,
    project_id: str,
    artifact_type: str,
    request_id: Optional[str] = None,
) -> Optional[ProposalOut]:
    """Trigger the Phase 4 compiler for a specific story artifact.

    Called from Wiki actions ("Generate Logline", "Refine Short Summary", etc.)
    or from the Co-Director route decision handler.

    Returns the created ProposalOut, or None if no proposal was created
    (empty output, no change, or validation failure).
    """
    evidence = build_story_evidence(db, project_id)

    if artifact_type == "logline":
        from .compilers.logline import compile_logline, validate_logline
        proposed = compile_logline(evidence)
        validation = validate_logline(proposed, evidence)
    elif artifact_type == "short_summary":
        from .compilers.short_summary import compile_short_summary, validate_short_summary
        proposed = compile_short_summary(evidence)
        validation = validate_short_summary(proposed, evidence)
    elif artifact_type == "long_summary":
        from .compilers.long_summary import compile_long_summary, validate_long_summary
        proposed = compile_long_summary(evidence)
        validation = validate_long_summary(proposed, evidence)
    else:
        raise ValueError(f"Unknown artifact_type: {artifact_type}")

    if not proposed or not validation.valid:
        logger.info("Compiler returned invalid/empty output for %s: %s", artifact_type, validation.errors)
        return None

    return route_compiler_output(
        db,
        project_id=project_id,
        artifact_type=artifact_type,
        proposed_value=proposed,
        evidence=evidence,
        request_id=request_id,
    )
