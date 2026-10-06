"""Prop Creator Advanced multi-angle sequential session (Phase 5).

Keeps Qwen Edit resident + ref-encode session across views. Enforces
single-flight (maxInFlight=1) for large Prop Advanced angle jobs so RTX 5090
never runs 7 concurrent Qwen Edit gens. Cancel must leave shared encode
session healthy (no corrupt key wipe).

Does not change steps/CFG/size/sampler/model.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


# Hard cap: never more than one large Prop Advanced angle on Comfy at once.
# Micro-batch >1 is intentionally not enabled (OOM risk on 5090).
MAX_INFLIGHT = 1


@dataclass
class AngleSession:
    session_id: str
    prop_id: str
    primary_asset_id: str
    angles_started: list[str] = field(default_factory=list)
    angles_completed: list[str] = field(default_factory=list)
    angles_cancelled: list[str] = field(default_factory=list)
    inflight_job_id: str = ""
    inflight_angle: str = ""
    seq: int = 0
    cancel_preserved_cache: bool = True


_lock = threading.RLock()
_sessions: dict[str, AngleSession] = {}  # prop_id -> session
_job_to_prop: dict[str, str] = {}


def _new_session(prop_id: str, primary_asset_id: str) -> AngleSession:
    return AngleSession(
        session_id=f"pas_{uuid.uuid4().hex[:12]}",
        prop_id=prop_id,
        primary_asset_id=str(primary_asset_id or "").strip(),
    )


def ensure_session(prop_id: str, primary_asset_id: str) -> AngleSession:
    """Return active session for prop; rotate if primary identity changed."""
    pid = str(prop_id or "").strip()
    primary = str(primary_asset_id or "").strip()
    with _lock:
        cur = _sessions.get(pid)
        if cur is None or (primary and cur.primary_asset_id and cur.primary_asset_id != primary):
            cur = _new_session(pid, primary)
            _sessions[pid] = cur
        elif primary and not cur.primary_asset_id:
            cur.primary_asset_id = primary
        return cur


def begin_angle(
    *,
    prop_id: str,
    primary_asset_id: str,
    angle: str,
    job_id: str,
) -> dict[str, Any]:
    """Register an angle job on the prop session. Enforces maxInFlight=1.

    Returns metadata to stamp on creativeContext / history. Raises RuntimeError
    if another angle for this prop is already in-flight (caller should 409).
    """
    angle_l = str(angle or "").strip().lower()
    jid = str(job_id or "").strip()
    with _lock:
        sess = ensure_session(prop_id, primary_asset_id)
        if sess.inflight_job_id and sess.inflight_job_id != jid:
            raise RuntimeError(
                f"Prop Advanced angle session busy ({sess.inflight_angle}); "
                f"maxInFlight={MAX_INFLIGHT}. Wait for the current angle to finish "
                f"or cancel it before starting another."
            )
        sess.seq += 1
        sess.inflight_job_id = jid
        sess.inflight_angle = angle_l
        if angle_l and angle_l not in sess.angles_started:
            sess.angles_started.append(angle_l)
        _job_to_prop[jid] = sess.prop_id
        return snapshot(sess)


def note_angle_completed(job_id: str, *, angle: str = "") -> Optional[dict[str, Any]]:
    jid = str(job_id or "").strip()
    with _lock:
        prop_id = _job_to_prop.get(jid)
        if not prop_id:
            return None
        sess = _sessions.get(prop_id)
        if not sess:
            return None
        ang = str(angle or sess.inflight_angle or "").strip().lower()
        if sess.inflight_job_id == jid:
            sess.inflight_job_id = ""
            sess.inflight_angle = ""
        if ang and ang not in sess.angles_completed:
            sess.angles_completed.append(ang)
        _job_to_prop.pop(jid, None)
        return snapshot(sess)


def note_angle_cancelled(job_id: str, *, angle: str = "") -> Optional[dict[str, Any]]:
    """Release flight after cancel. Does NOT clear ref-encode session.

    Marks cancel_preserved_cache=True so next angle can HIT or honest MISS.
    """
    from .ref_encode_cache import last_shared_digest

    jid = str(job_id or "").strip()
    with _lock:
        prop_id = _job_to_prop.get(jid) or ""
        # Fall back: scan sessions
        sess = _sessions.get(prop_id) if prop_id else None
        if sess is None:
            for s in _sessions.values():
                if s.inflight_job_id == jid:
                    sess = s
                    prop_id = s.prop_id
                    break
        if sess is None:
            return {
                "cancelled": True,
                "cachePreserved": True,
                "sharedDigestPresent": bool(last_shared_digest()),
                "maxInFlight": MAX_INFLIGHT,
            }
        ang = str(angle or sess.inflight_angle or "").strip().lower()
        if sess.inflight_job_id == jid:
            sess.inflight_job_id = ""
            sess.inflight_angle = ""
        if ang and ang not in sess.angles_cancelled:
            sess.angles_cancelled.append(ang)
        sess.cancel_preserved_cache = True
        _job_to_prop.pop(jid, None)
        out = snapshot(sess)
        out["cancelled"] = True
        out["cachePreserved"] = True
        out["sharedDigestPresent"] = bool(last_shared_digest())
        # Intentionally do NOT call clear_ref_encode_session()
        return out


def snapshot(sess: AngleSession) -> dict[str, Any]:
    return {
        "kind": "prop_advanced_angle_session",
        "sessionId": sess.session_id,
        "propId": sess.prop_id,
        "primaryAssetId": sess.primary_asset_id,
        "sessionSeq": sess.seq,
        "maxInFlight": MAX_INFLIGHT,
        "inflightJobId": sess.inflight_job_id or None,
        "inflightAngle": sess.inflight_angle or None,
        "anglesStarted": list(sess.angles_started),
        "anglesCompleted": list(sess.angles_completed),
        "anglesCancelled": list(sess.angles_cancelled),
        "cancelPreservedCache": sess.cancel_preserved_cache,
        "onlyPromptChangesBetweenAngles": True,
    }




def release_inflight(job_id: str) -> None:
    """Clear inflight if this job still owns the slot (success/fail/cancel)."""
    jid = str(job_id or "").strip()
    if not jid:
        return
    with _lock:
        prop_id = _job_to_prop.pop(jid, None)
        sess = _sessions.get(prop_id) if prop_id else None
        if sess is None:
            for s in _sessions.values():
                if s.inflight_job_id == jid:
                    sess = s
                    break
        if sess and sess.inflight_job_id == jid:
            sess.inflight_job_id = ""
            sess.inflight_angle = ""


def get_session(prop_id: str) -> Optional[dict[str, Any]]:
    with _lock:
        sess = _sessions.get(str(prop_id or "").strip())
        return snapshot(sess) if sess else None


def clear_sessions() -> None:
    """Test helper only."""
    with _lock:
        _sessions.clear()
        _job_to_prop.clear()


def is_prop_advanced_angle_params(params: dict[str, Any] | None) -> bool:
    """Detect Prop Advanced angle jobs for cancel-safe residency."""
    p = params if isinstance(params, dict) else {}
    purpose = str(p.get("purpose") or "").strip().lower()
    if purpose == "project_prop_angle":
        return True
    ctx = p.get("creativeContext") if isinstance(p.get("creativeContext"), dict) else {}
    if str(ctx.get("taskType") or "") == "PROP_ADVANCED_ANGLE":
        return True
    if str(ctx.get("objective") or "").strip().lower() == "project_prop_angle":
        return True
    return False


def should_preserve_residency_on_cancel(params: dict[str, Any] | None) -> bool:
    """Phase 5: skip Comfy /free on cancel for Prop Advanced angle session jobs."""
    return is_prop_advanced_angle_params(params)


__all__ = [
    "MAX_INFLIGHT",
    "AngleSession",
    "ensure_session",
    "begin_angle",
    "note_angle_completed",
    "note_angle_cancelled",
    "get_session",
    "release_inflight",
    "clear_sessions",
    "snapshot",
    "is_prop_advanced_angle_params",
    "should_preserve_residency_on_cancel",
]
