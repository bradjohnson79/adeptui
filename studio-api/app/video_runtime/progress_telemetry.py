"""Grounded MiniMax H3 / Comfy generation telemetry.

Numeric percentages are shown only when Comfy reports a real step fraction
(value/max with max>1). Elapsed time never invents a percent. When a step
fraction is unavailable, Timeline shows a creator phase instead of 0%.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

# No *real* Comfy/runtime event for this long → stall chrome.
# Synthetic "still running" poll ticks do not reset lastRuntimeEventAt.
# Repeating "Executing node 125" (or any non-heartbeat WS/queue event) does —
# MiniMax H3 Quality 2.0 MP routinely samples that node for 20–40 minutes
# without a grounded value/max step fraction.
STALL_THRESHOLD_SEC = 180.0

PHASE_QUEUED = "queued"
PHASE_PREPARING_MODEL = "preparing_model"
PHASE_LOADING_REFERENCES = "loading_references"
PHASE_ENCODING_PROMPT = "encoding_prompt"
PHASE_SAMPLING = "sampling"
PHASE_DECODING = "decoding"
PHASE_FINALIZING = "finalizing"
PHASE_STALLED = "stalled"
PHASE_INIT_STALL = "init_stall"
INIT_STALL_LABEL = "Generation stalled during model initialization."

CREATOR_PHASE_LABELS: dict[str, str] = {
    PHASE_QUEUED: "Queued",
    PHASE_PREPARING_MODEL: "Preparing model",
    PHASE_LOADING_REFERENCES: "Loading references",
    PHASE_ENCODING_PROMPT: "Encoding prompt",
    PHASE_SAMPLING: "Generating",
    PHASE_DECODING: "Decoding",
    PHASE_FINALIZING: "Finalizing",
    PHASE_STALLED: "Generation may be stalled",
    PHASE_INIT_STALL: INIT_STALL_LABEL,
}

# Activity noun shown beside the scene verb. Sampling stays "Sampling" so the
# chrome can read "Generating — Sampling" without inventing a percent.
PHASE_ACTIVITY_LABELS: dict[str, str] = {
    PHASE_QUEUED: "Queued",
    PHASE_PREPARING_MODEL: "Preparing model",
    PHASE_LOADING_REFERENCES: "Loading references",
    PHASE_ENCODING_PROMPT: "Encoding prompt",
    PHASE_SAMPLING: "Sampling",
    PHASE_DECODING: "Decoding",
    PHASE_FINALIZING: "Finalizing",
    PHASE_STALLED: "Generation may be stalled",
    PHASE_INIT_STALL: INIT_STALL_LABEL,
}

# Fresh Comfy/runtime event within this window → "Runtime active".
RUNTIME_ACTIVE_SEC = 30.0

# MiniMax H3 Ref2V Adept Comfy graph (workflows/h3_ref2v_builder.py).
H3_REF2V_NODE_PHASE: dict[str, str] = {
    "127": PHASE_PREPARING_MODEL,  # UNETLoader
    "144": PHASE_PREPARING_MODEL,  # PathchSageAttentionKJ
    "143": PHASE_PREPARING_MODEL,  # EasyCache (Fast)
    "128": PHASE_PREPARING_MODEL,  # CLIPLoader
    "119": PHASE_PREPARING_MODEL,  # video VAE
    "120": PHASE_PREPARING_MODEL,  # audio VAE
    "138": PHASE_ENCODING_PROMPT,  # PrimitiveStringMultiline
    "136": PHASE_ENCODING_PROMPT,  # MiniMaxH3ReferenceToVideo
    "129": PHASE_ENCODING_PROMPT,  # RandomNoise
    "123": PHASE_ENCODING_PROMPT,  # KSamplerSelect
    "124": PHASE_ENCODING_PROMPT,  # BasicScheduler
    "126": PHASE_ENCODING_PROMPT,  # BasicGuider
    "125": PHASE_SAMPLING,  # SamplerCustomAdvanced
    "122": PHASE_DECODING,  # VAEDecode
    "121": PHASE_DECODING,  # VAEDecodeAudio
    "130": PHASE_FINALIZING,  # CreateVideo
    "92": PHASE_FINALIZING,  # SaveVideo
    "137": PHASE_LOADING_REFERENCES,
    "139": PHASE_LOADING_REFERENCES,
    "145": PHASE_LOADING_REFERENCES,
    "146": PHASE_LOADING_REFERENCES,
    "147": PHASE_LOADING_REFERENCES,
    "148": PHASE_LOADING_REFERENCES,
    "149": PHASE_LOADING_REFERENCES,
    "150": PHASE_LOADING_REFERENCES,
    "151": PHASE_LOADING_REFERENCES,
}

# Route A T2V node floors (video_runtime.progress.ROUTE_A_NODE_FLOOR) → phases.
ROUTE_A_NODE_PHASE: dict[str, str] = {
    "15": PHASE_LOADING_REFERENCES,
    "1": PHASE_PREPARING_MODEL,
    "2": PHASE_PREPARING_MODEL,
    "3": PHASE_PREPARING_MODEL,
    "4": PHASE_PREPARING_MODEL,
    "5": PHASE_ENCODING_PROMPT,
    "90": PHASE_PREPARING_MODEL,
    "10": PHASE_SAMPLING,
    "11": PHASE_DECODING,
    "12": PHASE_DECODING,
    "13": PHASE_FINALIZING,
    "14": PHASE_FINALIZING,
}

_CLASS_PHASE: dict[str, str] = {
    "unetloader": PHASE_PREPARING_MODEL,
    "cliploader": PHASE_PREPARING_MODEL,
    "vaeloader": PHASE_PREPARING_MODEL,
    "pathchsageattentionkj": PHASE_PREPARING_MODEL,
    "easycache": PHASE_PREPARING_MODEL,
    "loadimage": PHASE_LOADING_REFERENCES,
    "loadaudio": PHASE_LOADING_REFERENCES,
    "primitivestringmultiline": PHASE_ENCODING_PROMPT,
    "minimaxh3referencetovideo": PHASE_ENCODING_PROMPT,
    "randomnoise": PHASE_ENCODING_PROMPT,
    "ksamplerselect": PHASE_ENCODING_PROMPT,
    "basicscheduler": PHASE_ENCODING_PROMPT,
    "basicguider": PHASE_ENCODING_PROMPT,
    "samplercustomadvanced": PHASE_SAMPLING,
    "ksampler": PHASE_SAMPLING,
    "vaedecode": PHASE_DECODING,
    "vaedecodeaudio": PHASE_DECODING,
    "createvideo": PHASE_FINALIZING,
    "savevideo": PHASE_FINALIZING,
    "vhs_videocombine": PHASE_FINALIZING,
}

# Timeline H3 fast graph node ids. These numbers also exist on Route A with
# different jobs, so this map is used only when the running graph is h3_fast.
# Node 13 is the sampler here. On Route A, node 13 is the mux.
H3_FAST_NODE_PHASE: dict[str, str] = {
    "1": PHASE_PREPARING_MODEL,
    "2": PHASE_PREPARING_MODEL,
    "3": PHASE_PREPARING_MODEL,
    "4": PHASE_PREPARING_MODEL,
    "5": PHASE_PREPARING_MODEL,
    "6": PHASE_PREPARING_MODEL,
    "18": PHASE_PREPARING_MODEL,
    "7": PHASE_ENCODING_PROMPT,
    "8": PHASE_ENCODING_PROMPT,
    "9": PHASE_ENCODING_PROMPT,
    "10": PHASE_ENCODING_PROMPT,
    "11": PHASE_ENCODING_PROMPT,
    "12": PHASE_ENCODING_PROMPT,
    "13": PHASE_SAMPLING,
    "14": PHASE_DECODING,
    "15": PHASE_DECODING,
    "16": PHASE_FINALIZING,
    "17": PHASE_FINALIZING,
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def utcnow_iso() -> str:
    return utcnow().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def creator_phase_label(phase: str | None) -> str:
    key = str(phase or "").strip()
    return CREATOR_PHASE_LABELS.get(key, "") or (key.replace("_", " ").title() if key else "")


def creator_activity_label(phase: str | None, phase_label: str | None = None) -> str:
    key = str(phase or "").strip()
    if key in PHASE_ACTIVITY_LABELS:
        return PHASE_ACTIVITY_LABELS[key]
    shown = str(phase_label or "").strip()
    if shown and shown.lower() != "generating":
        return shown
    return creator_phase_label(key)


def format_elapsed_clock(seconds: Any) -> str:
    try:
        total = max(0, int(float(seconds or 0)))
    except (TypeError, ValueError):
        return "00:00"
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def scene_verb(scene_status: str | None, phase: str | None) -> str:
    status = str(scene_status or "").strip().lower()
    phase_key = str(phase or "").strip()
    if status in {"queued", "pending"} and phase_key in {"", PHASE_QUEUED}:
        return "Queued"
    if status == "waiting" and phase_key in {"", PHASE_QUEUED}:
        return "Preparing"
    if phase_key in {PHASE_QUEUED}:
        return "Queued"
    if phase_key in {PHASE_PREPARING_MODEL, PHASE_LOADING_REFERENCES, PHASE_ENCODING_PROMPT}:
        return "Preparing"
    if status in {"queued", "pending"}:
        return "Queued"
    if status == "waiting":
        return "Preparing"
    return "Generating"


def phase_from_node(node: Any, class_type: str | None = None, graph: str | None = None) -> str | None:
    key = str(node or "").strip()
    if graph == "h3_fast" and key in H3_FAST_NODE_PHASE:
        return H3_FAST_NODE_PHASE[key]
    if key in H3_REF2V_NODE_PHASE:
        return H3_REF2V_NODE_PHASE[key]
    if key in ROUTE_A_NODE_PHASE:
        return ROUTE_A_NODE_PHASE[key]
    if key.isdigit() and int(key) >= 200:
        return PHASE_LOADING_REFERENCES
    token = str(class_type or "").strip().lower()
    if token in _CLASS_PHASE:
        return _CLASS_PHASE[token]
    return None


def phase_from_message(message: str | None, *, stage: str | None = None) -> str | None:
    low = f"{message or ''} {stage or ''}".lower()
    if "queued" in low or "pending" in low:
        return PHASE_QUEUED
    if "load" in low and "ref" in low:
        return PHASE_LOADING_REFERENCES
    if "prepar" in low or "load" in low or "model" in low or "unet" in low or "clip" in low:
        return PHASE_PREPARING_MODEL
    if "encod" in low or "prompt" in low or "conditioner" in low:
        return PHASE_ENCODING_PROMPT
    if "sampl" in low or "step" in low:
        return PHASE_SAMPLING
    if "decod" in low or "vae" in low:
        return PHASE_DECODING
    if "final" in low or "writ" in low or "sav" in low or "mux" in low or "done" in low:
        return PHASE_FINALIZING
    if "running in comfy" in low or "execut" in low:
        return PHASE_SAMPLING
    return None


def infer_creator_phase(
    *,
    message: str | None = None,
    stage: str | None = None,
    node: Any = None,
    class_type: str | None = None,
    job_status: str | None = None,
    graph: str | None = None,
) -> str:
    status = str(job_status or "").strip().lower()
    if status in {"queued", "pending"}:
        node_phase = phase_from_node(node, class_type, graph)
        return node_phase or PHASE_QUEUED
    node_phase = phase_from_node(node, class_type, graph)
    if node_phase:
        return node_phase
    msg_phase = phase_from_message(message, stage=stage)
    if msg_phase:
        return msg_phase
    if status in {"running", "processing"}:
        return PHASE_PREPARING_MODEL
    return PHASE_QUEUED


_COMFY_STEP_RE = re.compile(
    r"(?:sampling step|node(?:\s+progress)?(?:\s+\d+)?)\s+(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)",
    re.I,
)


def comfy_step_fraction(message: str | None) -> tuple[float, float] | None:
    """Raw Comfy value/max from a progress message. None when Comfy did not send a bar."""
    text = str(message or "")
    match = _COMFY_STEP_RE.search(text)
    if match is None:
        return None
    value = float(match.group(1))
    maximum = float(match.group(2))
    if maximum <= 1:
        return None
    return value, maximum


def comfy_progress_percent(message: str | None, *, progress: float | None = None) -> int | None:
    """Integer 0–100 from Comfy value/max, else a grounded 0–1 fraction."""
    step = comfy_step_fraction(message)
    if step is not None:
        value, maximum = step
        return max(0, min(100, int(round(100.0 * value / maximum))))
    if progress is None:
        return None
    raw = float(progress)
    if raw < 0:
        return None
    pct = int(round(raw * 100 if raw <= 1 else raw))
    return max(0, min(100, pct))


def is_grounded_progress_message(message: str | None, *, max_steps: float | None = None) -> bool:
    """True only for a real Comfy step fraction (value/max with max>1) or completion."""
    low = str(message or "").lower()
    if "done" in low or "complete" in low:
        return True
    if max_steps is not None and float(max_steps) > 1:
        return True
    return comfy_step_fraction(message) is not None


def is_heartbeat_only_message(message: str | None) -> bool:
    return "still running" in str(message or "").lower()


def seconds_since(iso_value: Any, *, now: datetime | None = None) -> float | None:
    stamp = parse_iso(iso_value)
    if stamp is None:
        return None
    current = now or utcnow()
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return max(0.0, (current - stamp).total_seconds())


def format_last_activity(iso_value: Any, *, now: datetime | None = None) -> str:
    sec = seconds_since(iso_value, now=now)
    if sec is None:
        return "unknown"
    if sec < 60:
        n = max(1, int(round(sec)))
        return f"{n} second{'s' if n != 1 else ''} ago"
    minutes = max(1, int(round(sec / 60.0)))
    return f"{minutes} minute{'s' if minutes != 1 else ''} ago"


def extract_progress_telemetry(history_json: str | None) -> dict[str, Any]:
    try:
        history = json.loads(history_json or "{}")
    except json.JSONDecodeError:
        history = {}
    if not isinstance(history, dict):
        return {}
    tel = history.get("progressTelemetry")
    return dict(tel) if isinstance(tel, dict) else {}


def merge_progress_telemetry(history_json: str | None, patch: dict[str, Any]) -> str:
    try:
        history = json.loads(history_json or "{}")
        if not isinstance(history, dict):
            history = {}
    except json.JSONDecodeError:
        history = {}
    prev = history.get("progressTelemetry")
    merged = dict(prev) if isinstance(prev, dict) else {}
    merged.update({k: v for k, v in patch.items() if v is not None})
    history["progressTelemetry"] = merged
    return json.dumps(history)


def apply_heartbeat(
    previous: dict[str, Any] | None,
    *,
    progress: float,
    message: str,
    stage: str | None,
    node: Any = None,
    class_type: str | None = None,
    job_status: str = "running",
    grounded: bool | None = None,
    started_at: str | None = None,
    now_iso: str | None = None,
    stall_threshold_sec: float = STALL_THRESHOLD_SEC,
    graph: str | None = None,
    sage_attention: str | None = None,
) -> dict[str, Any]:
    """Merge one runtime tick into progressTelemetry. Never invents a percent."""
    prev = dict(previous or {})
    now = now_iso or utcnow_iso()
    heartbeat_only = is_heartbeat_only_message(message)
    grounded_flag = (
        bool(grounded)
        if grounded is not None
        else is_grounded_progress_message(message)
    )
    phase = infer_creator_phase(
        message=message,
        stage=stage,
        node=node if node is not None else prev.get("currentNode"),
        class_type=class_type,
        job_status=job_status,
        graph=graph,
    )
    started = str(started_at or prev.get("startedAt") or now)
    last_event = prev.get("lastRuntimeEventAt")
    if not heartbeat_only:
        last_event = now
    elif not last_event:
        last_event = now

    last_progress = prev.get("lastProgressAt")
    prev_phase = str(prev.get("phase") or "")
    prev_node = str(prev.get("currentNode") or "")
    phase_changed = phase != prev_phase or (node is not None and str(node) != prev_node)
    if grounded_flag or phase_changed:
        last_progress = now

    elapsed = seconds_since(started, now=parse_iso(now)) or 0.0
    # Stall on silent runtime events, not on an unchanged sampler node.
    # lastProgressAt staying put during H3 sampling is expected when Comfy
    # emits executing/heartbeat but no value/max>1. lastRuntimeEventAt going
    # quiet means the progress channel or Comfy itself stopped talking.
    silent_for = seconds_since(last_event, now=parse_iso(now)) or 0.0
    active = str(job_status or "").lower() in {"running", "processing"}
    stalled = bool(active and silent_for >= stall_threshold_sec)

    out = {
        "phase": phase,
        "phaseLabel": creator_phase_label(phase),
        "progressGrounded": bool(grounded_flag),
        "progress": max(0.0, min(1.0, float(progress or 0.0))) if grounded_flag else prev.get("progress"),
        "currentNode": str(node) if node is not None else prev.get("currentNode"),
        "lastProgressAt": last_progress,
        "lastRuntimeEventAt": last_event,
        "lastHeartbeatAt": now,
        "startedAt": started,
        "elapsedActiveTime": elapsed,
        "stalled": stalled,
        "progressSource": "comfy_ws" if grounded_flag else ("heartbeat" if heartbeat_only else "phase"),
        "message": (message or "")[:400],
        "stage": stage or prev.get("stage"),
    }
    if stalled:
        out["stallLabel"] = (
            f"Generation may be stalled. Last activity: {format_last_activity(last_event, now=parse_iso(now))}"
        )
    return _apply_fast_kernel_watch(
        prev,
        out,
        message=message,
        sage_attention=sage_attention,
        now_iso=now,
        stall_threshold_sec=stall_threshold_sec,
    )


def _apply_fast_kernel_watch(
    prev: dict[str, Any],
    out: dict[str, Any],
    *,
    message: str,
    sage_attention: str | None,
    now_iso: str,
    stall_threshold_sec: float,
) -> dict[str, Any]:
    """Fast Base Optimized kernels must produce a new step inside the stall window.

    The safe continuation profile leaves sage off and is not watched. A frozen
    first tick is not inference progress: the percent is cleared and the
    creator sees the stall sentence instead of a stuck 17%.
    """

    mode = str(sage_attention or "").strip()
    if mode in {"", "disabled"}:
        return out
    phase = str(out.get("phase") or "")
    node = str(out.get("currentNode") or "")
    if phase != PHASE_SAMPLING and node != "13":
        return out
    step = comfy_step_fraction(message)
    prev_value = prev.get("inferenceStepValue")
    value = float(step[0]) if step is not None else prev_value
    advanced = prev.get("inferenceStepAdvancedAt")
    if step is not None and (prev_value is None or float(step[0]) != float(prev_value)):
        value = float(step[0])
        advanced = now_iso
    elif not advanced:
        advanced = now_iso
    out["inferenceStepValue"] = 0 if value is None else value
    out["inferenceStepAdvancedAt"] = advanced
    silent = seconds_since(advanced, now=parse_iso(now_iso)) or 0.0
    if silent < float(stall_threshold_sec):
        return out
    out["initStalled"] = True
    out["phase"] = PHASE_INIT_STALL
    out["phaseLabel"] = INIT_STALL_LABEL
    out["progressGrounded"] = False
    out["clearProgress"] = True
    out["stalled"] = True
    out["stallLabel"] = INIT_STALL_LABEL
    return out


def format_render_status_line(
    *,
    batch_index: int,
    total_batches: int,
    take_label: str | None = None,
    scene_status: str = "generating",
    progress: float | None = None,
    progress_grounded: bool = False,
    phase: str | None = None,
    phase_label: str | None = None,
    stalled: bool = False,
    last_runtime_event_at: str | None = None,
    elapsed_active_time: float | None = None,
    gpu_active: bool | None = None,
    now: datetime | None = None,
    message: str | None = None,
) -> str:
    """Creator chrome. Percent is Comfy value/max only — never a clock estimate."""
    n = max(1, int(batch_index or 1))
    m = max(1, int(total_batches or 1))
    label = str(take_label or "").strip()
    phase_key = str(phase or "")
    verb = scene_verb(scene_status, phase_key)
    activity = creator_activity_label(phase_key, phase_label)

    if label:
        parts = [verb, label, f"Batch {n}/{m}"]
    elif activity and activity != verb:
        parts = [f"Render Batch {n}/{m}", verb, activity]
    else:
        parts = [f"Render Batch {n}/{m}", verb]
    line = " — ".join(part for part in parts if part)

    pct = comfy_progress_percent(
        message,
        progress=progress if progress_grounded else None,
    )
    if pct is not None:
        line = f"{line} — {pct}%"

    extras: list[str] = []
    if elapsed_active_time is not None:
        extras.append(f"Elapsed: {format_elapsed_clock(elapsed_active_time)}")
    if stalled:
        extras.append("Generation may be stalled")
    else:
        extras.append("Runtime active")
        if gpu_active is True:
            extras.append("GPU active")
    if last_runtime_event_at:
        extras.append(
            f"Last runtime event: {format_last_activity(last_runtime_event_at, now=now)}"
        )
    return "\n".join([line, *extras])


def telemetry_from_job_row(row: Any) -> dict[str, Any]:
    history = getattr(row, "history_json", None)
    tel = extract_progress_telemetry(history if isinstance(history, str) else None)
    if not tel:
        tel = apply_heartbeat(
            {},
            progress=float(getattr(row, "progress", 0.0) or 0.0),
            message=str(getattr(row, "message", "") or ""),
            stage=str(getattr(row, "stage", "") or ""),
            job_status=str(getattr(row, "status", "") or ""),
            grounded=False,
            started_at=None,
        )
        started = getattr(row, "created_at", None)
        if started is not None:
            try:
                iso = started.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z") if getattr(started, "isoformat", None) else None
            except Exception:
                iso = None
            if iso:
                tel["startedAt"] = iso
                tel["elapsedActiveTime"] = seconds_since(iso) or 0.0
    return tel
