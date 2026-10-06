"""Timeline Master persistence (sole runtime SoT).

WAVE 5: `scenes.director_json.timelineMaster` is the storage slot for Master —
the sole runtime source of truth for generation and Timeline Master APIs.
Legacy DirectorTimeline tracks in the same JSON blob are migrate-only / inert
for generation. They must not be dual-written from Master (see orchestrator /
put_director WAVE 5). COW embed preserves non-Master keys on save.
"""


from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from ..db import Scene
from .contracts import SceneTimelineMaster, _now
from .migration import embed_master_into_director_dict, load_or_migrate_scene_master

DEFAULT_TIMELINE_SETTINGS: dict[str, Any] = {
    "trackDensity": "comfortable",
    "displayMode": "seconds",
    "showFilenames": True,
    "showThumbnails": True,
    "snapEnabled": True,
}

DEFAULT_GUIDANCE_PRIORITY = "visual_first"

OPTIONAL_REFS_POLICY_NOTE = (
    "Supporting references are optional and never block generation unless the selected "
    "generator technically requires them."
)

# Lineage / QC packets are not creator supporting-reference slots.
DIAGNOSTIC_REFERENCE_KINDS = frozenset(
    {
        "timelinegenerationlineage",
        "dialoguemanifest",
        "dialogueqcdiagnostics",
        "dialogueretakerepair",
        "omnicontinuitydiagnostics",
        "omniequipmentdiagnostics",
    }
)


def is_creator_supporting_reference(ref: dict[str, Any]) -> bool:
    """True for visual/cast/wardrobe slots; false for generation diagnostics."""
    kind = str(ref.get("kind") or "").strip().lower()
    return kind not in DIAGNOSTIC_REFERENCE_KINDS


def normalize_timeline_workspace(raw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "settings": dict(DEFAULT_TIMELINE_SETTINGS),
        "guidancePriority": DEFAULT_GUIDANCE_PRIORITY,
        "timelineRevision": 1,
        "removedItems": [],
        "layoutIntent": {},
        "inpaintIntent": {},
        # SINGLE-STORE: playhead is workspace state. save_master persists
        # Master + workspace only, so a director_tl.playhead write is a dead
        # write — the workspace carries the durable playhead.
        "playhead": 0.0,
    }
    if not isinstance(raw, dict):
        return base
    if raw.get("playhead") is not None:
        try:
            base["playhead"] = max(0.0, float(raw["playhead"]))
        except (TypeError, ValueError):
            pass
    if isinstance(raw.get("settings"), dict):
        base["settings"] = {**base["settings"], **raw["settings"]}
    if raw.get("guidancePriority"):
        base["guidancePriority"] = str(raw["guidancePriority"])
    if raw.get("timelineRevision") is not None:
        try:
            base["timelineRevision"] = max(1, int(raw["timelineRevision"]))
        except (TypeError, ValueError):
            pass
    if isinstance(raw.get("removedItems"), list):
        base["removedItems"] = list(raw["removedItems"])
    if isinstance(raw.get("layoutIntent"), dict):
        base["layoutIntent"] = dict(raw["layoutIntent"])
    if isinstance(raw.get("inpaintIntent"), dict):
        base["inpaintIntent"] = dict(raw["inpaintIntent"])
    if isinstance(raw.get("libraryAssetIds"), list):
        base["libraryAssetIds"] = [str(item) for item in raw["libraryAssetIds"] if str(item).strip()]
    return base


def set_library_asset_ids(
    db: Session,
    project_id: str,
    scene_id: str,
    asset_ids: list[str],
) -> dict[str, Any]:
    """Timeline Library tray membership. Workspace state, not a second clip store."""
    scene = get_scene(db, project_id, scene_id)
    if not scene:
        return {"ok": False, "error": "SCENE_NOT_FOUND"}
    raw: dict[str, Any] = {}
    try:
        parsed = json.loads(scene.director_json or "{}")
        if isinstance(parsed, dict):
            raw = parsed
    except Exception:
        raw = {}
    ws = normalize_timeline_workspace(raw.get("timelineWorkspace"))
    ws["libraryAssetIds"] = [str(item) for item in asset_ids if str(item).strip()]
    raw["timelineWorkspace"] = ws
    scene.director_json = json.dumps(raw, ensure_ascii=False)
    db.add(scene)
    db.commit()
    return {"ok": True, "libraryAssetIds": ws["libraryAssetIds"]}


def extract_timeline_workspace(director_raw: str | None) -> dict[str, Any]:
    if not director_raw or not str(director_raw).strip():
        return normalize_timeline_workspace(None)
    try:
        data = json.loads(director_raw)
        if isinstance(data, dict):
            return normalize_timeline_workspace(data.get("timelineWorkspace"))
    except Exception:
        pass
    return normalize_timeline_workspace(None)


