"""Gen-owned Execution Window materialization.

Consumes Co-Director execution window plans (PRIMARY start-in-window /
OVERLAP CARRY projector lives in CD `execution_windows.py` — Gen never
reimplements projector logic). Rematerializes Timeline Master `batchBlocks`
from CD plan windows only.

Authority:
  - PreparedSceneResult.spec.batchWindows / batch_count, OR
  - plan_spec_execution_windows(spec), OR
  - plan_execution_windows(duration_seconds, generator_id)
  Creator N-batches / creator batchCount are NOT authority.

Systems P5: store.replace_master / put_master mints new stk_ + executionRevision
  BEFORE rematerialize when topology changes. Caller MUST pass
  allow_scene_take_id == NEW currentSceneTakeId from put_master response
  (must differ from previous continuity stk_); optionally allow_revision.

HARD LOCK — generator switch:
  Rematerialize batchBlocks ONLY after Systems mints a new stk_/revision when
  requiresNewSceneTake / requiresRevisionBump. Never rematerialize onto the
  same stk_ after topology change.
"""

from __future__ import annotations

import re

from typing import Any, Iterable, Mapping, Optional, Sequence

from .contracts import BatchBlock, DurationState, TimelinePromptSegment
from .creator_batch_surface import default_execution_window_label, is_legacy_batch_label
from .migration import compute_config_fingerprint

CREATOR_BATCH_MUTATION_DISABLED = "CREATOR_BATCH_MUTATION_DISABLED"
GENERATOR_SWITCH_REQUIRES_NEW_SCENE_TAKE = "GENERATOR_SWITCH_REQUIRES_NEW_SCENE_TAKE"

_CREATOR_BATCH_MSG = (
    "Execution Windows are Co-Director plan / capability driven. "
    "Creator add/duplicate/delete/resize of batchBlocks is disabled; "
    "use rematerialize_execution_windows from a CD plan (and a new SceneTake "
    "when topology changes)."
)

# Fingerprint-safe content fields preserved by index when remapping windows.
_PRESERVE_BATCH_ATTRS = (
    "references",
    "h3Resolution",
    "ltxQuality",
    "seedanceResolution",
    "lora",
    "dialogueManifest",
    "speechWindows",
    "sourceAnchors",
)
_PRESERVE_SEGMENT_ATTRS = (
    "text",
    "productionPrompt",
    "userDirection",
    "dialogue",
    "negativePrompt",
    "role",
    "strength",
    "temperature",
    "referenceBindingIds",
    "referenceNameBindings",
    "legacyPromptSegmentId",
    "anchorIds",
    "executionStrategy",
    "movementSegmentRef",
    "movementSegmentRevision",
)


def creator_batch_mutation_blocked(reason: str = "") -> dict[str, Any]:
    """Constant error for creator batch CRUD / resize paths."""
    msg = _CREATOR_BATCH_MSG
    if reason:
        msg = f"{msg} ({reason})"
    return {
        "ok": False,
        "error": CREATOR_BATCH_MUTATION_DISABLED,
        "message": msg,
        "mock": False,
    }


def _as_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, Mapping):
        return dict(obj)
    if hasattr(obj, "model_dump"):
        try:
            return dict(obj.model_dump())
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in vars(obj).items() if not k.startswith("_")}
    return {}


def _window_bounds(window: Any) -> tuple[float, float]:
    """Normalize CD ExecutionWindow / dict / handoff window to (start, end)."""
    w = _as_dict(window) if not isinstance(window, Mapping) else dict(window)
    start = w.get("start", w.get("startSeconds", w.get("start_seconds")))
    end = w.get("end", w.get("endSeconds", w.get("end_seconds")))
    if start is None and "offset" in w:
        start = w.get("offset")
    length = w.get("length", w.get("duration", w.get("plannedDuration")))
    if start is None:
        start = 0.0
    start = float(start)
    if end is None:
        if length is None:
            end = start
        else:
            end = start + float(length)
    return start, float(end)


def _round_topology(windows: Sequence[Any]) -> list[tuple[float, float]]:
    return [(round(s, 3), round(e, 3)) for s, e in (_window_bounds(w) for w in windows)]


