"""Omni CONTINUITY QC producer — Final Check inventory #4.

Emits continuityQcDiagnostics / omniContinuityDiagnostics onto batch.references.
Ingest already wired in scene_final_check.collect_batch_qc_packets.

Authority = Narrative continuity canon (Timed Prompt / scene plan / CRS-temporal
intent). Omni observation never overwrites canon. Momentary continuity from a
bad frame never invents authority.

Investigate path: analyze_asset (Qwen Omni) + optional JEPA/temporal packet
corroboration. Prefer extending existing Omni analyze over a new subsystem.
"""

from __future__ import annotations

from typing import Any

CONTINUITY_QC_KIND = "omniContinuityDiagnostics"
CONTINUITY_QC_KINDS = frozenset(
    {
        "omniContinuityDiagnostics",
        "continuityQcDiagnostics",
        "omniContinuityQc",
    }
)

QC_PASS = "PASS"
QC_FAIL = "FAIL"
QC_UNCERTAIN = "UNCERTAIN"

# Continuity-focused Omni question (visual). Observation only — never canon.
CONTINUITY_ANALYZE_QUESTION = (
    "You are a film continuity supervisor. Watch this clip carefully. "
    "Respond with ONLY a JSON object (no prose) with keys:\n"
    '"summary": one-paragraph description of characters, wardrobe, location, screen sides, and action;\n'
    '"visualEvents": list of {"startTime","endTime","label","detail","confidence"};\n'
    '"sceneChanges": list of {"startTime","endTime","label","detail","confidence"} for cuts or location jumps;\n'
    '"characters": list of {"label","wardrobe","screenSide","position","confidence"};\n'
    '"environment": {"location","lighting","props","confidence"};\n'
    '"continuityFlags": list of short strings if you see teleport, wardrobe change mid-shot, '
    "screen-direction flip, or environment jump INSIDE this clip;\n"
    '"speechSegments": [];\n'
    '"audioEvents": [];\n'
    '"motionEvents": [];\n'
    '"contactEvents": [];\n'
    '"characterActions": [];\n'
    '"cameraMotion": list of {"startTime","endTime","motionType","direction","confidence"};\n'
    "Do NOT invent facts you cannot see. Prefer empty lists over guesses."
)

_TELEPORT_TOKENS = (
    "teleport",
    "suddenly appears",
    "jumped location",
    "location jump",
    "warped",
    "discontinuous position",
)
_SIDES_TOKENS = (
    "sides flip",
    "screen direction flip",
    "eyeline flip",
    "crossing the line",
    "180 rule",
    "reversed screen side",
)
_WARDROBE_TOKENS = (
    "wardrobe change",
    "costume change",
    "outfit changed",
    "clothing mismatch",
    "wardrobe mismatch",
)
_ENV_TOKENS = (
    "environment jump",
    "location mismatch",
    "set changed",
    "wrong location",
    "env vs canon",
    "background jump",
)


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _text_blob(obj: Any) -> str:
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        parts = []
        for v in obj.values():
            parts.append(_text_blob(v))
        return " ".join(parts)
    if isinstance(obj, (list, tuple)):
        return " ".join(_text_blob(x) for x in obj)
    return str(obj)


def established_scene_text_from_batch(batch: Any) -> str:
    """Canon prose from batch Timed Prompt segments — Narrative continuity authority."""
    parts: list[str] = []
    for seg in getattr(batch, "promptSegments", None) or []:
        text = str(getattr(seg, "text", None) or "").strip()
        if text:
            parts.append(text)
    if not parts:
        for ref in getattr(batch, "references", None) or []:
            if isinstance(ref, dict) and ref.get("kind") in {"timedPrompt", "scenePlan", "narrativeCanon"}:
                t = str(ref.get("text") or ref.get("prompt") or "").strip()
                if t:
                    parts.append(t)
    return "\n".join(parts).strip()


