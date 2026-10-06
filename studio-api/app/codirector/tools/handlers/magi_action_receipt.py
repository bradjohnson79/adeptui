"""MagiActionReceipt + VERIFY helpers (CONTRACT_FREEZE.md).

Reuses CoDirector proposal/execution bus; does not invent a second store.
VERIFY always re-reads sequence / finishing / MAGI Job rows — never prose-only success.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

RECEIPT_STATUSES = frozenset(
    {"proposed", "approved", "applied", "verified", "failed", "refused"}
)

ALLOWED_MUTATORS = frozenset(
    {
        "magi.color.apply",
        "magi.graphics.apply",
        "magi.upscale",
        "magi.audio.generate",
        "magi.render",
        "magi.propose_finish",
        "magi.recipe.apply",
        "magi.transition.apply",
        "magi.compare",
    }
)

NOT_SUPPORTED = frozenset(
    {
        "magi.trim",
        "magi.split",
        "magi.move",
        "magi.overlay",
        "magi.publish",
        "magi.final_check",
        "magi.mix_assist",
        "cd.publish",
        "cd.final_check",
    }
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_action_id() -> str:
    return f"magi_act_{uuid.uuid4().hex[:16]}"


def default_verify_plan(tool_id: str) -> dict[str, Any]:
    if tool_id == "magi.color.apply":
        return {
            "checks": [
                "clip_grade_persisted",
                "output_asset_exists",
                "source_asset_preserved",
            ]
        }
    if tool_id == "magi.upscale":
        return {
            "checks": [
                "job_terminal_or_active",
                "job_kind_magi_upscale",
                "output_asset_when_done",
            ]
        }
    if tool_id == "magi.audio.generate":
        return {
            "checks": [
                "job_terminal_or_active",
                "job_kind_magi_audio_generate",
                "finishing_audio_or_sequence_clip_when_done",
            ]
        }
    if tool_id == "magi.render":
        return {
            "checks": [
                "job_terminal_or_active",
                "job_kind_magi_final_render",
                "finishing_render_when_done",
            ]
        }
    if tool_id == "magi.propose_finish":
        return {
            "checks": [
                "re_read_sequence",
                "source_asset_preserved",
            ]
        }
    return {"checks": ["re_read_sequence"]}


def build_receipt(
    *,
    action_id: str | None = None,
    tool_id: str,
    status: str,
    asset_ids_in: list[str] | None = None,
    asset_ids_out: list[str] | None = None,
    job_id: str | None = None,
    evidence: dict[str, Any] | None = None,
    error: str | None = None,
    verify_plan: dict[str, Any] | None = None,
    requested_at: str | None = None,
    applied_at: str | None = None,
    verified_at: str | None = None,
    domain: str | None = None,
) -> dict[str, Any]:
    if status not in RECEIPT_STATUSES:
        raise ValueError(f"Invalid MagiActionReceipt status: {status}")
    receipt: dict[str, Any] = {
        "actionId": action_id or new_action_id(),
        "toolId": tool_id,
        "status": status,
        "requestedAt": requested_at or utc_now(),
        "assetIdsIn": list(asset_ids_in or []),
        "assetIdsOut": list(asset_ids_out or []),
        "evidence": dict(evidence or {}),
        "verifyPlan": verify_plan if verify_plan is not None else default_verify_plan(tool_id),
    }
    if domain:
        receipt["domain"] = domain
    if applied_at:
        receipt["appliedAt"] = applied_at
    if verified_at:
        receipt["verifiedAt"] = verified_at
    if job_id:
        receipt["jobId"] = job_id
    if error:
        receipt["error"] = error
    return receipt


def _job_payload(db: Session, project_id: str, job_id: str | None) -> dict[str, Any] | None:
    if not job_id:
        return None
    from ....db import Job

    job = db.get(Job, job_id)
    if job is None or job.project_id != project_id:
        return {"found": False, "jobId": job_id}
    history: dict[str, Any] = {}
    try:
        history = json.loads(job.history_json or "{}")
    except Exception:
        history = {}
    unified_status = str(job.status or "")
    try:
        from ....codirector.unified_jobs import to_unified_dto
        unified_status = str((to_unified_dto("studio", job) or {}).get("status") or job.status or "")
    except Exception:
        pass
    return {
        "found": True,
        "jobId": job.id,
        "kind": job.kind,
        "status": job.status,
        "unifiedStatus": unified_status,
        "stage": job.stage,
        "progress": job.progress,
        "message": job.message,
        "outputPath": job.output_path,
        "history": history,
        "jobDoneTruth": bool(str(job.status or "") == "done" or unified_status == "completed"),
    }


def verify_magi_action(
    db: Session,
    project_id: str,
    *,
    tool_id: str,
    clip_id: str | None = None,
    asset_ids_in: list[str] | None = None,
    asset_ids_out: list[str] | None = None,
    job_id: str | None = None,
    preset_id: str | None = None,
    verify_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Re-read MAGI sequence / finishing / Job and score verifyPlan checks."""
    from ....db import Asset
    from ....magi.finishing import finishing_of
    from ....magi.jobs import ACTIVE, TERMINAL
    from ....magi.sequence.store import get_sequence

    plan = verify_plan or default_verify_plan(tool_id)
    checks_wanted = list(plan.get("checks") or [])
    results: dict[str, Any] = {}
    evidence: dict[str, Any] = {"source": "magi.verify_magi_action"}

    seq = get_sequence(project_id)
    finishing = finishing_of(seq)
    evidence["sequenceClipCount"] = len(seq.get("clips") or [])
    evidence["finishingKeys"] = sorted(finishing.keys())

    job_info = _job_payload(db, project_id, job_id)
    if job_info is not None:
        evidence["job"] = job_info

    for check in checks_wanted:
        if check == "clip_grade_persisted":
            grades = finishing.get("clipGrades") or {}
            if clip_id:
                grade = grades.get(clip_id) if isinstance(grades, dict) else None
                ok = isinstance(grade, dict) and (
                    not preset_id or str(grade.get("presetId") or "") == str(preset_id)
                )
                results[check] = {
                    "ok": bool(ok),
                    "grade": grade if isinstance(grade, dict) else None,
                }
            else:
                results[check] = {
                    "ok": bool(grades),
                    "gradeCount": len(grades) if isinstance(grades, dict) else 0,
                }
        elif check == "output_asset_exists":
            outs = list(asset_ids_out or [])
            found = []
            for aid in outs:
                row = db.get(Asset, aid)
                found.append(
                    {
                        "assetId": aid,
                        "exists": bool(row and row.project_id == project_id),
                        "kind": getattr(row, "kind", None) if row else None,
                        "tag": getattr(row, "tag", None) if row else None,
                    }
                )
            results[check] = {
                "ok": bool(outs) and all(f["exists"] for f in found),
                "assets": found,
            }
        elif check == "source_asset_preserved":
            inns = list(asset_ids_in or [])
            preserved = []
            for aid in inns:
                row = db.get(Asset, aid)
                preserved.append(
                    {
                        "assetId": aid,
                        "exists": bool(row and row.project_id == project_id),
                    }
                )
            results[check] = {
                "ok": (not inns) or all(p["exists"] for p in preserved),
                "assets": preserved,
            }
        elif check == "job_terminal_or_active":
            if not job_info or not job_info.get("found"):
                results[check] = {"ok": False, "reason": "job_not_found"}
            else:
                st = str(job_info.get("status") or "")
                results[check] = {"ok": st in ACTIVE or st in TERMINAL, "status": st}
        elif check in {
            "job_kind_magi_upscale",
            "job_kind_magi_audio_generate",
            "job_kind_magi_final_render",
        }:
            expected = {
                "job_kind_magi_upscale": "magi_upscale",
                "job_kind_magi_audio_generate": "magi_audio_generate",
                "job_kind_magi_final_render": "magi_final_render",
            }[check]
            if not job_info or not job_info.get("found"):
                results[check] = {"ok": False, "reason": "job_not_found"}
            else:
                results[check] = {
                    "ok": str(job_info.get("kind") or "") == expected,
                    "kind": job_info.get("kind"),
                    "expected": expected,
                }
        elif check == "output_asset_when_done":
            if not job_info or not job_info.get("found"):
                results[check] = {"ok": False, "reason": "job_not_found"}
            elif str(job_info.get("status") or "") in ACTIVE:
                results[check] = {"ok": True, "pending": True, "status": job_info.get("status")}
            elif bool(job_info.get("jobDoneTruth") or str(job_info.get("status") or "") == "done" or str(job_info.get("unifiedStatus") or "") == "completed"):
                hist = job_info.get("history") or {}
                out_id = hist.get("assetId") or hist.get("output_asset_id") or hist.get("outputAssetId")
                results[check] = {"ok": bool(out_id), "assetId": out_id}
            else:
                results[check] = {
                    "ok": False,
                    "status": job_info.get("status"),
                    "message": job_info.get("message"),
                }
        elif check == "finishing_audio_or_sequence_clip_when_done":
            if job_info and job_info.get("found") and str(job_info.get("status") or "") in ACTIVE:
                results[check] = {"ok": True, "pending": True}
            else:
                audio = finishing.get("audio")
                has_audio_meta = isinstance(audio, dict) and bool(audio)
                clips = seq.get("clips") or []
                out_set = set(asset_ids_out or [])
                has_audio_clip = any(str(c.get("assetId") or "") in out_set for c in clips) if out_set else False
                if job_info and str(job_info.get("status") or "") == "done":
                    results[check] = {
                        "ok": True,
                        "finishingAudio": audio if isinstance(audio, dict) else None,
                        "hasAudioClip": has_audio_clip,
                        "hasAudioMeta": has_audio_meta,
                    }
                else:
                    results[check] = {
                        "ok": bool(has_audio_meta),
                        "finishingAudio": audio if isinstance(audio, dict) else None,
                    }
        elif check == "finishing_render_when_done":
            if job_info and job_info.get("found") and str(job_info.get("status") or "") in ACTIVE:
                results[check] = {"ok": True, "pending": True}
            else:
                render = finishing.get("render") or finishing.get("lastRender")
                if job_info and str(job_info.get("status") or "") == "done":
                    results[check] = {
                        "ok": True,
                        "finishingRender": render if isinstance(render, dict) else render,
                        "jobStatus": job_info.get("status"),
                    }
                else:
                    results[check] = {
                        "ok": isinstance(render, dict) and bool(render),
                        "finishingRender": render if isinstance(render, dict) else render,
                    }
        elif check == "re_read_sequence":
            results[check] = {"ok": isinstance(seq, dict) and bool(seq)}
        else:
            results[check] = {"ok": False, "reason": f"unknown_check:{check}"}

    hard_fails = [
        name
        for name, payload in results.items()
        if not payload.get("ok") and not payload.get("pending")
    ]
    any_pending = any(payload.get("pending") for payload in results.values())

    if hard_fails:
        status = "failed"
        ok = False
    elif any_pending:
        status = "applied"
        ok = True
    else:
        status = "verified"
        ok = True

    return {
        "ok": ok,
        "status": status,
        "checks": results,
        "evidence": evidence,
        "verifyPlan": plan,
        "verifiedAt": utc_now() if status == "verified" else None,
    }


