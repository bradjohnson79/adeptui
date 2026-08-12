"""Timeline Context Package — Co-Director-owned producer.

Produces a single `TimelineContextPackage` bundling all Project Bible context
for the Timeline to consume. The Timeline never requests Bible/Characters/
References individually — it consumes this package.

PRODUCTION_READINESS_OWNED_BY_CODIRECTOR: scene readiness is computed here
(from the Production Readiness Service), not by the Timeline. The Timeline
displays it; it never invents it.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from ..production_lifecycle.service import _load_life, scene_production_package
from ..wiki_intelligence.compiled.page_compiler import compile_wiki_bundle
from .contracts import (
    SceneCraftHierarchy,
    SceneCraftShot,
    TimelineContextCharacter,
    TimelineContextLocation,
    TimelineContextPackage,
    TimelineContextReference,
    TimelineContinuityLocks,
    TimelineGenerationConstraints,
    TimelineSceneReadiness,
)

try:
    from app.db import Project, Scene as SceneModel, Asset
except Exception:  # noqa: BLE001
    Project = None  # type: ignore[assignment]
    SceneModel = None  # type: ignore[assignment]
    Asset = None  # type: ignore[assignment]


def _continuity_from_scene(scene: Any) -> TimelineContinuityLocks:
    raw = getattr(scene, "continuity_json", None) if scene else None
    if not raw:
        return TimelineContinuityLocks()
    try:
        data = json.loads(raw)
    except Exception:  # noqa: BLE001
        return TimelineContinuityLocks()
    return TimelineContinuityLocks(
        identity=data.get("identity", "inherit_project"),
        wardrobe=data.get("wardrobe", "inherit_project"),
        environment=data.get("environment", "inherit_project"),
        lighting=data.get("lighting", "inherit_project"),
        camera=data.get("camera", "inherit_project"),
        props=data.get("props", "inherit_project"),
        audio_bed=data.get("audio_bed", "inherit_project"),
        motion_style=data.get("motion_style", "inherit_project"),
    )


def _gate_level(readiness: TimelineSceneReadiness, action_scope: str) -> str:
    """Derive the Smart Production Gate level from readiness + action scope.

    EXPLORATION: always allowed (storyboarding, drafts).
    PRODUCTION_WARNING: final generation allowed but warned if partially ready.
    PRODUCTION_LOCK: final generation blocked until readiness satisfied.
    """
    if action_scope == "exploration":
        return "EXPLORATION"
    if readiness.status == "BLOCKED":
        return "PRODUCTION_LOCK"
    if readiness.status == "PARTIAL":
        return "PRODUCTION_WARNING"
    return "EXPLORATION"


def build_timeline_context_package(
    db: Session,
    project_id: str,
    scene_id: str,
    *,
    action_scope: str = "exploration",
) -> dict[str, Any]:
    """Build the single TimelineContextPackage for a scene.

    Aggregates: compiled wiki canon (story summary, characters, locations),
    approved references (assets), scene continuity locks, production notes,
    reference assets bound to the scene, generation constraints, and the
    scene readiness from the Production Readiness Service.
    """
    # 1. Compiled wiki canon (compile_wiki_bundle returns a JSON dict)
    try:
        bundle = compile_wiki_bundle(db, project_id)
    except Exception:  # noqa: BLE001
        bundle = None

    story = (bundle or {}).get("storySummary") or {}
    logline = story.get("logline", "") or ""
    short_summary = story.get("shortSummary", "") or ""
    long_summary = story.get("longSummary", "") or ""
    themes = list(story.get("themes", []) or [])

    # 2. Characters from wiki pages (CHARACTER pages) + casting records
    characters: list[TimelineContextCharacter] = []
    for page in (bundle or {}).get("pages", []) or []:
        if page.get("pageType") != "CHARACTER":
            continue
        cid = page.get("pageId", "")
        name = page.get("title", "")
        characters.append(
            TimelineContextCharacter(
                characterId=cid,
                name=name,
                wikiPageId=cid,
                locked=page.get("canonState") in {"CONFIRMED", "LOCKED"},
            )
        )

    # Merge casting status from lifecycle
    try:
        _, life = _load_life(db, project_id)
        for rec in life.characterCasting:
            match = next((c for c in characters if c.characterId == rec.characterId), None)
            if match:
                match.castStatus = rec.status
                match.portraitAssetId = rec.selectedPortraitAssetId
                match.voiceId = rec.selectedVoiceId
                match.locked = match.locked or rec.status == "CAST_LOCKED"
            else:
                characters.append(
                    TimelineContextCharacter(
                        characterId=rec.characterId,
                        name=rec.characterName,
                        castStatus=rec.status,
                        portraitAssetId=rec.selectedPortraitAssetId,
                        voiceId=rec.selectedVoiceId,
                        wikiPageId=rec.wikiPageId,
                        locked=rec.status == "CAST_LOCKED",
                    )
                )
    except Exception:  # noqa: BLE001
        pass

    # 3. Locations from wiki pages
    locations: list[TimelineContextLocation] = []
    for page in (bundle or {}).get("pages", []) or []:
        if page.get("pageType") != "LOCATION":
            continue
        locations.append(
            TimelineContextLocation(
                locationId=page.get("pageId", ""),
                name=page.get("title", ""),
                wikiPageId=page.get("pageId"),
            )
        )

    # 4. Scene row (production notes, continuity, constraints)
    scene_row = None
    project_row = None
    try:
        if SceneModel is not None:
            scene_row = db.get(SceneModel, scene_id)
        if Project is not None:
            project_row = db.get(Project, project_id)
    except Exception:  # noqa: BLE001
        scene_row = None
        project_row = None

    continuity = _continuity_from_scene(scene_row)
    production_notes: dict[str, Any] = {}
    if scene_row is not None:
        production_notes = {
            "scenePrompt": getattr(scene_row, "prompt", "") or "",
            "cameraNote": getattr(scene_row, "camera_note", "") or "",
            "sceneName": getattr(scene_row, "name", "") or "",
        }

    constraints = TimelineGenerationConstraints(
        engine=getattr(scene_row, "engine", "auto") or "auto" if scene_row else "auto",
        durationSec=float(getattr(scene_row, "duration_sec", 5.0) or 5.0) if scene_row else 5.0,
        aspectRatio=getattr(scene_row, "aspect_ratio", "16:9") or "16:9" if scene_row else "16:9",
        fps=int(getattr(scene_row, "fps", 0) or 0) if scene_row else 0,
        fpsMode=getattr(scene_row, "fps_mode", "auto") or "auto" if scene_row else "auto",
        negativePrompt=getattr(project_row, "negative_prompt", "") or "" if project_row else "",
        globalStylePrompt=getattr(project_row, "global_prompt", "") or "" if project_row else "",
    )

    # 5. References / assets
    references: list[TimelineContextReference] = []
    reference_assets: list[TimelineContextReference] = []
    try:
        if Asset is not None:
            rows = (
                db.query(Asset)
                .filter(Asset.project_id == project_id)
                .all()
            )
            for a in rows:
                kind = (getattr(a, "kind", "image") or "image").lower()
                ref = TimelineContextReference(
                    assetId=str(a.id),
                    tag=getattr(a, "tag", "") or "",
                    kind=kind,
                    filename=getattr(a, "filename", "") or "",
                )
                references.append(ref)
                # Scene-bound reference assets (start_asset_id / audio_asset_id)
                if scene_row is not None and ref.assetId in {
                    getattr(scene_row, "start_asset_id", None),
                    getattr(scene_row, "audio_asset_id", None),
                    getattr(scene_row, "lipsync_audio_asset_id", None),
                }:
                    reference_assets.append(ref)
    except Exception:  # noqa: BLE001
        pass

    # 6. Scene readiness from the Production Readiness Service
    readiness = TimelineSceneReadiness(sceneId=scene_id)
    try:
        pkg = scene_production_package(db, project_id, scene_id)
        if pkg.get("ok") and pkg.get("package"):
            p = pkg["package"]
            readiness = TimelineSceneReadiness(
                sceneId=scene_id,
                status=p.get("status", "BLOCKED"),
                blockerSummary=p.get("blockerSummary", "") or "",
                castReady=bool(p.get("castReady", False)) or bool(p.get("approvedCastReferences")),
                locationReady=bool(p.get("locationReady", False)),
                wardrobeReady=bool(p.get("wardrobeReady", False)),
                propsReady=bool(p.get("propsReady", False)),
                imageReferencesReady=bool(p.get("imageReferencesReady", False)),
                voiceReady=bool(p.get("voiceReady", False)),
                generationPlanReady=bool(p.get("generationPlanReady", False)),
            )
        else:
            # Not ready — surface the blocker but still return the package so
            # editing remains available (provider outage resilience).
            upstream_error = str(pkg.get("error") or "")
            if upstream_error == "Scene not found":
                # The scene exists; it simply has no readiness record yet
                # (never assessed by the Production Readiness Service). Say so
                # plainly — "Scene not found" is alarming and untrue.
                readiness = TimelineSceneReadiness(
                    sceneId=scene_id,
                    status="BLOCKED",
                    blockerSummary="Readiness not assessed yet — run Co-Director Preflight to assess this scene.",
                )
            else:
                readiness = TimelineSceneReadiness(
                    sceneId=scene_id,
                    status="BLOCKED",
                    blockerSummary=str(pkg.get("blockerSummary") or pkg.get("error") or "Not ready"),
                )
    except Exception as exc:  # noqa: BLE001
        readiness = TimelineSceneReadiness(
            sceneId=scene_id,
            status="BLOCKED",
            blockerSummary=f"Readiness unavailable: {exc}",
        )

    # The package's gateLevel reflects the PRODUCTION gate (the most restrictive
    # applicable level) so the Timeline can display production readiness. The
    # exploration scope only relaxes the /gate endpoint decision, never the
    # package's readiness signal (SMART_PRODUCTION_GATES).
    gate = _gate_level(readiness, "production")

    package = TimelineContextPackage(
        projectId=project_id,
        sceneId=scene_id,
        logline=logline,
        shortSummary=short_summary,
        longSummary=long_summary,
        themes=themes,
        characters=characters,
        references=references,
        locations=locations,
        continuity=continuity,
        productionNotes=production_notes,
        referenceAssets=reference_assets,
        generationConstraints=constraints,
        readiness=readiness,
        gateLevel=gate,
        sceneStatus=_derive_scene_status(readiness, scene_row),
        sceneCraft=SceneCraftHierarchy(
            sceneId=scene_id,
            shots=[
                SceneCraftShot(
                    shotId=f"{scene_id}-shot-1",
                    sceneId=scene_id,
                    label=getattr(scene_row, "name", "") or "Scene",
                    assetIds=[r.assetId for r in reference_assets],
                )
            ],
        ),
    )
    return {"ok": True, "package": package.model_dump(mode="json")}


def _derive_scene_status(readiness: TimelineSceneReadiness, scene_row: Any) -> str:
    """Derive the scene-level lifecycle status from readiness + scene state.

    Draft      — nothing ready yet (BLOCKED, no output)
    Planning    — partially ready (PARTIAL)
    Ready       — fully ready, not yet generated (READY, no output)
    Generating  — a job is in flight (heuristic: READY + no output yet)
    Review      — output present, not yet approved
    Approved    — creator approved (scene status flag, if present)
    Locked      — locked by creator
    """
    try:
        from app.db import Job  # noqa: F401
    except Exception:  # noqa: BLE001
        pass
    has_output = bool(
        getattr(scene_row, "output_path", None) or getattr(scene_row, "lipsync_output_path", None)
    ) if scene_row else False
    if readiness.status == "BLOCKED":
        return "Draft"
    if readiness.status == "PARTIAL":
        return "Planning"
    # READY
    if has_output:
        return "Review"
    return "Ready"


def get_scene_status_aggregate(db: Session, project_id: str) -> dict[str, Any]:
    """Aggregate scene lifecycle counts across a project (SCENE_HAS_LIFECYCLE_STATUS).

    Returns per-scene status + counts by lifecycle stage, e.g.
    {"Draft": 41, "Planning": 12, "Ready": 7, "Generating": 0, ...}.
    """
    from .contracts import SCENE_LIFECYCLE_STATUSES

    scenes: list[Any] = []
    try:
        if SceneModel is not None:
            scenes = (
                db.query(SceneModel)
                .filter(SceneModel.project_id == project_id)
                .all()
            )
    except Exception:  # noqa: BLE001
        scenes = []

    per_scene: list[dict[str, Any]] = []
    counts: dict[str, int] = {s: 0 for s in SCENE_LIFECYCLE_STATUSES}
    for s in scenes:
        # Lightweight per-scene readiness via lifecycle (no full package build
        # to keep this endpoint cheap).
        status = "Draft"
        try:
            _, life = _load_life(db, project_id)
            rec = next((r for r in life.scenes if r.sceneId == str(s.id)), None)
            if rec is not None:
                readiness = TimelineSceneReadiness(
                    sceneId=str(s.id),
                    status=rec.status,
                    blockerSummary=rec.blockerSummary,
                )
                status = _derive_scene_status(readiness, s)
        except Exception:  # noqa: BLE001
            status = "Draft"
        per_scene.append({"sceneId": str(s.id), "name": getattr(s, "name", ""), "status": status})
        if status in counts:
            counts[status] += 1
        else:
            counts["Draft"] += 1

    return {
        "ok": True,
        "projectId": project_id,
        "counts": counts,
        "scenes": per_scene,
        "totalScenes": len(scenes),
    }
