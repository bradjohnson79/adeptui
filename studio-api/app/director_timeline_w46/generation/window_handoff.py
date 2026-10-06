"""One memory-gated completion handoff per scene, take, and batch.

The previous heavy model must be measured gone, and both VRAM and system RAM
must be measured safe, before the next heavy model starts. A poll observes
this state. It does not request another unload or another worker.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

from ...codirector.video_intelligence.gpu_lease import (
    admit_heavyweight,
    begin_handoff,
    handoff_key,
    handoff_state,
    note_handoff,
    probe_handoff_memory,
    release_generator_once,
)

HANDOFF_KIND = "handoffGate"
# Cert: the early probe failed, and memory was free within about 20 seconds.
MINIMAX_RELEASE_PROBES = 3
MINIMAX_RELEASE_WAIT_SEC = 10.0

_CREATOR_REASON = {
    "VRAM_UNKNOWN": "Waiting to start the next part. Memory could not be measured.",
    "RAM_UNKNOWN": "Waiting to start the next part. Memory could not be measured.",
    "MEMORY_UNKNOWN": "Waiting to start the next part. Memory could not be measured.",
    "GENERATOR_STILL_RESIDENT": "Waiting to start the next part. The previous model is still loaded.",
    "PREVIOUS_MODEL_STILL_RESIDENT": "Waiting to start the next part. The previous model is still loaded.",
    "INSUFFICIENT_VRAM": "Waiting to start the next part. The previous model is still loaded.",
    "INSUFFICIENT_RAM": "Waiting to start the next part. The computer needs more free memory.",
    "PROBE_REQUIRED": "Waiting to start the next part. Memory has not been checked.",
    "STALE_PROBE": "Waiting to start the next part. Memory has not been checked.",
    "STALE_HANDOFF": "Waiting to start the next part. Memory has not been checked.",
    "handoff_in_progress": "Preparing the next part.",
    "SOURCE_VIDEO_MISSING": "Waiting to start the next part. The finished clip could not be opened.",
    "PERCEPTION_FAILED": "Waiting to start the next part. The finished clip could not be reviewed.",
    "PERCEPTION_TIMEOUT": "Waiting to start the next part. The finished clip could not be reviewed.",
    "MODEL_NOT_INSTALLED": "Waiting to start the next part. The finished clip could not be reviewed.",
}


def creator_message(reason: str) -> str:
    return _CREATOR_REASON.get(reason or "", "Waiting to start the next part. Memory is not ready.")


def _take_id(master: Any) -> str:
    return str(getattr(master, "activeSceneTakeId", "") or "")


def _next_batch(master: Any, batch_id: str) -> Any | None:
    from ..continuity import next_batch_after

    return next_batch_after(master, batch_id)


def _stamp(batch: Any, reason: str) -> None:
    if batch is None:
        return
    refs = [
        r
        for r in (getattr(batch, "references", None) or [])
        if not (isinstance(r, dict) and r.get("kind") == HANDOFF_KIND)
    ]
    refs.append(
        {
            "kind": HANDOFF_KIND,
            "reason": reason,
            "message": creator_message(reason),
        }
    )
    batch.references = refs


def open_completion_handoff(master: Any, batch: Any) -> dict[str, Any]:
    scene_id = str(getattr(batch, "sceneId", "") or getattr(master, "sceneId", "") or "")
    return begin_handoff(handoff_key(scene_id, _take_id(master), getattr(batch, "id", "")))


def _recheck_wait() -> None:
    time.sleep(MINIMAX_RELEASE_WAIT_SEC)


def _probe_owned_by(probe: dict[str, Any], key: tuple[str, str, str]) -> bool:
    """A reading admits only the handoff that requested it."""
    current = handoff_state(key) or {}
    owner_id = current.get("handoffId")
    stamped = probe.get("handoffKey")
    if isinstance(stamped, list):
        stamped = tuple(stamped)
    return bool(
        owner_id
        and probe.get("handoffId") == owner_id
        and stamped == tuple(key)
    )


def _owned_probe(key: tuple[str, str, str]) -> dict[str, Any]:
    owner = handoff_state(key) or {}
    probe = probe_handoff_memory()
    probe["handoffKey"] = key
    probe["handoffId"] = owner.get("handoffId")
    return probe


def reading_admits_handoff(key: tuple[str, str, str], probe: dict[str, Any] | None, model: str) -> dict[str, Any]:
    """Admit one heavy model only from a probe owned by the current handoff."""
    if not isinstance(probe, dict) or not _probe_owned_by(probe, key):
        return {"ok": False, "reason": "STALE_PROBE", "admittedModel": None}
    return admit_heavyweight(model, probe)


def await_minimax_released(key: tuple[str, str, str]) -> dict[str, Any]:
    """Up to three readings after the single unload. No extra /free."""
    owner = handoff_state(key) or {}
    handoff_id = owner.get("handoffId")
    last: dict[str, Any] = {"ok": False, "reason": "MEMORY_UNKNOWN", "probes": 0}
    for attempt in range(MINIMAX_RELEASE_PROBES):
        if attempt:
            _recheck_wait()
        current = handoff_state(key) or {}
        if current.get("handoffId") != handoff_id or current.get("state") != "running":
            return {"ok": False, "reason": "STALE_HANDOFF", "probes": attempt, "admittedModel": None}
        probe = probe_handoff_memory()
        probe["handoffKey"] = key
        probe["handoffId"] = handoff_id
        gate = reading_admits_handoff(key, probe, "qwen-omni")
        gate["probes"] = attempt + 1
        logger.info(
            "handoff probe scene=%s take=%s batch=%s handoff=%s attempt=%s ok=%s reason=%s vramFreeGb=%s ramFreeGb=%s",
            key[0],
            key[1],
            key[2],
            handoff_id,
            attempt + 1,
            bool(gate.get("ok")),
            gate.get("reason"),
            gate.get("freeVramGb"),
            gate.get("freeRamGb"),
        )
        if gate.get("ok"):
            return gate
        last = gate
    return last


def uses_local_memory(batch: Any) -> bool:
    """Local engines load a model on this computer. An API engine does not."""
    gid = str(getattr(batch, "generatorId", "") or "").strip()
    if not gid:
        return True
    try:
        from .registry import get_registry

        caps = get_registry().capabilities(gid)
    except Exception:
        return True
    return str(getattr(caps, "executionType", "") or "local") != "api"


def handoff_submit_block(master: Any, nxt: Any) -> str | None:
    """Block a local Window N+1 unless the previous handoff measured safe.

    An API window renders off this computer. It does not wait for local memory.
    """
    if nxt is not None and not uses_local_memory(nxt):
        return None
    from ..continuity import next_batch_after

    pred = None
    for batch in getattr(master, "batchBlocks", None) or []:
        if next_batch_after(master, batch.id) is not None and next_batch_after(master, batch.id).id == nxt.id:
            pred = batch
            break
    if pred is None:
        return None
    scene_id = str(
        getattr(pred, "sceneId", "") or getattr(nxt, "sceneId", "") or getattr(master, "sceneId", "") or ""
    )
    row = handoff_state(handoff_key(scene_id, _take_id(master), pred.id))
    if row is None:
        return "memory_gate_required"
    if row.get("state") == "ready":
        return None
    if row.get("state") == "running":
        return "handoff_in_progress"
    return str(row.get("reason") or "memory_gate_required")


def run_completion_reviews(
    db: Any,
    *,
    project_id: str,
    scene_id: str,
    asset_id: str,
    batch: Any,
    master: Any,
    owner: bool = False,
) -> dict[str, Any]:
    """Continuity and equipment in one Omni process, then a gated temporal review."""
    key = handoff_key(scene_id, _take_id(master), getattr(batch, "id", ""))
    nxt = _next_batch(master, batch.id)
    if not uses_local_memory(batch) and (nxt is None or not uses_local_memory(nxt)):
        _clear_gate(nxt)
        note_handoff(key, state="ready", reason="")
        return {
            "ok": True,
            "reason": None,
            "continuityQc": None,
            "equipmentQc": None,
            "spawns": {"omni": 0, "free": 0},
            "readyForNext": nxt is not None,
        }
    if not owner:
        started = begin_handoff(key)
        if started.get("observe"):
            return started
    elif (handoff_state(key) or {}).get("state") != "running":
        row = handoff_state(key) or {}
        return {"ok": row.get("state") == "ready", "observe": True, "state": row.get("state"), "reason": row.get("reason") or ""}

    spawns = {"omni": 0, "free": 0}
    try:
        released = release_generator_once(key)
        if released.get("comfyFreeRequested"):
            spawns["free"] += 1
        gate = await_minimax_released(key)
        if not gate.get("ok"):
            _fail(key, nxt, str(gate.get("reason") or "MEMORY_UNKNOWN"))
            return {**gate, "spawns": spawns, "readyForNext": False}

        tail = None
        if nxt is not None:
            _clear_gate(nxt)
            from ..continuity import prepare_outgoing_bridge

            tail = prepare_outgoing_bridge(
                db,
                project_id,
                scene_id,
                master,
                batch.id,
                run_temporal=False,
            )
            _stamp_tail_lineage(tail, key, batch, master)

        continuity_qc, equipment_qc = _one_omni_pass(
            db,
            project_id=project_id,
            scene_id=scene_id,
            asset_id=asset_id,
            batch=batch,
            master=master,
        )
        spawns["omni"] += 1
        _stamp_semantic(tail, continuity_qc, equipment_qc)
        # The worker has returned, which only means the process exited.
        # The next model needs a new measurement.
        after_omni = _owned_probe(key)
        if nxt is None:
            released_gate = reading_admits_handoff(key, after_omni, "minimax")
            if not released_gate.get("ok"):
                _fail(key, None, str(released_gate.get("reason") or "PREVIOUS_MODEL_STILL_RESIDENT"))
                return {
                    "ok": False,
                    "reason": released_gate.get("reason"),
                    "continuityQc": continuity_qc,
                    "equipmentQc": equipment_qc,
                    "spawns": spawns,
                    "readyForNext": False,
                }
            note_handoff(key, state="finished", reason="")
            return {
                "ok": True,
                "reason": None,
                "continuityQc": continuity_qc,
                "equipmentQc": equipment_qc,
                "spawns": spawns,
                "readyForNext": False,
            }

        video_gate = reading_admits_handoff(key, after_omni, "videochat")
        if not video_gate.get("ok"):
            _fail(key, nxt, str(video_gate.get("reason") or "PREVIOUS_MODEL_STILL_RESIDENT"))
            return {
                "ok": False,
                "reason": video_gate.get("reason"),
                "continuityQc": continuity_qc,
                "equipmentQc": equipment_qc,
                "spawns": spawns,
                "readyForNext": False,
            }
        from ..continuity import prepare_outgoing_bridge

        prepare_outgoing_bridge(
            db,
            project_id,
            scene_id,
            master,
            batch.id,
            admitted_preflight={
                "ok": True,
                "freeVramGb": video_gate.get("freeVramGb"),
                "freeRamGb": video_gate.get("freeRamGb"),
                "unknownVram": False,
                "reason": None,
            },
            run_temporal=True,
        )
        after_temporal = _owned_probe(key)
        minimax_gate = reading_admits_handoff(key, after_temporal, "minimax")
        if not minimax_gate.get("ok"):
            _fail(key, nxt, str(minimax_gate.get("reason") or "PREVIOUS_MODEL_STILL_RESIDENT"))
            return {
                "ok": False,
                "reason": minimax_gate.get("reason"),
                "continuityQc": continuity_qc,
                "equipmentQc": equipment_qc,
                "spawns": spawns,
                "readyForNext": False,
            }
        from ...codirector.video_intelligence.service import packet_blocks_submit

        if packet_blocks_submit(master, nxt.id):
            _fail(key, nxt, "temporal_review_pending")
            return {
                "ok": False,
                "reason": "temporal_review_pending",
                "continuityQc": continuity_qc,
                "equipmentQc": equipment_qc,
                "spawns": spawns,
                "readyForNext": False,
            }
        note_handoff(key, state="ready", reason="")
        return {
            "ok": True,
            "reason": None,
            "continuityQc": continuity_qc,
            "equipmentQc": equipment_qc,
            "spawns": spawns,
            "readyForNext": True,
        }
    except Exception as exc:  # noqa: BLE001 — block the next window; do not retry the load
        reason = _perception_reason(exc)
        logger.exception("window handoff stopped: %s", reason)
        _fail(key, nxt, reason)
        return {
            "ok": False,
            "reason": reason,
            "error": str(exc)[:400],
            "spawns": spawns,
            "readyForNext": False,
        }


def _perception_reason(exc: Exception) -> str:
    text = str(exc)
    if "SOURCE_VIDEO_MISSING" in text:
        return "SOURCE_VIDEO_MISSING"
    if "MODEL_NOT_INSTALLED" in text:
        return "MODEL_NOT_INSTALLED"
    if "PERCEPTION_TIMEOUT" in text:
        return "PERCEPTION_TIMEOUT"
    return "PERCEPTION_FAILED"


def _stamp_tail_lineage(bridge: Any, key: tuple[str, str, str], batch: Any, master: Any) -> None:
    """Tail frames belong to this take and this handoff. A later take cannot reuse them."""
    if bridge is None:
        return
    snapshot_id = ""
    for cand in reversed(list(getattr(batch, "candidateVersions", None) or [])):
        snapshot_id = str(getattr(cand, "executionSnapshotId", "") or "")
        if snapshot_id:
            break
    state = dict(getattr(bridge, "continuityState", None) or {})
    state["sceneTakeId"] = _take_id(master)
    state["handoffId"] = (handoff_state(key) or {}).get("handoffId")
    state["executionSnapshotId"] = snapshot_id
    state["sourceBatchId"] = str(getattr(batch, "id", "") or "")
    bridge.continuityState = state


def _semantic_line(qc: dict[str, Any] | None) -> str:
    observed = qc.get("observed") if isinstance(qc, dict) else None
    if not isinstance(observed, dict):
        return ""
    return str(observed.get("summary") or "").strip()[:500]


def _stamp_semantic(bridge: Any, continuity_qc: dict[str, Any], equipment_qc: dict[str, Any]) -> None:
    if bridge is None:
        return
    state = dict(getattr(bridge, "continuityState", None) or {})
    semantic = _semantic_line(continuity_qc)
    equipment = _semantic_line(equipment_qc)
    if semantic:
        state["semanticContinuity"] = semantic
    if equipment:
        state["equipmentState"] = equipment
    bridge.continuityState = state


def _clear_gate(batch: Any) -> None:
    if batch is None:
        return
    batch.references = [
        ref
        for ref in (getattr(batch, "references", None) or [])
        if not (isinstance(ref, dict) and ref.get("kind") == HANDOFF_KIND)
    ]


def _fail(key: tuple[str, str, str], nxt: Any, reason: str) -> None:
    note_handoff(key, state="blocked", reason=reason)
    _stamp(nxt, reason)


def _review_seconds(batch: Any) -> float:
    """Omni watches this window, including its ending. Not a fixed 6 second prefix."""
    duration = None
    if getattr(batch, "duration", None) is not None:
        duration = getattr(batch.duration, "generatedDuration", None) or getattr(
            batch.duration, "plannedDuration", None
        )
    try:
        seconds = float(duration or 0)
    except (TypeError, ValueError):
        seconds = 0
    if seconds <= 0:
        return 6.0
    return min(max(seconds, 1.0), 16.0)


# Sampled stills, not the whole clip. The live benchmark selects the count and height.
HANDOFF_REVIEW_FRAMES = 8
HANDOFF_REVIEW_HEIGHT = 480
HANDOFF_REVIEW_QUESTION = (
    "These stills are in time order from the start of one shot to its end. "
    "Reply with ONLY a JSON object with keys: "
    "summary (two short sentences: what finished, what is still happening, and any change of subject or place), "
    "actionCompleted (short strings), actionInProgress (short strings), "
    "subjectState, propState, environmentState, cameraState, motionDirection, "
    "mustContinue (short strings), mustNotRepeat (short strings), "
    "continuityFlags (only a change of subject or place you can see, else []), "
    "equipmentFlags (else []), "
    "cameraMoves (short strings). Do not invent."
)


def _one_omni_pass(
    db: Any,
    *,
    project_id: str,
    scene_id: str,
    asset_id: str,
    batch: Any,
    master: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from ...codirector.video_intelligence.service import _batch_video_path
    from ...codirector.video_intelligence.worker_client import run_av_perception_pair
    from .omni_continuity_qc import persist_continuity_qc_diagnostics, run_omni_continuity_qc
    from .omni_equipment_qc import persist_equipment_qc_diagnostics, run_omni_equipment_qc

    from ...codirector.video_intelligence.service import _asset_path

    video = _asset_path(db, asset_id) or _batch_video_path(db, project_id, batch)
    if not video:
        raise RuntimeError("SOURCE_VIDEO_MISSING")
    payload = run_av_perception_pair(
        video,
        question=HANDOFF_REVIEW_QUESTION,
        question_b="",
        duration_sec=_review_seconds(batch),
        frame_count=HANDOFF_REVIEW_FRAMES,
        frame_height=HANDOFF_REVIEW_HEIGHT,
        max_new_tokens=320,
        timeout_sec=180.0,
        source_asset_id=str(asset_id or ""),
    )
    answers = payload.get("answers") if isinstance(payload.get("answers"), list) else [payload, payload]
    continuity_payload = answers[0] if answers else payload
    equipment_payload = answers[1] if len(answers) > 1 else payload
    continuity_qc = run_omni_continuity_qc(
        db,
        project_id=project_id,
        scene_id=scene_id,
        asset_id=asset_id,
        batch=batch,
        master=master,
        observed_packet=continuity_payload,
    )
    persist_continuity_qc_diagnostics(batch, continuity_qc)
    equipment_qc = run_omni_equipment_qc(
        db,
        project_id=project_id,
        scene_id=scene_id,
        asset_id=asset_id,
        observed_packet=equipment_payload,
    )
    persist_equipment_qc_diagnostics(batch, equipment_qc)
    return continuity_qc, equipment_qc
