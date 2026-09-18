"""Compile multi-step creator requests into ProductionPlan / ExecutionPlan steps.

Asset-ID dependency slots only — no free-text dependency strings.
Does not decide TalkAskAct; deliberation remains sole authority.
"""

from __future__ import annotations

import re
from typing import Any, Optional
from uuid import uuid4

from .plan_contracts import PlanStep, PlanStepStatus, ProductionPlan

# Explicit chain / "then" multi-modality patterns.
_IMAGE_RE = re.compile(
    r"\b(?:image|still|shot|picture|photo|generate\s+(?:an?\s+)?image|create\s+(?:an?\s+)?image)\b",
    re.I,
)
_VIDEO_RE = re.compile(
    r"\b(?:video|clip|animate|r2v|image\s*[- ]?to\s*[- ]?video|make\s+(?:a\s+)?video)\b",
    re.I,
)
_AUDIO_RE = re.compile(
    r"\b(?:audio|sound|sfx|voiceover|voice[\s-]?over|music|footsteps|add\s+audio)\b",
    re.I,
)
_PLAN_SPEECH_RE = re.compile(
    r"\b(?:let'?s\s+plan|plan\s+(?:this|it|out)|make\s+a\s+plan|production\s+plan|"
    r"break\s+(?:this|it)\s+down|multi[\s-]?step)\b",
    re.I,
)
_THEN_CHAIN_RE = re.compile(r"\bthen\b|\bafter\s+that\b|\bnext\b|\u2192|->", re.I)

_CAP_IMAGE = "image.generate"
_CAP_VIDEO = "video.generate"
_CAP_AUDIO = "timeline.add_audio"


def detect_requested_modalities(text: str) -> list[str]:
    raw = text or ""
    mods: list[str] = []
    if _IMAGE_RE.search(raw):
        mods.append("image")
    if _VIDEO_RE.search(raw):
        mods.append("video")
    if _AUDIO_RE.search(raw):
        mods.append("audio")
    return mods


def is_planning_speech(text: str) -> bool:
    return bool(_PLAN_SPEECH_RE.search(text or ""))


def is_multistep_request(text: str) -> bool:
    mods = detect_requested_modalities(text)
    if len(mods) >= 2:
        return True
    if is_planning_speech(text) and len(mods) >= 1:
        return True
    if _THEN_CHAIN_RE.search(text or "") and len(mods) >= 1:
        return True
    return False


def _cap_for(modality: str) -> str:
    return {"image": _CAP_IMAGE, "video": _CAP_VIDEO, "audio": _CAP_AUDIO}.get(modality, "")


def compile_multistep_request(
    *,
    user_message: str,
    project_id: str = "",
    route_lock: Optional[dict[str, Any]] = None,
    parent_execution_id: str = "",
    goal: str = "",
) -> Optional[ProductionPlan]:
    """Compile image→video→audio (or subset) into a versioned ProductionPlan.

    Returns None when the utterance is not multi-step / planning.
    Dependency slots use stepIds + producesAssetSlot — never free-text.
    """
    text = user_message or ""
    planning = is_planning_speech(text)
    multi = is_multistep_request(text)
    if not (planning or multi):
        return None

    mods = detect_requested_modalities(text)
    if not mods:
        # Pure "let's plan" without modalities → empty scaffold
        return ProductionPlan(
            goal=goal or text.strip()[:240] or "Production plan",
            projectId=project_id,
            summary="Planning speech — awaiting step details",
            status=PlanStepStatus.WAITING_FOR_CONFIRMATION if planning else PlanStepStatus.PLANNED,
            parentExecutionId=parent_execution_id,
            metadata={"planningSpeech": planning, "multiStep": False},
        )

    # Preserve natural order: image then video then audio when present.
    order_pref = ["image", "video", "audio"]
    ordered = [m for m in order_pref if m in mods]

    steps: list[PlanStep] = []
    prev_id = ""
    prev_slot = ""
    lock = dict(route_lock or {})
    for i, mod in enumerate(ordered):
        sid = f"step-{mod}-{uuid4().hex[:8]}"
        slot = f"{mod}_{i}"
        depends: list[str] = [prev_id] if prev_id else []
        required: list[str] = []
        # Asset-ID dependency slot placeholder (filled after prior step completes)
        params: dict[str, Any] = {
            "modality": mod,
            "user_instructions": text,
            "input_asset_slot": prev_slot or None,
            "input_asset_ids": [],  # filled from prior resultAssetIds
        }
        runtime = []
        if mod == "image":
            runtime = ["image_runtime"]
        elif mod == "video":
            runtime = ["video_runtime"]
            # Timeline / R2V when video after image
            params["timelineMode"] = "R2V" if prev_slot.startswith("image") or "image" in ordered[:i] else ""
        elif mod == "audio":
            runtime = ["timeline_audio"]

        step = PlanStep(
            stepId=sid,
            order=i,
            title=f"Generate {mod}",
            goal=f"{mod} step for: {(goal or text)[:120]}",
            capabilityId=_cap_for(mod),
            status=PlanStepStatus.READY if i == 0 else PlanStepStatus.BLOCKED,
            dependsOn=depends,
            requiredAssetIds=required,
            producesAssetSlot=slot,
            params=params,
            routeLock=dict(lock),
            runtimeNeeds=runtime,
            parentExecutionId=parent_execution_id,
            parentStepId=prev_id,
            reasonCodes=(["DEPENDENCY_BLOCKED"] if i > 0 and depends else []),
        )
        steps.append(step)
        prev_id = sid
        prev_slot = slot

    caps = [s.capabilityId for s in steps if s.capabilityId]
    runtime_needs = sorted({r for s in steps for r in s.runtimeNeeds})
    status = PlanStepStatus.WAITING_FOR_CONFIRMATION if planning else PlanStepStatus.PLANNED
    summary_bits = " → ".join(ordered)
    return ProductionPlan(
        goal=goal or text.strip()[:240],
        projectId=project_id,
        steps=steps,
        capabilities=caps,
        requiredAssets=[],
        runtimeNeeds=runtime_needs,
        risks=["multi_step"] if len(steps) > 1 else [],
        status=status,
        summary=f"Multi-step plan: {summary_bits}",
        parentExecutionId=parent_execution_id,
        metadata={
            "planningSpeech": planning,
            "multiStep": True,
            "modalities": ordered,
        },
    )