def narrative_continuity_authority(
    batch: Any,
    *,
    master: Any = None,
    prior_batch: Any = None,
    temporal_packet: Any = None,
) -> dict[str, Any]:
    """ONE Narrative continuity authority (canon). Observations never become canon.

    Sources (priority): Timed Prompt / scene plan on batch; prior-batch exit /
    temporal intent when present. Continuity QC compares TO this — does not write it.
    """
    canon_text = established_scene_text_from_batch(batch)
    prior_text = ""
    if prior_batch is not None:
        prior_text = established_scene_text_from_batch(prior_batch)
    temporal_intent = ""
    temporal_id = None
    if temporal_packet is not None:
        if hasattr(temporal_packet, "model_dump"):
            dump = temporal_packet.model_dump()
        elif isinstance(temporal_packet, dict):
            dump = temporal_packet
        else:
            dump = {}
        temporal_id = dump.get("packetId") or getattr(temporal_packet, "packetId", None)
        assessment = dump.get("assessment") or {}
        if isinstance(assessment, dict):
            temporal_intent = str(assessment.get("intendedState") or "")
        cont = dump.get("continuation") or {}
        if isinstance(cont, dict) and not temporal_intent:
            temporal_intent = " ".join(str(x) for x in (cont.get("preserve") or [])[:4])
    return {
        "authoritySource": "continuity_canon",
        "kind": "narrativeContinuityAuthority",
        "canonText": canon_text,
        "priorBatchCanonText": prior_text,
        "temporalIntent": temporal_intent,
        "temporalPacketId": temporal_id,
        "vsCanon": True,
        "establishedAuthority": True,
        "neverOverwriteCanonFromObservation": True,
        "note": (
            "Canon vs momentary continuity: Omni/JEPA observations are evidence only. "
            "They must not overwrite Narrative continuity authority."
        ),
    }


def extract_continuity_observations(packet: Any) -> dict[str, Any]:
    """Pull Omni visual observations. Observation never becomes authority."""
    if packet is None:
        return {
            "summary": "",
            "visualEvents": [],
            "sceneChanges": [],
            "characters": [],
            "environment": {},
            "continuityFlags": [],
            "availability": "unavailable",
            "role": "observation_only",
        }
    dump = packet.model_dump() if hasattr(packet, "model_dump") else (packet if isinstance(packet, dict) else {})
    extras = dump.get("extras") or {}
    avail = str(dump.get("availability") or extras.get("availability") or "ready")
    summary = str(dump.get("summary") or "")
    visual = dump.get("visualEvents") or []
    scene_changes = dump.get("sceneChanges") or extras.get("sceneChanges") or []
    characters = dump.get("characters") or extras.get("characters") or []
    environment = dump.get("environment") or extras.get("environment") or {}
    flags = extras.get("continuityFlags") or dump.get("continuityFlags") or []
    # Salvage flags from summary/visual labels when model stuffed them in prose.
    blob = " ".join(
        [
            summary,
            _text_blob(visual),
            _text_blob(scene_changes),
            _text_blob(flags),
        ]
    ).lower()
    salvaged: list[str] = list(flags) if isinstance(flags, list) else []
    for tok in _TELEPORT_TOKENS + _SIDES_TOKENS + _WARDROBE_TOKENS + _ENV_TOKENS:
        if tok in blob and tok not in salvaged:
            salvaged.append(tok)
    conf = None
    try:
        conf = float(dump.get("confidence") or extras.get("confidence") or 0.0) or None
    except (TypeError, ValueError):
        conf = None
    return {
        "summary": summary,
        "visualEvents": visual if isinstance(visual, list) else [],
        "sceneChanges": scene_changes if isinstance(scene_changes, list) else [],
        "characters": characters if isinstance(characters, list) else [],
        "environment": environment if isinstance(environment, dict) else {},
        "continuityFlags": salvaged,
        "availability": avail,
        "confidence": conf,
        "role": "observation_only",
        "rawExtras": {k: extras.get(k) for k in ("reason", "analyzeMode", "gpuPreflight") if k in extras},
    }


def _classify_flag(flag: str) -> str | None:
    low = str(flag or "").lower()
    if any(t in low for t in _TELEPORT_TOKENS):
        return "CONTINUITY_TELEPORT"
    if any(t in low for t in _SIDES_TOKENS):
        return "CONTINUITY_SIDES_FLIP"
    if any(t in low for t in _WARDROBE_TOKENS):
        return "CONTINUITY_WARDROBE"
    if any(t in low for t in _ENV_TOKENS):
        return "CONTINUITY_ENV_VS_CANON"
    if "continuity" in low or "break" in low:
        return "CONTINUITY_BREAK"
    return None


def _temporal_corroboration(temporal_packet: Any) -> dict[str, Any]:
    """CRS/JEPA temporal packet as corroborating modality — never sole invent."""
    if temporal_packet is None:
        return {"present": False, "conflict": False, "weak": False, "differences": []}
    dump = temporal_packet.model_dump() if hasattr(temporal_packet, "model_dump") else (
        temporal_packet if isinstance(temporal_packet, dict) else {}
    )
    assessment = dump.get("assessment") or {}
    diffs = list(assessment.get("differences") or []) if isinstance(assessment, dict) else []
    conf = assessment.get("confidence") if isinstance(assessment, dict) else None
    avail = str(dump.get("availability") or "")
    weak = avail in {"low_confidence", "degraded", "unavailable"} or (
        conf is not None and float(conf) < 0.45
    )
    conflict = bool(diffs) and not weak
    return {
        "present": True,
        "conflict": conflict,
        "weak": weak,
        "differences": diffs[:8],
        "availability": avail,
        "confidence": conf,
    }


