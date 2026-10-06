"""Persist and assemble CoDirectorWorkingContext from canonical stores."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from ...db import Project, Scene
from .confidence import (
    bind_confirmation,
    classify_needs_scene_choice,
    compile_confidence,
    decay_confidence,
    is_affirmative,
)
from .posecraft_slice import build_posecraft_slice, resolve_figure_for_character
from .working_context import (
    ApprovalRecord,
    CoDirectorWorkingContext,
    ConfirmationRecord,
    PoseCraftSlice,
    PreferenceHint,
    ProvenanceRecord,
    SceneSlice,
    _now,
    empty_working_context,
)

_MAX_LIST = 24


def _loads(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_persisted(db: Session, project_id: str) -> CoDirectorWorkingContext:
    project = db.get(Project, project_id)
    if project is None:
        return empty_working_context(project_id)
    raw = _loads(getattr(project, "working_context_json", "") or "")
    if not raw:
        return empty_working_context(project_id)
    try:
        raw.setdefault("activeProjectId", project_id)
        return CoDirectorWorkingContext.model_validate(raw)
    except Exception:
        return empty_working_context(project_id)


def save(db: Session, ctx: CoDirectorWorkingContext, *, commit: bool = True) -> CoDirectorWorkingContext:
    project = db.get(Project, ctx.activeProjectId)
    if project is None:
        raise ValueError(f"Project {ctx.activeProjectId} not found")
    ctx.updatedAt = _now()
    ctx.approvals = ctx.approvals[-_MAX_LIST:]
    ctx.confirmations = ctx.confirmations[-_MAX_LIST:]
    ctx.provenance = ctx.provenance[-48:]
    ctx.preferenceHints = ctx.preferenceHints[-_MAX_LIST:]
    project.working_context_json = json.dumps(ctx.model_dump(mode="json"), ensure_ascii=False)
    if commit:
        db.commit()
    return ctx


def _has_approved_crs(db: Session, project_id: str) -> bool:
    try:
        from ...character_identity.models import CharacterProfileRow
        from ...character_identity.service import resolve_approved_reference

        rows = (
            db.query(CharacterProfileRow)
            .filter(CharacterProfileRow.project_id == project_id)
            .all()
        )
        for row in rows:
            if resolve_approved_reference(db, row.id):
                return True
    except Exception:
        return False
    return False


def _has_spatial_map(db: Session, project_id: str) -> bool:
    try:
        from ...spatial_map.service import list_documents

        docs = list_documents(db, project_id) or []
        return bool(docs)
    except Exception:
        return False


def _scene_ids(db: Session, project_id: str) -> list[str]:
    rows = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.index.asc()).all()
    return [r.id for r in rows]


def assemble(db: Session, project_id: str) -> CoDirectorWorkingContext:
    """Persisted working context plus live PoseCraft / scene references."""

    ctx = load_persisted(db, project_id)
    ctx.activeProjectId = project_id
    try:
        ctx.posecraft = build_posecraft_slice(db, project_id)
    except Exception:
        if not ctx.posecraft:
            ctx.posecraft = PoseCraftSlice()
    if not ctx.activeSceneId:
        ids = _scene_ids(db, project_id)
        if ids:
            ctx.activeSceneId = ids[0]
            scene = db.get(Scene, ids[0])
            if scene is not None:
                ctx.scene = SceneSlice(sceneId=scene.id, name=scene.name or "", approved=False)
    elif ctx.scene.sceneId != ctx.activeSceneId:
        scene = db.get(Scene, ctx.activeSceneId)
        if scene is not None and scene.project_id == project_id:
            ctx.scene.sceneId = scene.id
            ctx.scene.name = scene.name or ctx.scene.name
    return ctx


def apply_patch(db: Session, project_id: str, patch: dict[str, Any]) -> CoDirectorWorkingContext:
    ctx = assemble(db, project_id)
    allowed = {
        "activeSceneId",
        "activeShotId",
        "scene",
        "performance",
        "camera",
        "preferenceHints",
    }
    data = ctx.model_dump(mode="json")
    for key, value in (patch or {}).items():
        if key in allowed:
            data[key] = value
    data["activeProjectId"] = project_id
    ctx = CoDirectorWorkingContext.model_validate(data)
    if patch.get("activeSceneId") and patch.get("activeSceneId") != load_persisted(db, project_id).activeSceneId:
        decay_confidence(ctx, reason="active scene changed")
    return save(db, ctx)


def record_approval(
    db: Session,
    project_id: str,
    *,
    what: str,
    source: str = "creator",
    scene_id: str = "",
    shot_id: str = "",
    asset_id: str = "",
    character_id: str = "",
) -> CoDirectorWorkingContext:
    ctx = assemble(db, project_id)
    ctx.approvals.append(
        ApprovalRecord(
            what=what,
            source=source,
            sceneId=scene_id or ctx.activeSceneId,
            shotId=shot_id or ctx.activeShotId,
            assetId=asset_id,
            characterId=character_id,
        )
    )
    if what in ("scene", "shot", "image"):
        ctx.scene.approved = True
    ctx.provenance.append(
        ProvenanceRecord(
            fact=f"approved:{what}",
            layer="SHOT" if what in ("shot", "image") else "SCENE",
            authority="approved_scene_shot",
            source=source,
        )
    )
    return save(db, ctx)


def record_pending_question(
    db: Session,
    project_id: str,
    *,
    instruction: str,
    question: str,
    scene_id: str = "",
    character_id: str = "",
) -> CoDirectorWorkingContext:
    ctx = assemble(db, project_id)
    ctx.confirmations.append(
        ConfirmationRecord(
            originalInstruction=instruction,
            question=question,
            answer="",
            resolved=False,
            boundSceneId=scene_id or ctx.activeSceneId,
            boundCharacterId=character_id,
        )
    )
    ctx.confidence.asked = True
    ctx.confidence.question = question
    return save(db, ctx)


def apply_instruction(
    db: Session,
    project_id: str,
    instruction: str,
    *,
    character_id: str = "",
    candidate_scene_ids: list[str] | None = None,
    candidate_character_ids: list[str] | None = None,
) -> CoDirectorWorkingContext:
    ctx = assemble(db, project_id)
    if candidate_scene_ids is not None:
        scenes = candidate_scene_ids
    elif ctx.activeSceneId and not classify_needs_scene_choice(instruction):
        scenes = [ctx.activeSceneId]
    else:
        scenes = _scene_ids(db, project_id)
    characters = list(candidate_character_ids or [])
    if character_id and character_id not in characters:
        characters.append(character_id)
    pending = ctx.pending_confirmation()
    if pending and is_affirmative(instruction):
        bind_confirmation(ctx, instruction)
        return save(db, ctx)
    ctx.confidence = compile_confidence(
        ctx,
        instruction,
        candidate_scene_ids=scenes,
        candidate_character_ids=characters,
        has_crs=_has_approved_crs(db, project_id),
        has_spatial_map=_has_spatial_map(db, project_id),
    )
    if ctx.confidence.level == "MEDIUM" and ctx.confidence.question:
        ctx.confirmations.append(
            ConfirmationRecord(
                originalInstruction=instruction,
                question=ctx.confidence.question,
                answer="",
                resolved=False,
                boundSceneId=ctx.activeSceneId,
                boundCharacterId=character_id,
            )
        )
    return save(db, ctx)


def add_preference_hint(db: Session, project_id: str, hint: str) -> CoDirectorWorkingContext:
    ctx = assemble(db, project_id)
    text = (hint or "").strip()
    if text:
        ctx.preferenceHints.append(PreferenceHint(hint=text[:240], source="learning"))
    return save(db, ctx)


def diagnostics(ctx: CoDirectorWorkingContext) -> dict[str, Any]:
    bindings = {
        fig.figureId: fig.characterId
        for fig in ctx.posecraft.figures
        if fig.characterId
    }
    primary = ctx.posecraft.figures[0] if ctx.posecraft.figures else None
    return {
        "activeProjectId": ctx.activeProjectId,
        "activeSceneId": ctx.activeSceneId,
        "activeShotId": ctx.activeShotId,
        "confidence": ctx.confidence.level,
        "confidenceReasons": list(ctx.confidence.reasons),
        "asked": ctx.confidence.asked,
        "question": ctx.confidence.question,
        "locked": list(ctx.confidence.locked),
        "changing": list(ctx.confidence.changing),
        "activePosecraftSceneId": ctx.posecraft.sceneId,
        "activePosecraftRevision": ctx.posecraft.revision,
        "resolvedFigureIds": list(ctx.posecraft.activeFigureIds),
        "resolvedCharacterBindings": bindings,
        "poseSource": "posecraft" if ctx.posecraft.activeFigureIds else "",
        "posePreset": (primary.posePresetId if primary else "") or ctx.performance.posePresetId,
        "poseWorldStatePacketIds": list(ctx.posecraft.poseWorldStatePacketIds),
        "poseConfidenceReasons": [r for r in ctx.confidence.reasons if "pose" in r.lower() or "performance" in r.lower()],
    }


def render_working_context_block(ctx: CoDirectorWorkingContext, *, max_chars: int = 1600) -> str:
    lines = [
        "WORKING CONTEXT (authoritative production state — not chat history)",
        f"- Project: {ctx.activeProjectId}",
    ]
    if ctx.activeSceneId or ctx.scene.name:
        lines.append(f"- Scene: {ctx.scene.name or ctx.activeSceneId} ({ctx.activeSceneId})")
    if ctx.scene.approved:
        lines.append("- Scene/shot: approved")
    if ctx.performance.intent or ctx.performance.posePresetName:
        lines.append(
            f"- Performance: {ctx.performance.intent or ctx.performance.posePresetName}"
        )
    if ctx.camera.framing or ctx.camera.angle:
        bits = [b for b in (ctx.camera.framing, ctx.camera.angle) if b]
        if ctx.camera.elevationDegrees is not None:
            bits.append(f"{ctx.camera.elevationDegrees:g} degrees")
        lines.append("- Camera: " + ", ".join(bits))
    if ctx.posecraft.activeFigureIds:
        lines.append(
            f"- PoseCraft scene revision {ctx.posecraft.revision} "
            f"({len(ctx.posecraft.activeFigureIds)} figures)"
        )
        for fig in ctx.posecraft.figures[:6]:
            bind = f" represents character {fig.characterId}" if fig.characterId else ""
            pose = fig.posePresetName or fig.posePresetId or "custom / rest"
            lines.append(f"  - {fig.name or fig.figureId}: {pose}{bind}")
            lines.append(
                "    (mannequin is physical performance only; CRS is appearance)"
            )
    if ctx.confidence.level:
        lines.append(f"- Confidence: {ctx.confidence.level}")
        for reason in ctx.confidence.reasons[:4]:
            lines.append(f"  - {reason}")
    if ctx.confidence.locked:
        lines.append("- Keep: " + ", ".join(ctx.confidence.locked))
    if ctx.confidence.changing:
        lines.append("- Change: " + ", ".join(ctx.confidence.changing))
    pending = ctx.pending_confirmation()
    if pending:
        lines.append(f"- Pending confirmation: {pending.question}")
        lines.append(f"- Bound instruction: {pending.originalInstruction[:160]}")
    if ctx.approvals:
        last = ctx.approvals[-1]
        lines.append(f"- Last approval: {last.what} ({last.source})")
    text = "\n".join(lines)
    if len(text) > max_chars:
        return text[: max_chars - 3] + "..."
    return text


def pose_answer_for_character(ctx: CoDirectorWorkingContext, *, character_id: str = "", name: str = "") -> str:
    fig = resolve_figure_for_character(ctx.posecraft, character_id=character_id, name=name)
    if fig is None:
        return ""
    pose = fig.posePresetName or fig.posePresetId or "a custom / rest pose"
    who = name or fig.name or "The figure"
    support = ", ".join(fig.contacts[:4])
    extra = f" Support: {support}." if support else ""
    return (
        f"{who} is the active PoseCraft figure ({fig.figureId}) in {pose}.{extra} "
        "That mannequin is the intended physical performance, not the character's appearance."
    )
