"""Adept Media Intelligence Service — asset analysis path (Phase C).

Runs Qwen2.5-Omni AV perception against a project asset and compiles the
frozen ``MediaIntelligencePacket`` (``media-intelligence-v1``).

Source-of-truth rules (non-negotiable):

- **C3 — Qwen is perceptual-only.** ``packet.media`` (codec, sampleRate,
  colorspace, frameCount, …) comes ONLY from ``media_probe.probe_media``
  (ffprobe). The VLM payload is never consulted for deterministic media
  facts, even if it claims them.
- **C2 — perceptual fields** (summary, visualEvents, audioEvents,
  speechSegments, motionEvents, …) come from the Qwen worker payload.
- **C1 — AV ingestion evidence** (``use_audio_in_video=True`` in preprocess +
  processor + generate, plus ingested audio/video shapes) is captured in
  ``packet.extras["qwenIngestion"]`` and ``modelEvidence.qwenOmni``.

GPU admission: never loads while a Comfy generation is active; frees the
generator via the canonical Comfy ``/free`` lease, then (if Qwen still
cannot fit) the existing Route A ``/free`` handoff for idle-warm H3
models. Requires ``MIN_QWEN_OMNI_VRAM_GB`` free VRAM. Degrades to an
explicit ``availability="unavailable"`` packet instead of raising —
perception must never deadlock generation.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, Optional

from .gpu_lease import (
    MIN_QWEN_OMNI_VRAM_GB,
    best_effort_free_generator,
    comfy_generation_active,
    preflight_for_review,
)
from .media_packet import (
    QWEN_OMNI_MODEL_ID,
    AnalysisFingerprint,
    AudioEvent,
    CharacterAction,
    ContactEvent,
    CueOpportunity,
    EnvironmentEvent,
    MediaFacts,
    MediaIntelligencePacket,
    ModelRunEvidence,
    MotionEvent,
    MusicOpportunity,
    SpeechSegment,
    TimelineAnalysisContext,
    VisualEvent,
)
from .media_probe import probe_media
from .paths import QWEN_OMNI_REVISION
from .worker_client import normalize_perception_reason, perception_mode, run_av_perception

logger = logging.getLogger(__name__)

QWEN_OMNI_MODEL_VERSION = f"qwen2-5-omni-7b@{QWEN_OMNI_REVISION[:12]}"

ANALYZE_QUESTION = (
    "You are the perception layer of a film production system. Watch AND listen to this clip carefully. "
    "Respond with ONLY a JSON object (no prose before or after) with these keys:\n"
    '"summary": one-paragraph description of what happens, including anything you hear;\n'
    '"visualEvents": list of {"startTime","endTime","label","detail","phase","confidence"} for visible actions;\n'
    '"audioEvents": list of {"startTime","endTime","eventType","intensity","material","context","presentInAudio","confidence"} '
    "for sounds you actually hear;\n"
    '"speechSegments": list of {"startTime","endTime","speaker","transcription","isSilence","overlap","confidence"} '
    "— transcribe any speech exactly word for word;\n"
    '"motionEvents": list of {"startTime","endTime","subject","motionType","direction","velocity","confidence"} '
    "for camera/character/object motion;\n"
    '"contactEvents": list of {"startTime","endTime","characterLabel","foot","surface","intensity","timingSource",'
    '"confidence"} for every visible foot or hand contact with a surface (footsteps, hand plants, object set-downs); '
    'foot is "left"|"right"|"unknown"; timingSource is "visible_contact" when you can see the contact frame, '
    '"motion_derived" when estimated from body motion;\n'
    '"characterActions": list of {"startTime","endTime","characterLabel","action","actionCompletion",'
    '"movementDirection","confidence"} for each character\'s main action; actionCompletion is 0-1;\n'
    '"environmentEvents": list of {"startTime","endTime","ambienceType","description","confidence"} for persistent '
    "ambience beds you hear or see (wind, crowd, rain, room tone);\n"
    '"sceneChanges": list of {"startTime","endTime","label","detail","phase","confidence"} for cuts, transitions, '
    "or location changes inside the clip;\n"
    '"cameraMotion": list of {"startTime","endTime","subject":"camera","motionType","direction","velocity",'
    '"confidence"} for camera moves (pan, tilt, dolly, handheld, static);\n'
    '"cueOpportunities": list of {"startTime","endTime","kind","label","suggestedQuery","presentInAudio",'
    '"characterLabel","confidence"} for moments where a sound effect could be placed; kind is one of '
    "footstep|door|impact|cloth|machinery|prop|environment|explosion|ambience|other; presentInAudio is true only "
    "when the sound is already audible in the clip;\n"
    '"musicOpportunities": list of {"startTime","endTime","role","intensity","dialogueDensity","emotionalTone",'
    '"duckUnderDialogue","confidence"} for music candidates; role is enter|exit|bed|swell|silence_window;\n'
    '"characters": list of {"label","actionState","actionCompletion","movementDirection","identityCertainty"};\n'
    '"camera": {"movementType","framing","certainty"};\n'
    '"confidence": number 0-1.\n'
    "Rules: report only what you genuinely see or hear; if the clip has audible sound, audioEvents or speechSegments "
    "must reflect it; if the clip is silent, say so in the summary and leave audioEvents empty; report contacts only "
    "when a foot or hand visibly meets a surface or the contact is clearly audible; leave any list empty when nothing "
    "qualifies; do not invent facts; times are seconds from clip start. "
    "Write every string value in English only. Do not answer in Chinese or any other language."
)

_LITERAL_DEFAULTS: dict[type, dict[str, Any]] = {
    VisualEvent: {"phase": "unknown"},
    MotionEvent: {"subject": "unknown"},
    AudioEvent: {},
    SpeechSegment: {},
    CharacterAction: {},
    ContactEvent: {"foot": "unknown", "timingSource": "visible_contact"},
    EnvironmentEvent: {},
    CueOpportunity: {"kind": "other"},
    MusicOpportunity: {"role": "bed"},
}

# JS stringification artifact ("[object Object]") — a payload field carrying it
# holds no information; the field is dropped (never the whole event) so real
# contact/cue data is never silently lost nor polluted with garbage strings.
_OBJECT_OBJECT = "[object Object]"


def _sanitize_event_item(item: dict[str, Any]) -> dict[str, Any]:
    """Drop placeholder junk fields from one VLM event dict.

    - ``"[object Object]"`` string values (upstream JS stringification) are
      removed — the event itself survives on its remaining valid fields.
    - Nested dict/list values are removed — no packet event model has nested
      fields, so keeping them would only fail validation and silently drop
      the whole event.
    """
    clean: dict[str, Any] = {}
    for key, value in item.items():
        if isinstance(value, str) and value.strip() == _OBJECT_OBJECT:
            continue
        if isinstance(value, (dict, list)):
            continue
        clean[key] = value
    return clean


def asset_sha256(path: str | Path) -> str:
    """Streaming SHA-256 of the asset bytes — cache fingerprint input (Ch 7)."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def build_fingerprint(asset_id: str, asset_hash: str) -> AnalysisFingerprint:
    return AnalysisFingerprint(
        assetId=asset_id,
        assetHash=asset_hash,
        qwenOmniModelVersion=QWEN_OMNI_MODEL_VERSION,
    )


