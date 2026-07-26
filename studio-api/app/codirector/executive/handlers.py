"""Real Production Executive job handlers (in-process Session, no self-HTTP).

Closed loop: storyboard -> image -> validate -> create_proposal -> await_approval -> apply_canon.
Never auto-approve and never mutate Production Bible canon directly.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from ...db import CoDirectorExecutionReceipt, Project, Scene
from ...storyboard_jobs import enqueue_imagegen_job, prepare_storyboard_generate
from ..bible.proposals import ProposalService
from ..bible.schemas import BibleMutationSet, EntityMutation
from ..errors import APPROVAL_ALREADY_RECORDED, CoDirectorError
from ..vision.engine import run_validation
from ..vision.schemas import ReferenceSetBindingSpec, ReferenceSetSpec, ValidateRequest
from .contracts import audit_metadata, validate_job_input, validate_job_output
from .imagegen_adapter import (
    poll_imagegen_job,
    read_job_asset_id,
    schedule_job_queue_enqueue,
)
from .models import JobType
from .schemas import JobOut

logger = logging.getLogger(__name__)


class HandlerResult:
    def __init__(
        self,
        *,
        ok: bool,
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        needs_review: bool = False,
    ) -> None:
        self.ok = ok
        self.status = status
        self.result = result or {}
        self.error = error
        self.needs_review = needs_review


def _ensure_scene(db: Session, project_id: str, scene_id: str | None) -> str | None:
    if not scene_id:
        return None
    scene = db.get(Scene, scene_id)
    if scene:
        return scene_id
    if not db.get(Project, project_id):
        raise ValueError("Project not found")
    db.add(
        Scene(
            id=scene_id,
            project_id=project_id,
            name=f"Scene {scene_id}",
            prompt="Production Executive closed-loop scene",
        )
    )
    db.commit()
    return scene_id


def _remap_reference_set(pkg: dict[str, Any] | None) -> ReferenceSetSpec | None:
    if not pkg or not pkg.get("referenceSet"):
        return None
    rs = pkg["referenceSet"]
    bindings = []
    for b in rs.get("bindings") or []:
        asset_id = b.get("assetId") or b.get("referenceAssetId")
        if not asset_id:
            continue
        bindings.append(
            ReferenceSetBindingSpec(
                bindingId=str(b.get("bindingId") or asset_id),
                role=str(b.get("role") or "style"),
                influence=str(b.get("influence") or "moderate"),
                assetId=str(asset_id),
            )
        )
    return ReferenceSetSpec(
        id=str(rs.get("id") or "refset"),
        version=int(rs.get("version") or 1),
        bindings=bindings,
    )


def _handle_storyboard(db: Session, job: JobOut, payload: dict[str, Any]) -> HandlerResult:
    scene_id = job.sceneId or payload.get("sceneId")
    _ensure_scene(db, job.projectId, scene_id)
    body = {
        **payload,
        "sceneId": scene_id,
        "panelId": payload.get("panelId") or payload.get("panel_id"),
        "segmentId": payload.get("segmentId") or payload.get("segment_id"),
        "prompt": payload.get("prompt"),
        "style": payload.get("style"),
    }
    prepared = prepare_storyboard_generate(db, job.projectId, body)
    schedule_job_queue_enqueue(prepared["job_id"])
    out = {
        "panelId": prepared["panel_id"],
        "imageJobId": prepared["job_id"],
        "segmentId": prepared.get("segment_id"),
        "status": prepared["status"],
        "provider": job.provider or payload.get("provider") or "comfy",
        "audit": audit_metadata(job.type, job_id=job.id),
    }
    return HandlerResult(ok=True, status="Completed", result=validate_job_output(job.type, out))


def _handle_image(db: Session, job: JobOut, payload: dict[str, Any]) -> HandlerResult:
    # M2.9 path: fixture only when fixtureComplete / ADEPT_M29_FIXTURE_MODE; else real Comfy.
    if payload.get("m29") or payload.get("fixtureComplete"):
        from ..m29.image.service import ImageService
        from ..m29.providers import ProviderError, ProviderUnavailable, handler_status_for_exc

        try:
            out = ImageService.execute_job(db, payload, job.projectId)
        except (ProviderUnavailable, ProviderError, Exception) as exc:  # noqa: BLE001
            status = handler_status_for_exc(exc)
            return HandlerResult(ok=False, status=status, error=str(exc))
        if out.get("assetId"):
            closed = {
                "assetId": out["assetId"],
                "imageJobId": out.get("imageJobId") or payload.get("imageJobId") or job.id,
                "panelId": out.get("panelId") or payload.get("panelId"),
                "provider": out.get("provider") or job.provider or payload.get("provider") or "comfy",
                "mockAdapter": bool(out.get("mockAdapter", False)),
            }
            return HandlerResult(ok=True, status="Completed", result=validate_job_output(job.type, closed))
        return HandlerResult(ok=True, status="Completed", result=out)

    if payload.get("assetId"):
        out = {
            "assetId": payload["assetId"],
            "imageJobId": payload.get("imageJobId") or "",
            "panelId": payload.get("panelId"),
            "provider": job.provider or payload.get("provider") or "comfy",
            "mockAdapter": False,
        }
        return HandlerResult(ok=True, status="Completed", result=validate_job_output(job.type, out))

    image_job_id = payload.get("imageJobId")
    panel_id = payload.get("panelId")
    if not image_job_id:
        body = {
            "prompt": payload.get("prompt") or "Production Executive image",
            "tag": "storyboard",
            "labels": ["storyboard"],
            "panel_id": panel_id,
            "width": int(payload.get("width") or 1280),
            "height": int(payload.get("height") or 720),
            "model": payload.get("model") or "auto",
        }
        studio_job = enqueue_imagegen_job(
            db, job.projectId, body, scene_id=job.sceneId or payload.get("sceneId")
        )
        image_job_id = studio_job.id
        schedule_job_queue_enqueue(image_job_id)

    try:
        asset_id, _used_mock = poll_imagegen_job(
            db,
            image_job_id,
            project_id=job.projectId,
            timeout_sec=float(payload.get("timeoutSec") or 120),
            allow_mock=False,
        )
    except Exception as exc:  # noqa: BLE001
        err = str(exc)
        low = err.lower()
        status = (
            "Blocked"
            if (
                "ComfyUI unavailable" in err
                or "unavailable" in low
                or "job_queue" in low
                or "checkpoint" in low
                or "workflow" in low
            )
            else "Failed"
        )
        return HandlerResult(ok=False, status=status, error=err)

    out = {
        "assetId": asset_id,
        "imageJobId": image_job_id,
        "panelId": panel_id,
        "provider": job.provider or payload.get("provider") or "comfy",
        "mockAdapter": False,
    }
    return HandlerResult(ok=True, status="Completed", result=validate_job_output(job.type, out))


def _handle_validate(db: Session, job: JobOut, payload: dict[str, Any]) -> HandlerResult:
    asset_id = payload.get("assetId")
    if not asset_id:
        return HandlerResult(ok=False, status="Failed", error="validate requires assetId from image_generate")

    provider = payload.get("provider") or job.provider or "local"
    if provider == "mock":
        return HandlerResult(
            ok=False,
            status="Failed",
            error="provider 'mock' is not allowed in runtime closed-loop path; use local",
        )
    if provider not in ("local", "cloud"):
        return HandlerResult(
            ok=False,
            status="Failed",
            error=f"unsupported validate provider '{provider}'; use local",
        )
    # Vision ValidateRequest currently accepts local (cloud reserved); map cloud->local until supported.
    vision_provider = "local" if provider in ("local", "cloud") else provider
    fixture = payload.get("fixtureProfile")  # do not default to "pass"

    reference_set = None
    timeline_item_id = job.timelineItemId or payload.get("timelineItemId")
    scene_id = job.sceneId or payload.get("sceneId")
    if timeline_item_id and scene_id:
        try:
            from ...director_references.package import ReferencePackageBuilder
            from ... import feature_flags as ff_mod

            if ff_mod.feature_flags.timeline_references_v1:
                pkg = ReferencePackageBuilder(db).build(job.projectId, scene_id, timeline_item_id)
                reference_set = _remap_reference_set(pkg)
        except Exception:  # noqa: BLE001
            logger.info("ReferencePackageBuilder skipped for validate job %s", job.id, exc_info=True)

    plan_id = payload.get("planId")
    request = ValidateRequest(
        projectId=job.projectId,
        assetId=asset_id,
        planId=plan_id,
        sceneId=scene_id,
        referenceAssetId=payload.get("referenceAssetId"),
        referenceSet=reference_set,
        provider=vision_provider,  # type: ignore[arg-type]
        fixtureProfile=fixture,
    )
    result = run_validation(db, request)
    session = result.get("session") or {}
    report = result.get("report") or {}
    session_id = session.get("sessionId") or session.get("id")
    report_id = report.get("reportId") or report.get("id")
    if not session_id or not report_id:
        return HandlerResult(
            ok=False,
            status="Failed",
            error="validation missing sessionId/reportId from real vision path",
        )
    score = float(report.get("score") if report.get("score") is not None else payload.get("score") or 0)
    passed = bool(report.get("passed")) if "passed" in report else score >= 80
    band = "approve" if passed else str(report.get("band") or "correction-required")
    out = {
        "sessionId": session_id,
        "reportId": report_id,
        "score": score,
        "passed": passed,
        "band": band,
        "provider": provider,
        # Cleared only by M2.5 VisionEngine when planId is provided — not by executive.
        "visualValidationPendingCleared": bool(plan_id),
    }
    return HandlerResult(ok=True, status="Completed", result=validate_job_output(job.type, out))


def _handle_create_proposal(db: Session, job: JobOut, payload: dict[str, Any]) -> HandlerResult:
    if payload.get("proposalId"):
        try:
            existing = ProposalService.get(db, job.projectId, payload["proposalId"])
            out = {
                "proposalId": existing.id,
                "status": existing.status,
                "path": "M2.2 Proposal → Review → Approval",
            }
            return HandlerResult(ok=True, status="Completed", result=validate_job_output(job.type, out))
        except CoDirectorError:
            pass

    scene_id = job.sceneId or payload.get("sceneId") or "unknown"
    asset_id = payload.get("assetId")
    session_id = payload.get("sessionId")
    score = payload.get("score")
    mutations = BibleMutationSet(
        entityMutations=[
            EntityMutation(
                entityType="production_decision",
                entityKey=f"exec-closed-loop-{scene_id}",
                displayName=f"Accept validated asset for {scene_id}",
                data={
                    "decision": f"Accept validated asset for scene {scene_id}",
                    "rationale": (
                        f"Production Executive closed-loop validation "
                        f"(asset={asset_id}, score={score}, passed={payload.get('passed')})"
                    ),
                    "sceneId": scene_id,
                    "impact": "storyboard / image acceptance",
                    "notes": (
                        f"source=production_executive; executiveJobId={job.id}; "
                        f"sessionId={session_id}; reportId={payload.get('reportId')}"
                    ),
                },
                lifecycleStatus="in_review",
            )
        ],
        summary=f"Closed-loop validation accept for scene {scene_id}",
        changeReason="production_executive_closed_loop",
    )
    prop = ProposalService.create_proposal(
        db,
        project_id=job.projectId,
        proposal_type="entity_create",
        title=f"Executive: accept validated asset ({scene_id})",
        summary=mutations.summary,
        payload=mutations,
        request_id=job.id,
        created_by=job.owner or "production_executive",
    )
    out = {
        "proposalId": prop.id,
        "status": prop.status,
        "path": "M2.2 Proposal → Review → Approval",
    }
    return HandlerResult(ok=True, status="Completed", result=validate_job_output(job.type, out))


def _handle_await_approval(db: Session, job: JobOut, payload: dict[str, Any]) -> HandlerResult:
    proposal_id = payload.get("proposalId")
    if not proposal_id:
        return HandlerResult(ok=False, status="Failed", error="await_approval requires proposalId")

    proposal_status: Optional[str] = None
    try:
        prop = ProposalService.get(db, job.projectId, proposal_id)
        proposal_status = prop.status
    except CoDirectorError as exc:
        if exc.code != "PROPOSAL_NOT_FOUND" and "not found" not in (exc.message or "").lower():
            return HandlerResult(ok=False, status="Failed", error=str(exc.message))

    if proposal_status in ("rejected", "cancelled"):
        return HandlerResult(
            ok=False,
            status="Cancelled",
            error=f"proposal {proposal_status}",
            result={"proposalId": proposal_id, "proposalStatus": proposal_status},
        )

    # External mark-approval adapter OR proposal already approved/applied via M2.2 UI.
    if payload.get("proposalApproved") or proposal_status in ("completed", "executing"):
        out = {
            "proposalId": proposal_id,
            "awaited": True,
            "approvedExternally": True,
            "proposalStatus": proposal_status or "approved_signal",
            "message": "M2.2 approval signal received (autoApproved=false)",
        }
        return HandlerResult(ok=True, status="Completed", result=validate_job_output(job.type, out))

    out = {
        "proposalId": proposal_id,
        "awaited": True,
        "approvedExternally": False,
        "proposalStatus": proposal_status or "pending",
        "message": "Waiting for M2.2 Proposal → Review → Approval (not auto-approved)",
    }
    return HandlerResult(
        ok=True,
        status="NeedsReview",
        needs_review=True,
        result=validate_job_output(job.type, out),
    )


def _handle_apply_canon(db: Session, job: JobOut, payload: dict[str, Any]) -> HandlerResult:
    """Apply canon only through ProposalService.approve after explicit approval.

    Never mutates Production Bible canon directly; requires proposalApproved and
    delegates apply to the M2.2 ProposalService approval path.
    """
    proposal_id = payload.get("proposalId")
    if not proposal_id:
        return HandlerResult(ok=False, status="Failed", error="apply_canon requires proposalId")

    try:
        prop = ProposalService.get(db, job.projectId, proposal_id)
    except CoDirectorError as exc:
        return HandlerResult(ok=False, status="Failed", error=str(exc.message))

    if prop.proposalType == "tool_call":
        # Closed-loop uses bible entity proposals; tool proposals are out of scope here.
        return HandlerResult(
            ok=False,
            status="Blocked",
            error="apply_canon expects a bible proposal type, not tool_call",
        )

    if prop.status == "rejected":
        return HandlerResult(
            ok=False,
            status="Blocked",
            error="apply_canon blocked: proposal rejected",
        )

    if prop.status == "completed":
        receipt = (
            db.query(CoDirectorExecutionReceipt)
            .filter(
                CoDirectorExecutionReceipt.proposal_id == proposal_id,
                CoDirectorExecutionReceipt.status == "success",
            )
            .order_by(CoDirectorExecutionReceipt.executed_at.desc())
            .first()
        )
        out = {
            "proposalId": proposal_id,
            "applied": True,
            "receiptId": receipt.id if receipt else None,
            "resultingVersionId": receipt.resulting_version_id if receipt else None,
            "notes": "Idempotent: proposal already applied; returning existing receipt.",
        }
        return HandlerResult(ok=True, status="Completed", result=validate_job_output(job.type, out))

    if not payload.get("proposalApproved"):
        return HandlerResult(
            ok=False,
            status="Blocked",
            error="apply_canon blocked: proposal not approved (M2.2 gate)",
        )

    try:
        receipt = ProposalService.approve(
            db,
            job.projectId,
            proposal_id,
            note="Production Executive apply_canon after explicit M2.2 approval signal",
            decided_by=job.owner or "production_executive",
        )
    except CoDirectorError as exc:
        if exc.code == APPROVAL_ALREADY_RECORDED:
            existing = (
                db.query(CoDirectorExecutionReceipt)
                .filter(CoDirectorExecutionReceipt.proposal_id == proposal_id)
                .order_by(CoDirectorExecutionReceipt.executed_at.desc())
                .first()
            )
            out = {
                "proposalId": proposal_id,
                "applied": True,
                "receiptId": existing.id if existing else None,
                "resultingVersionId": existing.resulting_version_id if existing else None,
                "notes": "Idempotent approval-already-recorded.",
            }
            return HandlerResult(ok=True, status="Completed", result=validate_job_output(job.type, out))
        return HandlerResult(ok=False, status="Failed", error=str(exc.message))

    out = {
        "proposalId": proposal_id,
        "applied": receipt.status == "success",
        "receiptId": receipt.id,
        "resultingVersionId": receipt.resultingVersionId,
        "notes": "Applied via ProposalService.approve after explicit approval — never silent canon.",
    }
    return HandlerResult(ok=True, status="Completed", result=validate_job_output(job.type, out))




def _handle_model_discover(db: Session, job: JobOut, payload: dict[str, Any]) -> HandlerResult:
    from ..m28.radar.service import RadarService

    source = str(payload.get("source") or "huggingface")
    out = RadarService.discover(db, source=source)
    return HandlerResult(ok=True, status="Completed", result=validate_job_output(job.type, out))


def _handle_evaluate_compatibility(db: Session, job: JobOut, payload: dict[str, Any]) -> HandlerResult:
    from ..m28.compat.service import CompatService

    entry_id = payload.get("entryId")
    if not entry_id:
        return HandlerResult(ok=False, status="Failed", error="evaluate_compatibility requires entryId")
    out = CompatService.evaluate(db, entry_id=str(entry_id), env_profile=payload.get("env"))
    return HandlerResult(ok=True, status="Completed", result=validate_job_output(job.type, out))


def _handle_sandbox_plan(db: Session, job: JobOut, payload: dict[str, Any]) -> HandlerResult:
    from ..m28.sandbox.service import SandboxService

    sandbox_id = payload.get("sandboxId")
    entry_id = payload.get("entryId")
    if not sandbox_id or not entry_id:
        return HandlerResult(ok=False, status="Failed", error="sandbox_plan requires sandboxId and entryId")
    out = SandboxService.create_plan(db, sandbox_id=str(sandbox_id), entry_id=str(entry_id))
    return HandlerResult(ok=True, status="Completed", result=validate_job_output(job.type, out))


def _handle_sandbox_install(db: Session, job: JobOut, payload: dict[str, Any]) -> HandlerResult:
    from ..m28.sandbox.service import SandboxService

    plan_id = payload.get("planId")
    if not plan_id:
        return HandlerResult(ok=False, status="Failed", error="sandbox_install requires planId")
    if not payload.get("approved"):
        return HandlerResult(
            ok=False,
            status="Blocked",
            error="sandbox_install blocked: approval required (no silent install)",
        )
    try:
        out = SandboxService.execute_approved_install(db, plan_id=str(plan_id))
    except PermissionError as exc:
        return HandlerResult(ok=False, status="Blocked", error=str(exc))
    return HandlerResult(ok=True, status="Completed", result=validate_job_output(job.type, out))


def _handle_sandbox_validate(db: Session, job: JobOut, payload: dict[str, Any]) -> HandlerResult:
    from ..m28.sandbox.service import SandboxService

    sandbox_id = payload.get("sandboxId")
    if not sandbox_id:
        return HandlerResult(ok=False, status="Failed", error="sandbox_validate requires sandboxId")
    out = SandboxService.validate(db, str(sandbox_id))
    return HandlerResult(ok=True, status="Completed", result=validate_job_output(job.type, out))


def _handle_sandbox_promote(db: Session, job: JobOut, payload: dict[str, Any]) -> HandlerResult:
    if not payload.get("approved"):
        return HandlerResult(
            ok=False,
            status="Blocked",
            error="sandbox_promote blocked: approval required (no silent promote)",
        )
    manifest = payload.get("manifest") or {}
    if not manifest.get("approval"):
        return HandlerResult(
            ok=False,
            status="Blocked",
            error="sandbox_promote blocked: missing approval on manifest",
        )
    out = {
        "manifestId": payload.get("manifestId"),
        "sandboxId": payload.get("sandboxId"),
        "promoted": False,
        "recorded": True,
        "note": "Promotion recorded via M2.7 job; no silent production install",
        "manifest": manifest,
    }
    return HandlerResult(ok=True, status="Completed", result=validate_job_output(job.type, out))


def _handle_recipe_stage(db: Session, job: JobOut, payload: dict[str, Any]) -> HandlerResult:
    from ..m28.recipes.service import RecipeService

    recipe_id = payload.get("recipeId")
    stage_id = payload.get("stageId")
    if not recipe_id or not stage_id:
        return HandlerResult(ok=False, status="Failed", error="recipe_stage requires recipeId and stageId")
    failed = bool(payload.get("simulateProviderFailure") or payload.get("forceFail"))
    out = RecipeService.complete_stage(
        db, recipe_id=str(recipe_id), stage_id=str(stage_id), failed=failed
    )
    if failed:
        return HandlerResult(ok=False, status="Failed", error="simulated provider failure", result=out)
    return HandlerResult(ok=True, status="Completed", result=validate_job_output(job.type, out))


def _handle_apply_shot_profile(db: Session, job: JobOut, payload: dict[str, Any]) -> HandlerResult:
    from ..m28.shot_profiles.service import ShotProfileService

    profile_id = payload.get("profileId")
    if not profile_id:
        return HandlerResult(ok=False, status="Failed", error="apply_shot_profile requires profileId")
    profile = ShotProfileService.get(db, str(profile_id))
    if not profile:
        return HandlerResult(ok=False, status="Failed", error="shot profile not found")
    out = {
        "profileId": profile_id,
        "versionId": profile.get("activeVersionId"),
        "payload": profile.get("payload"),
        "applied": True,
        "provider": payload.get("provider") or "fixture",
        "note": "Shot profile applied to generation payload via M2.7 job",
    }
    return HandlerResult(ok=True, status="Completed", result=validate_job_output(job.type, out))




def _m29_run(fn, db: Session, job: JobOut, payload: dict[str, Any]) -> HandlerResult:
    from ..m29.providers import ProviderError, ProviderUnavailable, handler_status_for_exc

    try:
        out = fn(db, payload, job.projectId)
    except (ProviderUnavailable, ProviderError, PermissionError, ValueError, KeyError) as exc:
        return HandlerResult(ok=False, status=handler_status_for_exc(exc), error=str(exc))
    except Exception as exc:  # noqa: BLE001
        return HandlerResult(ok=False, status="Failed", error=str(exc))
    return HandlerResult(ok=True, status="Completed", result=out)


def _handle_frame_generate(db: Session, job: JobOut, payload: dict[str, Any]) -> HandlerResult:
    from ..m29.frames.service import FramesService

    return _m29_run(FramesService.execute_job, db, job, payload)


def _handle_frame_sequence(db: Session, job: JobOut, payload: dict[str, Any]) -> HandlerResult:
    return _handle_frame_generate(db, job, payload)


def _handle_video_generate(db: Session, job: JobOut, payload: dict[str, Any]) -> HandlerResult:
    from ..m29.video.service import VideoService

    return _m29_run(VideoService.execute_job, db, job, payload)


def _handle_lipsync_generate(db: Session, job: JobOut, payload: dict[str, Any]) -> HandlerResult:
    from ..m29.lipsync.service import LipsyncService

    return _m29_run(LipsyncService.execute_lipsync_job, db, job, payload)


def _handle_mouth_track_generate(db: Session, job: JobOut, payload: dict[str, Any]) -> HandlerResult:
    from ..m29.lipsync.service import LipsyncService

    return _m29_run(LipsyncService.execute_mouth_track_job, db, job, payload)


def _handle_audio_generate(db: Session, job: JobOut, payload: dict[str, Any]) -> HandlerResult:
    from ..m29.audio.service import AudioService

    return _m29_run(AudioService.execute_job, db, job, payload)


def _handle_audio_process(db: Session, job: JobOut, payload: dict[str, Any]) -> HandlerResult:
    return _handle_audio_generate(db, job, payload)


def _handle_timeline_render(db: Session, job: JobOut, payload: dict[str, Any]) -> HandlerResult:
    from ..m29.render.service import RenderService

    return _m29_run(RenderService.execute_job, db, job, payload)


def _handle_scene_render(db: Session, job: JobOut, payload: dict[str, Any]) -> HandlerResult:
    return _handle_timeline_render(db, job, payload)


def _handle_edit_apply(db: Session, job: JobOut, payload: dict[str, Any]) -> HandlerResult:
    from ..m29.editing.service import EditingService

    return _m29_run(EditingService.execute_job, db, job, payload)


def execute_job(job: JobOut, db: Session | None = None) -> HandlerResult:
    """Run a single job attempt. Pass db for real service wiring; without db, generic only."""
    payload = dict(job.payload or {})
    if payload.get("forceFail"):
        return HandlerResult(
            ok=False,
            status="Failed",
            error=str(payload.get("failMessage") or "forced failure"),
        )

    job_type = job.type

    known = {
        JobType.STORYBOARD_GENERATE.value,
        JobType.IMAGE_GENERATE.value,
        JobType.VALIDATE.value,
        JobType.CREATE_PROPOSAL.value,
        JobType.AWAIT_APPROVAL.value,
        JobType.APPLY_CANON.value,
        JobType.MODEL_DISCOVER.value,
        JobType.EVALUATE_COMPATIBILITY.value,
        JobType.SANDBOX_PLAN.value,
        JobType.SANDBOX_INSTALL.value,
        JobType.SANDBOX_VALIDATE.value,
        JobType.SANDBOX_PROMOTE.value,
        JobType.RECIPE_STAGE.value,
        JobType.APPLY_SHOT_PROFILE.value,
        JobType.FRAME_GENERATE.value,
        JobType.FRAME_SEQUENCE.value,
        JobType.VIDEO_GENERATE.value,
        JobType.LIPSYNC_GENERATE.value,
        JobType.MOUTH_TRACK_GENERATE.value,
        JobType.AUDIO_GENERATE.value,
        JobType.AUDIO_PROCESS.value,
        JobType.TIMELINE_RENDER.value,
        JobType.SCENE_RENDER.value,
        JobType.EDIT_APPLY.value,
    }

    # Generic jobs remain lightweight (orchestration tests / drain).
    if job_type == JobType.GENERIC.value or job_type not in known:
        return HandlerResult(ok=True, status="Completed", result={"echo": payload, "type": job_type})

    if db is None:
        return HandlerResult(
            ok=False,
            status="Failed",
            error="executive handler requires in-process Session (no self-HTTP)",
        )

    # Closed-loop types enforce contracts; M2.8 types accept free-form payload dicts.
    if job_type in {
        JobType.STORYBOARD_GENERATE.value,
        JobType.IMAGE_GENERATE.value,
        JobType.VALIDATE.value,
        JobType.CREATE_PROPOSAL.value,
        JobType.AWAIT_APPROVAL.value,
        JobType.APPLY_CANON.value,
    }:
        try:
            validate_job_input(job_type, payload, project_id=job.projectId)
        except ValueError as exc:
            return HandlerResult(ok=False, status="Failed", error=str(exc))

    try:
        if job_type == JobType.STORYBOARD_GENERATE.value:
            return _handle_storyboard(db, job, payload)
        if job_type == JobType.IMAGE_GENERATE.value:
            return _handle_image(db, job, payload)
        if job_type == JobType.VALIDATE.value:
            return _handle_validate(db, job, payload)
        if job_type == JobType.CREATE_PROPOSAL.value:
            return _handle_create_proposal(db, job, payload)
        if job_type == JobType.AWAIT_APPROVAL.value:
            return _handle_await_approval(db, job, payload)
        if job_type == JobType.APPLY_CANON.value:
            return _handle_apply_canon(db, job, payload)
        if job_type == JobType.MODEL_DISCOVER.value:
            return _handle_model_discover(db, job, payload)
        if job_type == JobType.EVALUATE_COMPATIBILITY.value:
            return _handle_evaluate_compatibility(db, job, payload)
        if job_type == JobType.SANDBOX_PLAN.value:
            return _handle_sandbox_plan(db, job, payload)
        if job_type == JobType.SANDBOX_INSTALL.value:
            return _handle_sandbox_install(db, job, payload)
        if job_type == JobType.SANDBOX_VALIDATE.value:
            return _handle_sandbox_validate(db, job, payload)
        if job_type == JobType.SANDBOX_PROMOTE.value:
            return _handle_sandbox_promote(db, job, payload)
        if job_type == JobType.RECIPE_STAGE.value:
            return _handle_recipe_stage(db, job, payload)
        if job_type == JobType.APPLY_SHOT_PROFILE.value:
            return _handle_apply_shot_profile(db, job, payload)
        if job_type == JobType.FRAME_GENERATE.value:
            return _handle_frame_generate(db, job, payload)
        if job_type == JobType.FRAME_SEQUENCE.value:
            return _handle_frame_sequence(db, job, payload)
        if job_type == JobType.VIDEO_GENERATE.value:
            return _handle_video_generate(db, job, payload)
        if job_type == JobType.LIPSYNC_GENERATE.value:
            return _handle_lipsync_generate(db, job, payload)
        if job_type == JobType.MOUTH_TRACK_GENERATE.value:
            return _handle_mouth_track_generate(db, job, payload)
        if job_type == JobType.AUDIO_GENERATE.value:
            return _handle_audio_generate(db, job, payload)
        if job_type == JobType.AUDIO_PROCESS.value:
            return _handle_audio_process(db, job, payload)
        if job_type == JobType.TIMELINE_RENDER.value:
            return _handle_timeline_render(db, job, payload)
        if job_type == JobType.SCENE_RENDER.value:
            return _handle_scene_render(db, job, payload)
        if job_type == JobType.EDIT_APPLY.value:
            return _handle_edit_apply(db, job, payload)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Executive handler failed job=%s type=%s", job.id, job_type)
        return HandlerResult(ok=False, status="Failed", error=str(exc)[:500])

    return HandlerResult(ok=True, status="Completed", result={"echo": payload, "type": job_type})