def evaluate_continuity_qc(
    authority: dict[str, Any],
    observed: dict[str, Any],
    *,
    prior_observed: dict[str, Any] | None = None,
    temporal_packet: Any = None,
) -> dict[str, Any]:
    """Compare Omni observation to Narrative continuity authority.

    High-conf established-authority breaks → FAIL + retakeEligible (Hard).
    Weak visual + CRS/temporal conflict → UNCERTAIN / creator review (never auto-destroy).
    Absence of evidence from one modality ≠ evidence of absence when another contradicts.
    """
    auth = authority or {}
    obs = observed or {}
    temporal = _temporal_corroboration(temporal_packet)
    availability = str(obs.get("availability") or "unavailable")
    findings: list[dict[str, Any]] = []

    if availability in {"unavailable", "degraded"} or obs.get("error"):
        finding = {
            "code": "CONTINUITY_UNCERTAIN",
            "severity": "warning",
            "confidence": "low",
            "message": "Omni continuity observation unavailable — UNCERTAIN != PASS",
            "establishedAuthority": True,
            "authoritySource": auth.get("authoritySource") or "continuity_canon",
            "finalCheck": {
                "retakeEligible": False,
                "autoDestroy": False,
                "acceptanceEligible": False,
                "creativeTaste": False,
                "authoritySource": auth.get("authoritySource") or "continuity_canon",
            },
            "crossModality": {
                "primaryMiss": True,
                "contradictingModality": bool(temporal.get("conflict")),
                "law": "ABSENCE_OF_EVIDENCE_NEQ_EVIDENCE_OF_ABSENCE",
            },
        }
        return {
            "kind": CONTINUITY_QC_KIND,
            "verdict": QC_UNCERTAIN,
            "reason": "CONTINUITY_UNCERTAIN",
            "sceneFinishedEligible": False,
            "findings": [finding],
            "continuityFindings": [finding],
            "authority": auth,
            "observed": {"availability": availability, "role": "observation_only"},
            "temporalCorroboration": temporal,
            "createdAt": _now(),
        }

    flags = list(obs.get("continuityFlags") or [])
    # Adjacent-shot / batch-to-batch: sceneChanges mid-clip or vs prior summary conflict.
    scene_changes = obs.get("sceneChanges") or []
    if scene_changes and len(scene_changes) >= 1:
        for sc in scene_changes[:3]:
            label = ""
            if isinstance(sc, dict):
                label = str(sc.get("label") or sc.get("detail") or "")
            else:
                label = str(sc)
            if label and "cut" not in label.lower():
                flags.append(f"scene change: {label}")

    prior = prior_observed or {}
    if prior.get("summary") and obs.get("summary"):
        # Soft adjacent check — only flag when both summaries assert conflicting locations
        # AND temporal corroborates; never invent from thin visual alone.
        prior_sum = str(prior.get("summary") or "").lower()
        cur_sum = str(obs.get("summary") or "").lower()
        if temporal.get("conflict") and prior_sum and cur_sum and prior_sum[:40] != cur_sum[:40]:
            flags.append("adjacent-shot continuity conflict vs prior batch")

    conf_raw = obs.get("confidence")
    try:
        conf_f = float(conf_raw) if conf_raw is not None else None
    except (TypeError, ValueError):
        conf_f = None
    weak_visual = conf_f is not None and conf_f < 0.45
    if weak_visual and not flags and temporal.get("conflict"):
        finding = {
            "code": "CONTINUITY_CRS_TEMPORAL_CONFLICT",
            "severity": "warning",
            "confidence": "low",
            "weakVisual": True,
            "crsTemporalConflict": True,
            "message": (
                "Weak Omni visual + CRS/temporal conflict — escalate to creator review; "
                "do not auto-regenerate on single weak modality"
            ),
            "establishedAuthority": True,
            "authoritySource": "crs_temporal",
            "finalCheck": {
                "retakeEligible": False,
                "autoDestroy": False,
                "acceptanceEligible": False,
                "creativeTaste": False,
                "authoritySource": "crs_temporal",
            },
            "crossModality": {
                "primaryMiss": True,
                "contradictingModality": True,
                "law": "ABSENCE_OF_EVIDENCE_NEQ_EVIDENCE_OF_ABSENCE",
            },
        }
        return {
            "kind": CONTINUITY_QC_KIND,
            "verdict": QC_UNCERTAIN,
            "reason": "CONTINUITY_CRS_TEMPORAL_CONFLICT",
            "sceneFinishedEligible": False,
            "findings": [finding],
            "continuityFindings": [finding],
            "authority": auth,
            "observed": {
                "summary": obs.get("summary"),
                "continuityFlags": flags,
                "availability": availability,
                "confidence": conf_f,
                "role": "observation_only",
            },
            "temporalCorroboration": temporal,
            "createdAt": _now(),
        }

    hard_codes: list[str] = []
    for flag in flags:
        code = _classify_flag(flag)
        if code:
            hard_codes.append(code)
            high = not weak_visual and (conf_f is None or conf_f >= 0.55)
            findings.append(
                {
                    "code": code,
                    "severity": "error",
                    "confidence": "high" if high else "low",
                    "message": str(flag),
                    "establishedAuthority": True,
                    "vsCanon": True,
                    "authoritySource": auth.get("authoritySource") or "continuity_canon",
                    "finalCheck": {
                        "retakeEligible": bool(high),
                        "autoDestroy": False,
                        "acceptanceEligible": False,
                        "creativeTaste": False,
                        "authoritySource": auth.get("authoritySource") or "continuity_canon",
                    },
                }
            )

    if weak_visual and findings:
        for f in findings:
            f["confidence"] = "low"
            f["weakVisual"] = True
            f["finalCheck"] = {
                **(f.get("finalCheck") or {}),
                "retakeEligible": False,
                "autoDestroy": False,
            }
        return {
            "kind": CONTINUITY_QC_KIND,
            "verdict": QC_UNCERTAIN,
            "reason": "CONTINUITY_WEAK_VISUAL",
            "sceneFinishedEligible": False,
            "findings": findings,
            "continuityFindings": findings,
            "authority": auth,
            "observed": {
                "summary": obs.get("summary"),
                "continuityFlags": flags,
                "availability": availability,
                "confidence": conf_f,
                "role": "observation_only",
            },
            "temporalCorroboration": temporal,
            "createdAt": _now(),
        }

    if findings:
        return {
            "kind": CONTINUITY_QC_KIND,
            "verdict": QC_FAIL,
            "reason": hard_codes[0] if hard_codes else "CONTINUITY_BREAK",
            "sceneFinishedEligible": False,
            "findings": findings,
            "continuityFindings": findings,
            "authority": auth,
            "observed": {
                "summary": obs.get("summary"),
                "continuityFlags": flags,
                "availability": availability,
                "confidence": conf_f,
                "role": "observation_only",
            },
            "temporalCorroboration": temporal,
            "createdAt": _now(),
        }

    # No continuity breaks observed — gate ran (PASS). Empty flags ≠ invent PASS from missing gate.
    return {
        "kind": CONTINUITY_QC_KIND,
        "verdict": QC_PASS,
        "reason": None,
        "sceneFinishedEligible": True,
        "findings": [],
        "continuityFindings": [],
        "authority": auth,
        "observed": {
            "summary": obs.get("summary"),
            "continuityFlags": [],
            "availability": availability,
            "confidence": conf_f,
            "role": "observation_only",
        },
        "temporalCorroboration": temporal,
        "createdAt": _now(),
        "note": "Omni continuity gate: no breaks.",
    }