def _coerce_event_list(items: Any, model: type) -> list[Any]:
    """Tolerantly validate VLM event dicts against a packet event model.

    Pydantic ignores unknown keys by default; Literal/type mismatches are
    salvaged (invalid Literal -> model default, unparseable numbers dropped).
    Items that still fail are skipped and counted in the salvage log.
    """
    out: list[Any] = []
    if not isinstance(items, list):
        return out
    literal_defaults = _LITERAL_DEFAULTS.get(model, {})
    for item in items:
        if not isinstance(item, dict):
            continue
        item = _sanitize_event_item(item)
        if not item:
            continue
        try:
            out.append(model.model_validate(item))
            continue
        except Exception:
            pass
        slim = dict(item)
        for key, default in literal_defaults.items():
            if key in slim:
                try:
                    model.model_validate({key: slim[key]})
                except Exception:
                    slim[key] = default
        for key in ("startTime", "endTime", "confidence", "actionCompletion", "intensity"):
            if key in slim and slim[key] is not None:
                try:
                    slim[key] = float(slim[key])
                except (TypeError, ValueError):
                    slim.pop(key, None)
        try:
            out.append(model.model_validate(slim))
        except Exception:
            logger.debug("media_analyze: dropped malformed %s event: %r", model.__name__, str(item)[:160])
    return out