def current_window_topology(master: Any) -> list[dict[str, float]]:
    """Cumulative plannedDuration of ordered batchBlocks → [{start,end}, ...]."""
    blocks = list(getattr(master, "batchBlocks", None) or [])
    blocks = sorted(blocks, key=lambda b: int(getattr(b, "order", 0) or 0))
    out: list[dict[str, float]] = []
    cursor = 0.0
    for b in blocks:
        dur = getattr(b, "duration", None)
        planned = float(getattr(dur, "plannedDuration", None) or 0.0) if dur is not None else 0.0
        planned = max(0.0, planned)
        start = cursor
        end = cursor + planned
        out.append({"start": start, "end": end})
        cursor = end
    return out


def topology_changed(previous: Sequence[Any], new_windows: Sequence[Any]) -> bool:
    prev = _round_topology(previous)
    nxt = _round_topology(new_windows)
    return prev != nxt


def _normalize_windows_payload(
    windows: Any = None,
    plan: Any = None,
) -> list[Any]:
    if windows is not None:
        if isinstance(windows, dict) and "windows" in windows:
            return list(windows.get("windows") or [])
        if isinstance(windows, dict) and "newWindows" in windows:
            return list(windows.get("newWindows") or [])
        return list(windows)
    if plan is None:
        return []
    p = _as_dict(plan)
    for key in ("windows", "newWindows", "new_windows", "batchWindows"):
        if key in p and p[key] is not None:
            return list(p[key])
    if isinstance(plan, (list, tuple)):
        return list(plan)
    return []


def resolve_plan_windows(
    *,
    duration_seconds: float | None = None,
    generator_id: str | None = None,
    windows: Any = None,
    plan: Any = None,
    spec: Any = None,
) -> list[Any]:
    """Prefer explicit CD plan / spec.batchWindows; else call CD planner."""
    explicit = _normalize_windows_payload(windows=windows, plan=plan)
    if explicit:
        return explicit

    if spec is not None:
        s = _as_dict(spec)
        bw = s.get("batchWindows") or s.get("batch_windows")
        if bw:
            return list(bw)
        try:
            from app.codirector.production.execution_windows import (  # type: ignore
                plan_spec_execution_windows,
            )

            planned = plan_spec_execution_windows(spec)
            got = _normalize_windows_payload(plan=planned)
            if got:
                return got
        except Exception:
            pass

    if duration_seconds is None or generator_id is None:
        return []

    from app.codirector.production.execution_windows import (  # type: ignore
        plan_execution_windows,
    )

    planned = plan_execution_windows(
        duration_seconds=float(duration_seconds),
        generator_id=generator_id,
    )
    return _normalize_windows_payload(plan=planned) or list(planned or [])


def resolve_scene_duration_and_generator(
    master: Any,
    *,
    duration_seconds: float | None = None,
    generator_id: str | None = None,
    scene: Any = None,
) -> tuple[float | None, str | None]:
    dur = duration_seconds
    gid = generator_id
    if dur is None and scene is not None:
        dur = getattr(scene, "duration_sec", None)
        if dur is None:
            dur = _as_dict(scene).get("duration_sec") or _as_dict(scene).get("durationSeconds")
    if dur is None:
        topo = current_window_topology(master)
        if topo:
            dur = float(topo[-1]["end"])
    if gid is None:
        gid = getattr(master, "sceneGeneratorId", None)
    if gid is None and scene is not None:
        gid = getattr(scene, "generator_id", None) or _as_dict(scene).get("generatorId")
    if gid is None:
        blocks = list(getattr(master, "batchBlocks", None) or [])
        if blocks:
            gid = getattr(blocks[0], "generatorId", None)
    return (float(dur) if dur is not None else None), (str(gid) if gid else None)


def _master_scene_take_id(master: Any) -> str | None:
    for attr in ("currentSceneTakeId", "activeSceneTakeId", "sceneTakeId"):
        val = getattr(master, attr, None)
        if val:
            return str(val)
    return None


def _master_revision(master: Any) -> int | None:
    for attr in ("executionRevision", "revision", "sceneTakeRevision"):
        val = getattr(master, attr, None)
        if val is not None:
            try:
                return int(val)
            except Exception:
                continue
    return None


