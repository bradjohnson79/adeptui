"""Lifecycle persistence, gates, scene packages, stage history."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..conversation.snapshot import load_snapshot, save_snapshot
from .contracts import (
    CharacterCastingRecord,
    ProjectProductionLifecycle,
    SceneProductionReadiness,
)
from .format_maps import FORMAT_PROFILES, profile_for_project_type, specialists_for_stage


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_life(db: Session, project_id: str) -> tuple[Any, ProjectProductionLifecycle]:
    snapshot = load_snapshot(db, project_id)
    raw = getattr(snapshot, "productionLifecycle", None) or {}
    if raw.get("projectId"):
        life = ProjectProductionLifecycle.model_validate(raw)
    else:
        primary = None
        try:
            from app.db import Project

            proj = db.get(Project, project_id)
            primary = getattr(proj, "primary_project_type", None) if proj else None
        except Exception:  # noqa: BLE001
            primary = None
        profile = profile_for_project_type(primary)
        life = ProjectProductionLifecycle(projectId=project_id, formatProfile=profile)
        if not FORMAT_PROFILES[profile]["requiresScriptForCasting"]:
            life.castingStatus = "OPEN"
    return snapshot, life


def _save_life(db: Session, snapshot: Any, life: ProjectProductionLifecycle) -> ProjectProductionLifecycle:
    life.updatedAt = _now()
    snapshot.productionLifecycle = life.model_dump(mode="json")
    save_snapshot(db, snapshot)
    return life


def _record(life: ProjectProductionLifecycle, event: str, detail: dict | None = None) -> None:
    life.stageHistory = [
        {"at": _now(), "event": event, "stage": life.currentStage, **(detail or {})},
        *list(life.stageHistory or []),
    ][:40]


def get_lifecycle(db: Session, project_id: str) -> dict[str, Any]:
    snapshot, life = _load_life(db, project_id)
    _save_life(db, snapshot, life)
    profile = FORMAT_PROFILES.get(life.formatProfile, FORMAT_PROFILES["narrative_visual"])
    ready_scenes = [s.sceneId for s in life.scenes if s.status in {"READY", "IN_PRODUCTION", "COMPLETE"}]
    timeline_ok = life.productionStatus in {"IN_PROGRESS", "COMPLETE"} or life.currentStage in {
        "TIMELINE_ASSEMBLY",
        "POST_PRODUCTION",
        "FINAL_QC",
        "COMPLETE",
    }
    magi_ok = life.postStatus in {"READY", "IN_PROGRESS", "COMPLETE"}
    return {
        "ok": True,
        "lifecycle": life.model_dump(mode="json"),
        "hardLaws": [
            "NO_FORMAL_CASTING_WITHOUT_SCRIPT",
            "NO_FORMAL_PRODUCTION_WITHOUT_CAST",
            "NO_FINAL_GENERATION_WITHOUT_SCENE_READINESS",
            "NO_POST_WITHOUT_PRODUCTION_ASSETS",
            "NO_COMPLETE_WITHOUT_FINAL_QC",
        ],
        "formatProfile": life.formatProfile,
        "requiresScriptForCasting": profile["requiresScriptForCasting"],
        "castingBlockedReason": (
            None
            if can_formal_cast(life)
            else "Script required — approve a script before formal casting begins."
        ),
        "productionBlockedReason": (
            None
            if can_formal_production(life)
            else "Required cast is not locked yet."
        ),
        "specialistsForStage": specialists_for_stage(life.currentStage),
        "sceneReadinessMatrix": [
            {
                "sceneId": s.sceneId,
                "status": s.status,
                "blockerSummary": s.blockerSummary,
                "castReady": s.castReady,
                "locationReady": s.locationReady,
                "propsReady": s.propsReady,
                "imageReferencesReady": s.imageReferencesReady,
                "generationPlanReady": s.generationPlanReady,
            }
            for s in life.scenes
        ],
        "handoffs": {
            "timelineReady": timeline_ok,
            "magiReady": magi_ok,
            "generationAllowedSceneIds": ready_scenes,
        },
    }


def can_formal_cast(life: ProjectProductionLifecycle) -> bool:
    profile = FORMAT_PROFILES.get(life.formatProfile, FORMAT_PROFILES["narrative_visual"])
    if not profile["requiresScriptForCasting"]:
        return True
    return life.scriptStatus in {"APPROVED", "LOCKED"}


def can_formal_production(life: ProjectProductionLifecycle) -> bool:
    profile = FORMAT_PROFILES.get(life.formatProfile, FORMAT_PROFILES["narrative_visual"])
    if not profile["requiresCastForProduction"]:
        return life.scriptStatus in {"APPROVED", "LOCKED"} or not profile["requiresScriptForCasting"]
    if life.scriptStatus not in {"APPROVED", "LOCKED"} and profile["requiresScriptForCasting"]:
        return False
    if not life.characterCasting:
        return False
    required = [c for c in life.characterCasting if not c.exploratory]
    if not required:
        return False
    return all(c.status == "CAST_LOCKED" for c in required)


def advance_script_status(db: Session, project_id: str, status: str) -> dict[str, Any]:
    snapshot, life = _load_life(db, project_id)
    allowed = {"NONE", "DRAFT", "REVISING", "APPROVED", "LOCKED"}
    if status not in allowed:
        return {"ok": False, "error": "Invalid script status"}
    life.scriptStatus = status  # type: ignore[assignment]
    if status in {"DRAFT", "REVISING", "APPROVED", "LOCKED"}:
        life.storyReady = True
        if life.currentStage == "STORY":
            life.currentStage = "SCRIPT"
    if status in {"APPROVED", "LOCKED"} and can_formal_cast(life):
        life.castingStatus = "OPEN" if life.castingStatus == "NOT_AVAILABLE" else life.castingStatus
        if life.currentStage in {"STORY", "SCRIPT"}:
            life.currentStage = "CASTING"
    if status == "LOCKED" and can_formal_production(life):
        life.productionStatus = "PLANNING"
        life.currentStage = "PRODUCTION_PLANNING"
    _record(life, "script_status", {"scriptStatus": status})
    _save_life(db, snapshot, life)
    return {"ok": True, "lifecycle": life.model_dump(mode="json")}


def set_story_ready(db: Session, project_id: str, ready: bool = True) -> dict[str, Any]:
    snapshot, life = _load_life(db, project_id)
    life.storyReady = ready
    if ready and life.currentStage == "STORY":
        # Script available, still on story until draft exists
        pass
    _record(life, "story_ready", {"storyReady": ready})
    _save_life(db, snapshot, life)
    return {"ok": True, "lifecycle": life.model_dump(mode="json")}


def set_character_cast_status(
    db: Session,
    project_id: str,
    *,
    character_name: str,
    status: str,
    exploratory: bool = False,
    wiki_page_id: str | None = None,
) -> dict[str, Any]:
    snapshot, life = _load_life(db, project_id)
    if status == "CAST_LOCKED" and not can_formal_cast(life):
        return {
            "ok": False,
            "error": "NO_FORMAL_CASTING_WITHOUT_SCRIPT",
            "message": "Script required before cast lock.",
            "exploratoryAllowed": True,
        }
    if exploratory and status == "CAST_LOCKED":
        return {"ok": False, "error": "Exploratory casting cannot cast-lock."}

    cid = character_name.strip().lower().replace(" ", "-")[:40]
    rec = next((c for c in life.characterCasting if c.characterId == cid), None)
    if not rec:
        rec = CharacterCastingRecord(
            characterId=cid,
            characterName=character_name.strip(),
            wikiPageId=wiki_page_id,
        )
        life.characterCasting.append(rec)
    rec.status = status  # type: ignore[assignment]
    rec.exploratory = exploratory
    if wiki_page_id:
        rec.wikiPageId = wiki_page_id

    if any(c.status not in {"NOT_STARTED"} for c in life.characterCasting):
        life.castingStatus = "IN_PROGRESS"
    if life.characterCasting and all(
        c.status == "CAST_LOCKED" for c in life.characterCasting if not c.exploratory
    ):
        life.castingStatus = "CAST_LOCKED"
        if can_formal_production(life):
            life.productionStatus = "PLANNING"
            life.currentStage = "PRODUCTION_PLANNING"
    _record(life, "cast_status", {"character": character_name, "status": status})
    _save_life(db, snapshot, life)
    return {"ok": True, "lifecycle": life.model_dump(mode="json"), "character": rec.model_dump(mode="json")}


def upsert_scene_readiness(db: Session, project_id: str, scene: dict[str, Any]) -> dict[str, Any]:
    snapshot, life = _load_life(db, project_id)
    readiness = SceneProductionReadiness.model_validate(scene)
    # Derive status
    flags = [
        readiness.scriptLocked,
        readiness.castReady,
        readiness.locationReady,
        readiness.propsReady,
    ]
    if not can_formal_production(life) and FORMAT_PROFILES.get(life.formatProfile, {}).get(
        "requiresCastForProduction", True
    ):
        readiness.status = "BLOCKED"
        readiness.blockerSummary = "Production is blocked until required cast is locked."
    elif all(flags) and readiness.imageReferencesReady:
        readiness.status = "READY"
        readiness.blockerSummary = ""
        readiness.generationPlanReady = True
    elif any(flags):
        readiness.status = "PARTIAL"
        missing = []
        if not readiness.locationReady:
            missing.append("location reference")
        if not readiness.castReady:
            missing.append("cast")
        if not readiness.imageReferencesReady:
            missing.append("image references")
        readiness.blockerSummary = (
            f"Almost ready — still needs {', '.join(missing)}." if missing else "Partially ready."
        )
    else:
        readiness.status = "BLOCKED"
        readiness.blockerSummary = readiness.blockerSummary or "Scene is not ready for generation."

    life.scenes = [s for s in life.scenes if s.sceneId != readiness.sceneId]
    life.scenes.insert(0, readiness)
    if any(s.status == "READY" for s in life.scenes) and can_formal_production(life):
        life.productionStatus = "IN_PROGRESS"
        life.currentStage = "PRODUCTION"
    _save_life(db, snapshot, life)
    return {"ok": True, "scene": readiness.model_dump(mode="json"), "lifecycle": life.model_dump(mode="json")}


def scene_production_package(db: Session, project_id: str, scene_id: str) -> dict[str, Any]:
    _, life = _load_life(db, project_id)
    scene = next((s for s in life.scenes if s.sceneId == scene_id), None)
    if not scene:
        return {"ok": False, "error": "Scene not found"}
    if scene.status not in {"READY", "IN_PRODUCTION", "COMPLETE"}:
        return {
            "ok": False,
            "error": "NO_FINAL_GENERATION_WITHOUT_SCENE_READINESS",
            "blockerSummary": scene.blockerSummary,
            "scene": scene.model_dump(mode="json"),
        }
    cast_refs = [
        c.model_dump(mode="json")
        for c in life.characterCasting
        if c.characterName in scene.requiredCharacters or c.characterId in scene.requiredCharacters
    ]
    return {
        "ok": True,
        "package": {
            "sceneId": scene_id,
            "scriptLocked": scene.scriptLocked,
            "characters": scene.requiredCharacters,
            "approvedCastReferences": cast_refs,
            "locationReady": scene.locationReady,
            "wardrobeReady": scene.wardrobeReady,
            "propsReady": scene.propsReady,
            "voiceReady": scene.voiceReady,
            "generationPlanReady": scene.generationPlanReady,
            "status": scene.status,
        },
    }


def mark_timeline_ready(db: Session, project_id: str) -> dict[str, Any]:
    snapshot, life = _load_life(db, project_id)
    if life.productionStatus not in {"IN_PROGRESS", "COMPLETE"}:
        return {"ok": False, "error": "Production assets required before Timeline assembly."}
    life.currentStage = "TIMELINE_ASSEMBLY"
    life.postStatus = "READY"
    _record(life, "timeline_assembly")
    _save_life(db, snapshot, life)
    return {"ok": True, "lifecycle": life.model_dump(mode="json")}


def mark_post_progress(db: Session, project_id: str, status: str) -> dict[str, Any]:
    snapshot, life = _load_life(db, project_id)
    if life.postStatus == "NOT_READY":
        return {"ok": False, "error": "NO_POST_WITHOUT_PRODUCTION_ASSETS"}
    life.postStatus = status  # type: ignore[assignment]
    if status in {"IN_PROGRESS", "COMPLETE"}:
        life.currentStage = "POST_PRODUCTION"
    _record(life, "post_status", {"postStatus": status})
    _save_life(db, snapshot, life)
    return {"ok": True, "lifecycle": life.model_dump(mode="json")}


def run_final_qc(db: Session, project_id: str, *, passed: bool) -> dict[str, Any]:
    snapshot, life = _load_life(db, project_id)
    life.currentStage = "FINAL_QC"
    life.finalQcPassed = passed
    _record(life, "final_qc", {"passed": passed})
    _save_life(db, snapshot, life)
    return {
        "ok": True,
        "status": "READY_FOR_FINAL" if passed else "ISSUES_FOUND",
        "lifecycle": life.model_dump(mode="json"),
    }


def mark_complete(db: Session, project_id: str, *, level: str = "PROJECT") -> dict[str, Any]:
    snapshot, life = _load_life(db, project_id)
    if not life.finalQcPassed:
        return {"ok": False, "error": "NO_COMPLETE_WITHOUT_FINAL_QC"}
    life.projectComplete = True
    life.lockedComplete = True
    life.currentStage = "COMPLETE"
    life.productionStatus = "COMPLETE"
    life.postStatus = "COMPLETE"
    _record(life, "complete", {"level": level, "locked": True})
    _save_life(db, snapshot, life)
    return {"ok": True, "lifecycle": life.model_dump(mode="json"), "lockedComplete": True}


def reopen_complete(db: Session, project_id: str) -> dict[str, Any]:
    snapshot, life = _load_life(db, project_id)
    life.lockedComplete = False
    life.projectComplete = False
    life.currentStage = "FINAL_QC"
    _record(life, "reopen")
    _save_life(db, snapshot, life)
    return {"ok": True, "lifecycle": life.model_dump(mode="json")}


def stage_aware_next_steps(life: ProjectProductionLifecycle) -> list[str]:
    stage = life.currentStage
    if stage == "STORY":
        return ["Keep developing the story", "Build the treatment", "Explore a character", "Create the outline"]
    if stage == "SCRIPT":
        return ["Continue script", "Review scene structure", "Revise dialogue", "Approve script"]
    if stage == "CASTING":
        return ["Create character concepts", "Review portrait candidates", "Build character sheet", "Select voice"]
    if stage in {"PRODUCTION_PLANNING", "PRODUCTION"}:
        return ["Prepare Scene 1", "Generate storyboard", "Create environment reference", "Open Timeline"]
    if stage in {"TIMELINE_ASSEMBLY", "POST_PRODUCTION"}:
        return ["Open MAGI", "Review edit", "Add SFX", "Mix scene"]
    if stage == "FINAL_QC":
        return ["Review continuity", "Fix issues", "Mark complete"]
    return ["Review the Project Bible"]