def build_packet_from_payload(
    *,
    project_id: str,
    asset_id: str,
    facts: MediaFacts,
    payload: dict[str, Any],
    mode: str = "summary",
    fingerprint: Optional[AnalysisFingerprint] = None,
) -> MediaIntelligencePacket:
    """Compile the frozen packet from probe facts + Qwen worker payload.

    C3: ``media`` is assigned from ``facts`` (ffprobe) verbatim. The VLM
    payload is read ONLY for perceptual fields; any codec/sampleRate/
    colorspace/frameCount claims inside the payload are ignored by design.
    """
    parse_ok = bool(payload.get("parseOk"))
    raw_text = str(payload.get("rawText") or "")
    summary = str(payload.get("summary") or "").strip()
    if not summary and parse_ok:
        summary = raw_text.strip()[:600]

    confidence = payload.get("confidence")
    try:
        confidence = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        confidence = None

    evidence = ModelRunEvidence(
        modelId=str(payload.get("modelId") or QWEN_OMNI_MODEL_ID),
        invoked=True,
        availability="ready" if parse_ok else "low_confidence",
        loadToInferSec=payload.get("loadToInferSec"),
        vramUsedGb=payload.get("vramUsedGb") or payload.get("vramDuringGb"),
        device=payload.get("device"),
        rawText=raw_text[:4000],
        parseOk=parse_ok,
        confidence=confidence,
    )

    packet = MediaIntelligencePacket(
        projectId=project_id,
        assetId=asset_id,
        mode=mode if mode in ("summary", "events", "ground", "transcribe", "diagnose", "footsteps", "full") else "summary",
        media=facts,  # C3 — deterministic facts from media_probe ONLY.
        summary=summary,
        visualEvents=_coerce_event_list(payload.get("visualEvents"), VisualEvent),
        audioEvents=_coerce_event_list(payload.get("audioEvents"), AudioEvent),
        speechSegments=_coerce_event_list(payload.get("speechSegments"), SpeechSegment),
        motionEvents=_coerce_event_list(payload.get("motionEvents"), MotionEvent),
        characterActions=_coerce_event_list(payload.get("characterActions"), CharacterAction),
        contactEvents=_coerce_event_list(payload.get("contactEvents"), ContactEvent),
        environmentEvents=_coerce_event_list(payload.get("environmentEvents"), EnvironmentEvent),
        sceneChanges=_coerce_event_list(payload.get("sceneChanges"), VisualEvent),
        cameraMotion=_coerce_event_list(payload.get("cameraMotion"), MotionEvent),
        cueOpportunities=_coerce_event_list(payload.get("cueOpportunities"), CueOpportunity),
        musicOpportunities=_coerce_event_list(payload.get("musicOpportunities"), MusicOpportunity),
        fingerprint=fingerprint or build_fingerprint(asset_id, ""),
    )
    packet.modelEvidence.qwenOmni = evidence
    ingestion = payload.get("ingestion")
    if isinstance(ingestion, dict):
        packet.extras["qwenIngestion"] = ingestion
    packet.availability = "ready" if parse_ok else "low_confidence"
    if not parse_ok and not raw_text.strip():
        packet.availability = "degraded"
        packet.reason = "EMPTY_PERCEPTION_OUTPUT"
    return packet


def _resolve_asset_path(db: Any, asset_id: str) -> Optional[str]:
    if db is None or not asset_id:
        return None
    try:
        from ...db import Asset

        asset = db.get(Asset, asset_id)
        path = getattr(asset, "path", None) if asset is not None else None
        if path and Path(str(path)).is_file():
            return str(path)
    except Exception:
        return None
    return None


