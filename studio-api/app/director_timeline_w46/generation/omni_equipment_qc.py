# -*- coding: utf-8 -*-
"""Omni UNAUTHORIZED PRODUCTION EQUIPMENT visual QC producer — Final Check inventory #5.

Emits equipmentQcDiagnostics / omniEquipmentDiagnostics onto batch.references.
Ingest already wired in scene_final_check.collect_batch_qc_packets.

AUTHORITY remains retake_context_package.unauthorized_equipment_authority() /
prompt_law_crew_out + CRS/ERS/scene plan. ONE authority — do not invent a second
exclusion list.

Cinematography language (push-in, dolly, boom as CAMERA MOVE) is Creative taste —
never auto Hard. Diegetic crew / boom-in-frame / camera-crew-in-frame = Hard.

12B policy lock: interviewer + crew behind camera OFF-SCREEN is AUTHORIZED.
Bare "interviewer" without in-frame evidence → UNCERTAIN / review (not auto-destroy).
"""

from __future__ import annotations

import re
from typing import Any

EQUIPMENT_QC_KIND = "omniEquipmentDiagnostics"
EQUIPMENT_QC_KINDS = frozenset(
    {
        "omniEquipmentDiagnostics",
        "equipmentQcDiagnostics",
        "omniEquipmentQc",
        "omniVisualQc",
    }
)

QC_PASS = "PASS"
QC_FAIL = "FAIL"
QC_UNCERTAIN = "UNCERTAIN"

# Targeted Omni question — diegetic production equipment / crew IN FRAME only.
EQUIPMENT_ANALYZE_QUESTION = (
    "You are a film production QC inspector checking for UNAUTHORIZED DIEGETIC "
    "production equipment or crew visible IN FRAME. Watch carefully.\n"
    "Respond with ONLY a JSON object (no prose) with keys:\n"
    '"summary": one-paragraph description of what is visible;\n'
    '"visualEvents": list of {"startTime","endTime","label","detail","confidence"};\n'
    '"equipmentFlags": list of short strings ONLY when you clearly see diegetic '
    "film crew, camera operators, boom mic / boom pole in frame, interviewer "
    "VISIBLE IN THE PICTURE, clapperboard/slate, or other production equipment "
    "visible as part of the story world;\n"
    '"cameraMoves": list of {"startTime","endTime","motionType","direction","confidence"} '
    "for cinematography moves (pan, tilt, dolly, crane, push-in, handheld, static, "
    "boom-as-camera-move) — these are NOT equipment defects;\n"
    '"speechSegments": [];\n'
    '"audioEvents": [];\n'
    '"motionEvents": [];\n'
    '"contactEvents": [];\n'
    '"characterActions": [];\n'
    '"sceneChanges": [];\n'
    "CRITICAL: Do NOT flag a camera boom/dolly/crane MOVE as crew or boom-in-frame. "
    "Only flag physical crew members or boom microphones/poles visibly in the shot. "
    "Interviewer or crew BEHIND THE CAMERA / OFF-SCREEN / not visible in picture is "
    "AUTHORIZED interview setup — do NOT put that in equipmentFlags. "
    "If you only infer an interviewer exists but cannot see them in frame, leave "
    "equipmentFlags empty (uncertain ≠ in-frame). If unsure, leave equipmentFlags "
    "empty. Do NOT invent."
)

# Cinematography language — Creative, never auto Hard.
_CAMERA_MOVE_RE = re.compile(
    r"\b("
    r"push[\s-]*in|push[\s-]*out|dolly(?:\s+in|\s+out|\s+shot)?|crane(?:\s+shot)?|"
    r"handheld|steadicam|pan(?:ning)?|tilt(?:ing)?|tracking\s+shot|truck(?:ing)?|"
    r"zoom(?:ing)?|whip\s+pan|camera\s+move|camera\s+motion|"
    r"boom\s+(?:shot|up|down|move|as\s+camera)|jib(?:\s+shot)?"
    r")\b",
    re.IGNORECASE,
)