def wrap_apply_result(
    *,
    tool_id: str,
    domain: str,
    apply_result: dict[str, Any],
    asset_ids_in: list[str],
    db: Session,
    project_id: str,
    clip_id: str | None = None,
    preset_id: str | None = None,
    action_id: str | None = None,
    requested_at: str | None = None,
    verify_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Attach MagiActionReceipt to an apply result and run VERIFY when possible."""
    applied_at = utc_now()
    outs: list[str] = []
    for key in ("assetId", "output_asset_id", "outputAssetId"):
        val = apply_result.get(key)
        if val:
            outs.append(str(val))
    for key in ("assetIds", "outputAssetIds"):
        val = apply_result.get(key)
        if isinstance(val, list):
            outs.extend(str(x) for x in val if x)

    job_id = apply_result.get("jobId")
    if not job_id and apply_result.get("jobIds"):
        job_ids = apply_result.get("jobIds") or []
        job_id = job_ids[0] if job_ids else None
    if job_id is not None:
        job_id = str(job_id)

    error = None
    status = "applied"
    if apply_result.get("ok") is False:
        status = "failed"
        error = str(apply_result.get("error") or apply_result.get("message") or "apply failed")

    receipt = build_receipt(
        action_id=action_id,
        tool_id=tool_id,
        status=status,
        asset_ids_in=asset_ids_in,
        asset_ids_out=outs,
        job_id=job_id,
        evidence={
            "applyResultKeys": sorted(apply_result.keys()),
            "source": "magi.wrap_apply_result",
        },
        error=error,
        requested_at=requested_at,
        applied_at=applied_at,
        domain=domain,
        verify_plan=verify_plan,
    )

    if status == "applied":
        verify = verify_magi_action(
            db,
            project_id,
            tool_id=tool_id,
            clip_id=clip_id,
            asset_ids_in=asset_ids_in,
            asset_ids_out=outs,
            job_id=job_id,
            preset_id=preset_id,
            verify_plan=receipt["verifyPlan"],
        )
        receipt["evidence"]["verify"] = {
            "checks": verify.get("checks"),
            "job": (verify.get("evidence") or {}).get("job"),
            "finishingKeys": (verify.get("evidence") or {}).get("finishingKeys"),
        }
        receipt["status"] = verify["status"]
        if verify.get("verifiedAt"):
            receipt["verifiedAt"] = verify["verifiedAt"]
        if verify["status"] == "failed":
            receipt["error"] = receipt.get("error") or "verify_failed"
            apply_result = {**apply_result, "verifyOk": False}
        else:
            apply_result = {
                **apply_result,
                "verifyOk": verify["ok"],
                "verifyStatus": verify["status"],
            }

    return {**apply_result, "magiActionReceipt": receipt}