def compile_execution_steps(plan: ProductionPlan) -> list[dict[str, Any]]:
    """Map ProductionPlan steps → ExecutionPlan.planned_steps shaped dicts.

    Includes dependsOn, lifecycle status, lineage, asset slots.
    Top-level fields mirror ExecutionStep; metadata keeps UI/slot detail.
    """
    out: list[dict[str, Any]] = []
    for s in plan.steps:
        life = s.status.value if hasattr(s.status, "value") else str(s.status)
        parent_exec = s.parentExecutionId or plan.parentExecutionId or None
        meta = {
            "stepId": s.stepId,
            "dependsOn": list(s.dependsOn),
            "lifecycleStatus": life,
            "producesAssetSlot": s.producesAssetSlot,
            "requiredAssetIds": list(s.requiredAssetIds),
            "resultAssetIds": list(s.resultAssetIds),
            "failureReasonCodes": list(s.failureReasonCodes),
            "reasonCodes": list(s.reasonCodes),
            "parentExecutionId": parent_exec or "",
            "parentStepId": s.parentStepId,
            "params": dict(s.params),
            "routeLock": dict(s.routeLock),
            "runtimeNeeds": list(s.runtimeNeeds),
            "planId": plan.planId,
        }
        out.append(
            {
                "step_index": s.order,
                "label": s.title or s.goal or s.capabilityId,
                "capability": s.capabilityId,
                "status": "queued",
                "asset_id": (s.resultAssetIds[0] if s.resultAssetIds else None),
                "error": s.failureReason or None,
                "metadata": meta,
                # ExecutionStep top-level lineage (pack bridge)
                "step_id": s.stepId,
                "depends_on": list(s.dependsOn),
                "lifecycle_status": life,
                "result_asset_ids": list(s.resultAssetIds),
                "failure_reason": s.failureReason or None,
                "failure_reason_codes": list(s.failureReasonCodes or s.reasonCodes),
                "parent_execution_id": parent_exec,
                "parent_step_id": s.parentStepId or None,
                "plan_id": plan.planId,
            }
        )
    return out


def apply_dependency_block(plan: ProductionPlan) -> ProductionPlan:
    """Mark steps BLOCKED when dependsOn not yet COMPLETED; READY when deps satisfied."""
    completed = {s.stepId for s in plan.steps if s.status == PlanStepStatus.COMPLETED}
    failed = {s.stepId for s in plan.steps if s.status == PlanStepStatus.FAILED}
    for s in plan.steps:
        if s.status in {
            PlanStepStatus.COMPLETED,
            PlanStepStatus.SKIPPED,
            PlanStepStatus.CANCELLED,
            PlanStepStatus.RUNNING,
            PlanStepStatus.WAITING_FOR_CONFIRMATION,
        }:
            continue
        if any(d in failed for d in s.dependsOn):
            s.status = PlanStepStatus.BLOCKED
            if "DEPENDENCY_BLOCKED" not in s.reasonCodes:
                s.reasonCodes = list(s.reasonCodes) + ["DEPENDENCY_BLOCKED"]
            if "DEPENDENCY_BLOCKED" not in s.failureReasonCodes:
                s.failureReasonCodes = list(s.failureReasonCodes) + ["DEPENDENCY_BLOCKED"]
            s.failureReason = s.failureReason or "Upstream step failed"
            continue
        if s.dependsOn and not all(d in completed for d in s.dependsOn):
            s.status = PlanStepStatus.BLOCKED
            if "DEPENDENCY_BLOCKED" not in s.reasonCodes:
                s.reasonCodes = list(s.reasonCodes) + ["DEPENDENCY_BLOCKED"]
        elif s.status in {PlanStepStatus.PLANNED, PlanStepStatus.BLOCKED}:
            s.status = PlanStepStatus.READY
            s.reasonCodes = [c for c in s.reasonCodes if c != "DEPENDENCY_BLOCKED"]
    return plan