_CODE_BY_LABEL = (
    (("boom mic", "boom pole", "boom in frame", "microphone boom", "boom operator"), "BOOM_IN_FRAME"),
    (("camera crew", "camera operator", "camera operators"), "CAMERA_CREW_IN_FRAME"),
    (("diegetic crew",), "DIEGETIC_CREW"),
    (("crew in frame", "film crew", "documentary crew", "interviewer"), "CREW_IN_FRAME"),
    (("clapperboard", "slate in frame", "production equipment"), "UNAUTHORIZED_PRODUCTION_EQUIPMENT"),
)


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _blob(obj: Any) -> str:
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return " ".join(_blob(v) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return " ".join(_blob(x) for x in obj)
    return str(obj)


def is_camera_move_language(text: str | None) -> bool:
    """True when text is cinematography language, not diegetic crew/boom-in-frame."""
    raw = str(text or "").strip()
    if not raw:
        return False
    if _CAMERA_MOVE_RE.search(raw):
        # If also clearly diegetic crew, still treat as equipment — dual mention.
        low = raw.lower()
        diegetic = any(
            x in low
            for x in (
                "crew in frame",
                "operator in frame",
                "boom mic",
                "boom pole",
                "microphone in frame",
                "clapperboard",
            )
        )
        return not diegetic
    return False


def _crew_disposition(text: str | None, *, context: str | None = None) -> str:
    from .retake_context_package import (
        CREW_OBSERVATION_NONE,
        classify_crew_equipment_observation,
    )

    try:
        return classify_crew_equipment_observation(text, context=context)
    except Exception:
        return CREW_OBSERVATION_NONE


def classify_equipment_code(text: str | None, *, context: str | None = None) -> str | None:
    """Map observation text → equipment Hard code. None if not Hard in-frame."""
    low = str(text or "").strip().lower()
    if not low:
        return None
    if is_camera_move_language(low):
        return None
    from .retake_context_package import CREW_OBSERVATION_HARD

    if _crew_disposition(low, context=context) != CREW_OBSERVATION_HARD:
        return None
    blob = f"{low} {str(context or '').strip().lower()}".strip()
    for labels, code in _CODE_BY_LABEL:
        if any(lab in low for lab in labels) or any(lab in blob for lab in labels):
            return code
    try:
        from .retake_context_package import observation_matches_unauthorized_equipment

        if observation_matches_unauthorized_equipment(low, context=context):
            return "UNAUTHORIZED_PRODUCTION_EQUIPMENT"
    except Exception:
        pass
    return None


def equipment_authority_packet() -> dict[str, Any]:
    from .retake_context_package import unauthorized_equipment_authority

    return unauthorized_equipment_authority()


def extract_equipment_observations(packet: Any) -> dict[str, Any]:
    """Pull Omni visual observations for equipment/crew. Observation only."""
    if packet is None:
        return {
            "summary": "",
            "visualEvents": [],
            "equipmentFlags": [],
            "cameraMoves": [],
            "availability": "unavailable",
            "role": "observation_only",
        }
    dump = packet.model_dump() if hasattr(packet, "model_dump") else (packet if isinstance(packet, dict) else {})
    extras = dump.get("extras") or {}
    avail = str(dump.get("availability") or extras.get("availability") or "ready")
    summary = str(dump.get("summary") or "")
    visual = dump.get("visualEvents") or []
    flags = extras.get("equipmentFlags") or dump.get("equipmentFlags") or []
    camera_moves = extras.get("cameraMoves") or dump.get("cameraMotion") or dump.get("cameraMoves") or []
    if not isinstance(flags, list):
        flags = []
    # Salvage from summary/visual when model put crew mentions in prose.
    blob = " ".join([summary, _blob(visual), _blob(flags)]).lower()
    salvaged = list(flags)
    try:
        from .retake_context_package import (
            CREW_OBSERVATION_HARD,
            UNAUTHORIZED_EQUIPMENT_OBSERVATION_LABELS,
            classify_crew_equipment_observation,
        )

        labels = UNAUTHORIZED_EQUIPMENT_OBSERVATION_LABELS
    except Exception:
        labels = (
            "film crew",
            "camera crew",
            "boom mic",
            "boom in frame",
            "crew in frame",
            "camera operator",
        )
        CREW_OBSERVATION_HARD = "hard"  # noqa: N806
        classify_crew_equipment_observation = None  # type: ignore
    for lab in labels:
        if lab not in blob or lab in salvaged or is_camera_move_language(lab):
            continue
        # Only salvage when ONE authority says Hard IN-FRAME — never bare "interviewer".
        if classify_crew_equipment_observation is not None:
            try:
                if classify_crew_equipment_observation(lab, context=blob) != CREW_OBSERVATION_HARD:
                    continue
            except Exception:
                continue
        salvaged.append(lab)
    conf = None
    try:
        conf = float(dump.get("confidence") or extras.get("confidence") or 0.0) or None
    except (TypeError, ValueError):
        conf = None
    reason = extras.get("reason") or dump.get("reason")
    if reason and avail == "ready" and reason not in (None, ""):
        # Unavailable packets often still say ready incorrectly — trust reason.
        if str(reason) in {
            "SOURCE_VIDEO_MISSING",
            "GENERATION_ACTIVE",
            "INSUFFICIENT_VRAM",
            "TIMEOUT",
            "PERCEPTION_ERROR",
        }:
            avail = "unavailable"
    return {
        "summary": summary,
        "visualEvents": visual if isinstance(visual, list) else [],
        "equipmentFlags": salvaged,
        "cameraMoves": camera_moves if isinstance(camera_moves, list) else [],
        "availability": avail,
        "confidence": conf,
        "reason": reason,
        "role": "observation_only",
    }


def evaluate_equipment_qc(observed: dict[str, Any]) -> dict[str, Any]:
    """Evaluate Omni observation vs ONE unauthorized-equipment AUTHORITY.

    Hard+high-conf diegetic crew/boom IN FRAME → FAIL + retakeEligible.
    Off-screen / behind-camera authorized interview setup → NOT Hard.
    Bare interviewer/crew without in-frame evidence → UNCERTAIN (no auto-destroy).
    Camera-move language → Creative surface only (never auto).
    Unavailable Omni → UNCERTAIN (not PASS; not invented FAIL).
    """
    from .retake_context_package import (
        CREW_OBSERVATION_AUTHORIZED_OFFSCREEN,
        CREW_OBSERVATION_HARD,
        CREW_OBSERVATION_UNCERTAIN,
        classify_crew_equipment_observation,
    )

    auth = equipment_authority_packet()
    obs = observed or {}
    availability = str(obs.get("availability") or "unavailable")
    findings: list[dict[str, Any]] = []

    if availability in {"unavailable", "degraded"} or obs.get("error"):
        finding = {
            "code": "OMNI_EQUIPMENT_UNAVAILABLE",
            "severity": "warning",
            "confidence": "low",
            "message": (
                "Omni equipment/visual observation unavailable — UNCERTAIN != PASS; "
                "do not invent crew findings"
            ),
            "authoritySource": auth.get("authoritySource"),
            "finalCheck": {
                "retakeEligible": False,
                "autoDestroy": False,
                "acceptanceEligible": False,
                "creativeTaste": False,
                "authoritySource": auth.get("authoritySource"),
            },
        }
        return {
            "kind": EQUIPMENT_QC_KIND,
            "verdict": QC_UNCERTAIN,
            "reason": "OMNI_EQUIPMENT_UNAVAILABLE",
            "sceneFinishedEligible": False,
            "findings": [finding],
            "equipmentFindings": [finding],
            "authority": auth,
            "observed": {"availability": availability, "role": "observation_only"},
            "createdAt": _now(),
            "gateRan": True,
        }

    conf_raw = obs.get("confidence")
    try:
        conf_f = float(conf_raw) if conf_raw is not None else None
    except (TypeError, ValueError):
        conf_f = None
    weak = conf_f is not None and conf_f < 0.45

    summary = str(obs.get("summary") or "")
    context_blob = " ".join(
        [summary, _blob(obs.get("visualEvents")), _blob(obs.get("equipmentFlags"))]
    ).strip()

    # Creative camera moves — surface only.
    for move in obs.get("cameraMoves") or []:
        label = _blob(move)
        if not label:
            continue
        if is_camera_move_language(label) or True:
            findings.append(
                {
                    "code": "CREATIVE_CAMERA_TASTE",
                    "severity": "info",
                    "confidence": "high",
                    "creative": True,
                    "creativeTaste": True,
                    "message": f"Camera move (not equipment defect): {label[:160]}",
                    "authoritySource": "creative_suggestion",
                    "finalCheck": {
                        "retakeEligible": False,
                        "autoDestroy": False,
                        "acceptanceEligible": True,
                        "creativeTaste": True,
                        "authoritySource": "creative_suggestion",
                    },
                }
            )

    hard_flags: list[str] = []
    uncertain_seen = False
    authorized_offscreen_seen = False

    def _append_hard(text: str, code: str) -> None:
        high = not weak
        hard_flags.append(code)
        findings.append(
            {
                "code": code,
                "severity": "error",
                "confidence": "high" if high else "low",
                "message": text,
                "observation": text,
                "authoritySource": auth.get("authoritySource"),
                "finalCheck": {
                    "retakeEligible": bool(high),
                    "autoDestroy": False,
                    "acceptanceEligible": False,
                    "creativeTaste": False,
                    "authoritySource": auth.get("authoritySource"),
                },
            }
        )

    def _append_uncertain(text: str) -> None:
        nonlocal uncertain_seen
        uncertain_seen = True
        findings.append(
            {
                "code": "CREW_OBSERVATION_UNCERTAIN",
                "severity": "warning",
                "confidence": "low",
                "message": (
                    f"Crew/interviewer mentioned without in-frame evidence — "
                    f"review (not auto-retake): {text[:200]}"
                ),
                "observation": text,
                "authoritySource": auth.get("authoritySource"),
                "crossModalityUncertainty": True,
                "finalCheck": {
                    "retakeEligible": False,
                    "autoDestroy": False,
                    "acceptanceEligible": False,
                    "creativeTaste": False,
                    "authoritySource": auth.get("authoritySource"),
                },
            }
        )

    def _append_authorized(text: str) -> None:
        nonlocal authorized_offscreen_seen
        authorized_offscreen_seen = True
        findings.append(
            {
                "code": "CREW_OFFSCREEN_AUTHORIZED",
                "severity": "info",
                "confidence": "high",
                "message": (
                    f"Off-screen / behind-camera interview crew authorized (12B): "
                    f"{text[:200]}"
                ),
                "observation": text,
                "authoritySource": auth.get("authoritySource"),
                "finalCheck": {
                    "retakeEligible": False,
                    "autoDestroy": False,
                    "acceptanceEligible": True,
                    "creativeTaste": False,
                    "authoritySource": auth.get("authoritySource"),
                },
            }
        )

    for flag in obs.get("equipmentFlags") or []:
        text = str(flag)
        if is_camera_move_language(text):
            findings.append(
                {
                    "code": "CREATIVE_CAMERA_TASTE",
                    "severity": "info",
                    "confidence": "high",
                    "creative": True,
                    "creativeTaste": True,
                    "message": f"Cinematography language (not diegetic crew): {text[:160]}",
                    "authoritySource": "creative_suggestion",
                    "finalCheck": {
                        "retakeEligible": False,
                        "autoDestroy": False,
                        "acceptanceEligible": True,
                        "creativeTaste": True,
                        "authoritySource": "creative_suggestion",
                    },
                }
            )
            continue
        disp = classify_crew_equipment_observation(text, context=context_blob)
        if disp == CREW_OBSERVATION_AUTHORIZED_OFFSCREEN:
            _append_authorized(text)
            continue
        if disp == CREW_OBSERVATION_UNCERTAIN:
            _append_uncertain(text)
            continue
        if disp != CREW_OBSERVATION_HARD:
            continue
        code = classify_equipment_code(text, context=context_blob)
        if not code:
            continue
        _append_hard(text, code)

    # Also scan summary when flags empty / no Hard yet but prose names framing.
    if not hard_flags and summary:
        disp = classify_crew_equipment_observation(summary, context=context_blob)
        if disp == CREW_OBSERVATION_HARD:
            code = classify_equipment_code(summary, context=context_blob)
            if code:
                _append_hard(summary[:240], code)
        elif disp == CREW_OBSERVATION_AUTHORIZED_OFFSCREEN and not authorized_offscreen_seen:
            _append_authorized(summary[:240])
        elif disp == CREW_OBSERVATION_UNCERTAIN and not uncertain_seen:
            _append_uncertain(summary[:240])

    hard_findings = [
        f
        for f in findings
        if f.get("code")
        not in {
            "CREATIVE_CAMERA_TASTE",
            "CREW_OFFSCREEN_AUTHORIZED",
            "CREW_OBSERVATION_UNCERTAIN",
        }
    ]
    if hard_findings and any(f.get("confidence") == "high" for f in hard_findings):
        return {
            "kind": EQUIPMENT_QC_KIND,
            "verdict": QC_FAIL,
            "reason": hard_flags[0] if hard_flags else "UNAUTHORIZED_PRODUCTION_EQUIPMENT",
            "sceneFinishedEligible": False,
            "findings": findings,
            "equipmentFindings": hard_findings,
            "authority": auth,
            "observed": {
                "summary": obs.get("summary"),
                "equipmentFlags": obs.get("equipmentFlags"),
                "cameraMoves": obs.get("cameraMoves"),
                "availability": availability,
                "confidence": conf_f,
                "role": "observation_only",
            },
            "createdAt": _now(),
            "gateRan": True,
        }

    if hard_findings:
        # All low-conf
        for f in hard_findings:
            f["confidence"] = "low"
            f["finalCheck"] = {
                **(f.get("finalCheck") or {}),
                "retakeEligible": False,
                "autoDestroy": False,
            }
        return {
            "kind": EQUIPMENT_QC_KIND,
            "verdict": QC_UNCERTAIN,
            "reason": "EQUIPMENT_LOW_CONFIDENCE",
            "sceneFinishedEligible": False,
            "findings": findings,
            "equipmentFindings": hard_findings,
            "authority": auth,
            "observed": {
                "summary": obs.get("summary"),
                "equipmentFlags": obs.get("equipmentFlags"),
                "availability": availability,
                "confidence": conf_f,
                "role": "observation_only",
            },
            "createdAt": _now(),
            "gateRan": True,
        }

    if uncertain_seen:
        uncertain_findings = [f for f in findings if f.get("code") == "CREW_OBSERVATION_UNCERTAIN"]
        return {
            "kind": EQUIPMENT_QC_KIND,
            "verdict": QC_UNCERTAIN,
            "reason": "CREW_FRAMING_UNCERTAIN",
            "sceneFinishedEligible": False,
            "findings": findings,
            "equipmentFindings": uncertain_findings,
            "authority": auth,
            "observed": {
                "summary": obs.get("summary"),
                "equipmentFlags": obs.get("equipmentFlags"),
                "cameraMoves": obs.get("cameraMoves"),
                "availability": availability,
                "confidence": conf_f,
                "role": "observation_only",
            },
            "createdAt": _now(),
            "gateRan": True,
            "note": (
                "Bare interviewer/crew without in-frame evidence — UNCERTAIN / review; "
                "absence of in-frame evidence ≠ presence (cross-modality)."
            ),
        }

    # Gate ran, no diegetic in-frame equipment — PASS (authorized off-screen / creative OK).
    return {
        "kind": EQUIPMENT_QC_KIND,
        "verdict": QC_PASS,
        "reason": None,
        "sceneFinishedEligible": True,
        "findings": findings,  # may include Creative-only / authorized off-screen
        "equipmentFindings": [],
        "authority": auth,
        "observed": {
            "summary": obs.get("summary"),
            "equipmentFlags": [],
            "cameraMoves": obs.get("cameraMoves"),
            "availability": availability,
            "confidence": conf_f,
            "role": "observation_only",
        },
        "createdAt": _now(),
        "gateRan": True,
        "note": (
            "No unauthorized diegetic production equipment / crew in frame."
            + (
                " Off-screen interviewer/crew authorized."
                if authorized_offscreen_seen
                else ""
            )
        ),
    }


def run_omni_equipment_qc(
    db: Any,
    *,
    project_id: str,
    scene_id: str,
    asset_id: str,
    force: bool = True,
    timeout_sec: float = 180.0,
    observed_packet: Any = None,
) -> dict[str, Any]:
    """Invoke Adept Omni visual analyze and evaluate vs unauthorized-equipment AUTHORITY."""
    observed: dict[str, Any]
    try:
        from app.codirector.video_intelligence.media_analyze import analyze_asset

        packet = observed_packet if observed_packet is not None else analyze_asset(
            db,
            project_id,
            asset_id,
            mode="summary",
            question=EQUIPMENT_ANALYZE_QUESTION,
            scene_id=scene_id,
            force=force,
            persist=True,
            timeout_sec=timeout_sec,
        )
        observed = extract_equipment_observations(packet)
    except Exception as exc:  # noqa: BLE001
        observed = {
            "summary": "",
            "visualEvents": [],
            "equipmentFlags": [],
            "cameraMoves": [],
            "availability": "unavailable",
            "error": str(exc),
            "role": "observation_only",
        }
    return evaluate_equipment_qc(observed)


def persist_equipment_qc_diagnostics(batch: Any, qc: dict[str, Any]) -> None:
    """Attach omniEquipmentDiagnostics onto batch.references (replace prior same kind)."""
    packet = dict(qc)
    packet["kind"] = EQUIPMENT_QC_KIND
    refs = [
        r
        for r in (getattr(batch, "references", None) or [])
        if not (isinstance(r, dict) and r.get("kind") in EQUIPMENT_QC_KINDS)
    ]
    refs.append(packet)
    batch.references = refs
