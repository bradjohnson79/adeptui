"""M4.12 Co-Director avatar presentation intelligence tools."""

from __future__ import annotations

from typing import Any

from .... import avatar_studio as avatar
from ....avatar_runtimes import inspect_runtime
from ..definitions import ToolContext, ToolPreview


def _string(args: dict[str, Any], key: str) -> str:
    return str(args.get(key) or "").strip()


def _int(args: dict[str, Any], key: str, default: int = 0) -> int:
    value = args.get(key)
    if value in (None, ""):
        return default
    return int(value)


def _bool(args: dict[str, Any], key: str, default: bool = False) -> bool:
    value = args.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _latest_session_id(ctx: ToolContext) -> str:
    row = (
        ctx.db.query(avatar.AvatarSessionRow)
        .filter(avatar.AvatarSessionRow.project_id == ctx.project_id)
        .order_by(avatar.AvatarSessionRow.updated_at.desc())
        .first()
    )
    if not row:
        raise ValueError("No Avatar Studio session exists for this project yet.")
    return str(row.id)


def _session_id(ctx: ToolContext, args: dict[str, Any]) -> str:
    session_id = _string(args, "sessionId")
    return session_id or _latest_session_id(ctx)


def _session_data(ctx: ToolContext, args: dict[str, Any]) -> tuple[avatar.AvatarSessionRow, dict[str, Any]]:
    session_row = avatar._session_or_404(ctx.db, ctx.project_id, _session_id(ctx, args))
    return session_row, avatar._row_to_data(session_row)


def _job_id(args: dict[str, Any]) -> str:
    job_id = _string(args, "jobId")
    if not job_id:
        raise ValueError("jobId is required")
    return job_id


def _job_data(ctx: ToolContext, args: dict[str, Any]) -> tuple[avatar.AvatarProjectJobRow, dict[str, Any]]:
    job_row = avatar._job_or_404(ctx.db, ctx.project_id, _job_id(args))
    return job_row, avatar._job_to_row_data(job_row)