def find_temporal_packet_for_batch(master: Any, batch_id: str) -> Any | None:
    """Best-effort JEPA/temporal continuity packet for corroboration (T3 path).

    REBUILD LAW: reads the ONE canonical packet store — ``master.temporalPackets``
    (the attribute the packet service persists). The former implementation read
    a nonexistent ``temporalContinuityPackets`` attribute and a bridge key
    (``temporalPacket``) that ``_persist`` never writes (it writes
    ``temporalPacketId``), so cross-modality corroboration was silently dead
    in production.
    """
    if master is None:
        return None
    packets = getattr(master, "temporalPackets", None) or []
    if isinstance(master, dict):
        packets = master.get("temporalPackets") or []
    by_id: dict[str, Any] = {}
    for p in packets:
        dump = p.model_dump() if hasattr(p, "model_dump") else (p if isinstance(p, dict) else {})
        packet_id = str(dump.get("packetId") or "")
        if packet_id:
            by_id[packet_id] = p
        src = dump.get("source") or {}
        if isinstance(src, dict) and str(src.get("batchId") or "") == str(batch_id):
            return p
        if str(dump.get("batchId") or "") == str(batch_id):
            return p
    # Bridge continuityState stashes the packet ID — resolve it against the
    # canonical packet store (observation only, never sole authority).
    for bridge in getattr(master, "continuityBridges", None) or []:
        st = getattr(bridge, "continuityState", None) or (
            bridge.get("continuityState") if isinstance(bridge, dict) else None
        )
        if isinstance(st, dict):
            packet_ref = str(st.get("temporalPacketId") or "")
            if packet_ref and packet_ref in by_id:
                return by_id[packet_ref]
    return None