def _unavailable(
    *,
    project_id: str,
    asset_id: str,
    facts: MediaFacts,
    reason: str,
    mode: str,
    fingerprint: AnalysisFingerprint,
    extras: dict[str, Any],
) -> MediaIntelligencePacket:
    packet = MediaIntelligencePacket(
        projectId=project_id,
        assetId=asset_id,
        mode=mode if mode in ("summary", "events", "ground", "transcribe", "diagnose", "footsteps", "full") else "summary",
        availability="unavailable",
        reason=reason,
        media=facts,
        fingerprint=fingerprint,
        extras=extras,
    )
    packet.modelEvidence.qwenOmni = ModelRunEvidence(
        modelId=QWEN_OMNI_MODEL_ID,
        invoked=False,
        availability="unavailable",
    )
    return packet


_FALLBACK_WINDOW_SEC = 6.0


def _resolve_analysis_window(
    facts: MediaFacts,
    duration_sec: Optional[float],
    range_start_sec: Optional[float],
    range_end_sec: Optional[float],
) -> tuple[float, float, str]:
    """Decide the (startSec, durationSec, source) analysis window.

    Default is the FULL probed clip (``facts.durationSec``) — never a silent
    cap. An explicit Timeline range (``rangeEndSec > rangeStartSec``) wins
    over everything; an explicit ``duration_sec`` override wins over the
    probe. Unprobed media (``durationSec <= 0``) falls back to a bounded
    window so the extract layer still gets a finite ``-t``.
    """
    start = 0.0
    try:
        start = max(0.0, float(range_start_sec or 0.0))
    except (TypeError, ValueError):
        start = 0.0
    if range_end_sec is not None:
        try:
            end = float(range_end_sec)
        except (TypeError, ValueError):
            end = 0.0
        if end > start:
            return start, end - start, "timelineRange"
    if duration_sec is not None:
        try:
            dur = float(duration_sec)
        except (TypeError, ValueError):
            dur = 0.0
        if dur > 0:
            return start, dur, "explicit"
    probed = float(getattr(facts, "durationSec", 0.0) or 0.0)
    if probed > 0:
        if 0.0 < start < probed:
            return start, probed - start, "probeFromRangeStart"
        return 0.0, probed, "probeFullDuration"
    return start, _FALLBACK_WINDOW_SEC, "fallbackUnprobed"