def _section(job: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    section_id = _string(args, "sectionId")
    if not section_id:
        raise ValueError("sectionId is required")
    return avatar._section_or_404(job, section_id)


def _sync_section_plan(section: dict[str, Any]) -> None:
    presentation = section.get("presentationPlan")
    if not isinstance(presentation, dict):
        presentation = {}
        section["presentationPlan"] = presentation
    key_pairs = (
        ("summary", "summary"),
        ("delivery", "delivery"),
        ("gaze", "gaze"),
        ("gesture", "gesture"),
        ("pacing", "pacing"),
        ("emphasis", "emphasis"),
        ("posture", "posture"),
        ("pronunciation", "pronunciation"),
        ("transition", "transition"),
        ("backgroundRecommendation", "backgroundRecommendation"),
        ("framingRecommendation", "framingRecommendation"),
        ("retakeFocus", "retakeFocus"),
        ("continuityChecklist", "continuityChecklist"),
    )
    for top_key, presentation_key in key_pairs:
        value = section.get(top_key)
        if value not in (None, ""):
            presentation[presentation_key] = value


def _apply_plan_overrides(plan: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    target_duration_ms = _int(args, "targetSectionDurationMs", 0)
    if target_duration_ms > 0:
        plan["sectionTargetSeconds"] = round(target_duration_ms / 1000, 1)
    field_map = {
        "summary": "summary",
        "sectioningStrategy": "sectioningStrategy",
        "deliveryStyle": "deliveryStyle",
        "gazeStyle": "gazeStyle",
        "gestureStyle": "gestureStyle",
        "pacingStyle": "pacingStyle",
        "chapterTransitionStyle": "chapterTransitionStyle",
        "emphasisNotes": "emphasisNotes",
        "postureNotes": "postureNotes",
        "pronunciationNotes": "pronunciationNotes",
        "backgroundRecommendation": "backgroundRecommendation",
        "framingRecommendation": "framingRecommendation",
        "continuityChecklist": "continuityChecklist",
        "retakeGuidance": "retakeGuidance",
    }
    for arg_key, plan_key in field_map.items():
        value = _string(args, arg_key)
        if value:
            plan[plan_key] = value
    for section in plan.get("sections") or []:
        if _string(args, "deliveryStyle"):
            section["delivery"] = plan["deliveryStyle"]
        if _string(args, "gazeStyle"):
            section["gaze"] = plan["gazeStyle"]
        if _string(args, "gestureStyle"):
            section["gesture"] = plan["gestureStyle"]
        if _string(args, "pacingStyle"):
            section["pacing"] = plan["pacingStyle"]
        if _string(args, "chapterTransitionStyle"):
            section["transition"] = plan["chapterTransitionStyle"]
        if _string(args, "postureNotes"):
            section["posture"] = plan["postureNotes"]
        if _string(args, "pronunciationNotes"):
            section["pronunciation"] = plan["pronunciationNotes"]
        if _string(args, "backgroundRecommendation"):
            section["background"] = plan["backgroundRecommendation"]
        if _string(args, "framingRecommendation"):
            section["framing"] = plan["framingRecommendation"]
        if _string(args, "continuityChecklist"):
            section["continuity"] = plan["continuityChecklist"]
        if _string(args, "retakeGuidance"):
            section["retakeFocus"] = plan["retakeGuidance"]
    plan["source"] = "codirector"
    plan["updatedAt"] = avatar._now()
    return plan


async def inspect(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    session_row, session = _session_data(ctx, args)
    active_job = None
    active_job_id = str(session.get("active_job_id") or "").strip()
    if active_job_id:
        try:
            active_job = avatar._job_to_row_data(avatar._job_or_404(ctx.db, ctx.project_id, active_job_id))
        except Exception:
            active_job = None
    return {
        "ok": True,
        "sessionId": session_row.id,
        "sessionName": session.get("name"),
        "characterName": session.get("character_name"),
        "inputMode": session.get("input_mode") or "script",
        "presentationPlan": session.get("presentation_plan") or {},
        "activeJob": active_job,
        "_summary": "Avatar presentation session inspected.",
        "_evidence": {"source": "avatar_studio.session"},
    }


async def get_provider_status(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _, session = _session_data(ctx, args)
    provider_id = avatar._select_provider(session, _string(args, "providerId") or None)
    runtime = inspect_runtime(provider_id)
    return {
        "ok": True,
        "sessionId": session.get("id"),
        "providerId": provider_id,
        "runtime": runtime,
        "supportsLiveGeneration": False,
        "_summary": "Avatar runtime status inspected honestly.",
        "_evidence": {"source": "avatar_runtimes.inspect_runtime"},
    }


async def get_script_context(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _, session = _session_data(ctx, args)
    script_text = str(session.get("dialogue_spoken") or session.get("dialogue_original") or "").strip()
    target_duration_ms = _int(
        args,
        "targetSectionDurationMs",
        int(round(float((session.get("presentation_plan") or {}).get("sectionTargetSeconds") or 0) * 1000)),
    )
    target_duration_ms = max(2000, target_duration_ms or avatar._duration_class_ms(session))
    plan = avatar._compose_presentation_plan(session, target_duration_ms=target_duration_ms, keep_existing=True)
    return {
        "ok": True,
        "sessionId": session.get("id"),
        "scriptText": script_text,
        "estimatedDurationMs": avatar._estimate_duration_ms(script_text, fallback_ms=target_duration_ms),
        "sectionPreview": plan.get("sections") or [],
        "sectionTargetSeconds": plan.get("sectionTargetSeconds"),
        "_summary": "Avatar script context prepared for presentation planning.",
        "_evidence": {"source": "avatar_studio.presentation_plan"},
    }


async def get_voice_context(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _, session = _session_data(ctx, args)
    voice = session.get("voice") or {}
    return {
        "ok": True,
        "sessionId": session.get("id"),
        "inputMode": session.get("input_mode") or "script",
        "voice": {
            "provider": voice.get("provider"),
            "model": voice.get("model"),
            "audioAssetId": voice.get("audio_asset_id"),
            "approvedRecordId": voice.get("approved_record_id"),
            "approvedTakeId": voice.get("approved_take_id"),
            "profileId": voice.get("profile_id"),
            "pronunciationNotes": voice.get("pronunciation_notes"),
        },
        "readyForPlannedSections": bool(
            session.get("dialogue_original") or session.get("dialogue_spoken") or voice.get("audio_asset_id")
        ),
        "_summary": "Avatar voice context inspected.",
        "_evidence": {"source": "avatar_studio.session_voice"},
    }


async def get_job(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _, job = _job_data(ctx, args)
    return {
        "ok": True,
        "job": job,
        "_summary": "Avatar long-form job inspected.",
        "_evidence": {"source": "avatar_studio.job"},
    }


async def get_section(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _, job = _job_data(ctx, args)
    section = _section(job, args)
    index = max(0, int(section.get("order") or 0))
    sections = job.get("sections") or []
    previous_section = sections[index - 1] if index > 0 and index - 1 < len(sections) else None
    next_section = sections[index + 1] if index + 1 < len(sections) else None
    return {
        "ok": True,
        "jobId": job.get("id"),
        "section": section,
        "previousSection": previous_section,
        "nextSection": next_section,
        "_summary": "Avatar section inspected with neighboring continuity context.",
        "_evidence": {"source": "avatar_studio.section"},
    }


async def compare_sections(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _, job = _job_data(ctx, args)
    first = avatar._section_or_404(job, _string(args, "firstSectionId"))
    second = avatar._section_or_404(job, _string(args, "secondSectionId"))
    first_plan = first.get("presentationPlan") or {}
    second_plan = second.get("presentationPlan") or {}
    keys = (
        "delivery",
        "gaze",
        "gesture",
        "pacing",
        "emphasis",
        "posture",
        "pronunciation",
        "transition",
        "backgroundRecommendation",
        "framingRecommendation",
    )
    differences = []
    for key in keys:
        left = first_plan.get(key)
        right = second_plan.get(key)
        if left != right:
            differences.append({"field": key, "first": left, "second": right})
    return {
        "ok": True,
        "jobId": job.get("id"),
        "firstSectionId": first.get("id"),
        "secondSectionId": second.get("id"),
        "differences": differences,
        "_summary": "Avatar sections compared for presentation continuity.",
        "_evidence": {"source": "avatar_studio.section_compare"},
    }


async def check_continuity(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _, job = _job_data(ctx, args)
    warnings: list[dict[str, Any]] = []
    sections = list(job.get("sections") or [])
    if not sections:
        return {"ok": True, "jobId": job.get("id"), "warnings": [], "continuityOk": True}
    shared_profile = sections[0].get("presentationPlan", {}).get("sharedStyleProfileId")
    prior = None
    for section in sections:
        plan = section.get("presentationPlan") or {}
        if plan.get("sharedStyleProfileId") != shared_profile:
            warnings.append(
                {
                    "sectionId": section.get("id"),
                    "code": "style_profile_drift",
                    "message": "This section is not using the shared presentation style profile.",
                }
            )
        if prior:
            prior_plan = prior.get("presentationPlan") or {}
            if plan.get("backgroundRecommendation") != prior_plan.get("backgroundRecommendation"):
                warnings.append(
                    {
                        "sectionId": section.get("id"),
                        "code": "background_shift",
                        "message": "Background recommendation changes between neighboring sections.",
                    }
                )
            if plan.get("framingRecommendation") != prior_plan.get("framingRecommendation"):
                warnings.append(
                    {
                        "sectionId": section.get("id"),
                        "code": "framing_shift",
                        "message": "Framing recommendation changes between neighboring sections.",
                    }
                )
            if int(section.get("overlapBeforeMs") or 0) <= 0:
                warnings.append(
                    {
                        "sectionId": section.get("id"),
                        "code": "overlap_missing",
                        "message": "This section has no overlap-in cushion for a continuity handoff.",
                    }
                )
        prior = section
    return {
        "ok": True,
        "jobId": job.get("id"),
        "continuityOk": len(warnings) == 0,
        "warnings": warnings,
        "_summary": "Avatar continuity audit completed.",
        "_evidence": {"source": "avatar_studio.continuity"},
    }


def preview_create_plan(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    _, session = _session_data(ctx, args)
    plan = _apply_plan_overrides(
        avatar._compose_presentation_plan(
            session,
            target_duration_ms=max(
                2000,
                _int(
                    args,
                    "targetSectionDurationMs",
                    int(round(float((session.get("presentation_plan") or {}).get("sectionTargetSeconds") or 0) * 1000)),
                )
                or avatar._duration_class_ms(session),
            ),
            keep_existing=True,
        ),
        args,
    )
    return ToolPreview(
        summary="Create or refresh the Avatar Studio presentation plan for this session.",
        lines=[
            f"sessionId: {session.get('id')}",
            f"sections planned: {len(plan.get('sections') or [])}",
            f"target section length: {plan.get('sectionTargetSeconds')}s",
            "Updates creator-facing planning notes only. Does not start generation.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_create_plan(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    session_row, session = _session_data(ctx, args)
    target_duration_ms = max(
        2000,
        _int(
            args,
            "targetSectionDurationMs",
            int(round(float((session.get("presentation_plan") or {}).get("sectionTargetSeconds") or 0) * 1000)),
        )
        or avatar._duration_class_ms(session),
    )
    plan = avatar._compose_presentation_plan(session, target_duration_ms=target_duration_ms, keep_existing=True)
    session["presentation_plan"] = _apply_plan_overrides(plan, args)
    avatar._write_session(session_row, session)
    ctx.db.commit()
    return {
        "ok": True,
        "session": avatar._row_to_data(session_row),
        "presentationPlan": session["presentation_plan"],
        "persisted": True,
        "_evidence": {"source": "avatar_studio.presentation_plan"},
    }


def preview_create_job(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    _, session = _session_data(ctx, args)
    target_duration_ms = max(
        2000,
        _int(
            args,
            "targetSectionDurationMs",
            int(round(float((session.get("presentation_plan") or {}).get("sectionTargetSeconds") or 0) * 1000)),
        )
        or avatar._duration_class_ms(session),
    )
    plan = avatar._compose_presentation_plan(session, target_duration_ms=target_duration_ms, keep_existing=True)
    provider_id = avatar._select_provider(session, _string(args, "providerId") or None)
    return ToolPreview(
        summary="Create a long-form Avatar Studio job from the current presenter session.",
        lines=[
            f"sessionId: {session.get('id')}",
            f"providerId: {provider_id}",
            f"planned sections: {len(plan.get('sections') or [])}",
            "Creates a new long-form job only after approval.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_create_job(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    session_id = _session_id(ctx, args)
    return avatar.create_avatar_job(
        ctx.project_id,
        session_id,
        avatar.CreateAvatarJobBody(
            providerId=_string(args, "providerId") or None,
            scriptSourceId=_string(args, "scriptSourceId") or None,
            startImmediately=_bool(args, "startImmediately", False),
            overlapMs=_int(args, "overlapMs", 250),
            targetSectionDurationMs=_int(args, "targetSectionDurationMs", 0) or None,
        ),
        db=ctx.db,
    )


def preview_adjust_section(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    _, job = _job_data(ctx, args)
    section = _section(job, args)
    return ToolPreview(
        summary="Adjust one planned avatar section without regenerating the rest of the job.",
        lines=[
            f"jobId: {job.get('id')}",
            f"section: {section.get('order', 0) + 1}",
            "Updates creator-facing delivery and continuity notes only.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_adjust_section(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    job_row, job = _job_data(ctx, args)
    section = _section(job, args)
    field_map = {
        "summary": "summary",
        "delivery": "delivery",
        "gaze": "gaze",
        "gesture": "gesture",
        "pacing": "pacing",
        "emphasis": "emphasis",
        "posture": "posture",
        "pronunciation": "pronunciation",
        "transition": "transition",
        "backgroundRecommendation": "backgroundRecommendation",
        "framingRecommendation": "framingRecommendation",
        "retakeFocus": "retakeFocus",
        "continuityChecklist": "continuityChecklist",
    }
    for arg_key, section_key in field_map.items():
        value = _string(args, arg_key)
        if value:
            section[section_key] = value
    _sync_section_plan(section)
    section["updatedAt"] = avatar._now()
    avatar._write_job(job_row, avatar._summarize_job(job))
    ctx.db.commit()
    return {
        "ok": True,
        "job": avatar._job_to_row_data(job_row),
        "section": section,
        "persisted": True,
        "_evidence": {"source": "avatar_studio.adjust_section"},
    }


def preview_request_retake(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    _, job = _job_data(ctx, args)
    section = _section(job, args)
    action_type = _string(args, "actionType") or "regenerate_section"
    return ToolPreview(
        summary="Request a retake for one completed Avatar Studio section.",
        lines=[
            f"jobId: {job.get('id')}",
            f"section: {section.get('order', 0) + 1}",
            f"action: {action_type.replace('_', ' ')}",
            "Leaves all other completed sections untouched.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_request_retake(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return avatar.request_avatar_section_retake(
        ctx.project_id,
        _job_id(args),
        _string(args, "sectionId"),
        avatar.SectionRetakeBody(
            note=_string(args, "note"),
            actionType=_string(args, "actionType") or "regenerate_section",
            reason=_string(args, "reason"),
        ),
        db=ctx.db,
    )


def preview_repair_lipsync(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    _, job = _job_data(ctx, args)
    section = _section(job, args) if _string(args, "sectionId") else None
    runtime = inspect_runtime("musetalk-1-5-local")
    installed = str(runtime.get("healthState") or "") != "not_installed"
    return ToolPreview(
        summary="Prepare a MuseTalk Lip-Sync Repair plan for the selected avatar section.",
        lines=[
            f"jobId: {job.get('id')}",
            f"sectionId: {section.get('id') if section else 'all-sections'}",
            f"provider: musetalk-1-5-local ({'installed' if installed else 'not installed'})",
            "Does not run a provider repair automatically.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
        warnings=[
            "This only records a repair plan. It does not execute MuseTalk or overwrite output media."
        ],
    )


def apply_repair_lipsync(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    job_row, job = _job_data(ctx, args)
    section_id = _string(args, "sectionId")
    runtime = inspect_runtime("musetalk-1-5-local")
    if str(runtime.get("healthState") or "") == "not_installed":
        raise avatar._raise_avatar_error(avatar.AvatarErrorCode.LIPSYNC_REPAIR_PROVIDER_REQUIRED)
    repair_plan = {
        "sectionId": section_id or None,
        "providerId": "musetalk-1-5-local",
        "providerRole": "Lip-Sync Repair",
        "note": _string(args, "note") or "Review mouth timing, phoneme drift, and the handoff pose before rerendering.",
        "updatedAt": avatar._now(),
        "executed": False,
        "runtime": runtime,
    }
    job["lipsyncRepairPlan"] = repair_plan
    if section_id:
        section = avatar._section_or_404(job, section_id)
        section["lipsyncRepairPlan"] = repair_plan
        section["updatedAt"] = avatar._now()
    avatar._write_job(job_row, avatar._summarize_job(job))
    ctx.db.commit()
    return {
        "ok": True,
        "job": avatar._job_to_row_data(job_row),
        "repairPlan": repair_plan,
        "executed": False,
        "_evidence": {"source": "avatar_studio.lipsync_repair_plan"},
    }


def preview_replace_voice(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    _, session = _session_data(ctx, args)
    return ToolPreview(
        summary="Replace the approved voice reference for this avatar session.",
        lines=[
            f"sessionId: {session.get('id')}",
            f"audioAssetId: {_string(args, 'audioAssetId') or 'not set'}",
            f"approvedTakeId: {_string(args, 'approvedTakeId') or 'current approved take'}",
            "Updates voice linkage and pronunciation notes only.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_replace_voice(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    session_row, session = _session_data(ctx, args)
    voice = dict(session.get("voice") or {})
    approved_record_id = _string(args, "approvedRecordId") or str(voice.get("approved_record_id") or "")
    approved_take_id = _string(args, "approvedTakeId") or str(voice.get("approved_take_id") or "")
    if not (approved_record_id and approved_take_id and _string(args, "audioAssetId")):
        raise avatar._raise_avatar_error(avatar.AvatarErrorCode.APPROVED_VOICE_REQUIRED)
    replacements = {
        "provider": _string(args, "providerId") or voice.get("provider") or "voice-performance-m410",
        "model": _string(args, "modelId") or voice.get("model") or "",
        "audio_asset_id": _string(args, "audioAssetId") or None,
        "approved_record_id": approved_record_id or None,
        "approved_take_id": approved_take_id or None,
        "profile_id": _string(args, "profileId") or None,
    }
    pronunciation_notes = _string(args, "pronunciationNotes")
    if pronunciation_notes:
        replacements["pronunciation_notes"] = pronunciation_notes
    voice.update(replacements)
    session["voice"] = voice
    session["presentation_plan"] = avatar._compose_presentation_plan(session, keep_existing=True)
    avatar._write_session(session_row, session)
    ctx.db.commit()
    return {
        "ok": True,
        "session": avatar._row_to_data(session_row),
        "persisted": True,
        "_evidence": {"source": "avatar_studio.voice_replace"},
    }


def preview_assemble(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    _, job = _job_data(ctx, args)
    return ToolPreview(
        summary="Assemble the current Avatar Studio job after section review.",
        lines=[
            f"jobId: {job.get('id')}",
            f"sections: {len(job.get('sections') or [])}",
            "Will still stop if transitions have not been validated.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_assemble(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return avatar.assemble_avatar_job(ctx.project_id, _job_id(args), db=ctx.db)


def preview_prepare_timeline(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    _, job = _job_data(ctx, args)
    placement_mode = _string(args, "placementMode") or "full_presentation"
    return ToolPreview(
        summary="Prepare an Avatar Studio timeline handoff proposal.",
        lines=[
            f"jobId: {job.get('id')}",
            f"placement mode: {placement_mode.replace('_', ' ')}",
            f"trackId: {_string(args, 'trackId') or 'avatar-presenter'}",
            "Stores a creator-approved handoff package only. It does not write the Timeline.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
        warnings=["Timeline clips are never written automatically by this tool."],
    )


def apply_prepare_timeline(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return avatar.prepare_avatar_timeline(
        ctx.project_id,
        _job_id(args),
        avatar.TimelinePrepareBody(
            placementMode=_string(args, "placementMode") or "full_presentation",
            sectionId=_string(args, "sectionId") or None,
            replaceSectionId=_string(args, "replaceSectionId") or None,
            trackId=_string(args, "trackId") or None,
            startMs=_int(args, "startMs", 0),
            confirmReplace=_bool(args, "confirmReplace", False),
        ),
        db=ctx.db,
    )