def prior_batch_for(master: Any, batch: Any) -> Any | None:
    if master is None or batch is None:
        return None
    batches = list(getattr(master, "batchBlocks", None) or [])
    bid = str(getattr(batch, "id", "") or "")
    ordered = sorted(
        batches,
        key=lambda b: float(getattr(getattr(b, "duration", None), "timelineStart", 0) or 0)
        if hasattr(b, "duration")
        else 0.0,
    )
    prev = None
    for b in ordered:
        if str(getattr(b, "id", "")) == bid:
            return prev
        prev = b
    # Fallback: order field
    try:
        cur_order = int(getattr(batch, "order", 0) or 0)
    except (TypeError, ValueError):
        cur_order = 0
    candidates = [
        b
        for b in batches
        if int(getattr(b, "order", 0) or 0) < cur_order
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda b: int(getattr(b, "order", 0) or 0))


def run_omni_continuity_qc(
    db: Any,
    *,
    project_id: str,
    scene_id: str,
    asset_id: str,
    batch: Any,
    master: Any = None,
    force: bool = True,
    timeout_sec: float = 180.0,
    observed_packet: Any = None,
) -> dict[str, Any]:
    """Invoke Adept Omni visual analyze and evaluate vs Narrative continuity authority."""
    prior = prior_batch_for(master, batch) if master is not None else None
    temporal = find_temporal_packet_for_batch(master, str(getattr(batch, "id", "") or "")) if master else None
    authority = narrative_continuity_authority(
        batch, master=master, prior_batch=prior, temporal_packet=temporal
    )
    observed: dict[str, Any]
    try:
        from app.codirector.video_intelligence.media_analyze import analyze_asset

        packet = observed_packet if observed_packet is not None else analyze_asset(
            db,
            project_id,
            asset_id,
            mode="summary",
            question=CONTINUITY_ANALYZE_QUESTION,
            scene_id=scene_id,
            force=force,
            persist=True,
            timeout_sec=timeout_sec,
        )
        # WAVE 6.1: CD VerifiedContinuityMemory after live Omni continuity Perception.
        # parseOk=false / UNCERTAIN/REJECTED never canon. No Take DB writes.
        try:
            from app.codirector.verified_continuity_memory import (
                continuity_advance_allowed,
                record_verified_continuity_from_packet,
            )

            # P6 hygiene: halt VCM while dialogue QC pending/retry/content-fail.
            if continuity_advance_allowed(batch=batch):
                record_verified_continuity_from_packet(
                    packet,
                    project_id=project_id,
                    scene_id=scene_id,
                    batch=batch,
                    master=master,
                )
        except Exception:
            pass
        observed = extract_continuity_observations(packet)
    except Exception as exc:  # noqa: BLE001
        observed = {
            "summary": "",
            "visualEvents": [],
            "sceneChanges": [],
            "characters": [],
            "environment": {},
            "continuityFlags": [],
            "availability": "unavailable",
            "error": str(exc),
            "role": "observation_only",
        }

    prior_obs = None
    # Adjacent-shot: only use prior QC summary if already on prior batch refs (no second Omni call here).
    if prior is not None:
        for r in getattr(prior, "references", None) or []:
            if isinstance(r, dict) and r.get("kind") in CONTINUITY_QC_KINDS:
                prior_obs = (r.get("observed") if isinstance(r.get("observed"), dict) else None) or {
                    "summary": (r.get("observed") or {}).get("summary") if isinstance(r.get("observed"), dict) else ""
                }
                break

    return evaluate_continuity_qc(
        authority,
        observed,
        prior_observed=prior_obs,
        temporal_packet=temporal,
    )


def persist_continuity_qc_diagnostics(batch: Any, qc: dict[str, Any]) -> None:
    """Attach omniContinuityDiagnostics onto batch.references (replace prior same kind)."""
    packet = dict(qc)
    packet["kind"] = CONTINUITY_QC_KIND
    refs = [
        r
        for r in (getattr(batch, "references", None) or [])
        if not (isinstance(r, dict) and r.get("kind") in CONTINUITY_QC_KINDS)
    ]
    refs.append(packet)
    batch.references = refs