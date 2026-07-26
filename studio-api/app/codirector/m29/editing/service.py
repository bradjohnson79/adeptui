"""M2.9 editing / SFX / music cue proposals."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ...executive.models import JobType
from .. import fixture_mode_enabled
from ..audio.service import AudioService
from ..fixtures import fixture_edit_result
from ..store import enqueue_executive_job


class EditingService:
    @staticmethod
    def propose_edit(
        db: Session,
        *,
        project_id: str,
        ops: list[dict[str, Any]] | None = None,
        scene_id: str | None = None,
        owner: str = "user",
    ) -> dict[str, Any]:
        result = fixture_edit_result({"ops": ops})
        result["projectId"] = project_id
        result["requiresApproval"] = True
        # Durable apply path goes through edit_apply job only after approval flag in payload.
        return result

    @staticmethod
    def apply_edit(
        db: Session,
        *,
        project_id: str,
        ops: list[dict[str, Any]],
        approved: bool = False,
        scene_id: str | None = None,
        owner: str = "user",
    ) -> dict[str, Any]:
        if not approved:
            raise PermissionError("edit_apply blocked: human approval required")
        payload = {"ops": ops, "approved": True, "m29": True}
        job = enqueue_executive_job(
            db,
            project_id=project_id,
            job_type=JobType.EDIT_APPLY,
            payload=payload,
            scene_id=scene_id,
            owner=owner,
        )
        return {
            "jobId": job.id,
            "ops": ops,
            "status": "queued" if not fixture_mode_enabled() else "applied",
            "fixture": fixture_mode_enabled(),
            "projectId": project_id,
        }

    @staticmethod
    def propose_sfx_cue(
        db: Session,
        *,
        project_id: str,
        prompt: str = "SFX cue",
        scene_id: str | None = None,
        owner: str = "user",
        **params: Any,
    ) -> dict[str, Any]:
        out = AudioService.generate(
            db,
            project_id=project_id,
            kind="sfx",
            prompt=prompt,
            scene_id=scene_id,
            owner=owner,
            **params,
        )
        out["requiresApproval"] = True
        out["proposalKind"] = "sfx_cue"
        return out

    @staticmethod
    def propose_music_cue(
        db: Session,
        *,
        project_id: str,
        prompt: str = "Music cue",
        scene_id: str | None = None,
        owner: str = "user",
        **params: Any,
    ) -> dict[str, Any]:
        out = AudioService.generate(
            db,
            project_id=project_id,
            kind="music",
            prompt=prompt,
            scene_id=scene_id,
            owner=owner,
            **params,
        )
        out["requiresApproval"] = True
        out["proposalKind"] = "music_cue"
        return out

    @staticmethod
    def execute_job(db: Session, payload: dict[str, Any], project_id: str) -> dict[str, Any]:
        if not payload.get("approved"):
            raise PermissionError("edit_apply blocked: human approval required")
        return {
            "ops": payload.get("ops") or [],
            "status": "applied",
            "fixture": fixture_mode_enabled(),
            "projectId": project_id,
        }