ALLOWED_SCENE_METADATA_KEYS = frozenset({"promptIntelligence"})


def patch_scene_metadata(
    db: Session,
    project_id: str,
    scene_id: str,
    patch: dict[str, Any],
) -> dict[str, Any]:
    """Merge isolated director_json keys from current disk state.

    Never accepts timelineMaster / timelineWorkspace from the client.
    """
    scene = get_scene(db, project_id, scene_id)
    if not scene:
        return {"ok": False, "error": "SCENE_NOT_FOUND"}
    if not isinstance(patch, dict) or not patch:
        return {"ok": False, "error": "METADATA_PATCH_REQUIRED"}
    forbidden = set(patch) - ALLOWED_SCENE_METADATA_KEYS
    if forbidden:
        return {"ok": False, "error": "METADATA_KEY_FORBIDDEN", "keys": sorted(forbidden)}
    raw: dict[str, Any] = {}
    try:
        parsed = json.loads(scene.director_json or "{}")
        if isinstance(parsed, dict):
            raw = parsed
    except Exception:
        raw = {}
    before_master = json.dumps(raw.get("timelineMaster"), sort_keys=True, default=str)
    for key, value in patch.items():
        raw[key] = value
    after_master = json.dumps(raw.get("timelineMaster"), sort_keys=True, default=str)
    if before_master != after_master:
        return {"ok": False, "error": "TIMELINE_MASTER_MUTATION_FORBIDDEN"}
    scene.director_json = json.dumps(raw, ensure_ascii=False)
    db.add(scene)
    db.commit()
    return {"ok": True, "promptIntelligence": raw.get("promptIntelligence")}


def get_scene(db: Session, project_id: str, scene_id: str) -> Scene | None:
    return (
        db.query(Scene)
        .filter(Scene.project_id == project_id, Scene.id == scene_id)
        .one_or_none()
    )


def load_master(db: Session, project_id: str, scene_id: str) -> dict[str, Any]:
    scene = get_scene(db, project_id, scene_id)
    if not scene:
        return {"ok": False, "error": "SCENE_NOT_FOUND", "mock": False}
    master, tl, data = load_or_migrate_scene_master(
        scene.director_json,
        scene_id=scene_id,
        fallback_duration=float(scene.duration_sec or 5.0),
        fallback_prompt=scene.prompt or "",
    )
    # NO_AUTO_PERSIST_ON_READ: only persist when migration actually created
    # new master state that is not already present in the blob. Previously
    # every GET /master re-saved the blob, which (after a legacy PUT had wiped
    # timelineMaster) cemented a collapsed single-Batch-1 migration. Now we
    # only persist if the blob has no embedded timelineMaster at all.
    existing_master = data.get("timelineMaster") if isinstance(data, dict) else None
    from ..creator_scope.identity_converge import migrate_loaded_master

    tag_repaired = migrate_loaded_master(db, project_id, master)
    # P6: never cement a collapsed migration over a richer embedded master.
    # An empty embedded master that this read filled (execution-window bootstrap)
    # is not a collapse. Persist that fill once so batch and prompt ids stay
    # stable. Leaving it in memory only minted a new track on every GET.
    collapse = False
    bootstrapped_empty = False
    if isinstance(existing_master, dict):
        prev_n = len(existing_master.get("batchBlocks") or [])
        next_n = len(getattr(master, "batchBlocks", None) or [])
        if prev_n >= 2 and next_n < prev_n:
            collapse = True
        elif prev_n == 0 and next_n > 0:
            bootstrapped_empty = True
    if collapse:
        # Prefer embedded master; do not persist migration wipe.
        try:
            master = SceneTimelineMaster.model_validate(existing_master)
        except Exception:
            pass
    elif not existing_master or tag_repaired or bootstrapped_empty:
        save_master(db, project_id, scene_id, master, director_tl=tl)
    from .same_track_no_overlap import audit_master_same_track_overlaps

    overlap_audit = audit_master_same_track_overlaps(master)
    if overlap_audit:
        import logging

        logging.getLogger(__name__).warning(
            "same-track overlap audit project=%s scene=%s findings=%s",
            project_id,
            scene_id,
            len(overlap_audit),
        )
    return {
        "ok": True,
        "projectId": project_id,
        "sceneId": scene_id,
        "master": master.model_dump(),
        "legacyMediaMode": tl.media_mode,
        "sameTrackOverlapAudit": overlap_audit,
        "mock": False,
    }


