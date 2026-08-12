"""Capability-readiness snapshot and fresh re-evaluation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from .schemas import (
    CapabilityEntry,
    PlanCapabilitySnapshot,
    PlanReadinessLevel,
    PlanReadinessReport,
    ProductionPlan,
    ProductionPlanStep,
)

# Still deferred / not Production Ready for Wave 6P local GO
_DEFERRED_CAPABILITIES = {
    "video.upscale",
    "image.upscale",
    "generation.upscale",
    "fal.cloud",
    "proposal.apply",
}

# Wave 6P executable media tools (closed registry)
_W6P_EXECUTABLE_TOOLS = {
    "propose_image_generate",
    "propose_video_generate",
    "propose_shot_generate",
    "propose_scene_generate",
    "propose_three_frame_generate",
    "propose_timeline_render",
    "propose_batch_timeline",
    "propose_video_extend",
    "propose_lipsync",
    "propose_music_generate",
    "propose_sfx_generate",
    "audio.generate_music",
    "audio.generate_sfx",
    "audio.generate_ambience",
    "audio.select_candidate",
    "audio.approve_candidate",
    "audio.place",
    "audio.replace_clip",
    "audio.cancel_batch",
    "audio.get_batch",
    "propose_voice_generate",
    "propose_subtitle_generate",
    "editor.place_asset",
    "job.cancel",
    "job.retry",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _level_from_steps(steps: list[ProductionPlanStep], open_blocking: int) -> PlanReadinessLevel:
    if open_blocking:
        return "blocked"
    avail = [s.executionAvailability for s in steps]
    if not steps:
        return "deferred"
    if all(a == "unsupported" for a in avail):
        return "unsupported"
    if any(a in {"deferred", "unsupported", "unconfigured"} for a in avail):
        if any(a == "available" for a in avail):
            return "partially_ready"
        return "deferred"
    if any(a == "permission_required" for a in avail):
        return "blocked"
    return "ready"


def annotate_step_availability(steps: list[ProductionPlanStep]) -> list[ProductionPlanStep]:
    out: list[ProductionPlanStep] = []
    for s in steps:
        copy = s.model_copy(deep=True)
        tool = (copy.proposedToolId or "").lower()
        caps = set(copy.requiredCapabilities or [])
        if caps & _DEFERRED_CAPABILITIES:
            copy.executionAvailability = "deferred"
        elif tool in {t.lower() for t in _W6P_EXECUTABLE_TOOLS} or tool.startswith(
            (
                "propose_image_generate",
                "propose_video_",
                "propose_shot_",
                "propose_scene_",
                "propose_three_frame",
                "propose_timeline",
                "propose_batch",
                "propose_lipsync",
                "propose_music",
                "propose_sfx",
                "audio.generate_",
                "audio.select_",
                "audio.approve_",
                "audio.place",
                "audio.replace_",
                "propose_voice",
                "propose_subtitle",
                "editor.place",
                "job.cancel",
                "job.retry",
            )
        ):
            copy.executionAvailability = "available"
        elif (
            tool.startswith("propose_image_upscale")
            or tool.startswith("propose_video_upscale")
            or tool.startswith("propose_background")
            or tool.startswith("propose_portrait")
        ):
            # Enhance ops exist but are not required local GO paths; keep honest.
            copy.executionAvailability = "deferred"
        elif copy.requiredCapabilities:
            if all(c.startswith("project.") or c.endswith(".read") for c in copy.requiredCapabilities):
                copy.executionAvailability = "available"
            else:
                copy.executionAvailability = "deferred"
        else:
            if copy.category in {
                "research",
                "review",
                "approval",
                "system",
                "script",
                "scene",
                "character",
                "bible",
                "continuity",
                "asset",
                "video",
                "audio",
                "editor",
                "subtitle",
                "image",
                "director",
            }:
                copy.executionAvailability = "available"
            else:
                copy.executionAvailability = "deferred"
        out.append(copy)
    return out


def build_capability_snapshot(
    db: Session,
    project_id: str,
    steps: list[ProductionPlanStep],
    *,
    open_blocking: int = 0,
) -> PlanCapabilitySnapshot:
    """Build snapshot from step requirements + Wave 6P capability honesty."""
    entries: list[CapabilityEntry] = []
    seen: set[str] = set()
    for s in steps:
        for cap in s.requiredCapabilities or []:
            if cap in seen:
                continue
            seen.add(cap)
            deferred = cap in _DEFERRED_CAPABILITIES
            entries.append(
                CapabilityEntry(
                    capabilityId=cap,
                    status="deferred"
                    if deferred
                    else ("available" if s.executionAvailability == "available" else "deferred"),
                    available=not deferred and s.executionAvailability == "available",
                    reason="Deferred / not Production Ready." if deferred else None,
                )
            )
        tool = s.proposedToolId
        if tool and tool not in seen:
            seen.add(tool)
            deferred = s.executionAvailability != "available"
            entries.append(
                CapabilityEntry(
                    capabilityId=tool,
                    status="deferred" if deferred else "available",
                    available=not deferred,
                    reason="Not wired for Wave 6P execution." if deferred else None,
                )
            )

    readiness = _level_from_steps(steps, open_blocking)
    return PlanCapabilitySnapshot(capturedAt=_now(), readiness=readiness, capabilities=entries)


def evaluate_readiness(db: Session, plan: ProductionPlan) -> PlanReadinessReport:
    steps = annotate_step_availability(plan.steps)
    open_blocking = sum(1 for b in plan.blockers if b.state == "open" and b.severity == "blocking")
    current = build_capability_snapshot(db, plan.projectId, steps, open_blocking=open_blocking)
    snapshot = plan.capabilitySnapshot or PlanCapabilitySnapshot()
    snap_map = {c.capabilityId: c for c in snapshot.capabilities}
    cur_map = {c.capabilityId: c for c in current.capabilities}
    changed: list[str] = []
    for cid, cur in cur_map.items():
        prev = snap_map.get(cid)
        if prev is None or prev.available != cur.available or prev.status != cur.status:
            changed.append(cid)
    for cid in snap_map:
        if cid not in cur_map:
            changed.append(cid)
    requires = bool(changed) and snapshot.readiness != current.readiness
    return PlanReadinessReport(
        snapshotReadiness=snapshot.readiness or "deferred",
        currentReadiness=current.readiness,
        changedCapabilities=sorted(set(changed)),
        snapshot=snapshot,
        current=current,
        requiresRefresh=requires or bool(changed),
    )