def _allow_gate_ok(
    master: Any,
    *,
    allow_scene_take_id: str | None,
    allow_revision: int | None,
    previous_scene_take_id: str | None = None,
) -> bool:
    """Systems P5: put_master already pointed currentSceneTakeId at the NEW stk_.

    Accept when allow_scene_take_id matches master.currentSceneTakeId (minted)
    and is proven fresh via previous_scene_take_id != allow and/or allow_revision.
    Never accept rematerialize onto the same continuity stk_ after topology change.
    """
    if not allow_scene_take_id:
        return False
    allow = str(allow_scene_take_id).strip()
    if not allow.startswith("stk_"):
        return False
    current = _master_scene_take_id(master)
    prev = str(previous_scene_take_id).strip() if previous_scene_take_id else None
    if current == allow:
        if prev and prev == allow:
            return False
        return True
    if current and allow != current:
        return True
    if current is None:
        return True
    return False



def _build_switch_handoff(
    *,
    previous_generator_id: str | None,
    new_generator_id: str | None,
    duration_seconds: float | None,
    previous_windows: Sequence[Any],
) -> dict[str, Any]:
    """Prefer CD orchestrator camelCase handoff; fall back to plan_delta."""
    try:
        from app.codirector.production.orchestrator import (  # type: ignore
            build_generator_switch_handoff,
        )

        handoff = build_generator_switch_handoff(
            previous_generator_id=previous_generator_id,
            new_generator_id=new_generator_id,
            duration_seconds=duration_seconds,
            previous_windows=list(previous_windows),
        )
        return _as_dict(handoff)
    except Exception:
        pass

    try:
        from app.codirector.production.execution_windows import (  # type: ignore
            generator_switch_plan_delta,
        )

        delta = generator_switch_plan_delta(
            previous_generator_id=previous_generator_id,
            new_generator_id=new_generator_id,
            duration_seconds=duration_seconds,
            previous_windows=list(previous_windows),
        )
        d = _as_dict(delta)
        # Normalize snake → camel for Gen consumers.
        return {
            "requiresNewSceneTake": bool(
                d.get("requiresNewSceneTake", d.get("requires_new_scene_take"))
            ),
            "requiresRevisionBump": bool(
                d.get("requiresRevisionBump", d.get("requires_revision_bump"))
            ),
            "newWindows": d.get("newWindows") or d.get("new_windows") or [],
            "newBatchCount": d.get("newBatchCount", d.get("new_batch_count")),
            **d,
        }
    except Exception as exc:
        return {
            "requiresNewSceneTake": True,
            "requiresRevisionBump": True,
            "newWindows": [],
            "error": f"SWITCH_HANDOFF_UNAVAILABLE:{exc}",
        }


def _scene_duration_from_windows(windows: Sequence[Any]) -> float:
    total = 0.0
    for w in windows:
        start, end = _window_bounds(w)
        total += max(0.0, float(end) - float(start))
    return total