def save_master(
    db: Session,
    project_id: str,
    scene_id: str,
    master: SceneTimelineMaster,
    *,
    director_tl=None,
    workspace: dict[str, Any] | None = None,
    bump_revision: bool = False,
    touch_batches: bool = True,
) -> SceneTimelineMaster:
    """Persist SceneTimelineMaster as the sole Timeline authority.

    SINGLE-STORE LAW: this writes timelineMaster + timelineWorkspace only. It
    does NOT serialize a live DirectorTimeline prompt/clip store as authority.
    The director_tl param is accepted for migrate-only callers and is not
    persisted as a second store. Legacy keys already on disk are preserved
    byte-for-byte (COW) but are never updated by this save.
    """
    scene = get_scene(db, project_id, scene_id)
    if not scene:
        raise ValueError("SCENE_NOT_FOUND")
    raw: dict[str, Any] = {}
    try:
        parsed = json.loads(scene.director_json or "{}")
        if isinstance(parsed, dict):
            raw = parsed
    except Exception:
        raw = {}
    existing_film = raw.get("filmTimeline")
    if isinstance(existing_film, dict) and existing_film.get("version"):
        return master
    # Preserve any non-Master, non-workspace keys already on disk (legacy blob,
    # lipsync, etc.) without re-serializing a live DirectorTimeline store.
    base = {k: v for k, v in raw.items() if k not in ("timelineMaster", "timelineWorkspace")}
    ws = normalize_timeline_workspace(workspace if workspace is not None else raw.get("timelineWorkspace"))
    if bump_revision:
        ws["timelineRevision"] = int(ws.get("timelineRevision") or 0) + 1
    base["timelineWorkspace"] = ws
    if touch_batches:
        for batch in master.batchBlocks:
            batch.updatedAt = _now()
    embedded = embed_master_into_director_dict(base, master)
    scene.director_json = json.dumps(embedded)
    db.add(scene)
    db.commit()
    return master