def analyze_asset(
    db: Any,
    project_id: str,
    asset_id: str,
    *,
    mode: str = "summary",
    question: str = ANALYZE_QUESTION,
    duration_sec: Optional[float] = None,
    timeout_sec: float = 300.0,
    persist: bool = True,
    force: bool = False,
    scene_id: Optional[str] = None,
    execution_id: Optional[str] = None,
    range_start_sec: Optional[float] = None,
    range_end_sec: Optional[float] = None,
    playhead_sec: Optional[float] = None,
) -> MediaIntelligencePacket:
    """Analyze one project asset with Qwen2.5-Omni (video + audio) and persist
    the Media Intelligence Packet. Returns the cached packet when the
    fingerprint is fresh (Ch 7) unless ``force``. Never raises for perception
    failures — returns an explicit ``unavailable`` packet instead.

    Analysis window: the FULL probed clip by default; a Timeline range
    (``range_start_sec``/``range_end_sec``) narrows it to that window. When
    Timeline coordinates (``scene_id`` / range / ``playhead_sec``) are given,
    a ``TimelineAnalysisContext`` is attached to the packet (and refreshed on
    cache hits) so consumers know which scene/range produced it.
    """
    from . import media_persist

    def _with_timeline_context(packet: MediaIntelligencePacket) -> bool:
        """Attach TimelineAnalysisContext when Timeline kwargs were supplied.

        Returns True when the packet's context changed (caller persists).
        """
        if not (
            scene_id
            or execution_id
            or range_start_sec is not None
            or range_end_sec is not None
            or playhead_sec is not None
        ):
            return False
        try:
            ctx = TimelineAnalysisContext(
                projectId=project_id,
                sceneId=scene_id or "",
                clipAssetId=asset_id,
                executionId=execution_id,
                rangeStartSec=float(range_start_sec or 0.0),
                rangeEndSec=float(range_end_sec) if range_end_sec is not None else None,
                playheadSec=float(playhead_sec) if playhead_sec is not None else None,
            )
        except (TypeError, ValueError):
            return False
        if packet.timelineContext == ctx:
            return False
        packet.timelineContext = ctx
        return True

    extras: dict[str, Any] = {"analyzeMode": mode}
    video_path = _resolve_asset_path(db, asset_id)
    if not video_path:
        packet = _unavailable(
            project_id=project_id,
            asset_id=asset_id,
            facts=MediaFacts(),
            reason="SOURCE_VIDEO_MISSING",
            mode=mode,
            fingerprint=build_fingerprint(asset_id, ""),
            extras=extras,
        )
        _with_timeline_context(packet)
        return packet

    facts = probe_media(video_path)
    window_start, window_dur, window_source = _resolve_analysis_window(
        facts, duration_sec, range_start_sec, range_end_sec
    )
    extras["durationSec"] = window_dur
    extras["analysisWindow"] = {
        "startSec": window_start,
        "durationSec": window_dur,
        "source": window_source,
    }
    fingerprint = build_fingerprint(asset_id, asset_sha256(video_path))

    if not force:
        cached = media_persist.get_or_invalidate(db, project_id, asset_id, fingerprint)
        if cached is not None:
            if _with_timeline_context(cached) and persist:
                media_persist.save_packet(db, project_id, cached)
            return cached

    mode_env = perception_mode()
    if mode_env not in ("stub", "1", "true", "yes", "fail", "error"):
        generation = comfy_generation_active()
        extras["comfyGeneration"] = generation
        if generation.get("active") is True:
            packet = _unavailable(
                project_id=project_id,
                asset_id=asset_id,
                facts=facts,
                reason="GENERATION_ACTIVE",
                mode=mode,
                fingerprint=fingerprint,
                extras=extras,
            )
            _with_timeline_context(packet)
            if persist:
                media_persist.save_packet(db, project_id, packet)
            return packet
        extras["gpuLease"] = best_effort_free_generator()
        preflight = preflight_for_review(min_gb=MIN_QWEN_OMNI_VRAM_GB)
        extras["gpuPreflight"] = preflight
        if not preflight.get("ok"):
            packet = _unavailable(
                project_id=project_id,
                asset_id=asset_id,
                facts=facts,
                reason=str(preflight.get("reason") or "INSUFFICIENT_VRAM"),
                mode=mode,
                fingerprint=fingerprint,
                extras=extras,
            )
            _with_timeline_context(packet)
            if persist:
                media_persist.save_packet(db, project_id, packet)
            return packet
    else:
        extras["gpuLease"] = {"skipped": True, "reason": f"perception_mode={mode_env}"}

    try:
        payload = run_av_perception(
            video_path,
            question=question,
            model_id=QWEN_OMNI_MODEL_ID,
            timeout_sec=timeout_sec,
            start_sec=window_start,
            duration_sec=window_dur,
        )
    except Exception as exc:
        packet = _unavailable(
            project_id=project_id,
            asset_id=asset_id,
            facts=facts,
            reason=normalize_perception_reason(exc),
            mode=mode,
            fingerprint=fingerprint,
            extras=extras,
        )
        _with_timeline_context(packet)
        if persist:
            media_persist.save_packet(db, project_id, packet)
        return packet

    packet = build_packet_from_payload(
        project_id=project_id,
        asset_id=asset_id,
        facts=facts,
        payload=payload,
        mode=mode,
        fingerprint=fingerprint,
    )
    packet.extras.update(extras)
    _with_timeline_context(packet)
    if persist:
        media_persist.save_packet(db, project_id, packet)
    return packet


def diagnose_asset(
    db: Any,
    project_id: str,
    asset_id: str,
    **kw: Any,
) -> MediaIntelligencePacket:
    """Engineering ``diagnose asset <assetId>`` path — thin alias for
    ``analyze_asset(..., mode="diagnose")``. Same canonical authority, NOT a
    separate implementation. The deterministic diagnostics stage and the
    shared CREATE inspection report live in ``inspection_report`` and are
    orchestrated by ``media_router``.
    """
    kw.pop("mode", None)
    return analyze_asset(db, project_id, asset_id, mode="diagnose", **kw)