def _looks_like_full_scene_prompt(seg: Any, scene_duration: float) -> bool:
    """True when a segment is the scene-level Timed Prompt (0-N), not window-local."""
    if seg is None:
        return False
    text = str(getattr(seg, "text", "") or "")
    start = float(getattr(seg, "start", 0.0) or 0.0)
    length = float(getattr(seg, "length", 0.0) or 0.0)
    if scene_duration > 0 and start <= 0.05 and length >= max(0.0, scene_duration - 0.05):
        return True
    m = re.search(r"Seconds:\s*0\s*[-–—]\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if m and scene_duration > 0 and float(m.group(1)) >= max(0.0, scene_duration - 0.5):
        return True
    return False


def _continuation_text(window_index: int, start: float, end: float) -> str:
    """Timed Prompts are not given a continuation header."""
    _ = (window_index, start, end)
    return ""


def _preserve_segment_content(
    src: Any,
    length: float,
    *,
    start: float = 0.0,
    force_blank_text: bool = False,
) -> TimelinePromptSegment:
    """Copy authored segment fields. Caller decides blank vs continuation for extensions."""
    data = _as_dict(src) if src is not None else {}
    kwargs: dict[str, Any] = {
        "start": float(start),
        "length": float(length),
        "text": "",
    }
    for attr in _PRESERVE_SEGMENT_ATTRS:
        if attr in data and data[attr] is not None:
            kwargs[attr] = data[attr]
    if force_blank_text:
        kwargs["text"] = ""
    elif not kwargs.get("text") and data.get("text"):
        kwargs["text"] = data["text"]
    return TimelinePromptSegment(**kwargs)


def _preserve_batch_content(src: Any, dest: BatchBlock) -> None:
    if src is None:
        return
    for attr in _PRESERVE_BATCH_ATTRS:
        if hasattr(src, attr):
            val = getattr(src, attr)
            if val is not None and hasattr(dest, attr):
                try:
                    setattr(dest, attr, val)
                except Exception:
                    pass
        else:
            data = _as_dict(src)
            if attr in data and data[attr] is not None and hasattr(dest, attr):
                try:
                    setattr(dest, attr, data[attr])
                except Exception:
                    pass
    # Preserve label when present (non-default)
    src_label = getattr(src, "label", None) or _as_dict(src).get("label")
    if src_label and str(src_label).strip() and not str(src_label).startswith("Batch "):
        dest.label = str(src_label)


def _build_batch_blocks(
    master: Any,
    windows: Sequence[Any],
    *,
    scene_id: str,
    generator_id: str | None,
) -> list[BatchBlock]:
    existing = sorted(
        list(getattr(master, "batchBlocks", None) or []),
        key=lambda b: int(getattr(b, "order", 0) or 0),
    )
    same_count = len(existing) == len(windows)
    scene_duration = _scene_duration_from_windows(windows)
    if existing:
        root_segs = getattr(existing[0], "promptSegments", None) or []
        if root_segs:
            root_len = float(getattr(root_segs[0], "length", 0.0) or 0.0)
            if root_len > scene_duration:
                scene_duration = root_len
    blocks: list[BatchBlock] = []
    for i, window in enumerate(windows):
        start, end = _window_bounds(window)
        length = max(0.0, float(end) - float(start))
        # Charter: root owns scene Timed Prompt (0-N). Extensions inherit+continuation
        # only — NEVER clone Seconds:0-N into window 2+ (Take P regression).
        src = existing[i] if i < len(existing) else None
        root_segs = (getattr(existing[0], "promptSegments", None) or []) if existing else []
        root_seg = root_segs[0] if root_segs else None
        if i == 0:
            seg_src = None
            if src is not None and getattr(src, "promptSegments", None):
                seg_src = src.promptSegments[0]
            elif root_seg is not None and str(getattr(root_seg, "text", "") or "").strip():
                seg_src = root_seg
            # Root keeps scene creative clock span, not the 15s window length.
            seg_len = max(
                float(getattr(seg_src, "length", 0.0) or 0.0) if seg_src is not None else 0.0,
                scene_duration,
                length,
            )
            seg = _preserve_segment_content(seg_src, seg_len, start=0.0)
            if not str(getattr(seg, "text", "") or "").strip() and seg_src is not None:
                # Never blank an authored root prompt on rematerialize.
                try:
                    seg.text = str(getattr(seg_src, "text", "") or "")
                except Exception:
                    pass
        else:
            # A take must not invent or replace Timed Prompt text. Keep the
            # words already on this window, including a full-scene script.
            seg_src = None
            if src is not None and getattr(src, "promptSegments", None):
                seg_src = src.promptSegments[0]
            authored_start = float(getattr(seg_src, "start", 0.0) or 0.0) if seg_src is not None else 0.0
            seg_start = authored_start if authored_start + 1e-6 >= start else start
            if seg_src is not None and str(getattr(seg_src, "text", "") or "").strip():
                seg = _preserve_segment_content(seg_src, length, start=seg_start)
            else:
                seg = _preserve_segment_content(None, length, start=seg_start, force_blank_text=True)
        batch = BatchBlock(
            sceneId=scene_id,
            order=i,
            label=((getattr(src, "label", None) if src and same_count and not is_legacy_batch_label(getattr(src, "label", None)) else None) or default_execution_window_label(i)),
            generatorId=generator_id
            or (getattr(src, "generatorId", None) if src else None)
            or getattr(master, "sceneGeneratorId", None),
            duration=DurationState(plannedDuration=length, timelineVisibleDuration=length),
            promptSegments=[seg],
            status=getattr(src, "status", None) if src and same_count else "Draft",
        )
        if src is not None:
            # Keep stable bb_* id when remapping by index (count may differ).
            try:
                batch.id = src.id
            except Exception:
                pass
            _preserve_batch_content(src, batch)
            # Preserve take/job lineage only when bounds unchanged for this index.
            prev_topo = current_window_topology(master)
            if i < len(prev_topo):
                prev_bounds = (
                    round(prev_topo[i]["start"], 3),
                    round(prev_topo[i]["end"], 3),
                )
                new_bounds = (round(start, 3), round(end, 3))
                if prev_bounds == new_bounds:
                    for attr in (
                        "generationJobs",
                        "candidateVersions",
                        "approvedClip",
                        "activeTakeId",
                        "visualClips",
                        "audioClips",
                        "sfxClips",
                        "cameraInstructions",
                    ):
                        if hasattr(src, attr) and hasattr(batch, attr):
                            try:
                                setattr(batch, attr, getattr(src, attr))
                            except Exception:
                                pass
        batch.configFingerprint = compute_config_fingerprint(batch)
        blocks.append(batch)
    from .generation.window_script import carry_root_references_to_empty_windows

    carry_root_references_to_empty_windows(type("_Windows", (), {"batchBlocks": blocks})())
    for batch in blocks:
        batch.configFingerprint = compute_config_fingerprint(batch)
    return blocks


def rematerialize_batch_blocks_from_plan(
    master: Any,
    *,
    windows: Any = None,
    plan: Any = None,
    spec: Any = None,
    generator_id: str | None = None,
    scene_id: str | None = None,
    duration_seconds: float | None = None,
    previous_generator_id: str | None = None,
    allow_scene_take_id: str | None = None,
    allow_revision: int | None = None,
    previous_scene_take_id: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Build/replace master.batchBlocks from CD window plan.

    On topology change: require new SceneTake/revision gate. Never rematerialize
    onto the same stk_ after topology change unless force=True (emergency only).
    """
    sid = scene_id or getattr(master, "sceneId", None)
    if not sid:
        blocks = list(getattr(master, "batchBlocks", None) or [])
        if blocks:
            sid = getattr(blocks[0], "sceneId", None)
    if not sid:
        return {"ok": False, "error": "SCENE_ID_REQUIRED", "mock": False}

    dur, gid = resolve_scene_duration_and_generator(
        master, duration_seconds=duration_seconds, generator_id=generator_id
    )
    gid = generator_id or gid

    resolved = resolve_plan_windows(
        duration_seconds=dur,
        generator_id=gid,
        windows=windows,
        plan=plan,
        spec=spec,
    )
    if not resolved:
        return {
            "ok": False,
            "error": "EXECUTION_WINDOW_PLAN_REQUIRED",
            "message": "No CD execution window plan available (spec.batchWindows / plan / planner).",
            "mock": False,
        }

    prev_topo = current_window_topology(master)
    changed = topology_changed(prev_topo, resolved)

    prev_gid = previous_generator_id
    if prev_gid is None:
        prev_gid = getattr(master, "sceneGeneratorId", None)
        if prev_gid is None:
            blocks = list(getattr(master, "batchBlocks", None) or [])
            if blocks:
                prev_gid = getattr(blocks[0], "generatorId", None)

    handoff: dict[str, Any] = {}
    if changed or (prev_gid and gid and str(prev_gid) != str(gid)):
        handoff = _build_switch_handoff(
            previous_generator_id=prev_gid,
            new_generator_id=gid,
            duration_seconds=dur,
            previous_windows=prev_topo,
        )
        # Prefer handoff.newWindows when topology must follow switch plan.
        hw = handoff.get("newWindows") or handoff.get("new_windows")
        if hw and (changed or handoff.get("requiresNewSceneTake") or handoff.get("requires_new_scene_take")):
            resolved = list(hw)
            changed = topology_changed(prev_topo, resolved)

        requires_take = bool(
            handoff.get("requiresNewSceneTake", handoff.get("requires_new_scene_take"))
        )
        requires_rev = bool(
            handoff.get("requiresRevisionBump", handoff.get("requires_revision_bump"))
        )
        # Topology change always implies new take gate even if handoff omitted flags.
        if changed:
            requires_take = True

        if (requires_take or requires_rev) and not force:
            # No finished or in-flight generation yet: window changes are planning,
            # not a new take. The first real take is minted when generation starts.
            from .scene_takes import scene_requires_execution_take_boundary

            if scene_requires_execution_take_boundary(master) and not _allow_gate_ok(
                master,
                allow_scene_take_id=allow_scene_take_id,
                allow_revision=allow_revision,
                previous_scene_take_id=previous_scene_take_id,
            ):
                return {
                    "ok": False,
                    "error": GENERATOR_SWITCH_REQUIRES_NEW_SCENE_TAKE,
                    "message": (
                        "Generator/window topology change requires a new SceneTake "
                        "(stk_) / revision minted by Systems before rematerializing batchBlocks."
                    ),
                    "requiresNewSceneTake": requires_take,
                    "requiresRevisionBump": requires_rev,
                    "newWindows": resolved,
                    "newBatchCount": len(resolved),
                    "previousTopology": prev_topo,
                    "handoff": handoff,
                    "note": "CD should recompile BatchPrompt[0..N-1] after new take is bound.",
                    "mock": False,
                }

    blocks = _build_batch_blocks(master, resolved, scene_id=str(sid), generator_id=gid)
    master.batchBlocks = blocks
    # Dual-stack removal left later windows empty while the root kept the
    # whole-scene Timed Prompt. Reconnect: each later window owns its slice.
    from .generation.window_script import assign_later_window_scripts

    assign_later_window_scripts(master)
    if gid:
        try:
            master.sceneGeneratorId = gid
        except Exception:
            pass
    # Optional stamp — plan/spec.batchWindows remains SoT; this is a Gen cache.
    try:
        stamp = [{"start": s, "end": e} for s, e in _round_topology(resolved)]
        if hasattr(master, "batchWindows"):
            master.batchWindows = stamp  # type: ignore[attr-defined]
        elif hasattr(master, "__dict__"):
            # Best-effort annotation without breaking pydantic extra=forbid masters.
            pass
        meta = getattr(master, "migrationMetadata", None)
        if isinstance(meta, dict):
            meta = dict(meta)
            meta["executionWindowsStamp"] = stamp
            meta["executionWindowsGeneratorId"] = gid
            master.migrationMetadata = meta  # type: ignore[attr-defined]
    except Exception:
        pass

    return {
        "ok": True,
        "batchCount": len(blocks),
        "windows": [{"start": s, "end": e} for s, e in _round_topology(resolved)],
        "topologyChanged": changed,
        "generatorId": gid,
        "note": (
            "CD should recompile BatchPrompt[0..N-1] after new take bound"
            if changed
            else None
        ),
        "handoff": handoff or None,
        "mock": False,
    }


def bootstrap_empty_master_from_plan(
    master: Any,
    *,
    scene_id: str,
    duration_seconds: float | None,
    generator_id: str | None,
    windows: Any = None,
    plan: Any = None,
    spec: Any = None,
) -> dict[str, Any]:
    """Fill empty batchBlocks once from CD plan. Never collapses existing multi-batch."""
    existing = list(getattr(master, "batchBlocks", None) or [])
    if existing:
        return {
            "ok": True,
            "skipped": True,
            "reason": "EXISTING_BATCH_BLOCKS_PRESERVED",
            "batchCount": len(existing),
            "mock": False,
        }
    if duration_seconds is None or (generator_id is None and windows is None and plan is None and spec is None):
        return {
            "ok": False,
            "error": "BOOTSTRAP_REQUIRES_DURATION_AND_GENERATOR_OR_PLAN",
            "mock": False,
        }
    return rematerialize_batch_blocks_from_plan(
        master,
        windows=windows,
        plan=plan,
        spec=spec,
        generator_id=generator_id,
        scene_id=scene_id,
        duration_seconds=duration_seconds,
        force=True,  # empty master: no prior topology / stk_ continuity
    )