def stash_removed_item(workspace: dict[str, Any], *, kind: str, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    ws = normalize_timeline_workspace(workspace)
    entry = {
        "id": f"rm_{uuid4().hex[:10]}",
        "kind": kind,
        "itemId": item_id,
        "payload": payload,
        "removedAt": _now(),
    }
    ws["removedItems"] = list(ws.get("removedItems") or []) + [entry]
    return ws


def _batch_windows_from_master_payload(master_obj: Any) -> list[dict[str, float]]:
    """Cumulative start/end windows from batch planned durations (CD handoff input)."""
    if master_obj is None:
        return []
    if isinstance(master_obj, dict):
        blocks = list(master_obj.get("batchBlocks") or [])

        def _order(b: dict) -> tuple:
            return (int(b.get("order") or 0), str(b.get("id") or ""))

        def _dur(b: dict) -> float:
            d = b.get("duration") or {}
            try:
                return float(d.get("plannedDuration") or d.get("timelineVisibleDuration") or 0.0)
            except (TypeError, ValueError):
                return 0.0

        ordered = sorted(blocks, key=_order)
    else:
        blocks = list(getattr(master_obj, "batchBlocks", None) or [])
        ordered = sorted(
            blocks,
            key=lambda b: (int(getattr(b, "order", 0) or 0), str(getattr(b, "id", "") or "")),
        )

        def _dur(b: Any) -> float:
            dur = getattr(b, "duration", None)
            try:
                return float(
                    getattr(dur, "plannedDuration", None)
                    or getattr(dur, "timelineVisibleDuration", None)
                    or 0.0
                )
            except (TypeError, ValueError):
                return 0.0

    out: list[dict[str, float]] = []
    t = 0.0
    for b in ordered:
        length = max(0.0, _dur(b))
        out.append({"start": t, "end": t + length})
        t += length
    return out


def _scene_duration_seconds(master_obj: Any, scene: Any = None) -> float:
    wins = _batch_windows_from_master_payload(master_obj)
    if wins:
        return float(wins[-1]["end"])
    if scene is not None:
        try:
            return float(getattr(scene, "duration_sec", None) or 0.0)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def replace_master(db: Session, project_id: str, scene_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Persist Master. Generator / window-topology changes mint a fresh SceneTake.

    Systems P5 fail-closed: honor CD ``build_generator_switch_handoff`` — mint NEW
    SceneTake + revision BEFORE rematerialize; same ``stk_`` must NOT keep VCM
    continuity across changed window topology.
    """
    scene = get_scene(db, project_id, scene_id)
    if not scene:
        return {"ok": False, "error": "SCENE_NOT_FOUND", "mock": False}
    incoming = dict(payload or {})
    existing = load_master(db, project_id, scene_id)
    prev_master: dict[str, Any] | None = None
    if existing.get("ok") and isinstance(existing.get("master"), dict):
        prev_master = existing["master"]
        if not incoming.get("sceneTakes") and prev_master.get("sceneTakes"):
            incoming["sceneTakes"] = prev_master["sceneTakes"]
            incoming.setdefault("currentSceneTakeId", prev_master.get("currentSceneTakeId"))
            incoming.setdefault("activeSceneTakeId", prev_master.get("activeSceneTakeId"))
    # P6 master-stability: never persist a collapsed single-Draft over multi-batch.
    from .generation.timeline_reconciler import refuse_master_structure_collapse

    collapse = refuse_master_structure_collapse(previous=prev_master, incoming=incoming)
    if collapse is not None:
        return collapse
    master = SceneTimelineMaster.model_validate(incoming)
    from .scene_takes import (
        begin_execution_revision,
        enforce_execution_boundary_if_topology_changed,
        window_execution_fingerprint,
    )

    boundary = None
    bump = False
    handoff: dict[str, Any] | None = None
    if prev_master is not None:
        prev_gen = str((prev_master or {}).get("sceneGeneratorId") or "").strip()
        next_gen = str(getattr(master, "sceneGeneratorId", None) or "").strip()
        prev_fp = window_execution_fingerprint(prev_master)
        next_fp = window_execution_fingerprint(master)
        must_mint = False
        reason = "window_topology_change"

        if prev_gen != next_gen:
            # CD projection law owns windows; Systems honors handoff mint flags.
            try:
                from ..codirector.production.orchestrator import build_generator_switch_handoff

                duration_sec = _scene_duration_seconds(master, scene) or _scene_duration_seconds(
                    prev_master, scene
                )
                handoff = build_generator_switch_handoff(
                    previous_generator_id=prev_gen,
                    new_generator_id=next_gen,
                    duration_seconds=float(duration_sec or 0.0),
                    previous_windows=_batch_windows_from_master_payload(prev_master),
                )
                must_mint = bool(handoff.get("requiresNewSceneTake"))
                reason = str(handoff.get("reason") or "generator_switch_window_topology_change")
            except Exception:
                # Fail-closed: generator id changed → always mint even if CD import fails.
                must_mint = True
                reason = "generator_switch"
                handoff = {
                    "requiresNewSceneTake": True,
                    "requiresRevisionBump": True,
                    "reason": reason,
                    "previousGeneratorId": prev_gen,
                    "newGeneratorId": next_gen,
                    "note": "fallback_mint_cd_handoff_unavailable",
                }
        elif prev_fp != next_fp:
            must_mint = True
            reason = "window_topology_change"

        if must_mint:
            if prev_master.get("sceneTakes") and not (
                incoming.get("sceneTakes") and incoming.get("_replaceSceneTakes")
            ):
                try:
                    from .contracts import SceneTake as _SceneTake

                    server_takes = [
                        _SceneTake.model_validate(t) for t in (prev_master.get("sceneTakes") or [])
                    ]
                    by_id = {t.id: t for t in server_takes}
                    for t in list(master.sceneTakes or []):
                        if t.id not in by_id:
                            by_id[t.id] = t
                    master.sceneTakes = list(by_id.values())
                except Exception:
                    pass
            if prev_fp != next_fp:
                boundary = enforce_execution_boundary_if_topology_changed(
                    prev_master, master, reason=reason
                )
            else:
                # Generator changed but batch id fingerprint unchanged (Gen rematerialize pending).
                boundary = begin_execution_revision(master, reason=reason)
            if handoff and boundary is not None:
                snap = dict(boundary.generationSnapshot or {})
                snap["cdGeneratorSwitchHandoff"] = {
                    "requiresNewSceneTake": handoff.get("requiresNewSceneTake"),
                    "requiresRevisionBump": handoff.get("requiresRevisionBump"),
                    "reason": handoff.get("reason"),
                    "previousGeneratorId": handoff.get("previousGeneratorId"),
                    "newGeneratorId": handoff.get("newGeneratorId"),
                    "newBatchCount": handoff.get("newBatchCount"),
                    "newWindows": handoff.get("newWindows"),
                }
                boundary.generationSnapshot = snap
            bump = boundary is not None or bool((handoff or {}).get("requiresRevisionBump"))
            if bump and boundary is None and handoff and handoff.get("requiresNewSceneTake"):
                boundary = begin_execution_revision(master, reason=reason)
                bump = True
    save_master(db, project_id, scene_id, master, bump_revision=bump)
    out: dict[str, Any] = {"ok": True, "master": master.model_dump(), "mock": False}
    if boundary is not None:
        out["executionRevision"] = {
            "mintedSceneTakeId": boundary.id,
            "reason": (boundary.generationSnapshot or {}).get("executionBoundaryReason"),
            "supersedesSceneTakeId": (boundary.generationSnapshot or {}).get("supersedesSceneTakeId"),
            "timelineRevisionBumped": True,
        }
    if handoff is not None:
        out["generatorSwitchHandoff"] = handoff
    return out
