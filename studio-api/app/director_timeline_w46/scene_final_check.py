"""Co-Director Final Check — scene lifecycle authority + repair gates.

Extends (does not replace) scene_render_progress / current_take / SceneStatusStrip.
Dialogue Authority owns dialogue/language/speaker Hard classifiers — we consume
QC findings; we do not invent a parallel dialogue classifier or touch Omni ASR.

Inventory #4 Continuity + #5 Unauthorized Production Equipment: Final Check
category pipelines + eligibility. Omni Continuity gate (if present) is ingested;
equipment AUTHORITY = retake_context_package prompt-law crew-out (ONE authority).
Never invent continuity from bad frames. Creative camera taste never auto.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from .contracts import _now

# ---------------------------------------------------------------------------
# Canonical scene lifecycle (ONE authority for Final Check / finish law)
# ---------------------------------------------------------------------------

SceneLifecycleStatus = Literal[
    "RENDERING",
    "BATCHES_COMPLETE",
    "STITCHING",
    "FINAL_CHECK",
    "REPAIRING",
    "REVERIFYING",
    "SCENE_FINISHED",
    "SCENE_FINISHED_WITH_ACCEPTED_ISSUES",
    "SCENE_NOT_FINISHED",
]

LIFECYCLE_STATES: tuple[str, ...] = (
    "RENDERING",
    "BATCHES_COMPLETE",
    "STITCHING",
    "FINAL_CHECK",
    "REPAIRING",
    "REVERIFYING",
    "SCENE_FINISHED",
    "SCENE_FINISHED_WITH_ACCEPTED_ISSUES",
    "SCENE_NOT_FINISHED",
)

VERDICT_PASSED = "FINAL CHECK PASSED / SCENE FINISHED"
VERDICT_FOUND_ISSUES = "FOUND ISSUES / SCENE NOT FINISHED"
VERDICT_ACCEPTED = "SCENE FINISHED ISSUES ACCEPTED BY CREATOR"

FINAL_CHECK_CATEGORIES: tuple[str, ...] = (
    "dialogue",
    "language",
    "speaker",
    "identity",
    "environment",
    "continuity",
    "camera",
    "equipment",
    "audio",
    "technical",
)

DIALOGUE_OWNED_CATEGORIES = frozenset({"dialogue", "language", "speaker"})
PIPELINE_CATEGORIES = frozenset({"continuity", "camera", "equipment", "audio"})
STUB_CATEGORIES = frozenset({"identity", "environment", "technical"})

Taxonomy = Literal["Hard", "Soft", "Creative"]

DA_HARD_CODES = frozenset(
    {
        "WRONG_LANGUAGE",
        "WRONG_SPEAKER",
        "ADLIB_OR_NONLITERAL",
        "LINE_FIDELITY_FAIL",
        "SILENT_WHEN_SPEECH_EXPECTED",
        "SPEECH_WHEN_SILENCE_EXPECTED",
        "UNAUTHORIZED_BACKGROUND_SPEAKER",
        "OMNI_TRANSCRIPT_MISS",
        "MODALITY_CONFLICT",
        "SPOKEN_LANGUAGE_AUTHORITY_MISSING",
        "UNAUTHORIZED_LANGUAGE",
    }
)

DA_NO_AUTO_RETAKE_CODES = frozenset(
    {
        "OMNI_TRANSCRIPT_MISS",
        "MODALITY_CONFLICT",
        "OMNI_UNAVAILABLE",
        "OBSERVED_LANGUAGE_UNKNOWN",
    }
)

DA_CODE_TO_CATEGORY = {
    "WRONG_LANGUAGE": "language",
    "UNAUTHORIZED_LANGUAGE": "language",
    "SPOKEN_LANGUAGE_AUTHORITY_MISSING": "language",
    "OBSERVED_LANGUAGE_UNKNOWN": "language",
    "WRONG_SPEAKER": "speaker",
    "UNAUTHORIZED_BACKGROUND_SPEAKER": "speaker",
    "ADLIB_OR_NONLITERAL": "dialogue",
    "LINE_FIDELITY_FAIL": "dialogue",
    "SILENT_WHEN_SPEECH_EXPECTED": "dialogue",
    "SPEECH_WHEN_SILENCE_EXPECTED": "dialogue",
    "OMNI_TRANSCRIPT_MISS": "dialogue",
    "OMNI_UNAVAILABLE": "dialogue",
    "MODALITY_CONFLICT": "dialogue",
}

CONTINUITY_HARD_CODES = frozenset(
    {
        "CONTINUITY_BREAK",
        "CONTINUITY_TELEPORT",
        "CONTINUITY_SIDES_FLIP",
        "CONTINUITY_WARDROBE",
        "CONTINUITY_ENV_VS_CANON",
        "CONTINUITY_AUTHORITY_VIOLATION",
    }
)

CONTINUITY_UNCERTAIN_CODES = frozenset(
    {
        "CONTINUITY_UNCERTAIN",
        "CONTINUITY_WEAK_VISUAL",
        "CONTINUITY_CRS_TEMPORAL_CONFLICT",
        "IDENTITY_UNCERTAIN_CRS_CONFLICT",
    }
)

EQUIPMENT_HARD_CODES = frozenset(
    {
        "UNAUTHORIZED_PRODUCTION_EQUIPMENT",
        "DIEGETIC_CREW",
        "BOOM_IN_FRAME",
        "CAMERA_CREW_IN_FRAME",
        "CREW_IN_FRAME",
    }
)

CAMERA_CREATIVE_CODES = frozenset(
    {
        "CREATIVE_CAMERA_TASTE",
        "CREATIVE_PUSH_IN",
        "CREATIVE_GRADE",
        "CREATIVE_FRAMING_SUGGESTION",
    }
)

RuntimeKind = Literal["local", "api"]
RepairPermission = Literal[
    "not_required",
    "required",
    "granted",
    "declined",
    "keep_current",
]

DEFAULT_MAX_RETAKE_LOOPS = 3
CROSS_MODALITY_LAW_ID = "ABSENCE_OF_EVIDENCE_NEQ_EVIDENCE_OF_ABSENCE"


def is_local_runtime(
    *,
    locality: str | None = None,
    execution_type: str | None = None,
    capability: Any = None,
) -> bool:
    """Classify local vs metered API via capability/provider — not name string checks."""
    if capability is not None:
        loc = str(getattr(capability, "locality", None) or "").strip().lower()
        if loc == "local":
            return True
        if loc == "hosted":
            return False
        exec_t = str(
            getattr(capability, "executionType", None)
            or getattr(capability, "execution_type", None)
            or ""
        ).strip().lower()
        if exec_t == "api":
            return False
        if exec_t in ("local", "comfy", "comfyui"):
            return True
    loc = str(locality or "").strip().lower()
    if loc == "local":
        return True
    if loc in ("hosted", "api", "cloud"):
        return False
    exec_t = str(execution_type or "").strip().lower()
    if exec_t == "api":
        return False
    if exec_t in ("local", "comfy", "comfyui"):
        return True
    return False


def resolve_generator_capability(generator_id: str | None) -> Any | None:
    """Look up VideoGeneratorCapabilities via registry — locality from executionType.

    Does not string-match generator names. Unknown ids return None (caller defaults api).
    """
    gid = str(generator_id or "").strip()
    if not gid:
        return None
    try:
        from .generation.registry import get_registry

        return get_registry().capabilities(gid)
    except Exception:
        return None


def classify_runtime_kind(
    *,
    locality: str | None = None,
    execution_type: str | None = None,
    capability: Any = None,
    generator_id: str | None = None,
    adapter_profile: dict[str, Any] | None = None,
) -> RuntimeKind:
    """Return 'local' | 'api'. Adapter/profile may map Seedance→API, H3/LTX→local.

    When capability/locality omitted, resolve capability from generator registry
    (executionType local|api) so stitch/open/decision do not default H3/LTX to api.
    """
    if adapter_profile:
        mapped = adapter_profile.get("runtimeKind") or adapter_profile.get("repairRuntime")
        if mapped in ("local", "api"):
            return mapped  # type: ignore[return-value]
        if "locality" in adapter_profile:
            locality = str(adapter_profile.get("locality") or locality)
        if "executionType" in adapter_profile:
            execution_type = str(adapter_profile.get("executionType") or execution_type)
    if capability is None and generator_id:
        capability = resolve_generator_capability(generator_id)
    if is_local_runtime(locality=locality, execution_type=execution_type, capability=capability):
        return "local"
    if adapter_profile and generator_id:
        by_id = adapter_profile.get("byGeneratorId") or {}
        entry = by_id.get(generator_id) if isinstance(by_id, dict) else None
        if isinstance(entry, dict) and entry.get("runtimeKind") in ("local", "api"):
            return entry["runtimeKind"]
    # Hosted/API capability (executionType=api) or unknown → api ask-once
    if capability is not None and not is_local_runtime(capability=capability):
        return "api"
    return "api"



def empty_stub_category(category: str) -> dict[str, Any]:
    """Honest not-run stub — never fake PASS."""
    return {
        "category": category,
        "status": "not_run",
        "taxonomy": None,
        "findings": [],
        "source": "stub",
        "note": "Category not owned by Omni Dialogue QC yet — not run (not PASS).",
    }


def empty_pipeline_not_run(category: str, *, note: str) -> dict[str, Any]:
    """Pipeline wired but no Omni packet this scene — honest not_run (not PASS)."""
    return {
        "category": category,
        "status": "not_run",
        "taxonomy": None,
        "findings": [],
        "source": "pipeline_ready",
        "note": note,
    }


def map_dialogue_finding(finding: dict[str, Any], *, verdict: str | None = None) -> dict[str, Any]:
    """Map a Dialogue Authority QC finding into Final Check shape.

    Eligibility authority = findings[].finalCheck sidecar (Dialogue Authority).
    Do NOT re-derive retakeEligible from codes when sidecar is present.
    Slice B: SPEECH_WHEN_SILENCE_EXPECTED / UNAUTHORIZED_BACKGROUND_SPEAKER /
    MODALITY_CONFLICT consumed via sidecar (+ modalityConflict fields).
    """
    code = str(finding.get("code") or "").strip()
    severity = str(finding.get("severity") or "").strip().lower()
    sidecar = finding.get("finalCheck") if isinstance(finding.get("finalCheck"), dict) else None

    category = DA_CODE_TO_CATEGORY.get(code, "dialogue")
    is_hard = severity == "error" or code in DA_HARD_CODES

    taxonomy: Taxonomy = "Hard" if is_hard else "Soft"
    if finding.get("taxonomy") in ("Hard", "Soft", "Creative"):
        taxonomy = finding["taxonomy"]  # type: ignore[assignment]
    if finding.get("creative") is True or (sidecar and sidecar.get("creativeTaste") is True):
        taxonomy = "Creative"

    confidence_raw = str(finding.get("confidence") or "").strip().lower()
    if confidence_raw in ("high", "low"):
        confidence = confidence_raw
    elif code in DA_NO_AUTO_RETAKE_CODES or str(verdict or "").upper() == "UNCERTAIN":
        confidence = "low"
    elif sidecar and sidecar.get("retakeEligible") is False and sidecar.get("acceptanceEligible") is False:
        if code in DA_NO_AUTO_RETAKE_CODES:
            confidence = "low"
        else:
            confidence = "high"
    else:
        confidence = "high"

    if code in {"MODALITY_CONFLICT", "OMNI_TRANSCRIPT_MISS"}:
        confidence = "low"
        if str(verdict or "").upper() != "FAIL":
            taxonomy = "Hard"

    if sidecar is not None:
        retake_eligible = bool(sidecar.get("retakeEligible"))
        auto_destroy = bool(sidecar.get("autoDestroy", False))
        acceptance_eligible = bool(sidecar.get("acceptanceEligible", False))
        creative_taste = bool(sidecar.get("creativeTaste", False))
        authority_source = str(sidecar.get("authoritySource") or "dialogue_manifest")
        if creative_taste:
            taxonomy = "Creative"
            retake_eligible = False
    else:
        explicit = finding.get("retakeEligible")
        if explicit is not None:
            retake_eligible = bool(explicit)
        elif taxonomy == "Creative" or code in DA_NO_AUTO_RETAKE_CODES or confidence != "high":
            retake_eligible = False
        elif str(verdict or "").upper() == "UNCERTAIN":
            retake_eligible = False
        else:
            retake_eligible = is_hard and taxonomy == "Hard"
        auto_destroy = False
        acceptance_eligible = False
        creative_taste = taxonomy == "Creative"
        authority_source = "dialogue_manifest"

    out: dict[str, Any] = {
        "category": category,
        "taxonomy": taxonomy,
        "code": code or None,
        "severity": finding.get("severity") or ("error" if is_hard else "warning"),
        "retakeEligible": retake_eligible,
        "autoDestroy": auto_destroy,
        "acceptanceEligible": acceptance_eligible,
        "creativeTaste": creative_taste,
        "authoritySource": authority_source,
        "confidence": confidence,
        "message": finding.get("message") or finding.get("reason"),
        "source": "dialogueQcDiagnostics",
        "finalCheck": dict(sidecar)
        if sidecar
        else {
            "retakeEligible": retake_eligible,
            "autoDestroy": auto_destroy,
            "acceptanceEligible": acceptance_eligible,
            "creativeTaste": creative_taste,
            "authoritySource": authority_source,
        },
    }

    fc = out["finalCheck"]
    if sidecar:
        if "modalityConflict" in sidecar:
            fc["modalityConflict"] = bool(sidecar.get("modalityConflict"))
            out["modalityConflict"] = bool(sidecar.get("modalityConflict"))
        if sidecar.get("modalities") is not None:
            fc["modalities"] = list(sidecar.get("modalities") or [])
            out["modalities"] = list(sidecar.get("modalities") or [])
        if sidecar.get("conflictReason"):
            fc["conflictReason"] = str(sidecar.get("conflictReason"))
            out["conflictReason"] = str(sidecar.get("conflictReason"))
    if finding.get("crossModalityContradiction") or finding.get("loudEnergyWithEmptyTranscript"):
        out["crossModalityContradiction"] = True
    if isinstance(finding.get("crossModality"), dict):
        out["crossModality"] = dict(finding["crossModality"])

    if code in {"UNAUTHORIZED_BACKGROUND_SPEAKER", "WRONG_SPEAKER"}:
        out["alsoCategories"] = ["dialogue"]

    if (
        code in {"MODALITY_CONFLICT", "OMNI_TRANSCRIPT_MISS"}
        or out.get("modalityConflict")
        or (sidecar and sidecar.get("modalityConflict"))
    ):
        also = list(out.get("alsoCategories") or [])
        if "audio" not in also:
            also.append("audio")
        out["alsoCategories"] = also

    return out


def ingest_dialogue_qc(qc: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Consume Dialogue Authority QC packet → Final Check findings (no rewrite)."""
    if not qc or not isinstance(qc, dict):
        return []
    verdict = str(qc.get("verdict") or "").upper()
    out: list[dict[str, Any]] = []
    for finding in qc.get("findings") or []:
        if isinstance(finding, dict):
            out.append(map_dialogue_finding(finding, verdict=verdict))
    if not out and verdict in ("FAIL", "UNCERTAIN"):
        code = str(qc.get("reason") or qc.get("code") or "DIALOGUE_QC_FAIL").strip()
        synthetic = {
            "code": code,
            "severity": "error",
            "message": qc.get("message") or qc.get("reason") or code,
            "confidence": "low" if verdict == "UNCERTAIN" or code in DA_NO_AUTO_RETAKE_CODES else "high",
            "retakeEligible": False
            if verdict == "UNCERTAIN" or code in DA_NO_AUTO_RETAKE_CODES
            else True,
        }
        out.append(map_dialogue_finding(synthetic, verdict=verdict))
    return out


def map_continuity_finding(finding: dict[str, Any], *, verdict: str | None = None) -> dict[str, Any]:
    """Map Omni continuity / CRS finding into Final Check continuity category.

    Hard continuity break retakeEligible only when high-conf AND established
    authority (teleport/sides/wardrobe/env vs canon). Never invent continuity
    from bad frames. Uncertain visual + CRS/temporal conflict → escalate,
    no auto-regenerate.
    """
    code = str(finding.get("code") or "").strip().upper()
    sidecar = finding.get("finalCheck") if isinstance(finding.get("finalCheck"), dict) else None
    severity = str(finding.get("severity") or "").strip().lower()
    conf_raw = str(finding.get("confidence") or "").strip().lower()

    established = bool(
        finding.get("establishedAuthority")
        or finding.get("vsCanon")
        or (
            sidecar
            and sidecar.get("authoritySource")
            in {
                "continuity_canon",
                "crs_temporal",
                "scene_canon",
                "wardrobe_canon",
                "sides_canon",
            }
        )
    )
    invented = bool(finding.get("inventedFromBadFrame") or finding.get("fromBadFrame"))
    uncertain_class = (
        code in CONTINUITY_UNCERTAIN_CODES
        or conf_raw == "low"
        or str(verdict or "").upper() == "UNCERTAIN"
        or bool(finding.get("weakVisual"))
        or invented
    )

    if code in CAMERA_CREATIVE_CODES or finding.get("creative") is True:
        taxonomy: Taxonomy = "Creative"
    elif code in CONTINUITY_HARD_CODES or severity == "error":
        taxonomy = "Hard"
    else:
        taxonomy = "Soft"

    if uncertain_class:
        confidence = "low"
        retake_eligible = False
        if sidecar is not None and "retakeEligible" in sidecar:
            retake_eligible = bool(sidecar.get("retakeEligible"))
    elif sidecar is not None:
        confidence = conf_raw if conf_raw in ("high", "low") else "high"
        retake_eligible = bool(sidecar.get("retakeEligible"))
    else:
        confidence = conf_raw if conf_raw in ("high", "low") else ("high" if established and not invented else "low")
        retake_eligible = (
            taxonomy == "Hard"
            and confidence == "high"
            and established
            and not invented
            and not uncertain_class
        )

    if invented:
        retake_eligible = False
        confidence = "low"
        taxonomy = "Hard"

    auto_destroy = bool(sidecar.get("autoDestroy") if sidecar else False)
    acceptance_eligible = bool(sidecar.get("acceptanceEligible") if sidecar else False)
    creative_taste = taxonomy == "Creative" or bool(sidecar.get("creativeTaste") if sidecar else False)
    if creative_taste:
        retake_eligible = False
        taxonomy = "Creative"

    authority_source = str(
        (sidecar or {}).get("authoritySource")
        or finding.get("authoritySource")
        or ("continuity_canon" if established else "omni_continuity")
    )

    out = {
        "category": "continuity",
        "taxonomy": taxonomy,
        "code": code or "CONTINUITY_BREAK",
        "severity": finding.get("severity") or ("error" if taxonomy == "Hard" else "warning"),
        "retakeEligible": retake_eligible,
        "autoDestroy": auto_destroy,
        "acceptanceEligible": acceptance_eligible,
        "creativeTaste": creative_taste,
        "authoritySource": authority_source,
        "confidence": confidence,
        "message": finding.get("message") or finding.get("reason"),
        "source": finding.get("source") or "omniContinuityDiagnostics",
        "establishedAuthority": established,
        "neverInventFromBadFrame": True,
        "finalCheck": dict(sidecar)
        if sidecar
        else {
            "retakeEligible": retake_eligible,
            "autoDestroy": auto_destroy,
            "acceptanceEligible": acceptance_eligible,
            "creativeTaste": creative_taste,
            "authoritySource": authority_source,
        },
    }
    if uncertain_class or finding.get("crossModality"):
        out["crossModality"] = finding.get("crossModality") or {
            "primaryMiss": True,
            "contradictingModality": bool(
                finding.get("crsTemporalConflict") or code in CONTINUITY_UNCERTAIN_CODES
            ),
        }
    return out


def ingest_continuity_qc(qc: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Ingest Omni continuity findings when present. Empty → caller keeps not_run."""
    if not qc or not isinstance(qc, dict):
        return []
    verdict = str(qc.get("verdict") or "").upper()
    out: list[dict[str, Any]] = []
    findings = qc.get("findings") or qc.get("continuityFindings") or []
    for finding in findings:
        if isinstance(finding, dict):
            out.append(map_continuity_finding(finding, verdict=verdict))
    if not out and str(qc.get("status") or "").lower() == "pass" and verdict in ("", "PASS", "OK"):
        return []
    if not out and verdict in ("FAIL", "UNCERTAIN"):
        out.append(
            map_continuity_finding(
                {
                    "code": str(qc.get("reason") or qc.get("code") or "CONTINUITY_BREAK"),
                    "severity": "error",
                    "confidence": "low" if verdict == "UNCERTAIN" else str(qc.get("confidence") or "high"),
                    "message": qc.get("message") or qc.get("reason"),
                    "establishedAuthority": bool(qc.get("establishedAuthority")),
                    "finalCheck": qc.get("finalCheck") if isinstance(qc.get("finalCheck"), dict) else None,
                },
                verdict=verdict,
            )
        )
    return out


def equipment_authority_packet() -> dict[str, Any]:
    """ONE unauthorized-equipment AUTHORITY — retake_context_package prompt-law."""
    try:
        from .generation.retake_context_package import unauthorized_equipment_authority

        return unauthorized_equipment_authority()
    except Exception:
        return {
            "authoritySource": "retake_context_package.prompt_law_crew_out",
            "code": "UNAUTHORIZED_PRODUCTION_EQUIPMENT",
            "exclusions": [
                "film crew",
                "documentary crew",
                "interviewer",
                "camera operators",
                "camera crew",
                "boom mic operator",
                "crew in frame",
                "wide establishing interview set with crew",
            ],
            "taxonomy": "Hard",
            "neverInventFromBadOutput": True,
        }


def map_equipment_finding(finding: dict[str, Any], *, verdict: str | None = None) -> dict[str, Any]:
    """Map Omni visual / equipment observation → camera + equipment Hard.

    AUTHORITY = retake_context_package prompt-law crew-out (12B textbook).
    Hard+high-conf → local auto Re-Take; API ask once. Creative camera never auto.
    """
    auth = equipment_authority_packet()
    code = str(finding.get("code") or "").strip().upper() or str(
        auth.get("code") or "UNAUTHORIZED_PRODUCTION_EQUIPMENT"
    )
    sidecar = finding.get("finalCheck") if isinstance(finding.get("finalCheck"), dict) else None
    msg = str(finding.get("message") or finding.get("reason") or finding.get("observation") or "")

    if code in CAMERA_CREATIVE_CODES or finding.get("creative") is True or finding.get("creativeTaste") is True:
        return {
            "category": "camera",
            "taxonomy": "Creative",
            "code": code,
            "severity": "info",
            "retakeEligible": False,
            "autoDestroy": False,
            "acceptanceEligible": True,
            "creativeTaste": True,
            "authoritySource": "creative_suggestion",
            "confidence": "high",
            "message": msg or "Creative camera suggestion — surface only",
            "source": finding.get("source") or "omniEquipmentDiagnostics",
            "alsoCategories": [],
            "finalCheck": {
                "retakeEligible": False,
                "autoDestroy": False,
                "acceptanceEligible": True,
                "creativeTaste": True,
                "authoritySource": "creative_suggestion",
            },
        }

    # ONE authority disposition (12B): in-frame Hard vs off-screen authorized vs uncertain.
    # Producer evaluate() already applied context (summary+flags); trust sidecar when present.
    disposition = "none"
    try:
        from .generation.retake_context_package import (
            CREW_OBSERVATION_AUTHORIZED_OFFSCREEN,
            CREW_OBSERVATION_HARD,
            CREW_OBSERVATION_UNCERTAIN,
            classify_crew_equipment_observation,
            observation_matches_unauthorized_equipment,
        )

        disposition = classify_crew_equipment_observation(msg)
        matches = disposition == CREW_OBSERVATION_HARD or observation_matches_unauthorized_equipment(code)
    except Exception:
        CREW_OBSERVATION_HARD = "hard"
        CREW_OBSERVATION_AUTHORIZED_OFFSCREEN = "authorized_offscreen"
        CREW_OBSERVATION_UNCERTAIN = "uncertain"
        matches = any(lab in msg.lower() for lab in (auth.get("exclusions") or [])) or code in EQUIPMENT_HARD_CODES

    EQUIPMENT_NON_HARD_CODES = {
        "CREW_OBSERVATION_UNCERTAIN",
        "CREW_OFFSCREEN_AUTHORIZED",
        "CREW_FRAMING_UNCERTAIN",
        "OMNI_EQUIPMENT_UNAVAILABLE",
    }

    producer_hard = (
        sidecar is not None
        and bool(sidecar.get("retakeEligible"))
        and code in EQUIPMENT_HARD_CODES
    )

    if code in EQUIPMENT_NON_HARD_CODES or disposition == CREW_OBSERVATION_AUTHORIZED_OFFSCREEN:
        matches = False
    elif producer_hard:
        matches = True
    elif code not in EQUIPMENT_HARD_CODES and matches:
        code = "UNAUTHORIZED_PRODUCTION_EQUIPMENT"
    elif (
        code in EQUIPMENT_HARD_CODES
        and disposition == CREW_OBSERVATION_UNCERTAIN
        and sidecar is None
    ):
        # Legacy coarse CREW_IN_FRAME + bare "interviewer" without producer sidecar → review.
        matches = False
        code = "CREW_OBSERVATION_UNCERTAIN"

    conf_raw = str(finding.get("confidence") or "").strip().lower()
    confidence = conf_raw if conf_raw in ("high", "low") else "high"
    taxonomy: Taxonomy = "Hard"
    if not producer_hard and (
        code in EQUIPMENT_NON_HARD_CODES
        or disposition
        in {
            CREW_OBSERVATION_UNCERTAIN,
            CREW_OBSERVATION_AUTHORIZED_OFFSCREEN,
        }
    ):
        taxonomy = "Soft"
        confidence = "low" if disposition != CREW_OBSERVATION_AUTHORIZED_OFFSCREEN else confidence

    if sidecar is not None:
        retake_eligible = bool(sidecar.get("retakeEligible"))
        auto_destroy = bool(sidecar.get("autoDestroy", False))
        acceptance_eligible = bool(sidecar.get("acceptanceEligible", False))
        creative_taste = bool(sidecar.get("creativeTaste", False))
        authority_source = str(sidecar.get("authoritySource") or auth.get("authoritySource"))
    else:
        retake_eligible = taxonomy == "Hard" and confidence == "high" and (
            matches or code in EQUIPMENT_HARD_CODES
        )
        auto_destroy = False
        acceptance_eligible = disposition == CREW_OBSERVATION_AUTHORIZED_OFFSCREEN
        creative_taste = False
        authority_source = str(auth.get("authoritySource"))

    if confidence == "low" or str(verdict or "").upper() == "UNCERTAIN":
        retake_eligible = False
        if disposition != CREW_OBSERVATION_AUTHORIZED_OFFSCREEN:
            confidence = "low"
    elif not producer_hard and (
        disposition == CREW_OBSERVATION_UNCERTAIN or code in EQUIPMENT_NON_HARD_CODES
    ):
        retake_eligible = False
        confidence = "low"

    return {
        "category": "equipment",
        "taxonomy": taxonomy,
        "code": code,
        "severity": finding.get("severity") or "error",
        "retakeEligible": retake_eligible,
        "autoDestroy": auto_destroy,
        "acceptanceEligible": acceptance_eligible,
        "creativeTaste": creative_taste,
        "authoritySource": authority_source,
        "confidence": confidence,
        "message": msg or "Unauthorized diegetic production equipment / crew in frame",
        "source": finding.get("source") or "omniEquipmentDiagnostics",
        "alsoCategories": ["camera"],
        "equipmentAuthority": auth.get("authoritySource"),
        "finalCheck": dict(sidecar)
        if sidecar
        else {
            "retakeEligible": retake_eligible,
            "autoDestroy": auto_destroy,
            "acceptanceEligible": acceptance_eligible,
            "creativeTaste": creative_taste,
            "authoritySource": authority_source,
        },
    }


def ingest_equipment_qc(qc: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Ingest Omni visual equipment / crew findings when present."""
    if not qc or not isinstance(qc, dict):
        return []
    verdict = str(qc.get("verdict") or "").upper()
    out: list[dict[str, Any]] = []
    findings = qc.get("findings") or qc.get("equipmentFindings") or []
    for finding in findings:
        if isinstance(finding, dict):
            out.append(map_equipment_finding(finding, verdict=verdict))
    if not out and verdict in ("FAIL", "UNCERTAIN"):
        out.append(
            map_equipment_finding(
                {
                    "code": str(qc.get("reason") or qc.get("code") or "UNAUTHORIZED_PRODUCTION_EQUIPMENT"),
                    "severity": "error",
                    "confidence": "low" if verdict == "UNCERTAIN" else str(qc.get("confidence") or "high"),
                    "message": qc.get("message") or qc.get("observation") or qc.get("reason"),
                    "finalCheck": qc.get("finalCheck") if isinstance(qc.get("finalCheck"), dict) else None,
                },
                verdict=verdict,
            )
        )
    return out


def collect_batch_qc_packets(master: Any) -> dict[str, Any]:
    """Gather dialogue / continuity / equipment QC refs from all batches."""
    dialogue: list[dict[str, Any]] = []
    continuity: list[dict[str, Any]] = []
    equipment: list[dict[str, Any]] = []
    continuity_gate_seen = False
    equipment_gate_seen = False
    for batch in list(getattr(master, "batchBlocks", None) or []):
        for ref in getattr(batch, "references", None) or []:
            if not isinstance(ref, dict):
                continue
            kind = str(ref.get("kind") or "")
            if kind == "dialogueQcDiagnostics":
                dialogue.extend(ingest_dialogue_qc(ref))
            elif kind in {"continuityQcDiagnostics", "omniContinuityDiagnostics", "omniContinuityQc"}:
                continuity_gate_seen = True
                continuity.extend(ingest_continuity_qc(ref))
            elif kind in {
                "equipmentQcDiagnostics",
                "omniEquipmentDiagnostics",
                "omniEquipmentQc",
                "omniVisualQc",
            }:
                equipment_gate_seen = True
                equipment.extend(ingest_equipment_qc(ref))
    return {
        "dialogue": dialogue,
        "continuity": continuity,
        "equipment": equipment,
        "continuityGateSeen": continuity_gate_seen,
        "equipmentGateSeen": equipment_gate_seen,
    }


def collect_batch_dialogue_qc(master: Any) -> list[dict[str, Any]]:
    """Gather dialogueQcDiagnostics refs from all batches (compat)."""
    return collect_batch_qc_packets(master)["dialogue"]


def _expand_also_categories(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Duplicate findings into alsoCategories (e.g. modality→audio, equipment→camera)."""
    expanded: list[dict[str, Any]] = list(findings)
    for f in findings:
        for also in f.get("alsoCategories") or []:
            mirror = dict(f)
            mirror["category"] = also
            mirror["mirroredFrom"] = f.get("category")
            expanded.append(mirror)
    return expanded


def _category_row_from_findings(
    cat: str,
    cat_findings: list[dict[str, Any]],
    *,
    source: str,
    empty_pass_note: str,
) -> dict[str, Any]:
    if not cat_findings:
        return {
            "category": cat,
            "status": "pass",
            "taxonomy": None,
            "findings": [],
            "source": source,
            "note": empty_pass_note,
        }
    has_fail = any(
        f.get("taxonomy") in ("Hard", "Soft") and f.get("severity") in ("error", "warning", "info")
        for f in cat_findings
        if f.get("taxonomy") != "Creative"
    )
    has_uncertain = any(
        f.get("confidence") == "low"
        or f.get("code") in DA_NO_AUTO_RETAKE_CODES
        or f.get("modalityConflict")
        or str(f.get("code") or "") in CONTINUITY_UNCERTAIN_CODES
        for f in cat_findings
    )
    hard_errors = [f for f in cat_findings if f.get("taxonomy") == "Hard" and f.get("severity") == "error"]
    if hard_errors and any(f.get("confidence") != "low" or f.get("retakeEligible") for f in hard_errors):
        status = "fail"
    elif has_uncertain and (not hard_errors or all(f.get("confidence") == "low" for f in hard_errors)):
        status = "uncertain"
    elif has_fail:
        status = "fail"
    else:
        status = "pass"
    if any(f.get("code") in {"MODALITY_CONFLICT", "OMNI_TRANSCRIPT_MISS"} for f in cat_findings):
        if not any(f.get("retakeEligible") and f.get("confidence") == "high" for f in cat_findings):
            status = "uncertain"
    return {
        "category": cat,
        "status": status,
        "taxonomy": "Hard" if any(f.get("taxonomy") == "Hard" for f in cat_findings) else "Soft",
        "findings": cat_findings,
        "source": source,
    }


def build_category_shell(
    findings: list[dict[str, Any]],
    *,
    continuity_gate_seen: bool = False,
    equipment_gate_seen: bool = False,
    continuity_findings: list[dict[str, Any]] | None = None,
    equipment_findings: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Checklist shell: DA slices + continuity/equipment/camera/audio pipelines + stubs."""
    all_findings = list(findings)
    if continuity_findings:
        all_findings.extend(continuity_findings)
    if equipment_findings:
        all_findings.extend(equipment_findings)
    all_findings = _expand_also_categories(all_findings)

    by_cat: dict[str, list[dict[str, Any]]] = {c: [] for c in FINAL_CHECK_CATEGORIES}
    for f in all_findings:
        cat = str(f.get("category") or "dialogue")
        if cat not in by_cat:
            cat = "dialogue"
        by_cat[cat].append(f)

    categories: list[dict[str, Any]] = []
    for cat in FINAL_CHECK_CATEGORIES:
        if cat in STUB_CATEGORIES:
            categories.append(empty_stub_category(cat))
            continue

        cat_findings = by_cat.get(cat) or []

        if cat == "continuity":
            if cat_findings:
                categories.append(
                    _category_row_from_findings(
                        cat,
                        cat_findings,
                        source="omniContinuityDiagnostics",
                        empty_pass_note="Omni continuity gate: no breaks.",
                    )
                )
            elif continuity_gate_seen:
                categories.append(
                    {
                        "category": cat,
                        "status": "pass",
                        "taxonomy": None,
                        "findings": [],
                        "source": "omniContinuityDiagnostics",
                        "note": "Omni continuity gate ran — no continuity findings.",
                    }
                )
            else:
                categories.append(
                    empty_pipeline_not_run(
                        cat,
                        note=(
                            "Continuity Final Check pipeline ready (eligibility + ingest). "
                            "No Omni continuity QC packet on this scene — not run (not PASS). "
                            "Never invent continuity from bad frames."
                        ),
                    )
                )
            continue

        if cat in {"equipment", "camera"}:
            if cat_findings:
                categories.append(
                    _category_row_from_findings(
                        cat,
                        cat_findings,
                        source="omniEquipmentDiagnostics",
                        empty_pass_note="No equipment/camera Hard findings.",
                    )
                )
            elif equipment_gate_seen:
                categories.append(
                    {
                        "category": cat,
                        "status": "pass",
                        "taxonomy": None,
                        "findings": [],
                        "source": "omniEquipmentDiagnostics",
                        "note": f"Omni equipment gate ran — no {cat} Hard findings.",
                    }
                )
            else:
                auth = equipment_authority_packet()
                categories.append(
                    empty_pipeline_not_run(
                        cat,
                        note=(
                            f"{cat.title()} pipeline ready. Authority={auth.get('authoritySource')}. "
                            "No Omni equipment/visual QC packet — not run (not PASS). "
                            "Diegetic crew/boom = Hard when high-conf vs prompt-law."
                        ),
                    )
                )
            continue

        if cat == "audio":
            if cat_findings:
                categories.append(
                    _category_row_from_findings(
                        cat,
                        cat_findings,
                        source="dialogueQcDiagnostics",
                        empty_pass_note="No audio modality conflicts.",
                    )
                )
            else:
                categories.append(
                    empty_pipeline_not_run(
                        cat,
                        note=(
                            "Audio category surfaces modality-conflict / energy contradiction "
                            "from Dialogue Authority sidecar. No conflict this scene — not run "
                            "(not a fake PASS on Music/SFX)."
                        ),
                    )
                )
            continue

        if not cat_findings:
            categories.append(
                {
                    "category": cat,
                    "status": "pass",
                    "taxonomy": None,
                    "findings": [],
                    "source": "dialogueQcDiagnostics",
                    "note": "No Dialogue Authority findings for this slice.",
                }
            )
            continue
        categories.append(
            _category_row_from_findings(
                cat,
                cat_findings,
                source="dialogueQcDiagnostics",
                empty_pass_note="No Dialogue Authority findings for this slice.",
            )
        )
    return categories


def blocking_hard_findings(categories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for cat in categories:
        for f in cat.get("findings") or []:
            if f.get("taxonomy") == "Hard":
                out.append(f)
            elif f.get("taxonomy") == "Soft" and f.get("autoRepair") is True:
                out.append(f)
    return out


def auto_repair_eligible_findings(categories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Hard eligible for auto Re-Take. Creative excluded. Never auto-destroy. Dedupes mirrors."""
    out: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for cat in categories:
        for f in cat.get("findings") or []:
            if f.get("taxonomy") == "Creative" or f.get("creativeTaste"):
                continue
            if f.get("autoDestroy"):
                continue
            if not f.get("retakeEligible"):
                continue
            conf = str(f.get("confidence") or "high").lower()
            if conf == "low":
                continue
            if f.get("mirroredFrom"):
                continue
            key = (f.get("code"), f.get("message"), f.get("category"))
            if key in seen:
                continue
            seen.add(key)
            if f.get("taxonomy") == "Hard" or f.get("autoRepair") is True or f.get("retakeEligible"):
                out.append(f)
    return out


def cross_modality_uncertainty(
    *,
    primary_miss: bool,
    contradicting_modality: bool,
    code: str | None = None,
) -> dict[str, Any]:
    """PRIMARY LAW (cross-modality): absence of evidence ≠ evidence of absence when contradicted."""
    code_u = str(code or "").strip().upper()
    if primary_miss and contradicting_modality:
        return {
            "uncertain": True,
            "autoRetake": False,
            "autoDestroy": False,
            "needsCreatorReview": True,
            "blocksFinished": True,
            "reason": (
                "Cross-modality contradiction: weak/single-modality miss is UNCERTAIN, "
                "not evidence of absence — creator review; never auto-destroy local gen"
            ),
            "codeHint": code_u or "OMNI_TRANSCRIPT_MISS",
            "law": CROSS_MODALITY_LAW_ID,
        }
    if primary_miss and not contradicting_modality:
        return {
            "uncertain": False,
            "autoRetake": None,
            "autoDestroy": False,
            "needsCreatorReview": False,
            "blocksFinished": True,
            "reason": "Single-modality miss without contradicting modality — defer to sidecar/Hard classifier",
            "law": CROSS_MODALITY_LAW_ID,
        }
    return {
        "uncertain": False,
        "autoRetake": None,
        "autoDestroy": False,
        "needsCreatorReview": False,
        "blocksFinished": False,
        "reason": "No cross-modality miss",
        "law": CROSS_MODALITY_LAW_ID,
    }


def qualify_retake(finding: dict[str, Any]) -> dict[str, Any]:
    """Retake Qualification Policy — architectural test. Sidecar is eligibility authority."""
    taxonomy = finding.get("taxonomy") or "Creative"
    confidence = str(finding.get("confidence") or "low").lower()
    code = str(finding.get("code") or "")
    sidecar = finding.get("finalCheck") if isinstance(finding.get("finalCheck"), dict) else None

    xm = finding.get("crossModality") if isinstance(finding.get("crossModality"), dict) else None
    if xm is None and (
        finding.get("crossModalityContradiction")
        or code in DA_NO_AUTO_RETAKE_CODES
        or code in CONTINUITY_UNCERTAIN_CODES
    ):
        xm_eval = cross_modality_uncertainty(
            primary_miss=True,
            contradicting_modality=bool(
                finding.get("crossModalityContradiction")
                or code in {"OMNI_TRANSCRIPT_MISS", "MODALITY_CONFLICT"}
                or finding.get("loudEnergyWithEmptyTranscript")
                or finding.get("modalityConflict")
                or code in CONTINUITY_UNCERTAIN_CODES
            ),
            code=code,
        )
        if xm_eval.get("uncertain"):
            return {
                "qualifies": False,
                "reason": xm_eval["reason"],
                "autoRetake": False,
                "needsCreatorReview": True,
                "blocksFinished": True,
                "autoDestroy": False,
                "crossModalityLaw": xm_eval.get("law"),
            }
    elif isinstance(xm, dict) and xm.get("primaryMiss") and xm.get("contradictingModality"):
        xm_eval = cross_modality_uncertainty(
            primary_miss=True,
            contradicting_modality=True,
            code=code,
        )
        return {
            "qualifies": False,
            "reason": xm_eval["reason"],
            "autoRetake": False,
            "needsCreatorReview": True,
            "blocksFinished": True,
            "autoDestroy": False,
            "crossModalityLaw": xm_eval.get("law"),
        }

    retake_eligible = bool(
        sidecar.get("retakeEligible") if sidecar is not None else finding.get("retakeEligible")
    )
    auto_destroy = bool(
        sidecar.get("autoDestroy") if sidecar is not None else finding.get("autoDestroy", False)
    )
    acceptance_eligible = bool(
        sidecar.get("acceptanceEligible")
        if sidecar is not None
        else finding.get("acceptanceEligible", False)
    )
    creative_taste = bool(
        sidecar.get("creativeTaste") if sidecar is not None else finding.get("creativeTaste", False)
    ) or taxonomy == "Creative"

    blocks_finished = not acceptance_eligible

    if creative_taste:
        return {
            "qualifies": False,
            "reason": "Creative suggestion — surface only; never auto-redirect creator",
            "autoRetake": False,
            "needsCreatorReview": True,
            "blocksFinished": False,
        }
    if auto_destroy:
        return {
            "qualifies": False,
            "reason": "autoDestroy forbidden — never destroy good local gen silently",
            "autoRetake": False,
            "needsCreatorReview": True,
            "blocksFinished": blocks_finished,
        }
    if finding.get("inventedFromBadFrame") or finding.get("fromBadFrame"):
        return {
            "qualifies": False,
            "reason": "Never invent continuity/authority from bad frames — creator review",
            "autoRetake": False,
            "needsCreatorReview": True,
            "blocksFinished": True,
            "autoDestroy": False,
        }
    if not retake_eligible:
        return {
            "qualifies": False,
            "reason": "Sidecar retakeEligible=false (uncertain/low/Omni miss or non-Hard)",
            "autoRetake": False,
            "needsCreatorReview": True,
            "blocksFinished": blocks_finished,
        }
    if confidence == "low" or code in DA_NO_AUTO_RETAKE_CODES:
        return {
            "qualifies": False,
            "reason": "Ambiguous/low confidence — creator review; do not destroy good local gen",
            "autoRetake": False,
            "needsCreatorReview": True,
            "blocksFinished": True,
        }
    return {
        "qualifies": True,
        "reason": "Objective Hard defect vs approved production intent (sidecar)",
        "autoRetake": True,
        "needsCreatorReview": False,
        "blocksFinished": True,
        "authoritySource": (sidecar or {}).get("authoritySource")
        or finding.get("authoritySource")
        or "dialogue_manifest",
    }


def _group_compatible_window(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Group compatible defects into ONE interval — smallest repair law."""
    windows: list[dict[str, Any]] = []
    for f in findings:
        w = f.get("window") or f.get("repairWindow") or f.get("timeRange")
        if isinstance(w, dict):
            windows.append(w)
        elif isinstance(w, (list, tuple)) and len(w) >= 2:
            windows.append({"start": w[0], "end": w[1]})
    if not windows:
        return {
            "mode": "smallest_compatible_interval",
            "start": None,
            "end": None,
            "note": "Group compatible defects into ONE interval; prefer audio-only repair when video clean",
        }
    starts = [float(w.get("start") or 0) for w in windows]
    ends = [float(w.get("end") or w.get("start") or 0) for w in windows]
    return {
        "mode": "smallest_compatible_interval",
        "start": min(starts),
        "end": max(ends),
        "groupedCount": len(windows),
        "note": "ONE interval covering grouped compatible defects",
    }


def build_retake_pack(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """WHAT WRONG / WHAT CHANGE / WHAT PRESERVE / WINDOW / AUTHORITIES / METHOD.

    Never invent authority from bad output. Group compatible defects into ONE interval.
    """
    eligible = [f for f in findings if qualify_retake(f).get("qualifies")]
    codes = [str(f.get("code") or "") for f in eligible]
    msgs = [str(f.get("message") or f.get("code") or "defect") for f in eligible]

    authorities: list[str] = []
    for f in eligible:
        src = str(f.get("authoritySource") or (f.get("finalCheck") or {}).get("authoritySource") or "")
        if src and src not in authorities:
            authorities.append(src)
    if not authorities:
        authorities = ["dialogueAuthorityManifest", "spokenLanguage", "speakerBinding"]

    cats = {str(f.get("category")) for f in eligible}
    method = (
        "Manifest-driven Re-Take via consume_dialogue_retake_repair (no second retake stack)"
    )
    if cats & {"equipment", "camera"}:
        method = (
            "Equipment/crew Hard → Re-Take with retake_context_package prompt-law crew-out "
            "(UNAUTHORIZED_PRODUCTION_EQUIPMENT authority). Preserve non-defective framing/cast."
        )
    if cats & {"continuity"}:
        method = (
            "Continuity Hard vs established canon → Re-Take smallest interval. "
            "Never invent continuity from bad frames."
        )

    what_change = "Restore approved production intent for grouped Hard defects"
    if any(c in codes for c in ("SPEECH_WHEN_SILENCE_EXPECTED", "UNAUTHORIZED_BACKGROUND_SPEAKER")):
        what_change = "Remove unauthorized speech / restore silence lock or Manifest speakers"
    if "UNAUTHORIZED_PRODUCTION_EQUIPMENT" in codes or any(c in EQUIPMENT_HARD_CODES for c in codes):
        what_change = (
            "Remove diegetic crew/boom/production equipment — keep cast/location; crew OUT OF FRAME"
        )
    if any(c in CONTINUITY_HARD_CODES for c in codes):
        what_change = "Restore continuity vs established canon (teleport/sides/wardrobe/env)"

    what_preserve = (
        "Approved Timeline R2V continuity, Timed Prompt bytes, non-defective ranges, "
        "cast identity refs, location/Quarters, Music/SFX when video-only defect"
    )
    if cats & {"equipment", "camera"} and (
        "UNAUTHORIZED_PRODUCTION_EQUIPMENT" in codes
        or any(c in EQUIPMENT_HARD_CODES for c in codes)
    ):
        what_preserve = (
            "PRESERVE Anadriya/Korri/dialogue/quarters (and non-defective cast/location/"
            "Timed Prompt bytes/R2V continuity); remove diegetic crew/equipment only"
        )
    window = _group_compatible_window(eligible)

    return {
        "WHAT_WRONG": msgs or codes,
        "WHAT_CHANGE": what_change,
        "WHAT_PRESERVE": what_preserve,
        "WINDOW": window,
        "AUTHORITIES": authorities,
        "METHOD": method,
        "whatWrong": codes or msgs,
        "whatChange": what_change,
        "whatPreserve": what_preserve,
        "window": window,
        "authorities": authorities,
        "method": method,
        "groupedFindingCount": len(eligible),
        "neverInventAuthorityFromBadOutput": True,
        "smallestRepairLaw": True,
        "oneIntervalForCompatibleDefects": True,
    }


def repair_gate_for_runtime(
    runtime_kind: RuntimeKind,
    *,
    has_auto_eligible: bool,
) -> dict[str, Any]:
    """Local HIGH-CONFIDENCE objective → auto. API → ask once even at 100% confidence."""
    if not has_auto_eligible:
        return {
            "runtimeKind": runtime_kind,
            "permission": "not_required",
            "apiCallCount": 0,
            "requiresApproval": False,
            "actions": [],
            "note": "No auto-repair-eligible findings",
        }
    if runtime_kind == "local":
        return {
            "runtimeKind": "local",
            "permission": "not_required",
            "apiCallCount": 0,
            "requiresApproval": False,
            "actions": ["auto_retake"],
            "note": "Local Hard → auto Manifest-driven Re-Take → reverify. NO permission prompt.",
            "reuse": "consume_dialogue_retake_repair / dialogueRetakeRepair",
        }
    return {
        "runtimeKind": "api",
        "permission": "required",
        "apiCallCount": 0,
        "requiresApproval": True,
        "actions": ["repair_automatically", "review_first", "keep_current"],
        "note": "API Hard → propose → one approval per repair cycle. Decline = zero extra API calls.",
        "oneApprovalPerCycle": True,
    }


def apply_api_repair_decision(
    gate: dict[str, Any],
    decision: Literal["repair_automatically", "review_first", "keep_current", "decline", "dismiss"],
) -> dict[str, Any]:
    """ONE approval per cycle. Decline/dismiss → apiCallCount += 0."""
    out = dict(gate)
    out["decision"] = decision
    out["apiCallCount"] = int(gate.get("apiCallCount") or 0)
    if decision in ("decline", "dismiss"):
        out["permission"] = "declined"
        out["apiCallsDelta"] = 0
        out["lifecycleStatus"] = "SCENE_NOT_FINISHED"
        out["creatorVerdict"] = VERDICT_FOUND_ISSUES
        return out
    if decision == "keep_current":
        out["permission"] = "keep_current"
        out["apiCallsDelta"] = 0
        out["lifecycleStatus"] = "SCENE_FINISHED_WITH_ACCEPTED_ISSUES"
        out["creatorVerdict"] = VERDICT_ACCEPTED
        return out
    if decision == "repair_automatically":
        out["permission"] = "granted"
        out["apiCallsDelta"] = 1
        out["lifecycleStatus"] = "REPAIRING"
        return out
    if decision == "review_first":
        out["permission"] = "required"
        out["apiCallsDelta"] = 0
        out["lifecycleStatus"] = "FINAL_CHECK"
        return out
    out["apiCallsDelta"] = 0
    return out


def apply_local_auto_repair(gate: dict[str, Any]) -> dict[str, Any]:
    """Local path: permission stays not_required; enter REPAIRING."""
    out = dict(gate)
    out["permission"] = "not_required"
    out["requiresApproval"] = False
    out["apiCallCount"] = int(gate.get("apiCallCount") or 0)
    out["apiCallsDelta"] = 0
    out["lifecycleStatus"] = "REPAIRING"
    out["decision"] = "auto_retake"
    return out


def advance_after_repair(
    *, pass_reverify: bool, loop_count: int, max_loops: int = DEFAULT_MAX_RETAKE_LOOPS
) -> dict[str, Any]:
    """Bounded retake loop → REVERIFYING → FINISHED or cleanup could not resolve."""
    if pass_reverify:
        return {
            "lifecycleStatus": "SCENE_FINISHED",
            "creatorVerdict": VERDICT_PASSED,
            "retakeLoopCount": loop_count,
            "cleanupFailed": False,
        }
    if loop_count >= max_loops:
        return {
            "lifecycleStatus": "SCENE_NOT_FINISHED",
            "creatorVerdict": VERDICT_FOUND_ISSUES,
            "retakeLoopCount": loop_count,
            "cleanupFailed": True,
            "message": "AUTOMATIC CLEANUP COULD NOT RESOLVE",
        }
    return {
        "lifecycleStatus": "REVERIFYING",
        "creatorVerdict": VERDICT_FOUND_ISSUES,
        "retakeLoopCount": loop_count,
        "cleanupFailed": False,
    }


def run_bounded_local_repair_loop(
    *,
    reverify_results: list[bool],
    max_loops: int = DEFAULT_MAX_RETAKE_LOOPS,
    initial_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """REPAIRING → reverify → loop or AUTOMATIC CLEANUP COULD NOT RESOLVE.

    Consumes provided reverify outcomes only — does not invent Omni results.
    """
    gate = apply_local_auto_repair(
        initial_gate or repair_gate_for_runtime("local", has_auto_eligible=True)
    )
    steps: list[dict[str, Any]] = [{"lifecycleStatus": "REPAIRING", "gate": dict(gate)}]
    loop_count = 0
    for passed in reverify_results:
        loop_count += 1
        steps.append({"lifecycleStatus": "REVERIFYING", "retakeLoopCount": loop_count, "pass": bool(passed)})
        advanced = advance_after_repair(
            pass_reverify=bool(passed), loop_count=loop_count, max_loops=max_loops
        )
        steps.append(advanced)
        if advanced.get("lifecycleStatus") == "SCENE_FINISHED":
            return {
                "ok": True,
                "lifecycleStatus": "SCENE_FINISHED",
                "creatorVerdict": VERDICT_PASSED,
                "retakeLoopCount": loop_count,
                "cleanupFailed": False,
                "steps": steps,
                "retakePackRequired": True,
            }
        if advanced.get("cleanupFailed"):
            return {
                "ok": False,
                "lifecycleStatus": "SCENE_NOT_FINISHED",
                "creatorVerdict": VERDICT_FOUND_ISSUES,
                "retakeLoopCount": loop_count,
                "cleanupFailed": True,
                "message": "AUTOMATIC CLEANUP COULD NOT RESOLVE",
                "steps": steps,
                "retakePackRequired": True,
            }
    return {
        "ok": False,
        "lifecycleStatus": "SCENE_NOT_FINISHED",
        "creatorVerdict": VERDICT_FOUND_ISSUES,
        "retakeLoopCount": loop_count,
        "cleanupFailed": loop_count >= max_loops,
        "message": "AUTOMATIC CLEANUP COULD NOT RESOLVE"
        if loop_count >= max_loops
        else "REVERIFY_PENDING",
        "steps": steps,
        "retakePackRequired": True,
    }


def _batches_render_complete(master: Any) -> tuple[int, int, bool, bool]:
    from .scene_render_progress import (
        ACTIVE_STATUSES,
        COMPLETE_STATUSES,
        FAILED_STATUSES,
        INCOMPLETE_DIALOGUE_STATUSES,
    )

    batches = list(getattr(master, "batchBlocks", None) or [])
    total = len(batches)
    render_done = 0
    queue_active = False
    for batch in batches:
        status = str(getattr(batch, "status", "") or "")
        if status in ACTIVE_STATUSES:
            queue_active = True
        if status in COMPLETE_STATUSES or status in INCOMPLETE_DIALOGUE_STATUSES:
            render_done += 1
        elif status in FAILED_STATUSES:
            pass
    all_done = total > 0 and render_done == total and not queue_active
    return render_done, total, queue_active, all_done


def derive_scene_lifecycle_status(master: Any) -> str:
    """ONE lifecycle authority. BATCHES_COMPLETE ≠ SCENE_FINISHED."""
    existing = getattr(master, "sceneFinalCheck", None)
    if existing is not None:
        if hasattr(existing, "lifecycleStatus"):
            stored = str(getattr(existing, "lifecycleStatus", "") or "")
        elif isinstance(existing, dict):
            stored = str(existing.get("lifecycleStatus") or "")
        else:
            stored = ""
        if stored in {
            "STITCHING",
            "FINAL_CHECK",
            "REPAIRING",
            "REVERIFYING",
            "SCENE_FINISHED",
            "SCENE_FINISHED_WITH_ACCEPTED_ISSUES",
            "SCENE_NOT_FINISHED",
        }:
            return stored

    from .scene_render_progress import derive_scene_render_progress

    derived = derive_scene_render_progress(master)
    if derived.get("queueActive") or derived.get("phase") in ("rendering", "queued"):
        return "RENDERING"

    render_done, total, queue_active, all_batches_done = _batches_render_complete(master)
    # LAW: RENDERING only while queue/work is actually in flight.
    # Draft/Ready idle (and empty masters) are NOT RENDERING — never drive
    # GENERATE SCENE / Multi-batch chrome from incomplete-but-idle batches.
    if queue_active:
        return "RENDERING"
    if total == 0:
        return "SCENE_NOT_FINISHED"
    if not all_batches_done:
        return "SCENE_NOT_FINISHED"
    return "BATCHES_COMPLETE"


def open_final_check_after_stitch(
    master: Any,
    *,
    runtime_kind: RuntimeKind | None = None,
    locality: str | None = None,
    capability: Any = None,
    generator_id: str | None = None,
) -> dict[str, Any]:
    """Open Final Check shell after stitch success. Persist on master.sceneFinalCheck."""
    packets = collect_batch_qc_packets(master)
    findings = packets["dialogue"]
    categories = build_category_shell(
        findings,
        continuity_gate_seen=bool(packets["continuityGateSeen"]),
        equipment_gate_seen=bool(packets["equipmentGateSeen"]),
        continuity_findings=packets["continuity"],
        equipment_findings=packets["equipment"],
    )
    auto_eligible = auto_repair_eligible_findings(categories)
    blocking = blocking_hard_findings(categories)

    gid = generator_id or getattr(master, "sceneGeneratorId", None)
    if not gid:
        batches = getattr(master, "batchBlocks", None) or []
        if batches:
            gid = getattr(batches[0], "generatorId", None) or (
                batches[0].get("generatorId") if isinstance(batches[0], dict) else None
            )
    if capability is None and gid:
        capability = resolve_generator_capability(gid)
    rk: RuntimeKind = runtime_kind or classify_runtime_kind(
        locality=locality,
        capability=capability,
        generator_id=gid,
    )

    gate = repair_gate_for_runtime(rk, has_auto_eligible=bool(auto_eligible))

    owned_block = any(
        c.get("status") in ("fail", "uncertain")
        for c in categories
        if c.get("category") in DIALOGUE_OWNED_CATEGORIES or c.get("category") in PIPELINE_CATEGORIES
    )
    if not blocking and not owned_block:
        lifecycle: str = "SCENE_FINISHED"
        verdict = VERDICT_PASSED
    else:
        lifecycle = "FINAL_CHECK"
        verdict = VERDICT_FOUND_ISSUES

    stitch = getattr(master, "sceneStitch", None)
    stitch_asset = None
    if stitch is not None:
        stitch_asset = getattr(stitch, "assetId", None) or (
            stitch.get("assetId") if isinstance(stitch, dict) else None
        )

    retake_pack = build_retake_pack(auto_eligible) if auto_eligible else None

    return {
        "lifecycleStatus": lifecycle,
        "creatorVerdict": verdict,
        "openedAt": _now(),
        "closedAt": _now() if lifecycle == "SCENE_FINISHED" else None,
        "categories": categories,
        "repairGate": gate,
        "stitchAssetId": stitch_asset,
        "retakeLoopCount": 0,
        "maxRetakeLoops": DEFAULT_MAX_RETAKE_LOOPS,
        "unresolvedBlocking": bool(blocking)
        or (lifecycle == "FINAL_CHECK" and verdict == VERDICT_FOUND_ISSUES),
        "retakePack": retake_pack,
        "autoRepairEligibleCount": len(auto_eligible),
        "policy": "RETAKE_QUALIFICATION_POLICY",
        "equipmentAuthority": equipment_authority_packet().get("authoritySource"),
    }


def creator_verdict_to_lifecycle(verdict: str) -> str:
    v = str(verdict or "").strip()
    if v == VERDICT_PASSED or v.startswith("FINAL CHECK PASSED"):
        return "SCENE_FINISHED"
    if v == VERDICT_ACCEPTED or "ISSUES ACCEPTED" in v.upper():
        return "SCENE_FINISHED_WITH_ACCEPTED_ISSUES"
    return "SCENE_NOT_FINISHED"


def attach_lifecycle_to_progress(progress: dict[str, Any], master: Any) -> dict[str, Any]:
    """Feed lifecycle into generationProgress without collapsing render chrome.

    LAW: clear/stale-heal statusLines when lifecycle is finished (or idle not-finished)
    and nothing is actively rendering/repairing — never leave Dialogue QC Failed /
    Scene Not Finished / Repairing Batch K… on keep_current finished scenes.
    """
    out = dict(progress)
    lifecycle = derive_scene_lifecycle_status(master)
    sfc = getattr(master, "sceneFinalCheck", None)
    if sfc is not None:
        if hasattr(sfc, "model_dump"):
            payload = sfc.model_dump()
        elif isinstance(sfc, dict):
            payload = sfc
        else:
            payload = {}
        if payload.get("lifecycleStatus"):
            lifecycle = str(payload["lifecycleStatus"])
        out["sceneFinalCheck"] = payload
    out["lifecycleStatus"] = lifecycle
    if lifecycle == "SCENE_FINISHED":
        out["sceneFinished"] = True
    elif lifecycle == "SCENE_FINISHED_WITH_ACCEPTED_ISSUES":
        out["sceneFinished"] = True
        out["sceneFinishedWithAcceptedIssues"] = True
    elif lifecycle in (
        "SCENE_NOT_FINISHED",
        "FINAL_CHECK",
        "REPAIRING",
        "REVERIFYING",
        "BATCHES_COMPLETE",
        "STITCHING",
    ):
        out["sceneFinished"] = False

    scene_status = str(out.get("sceneStatus") or "").lower()
    queue_busy = scene_status in {"generating", "queued", "waiting"}
    overlay_active = lifecycle in {
        "RENDERING",
        "STITCHING",
        "FINAL_CHECK",
        "REPAIRING",
        "REVERIFYING",
    } or queue_busy

    if lifecycle in {"SCENE_FINISHED", "SCENE_FINISHED_WITH_ACCEPTED_ISSUES"} and not queue_busy:
        # keep_current / passed → hide multi-batch overlay payload
        out["statusLines"] = []
        out["dialogueQcLabel"] = None
        out["message"] = ""
    elif lifecycle == "SCENE_NOT_FINISHED" and not overlay_active and not queue_busy:
        # Declined / idle Draft/Ready not-finished: no overlay chrome
        out["statusLines"] = []
        out["dialogueQcLabel"] = None
        out["message"] = ""
    elif lifecycle == "FINAL_CHECK":
        out["statusLines"] = ["Final Check Running"]
        out["dialogueQcLabel"] = None
    elif lifecycle == "REVERIFYING":
        out["statusLines"] = ["Re-verifying…"]
        out["dialogueQcLabel"] = None
    elif lifecycle == "REPAIRING":
        lines = list(out.get("statusLines") or [])
        if not any("Repairing Batch" in str(ln) for ln in lines):
            # Prefer existing Repairing line from QC helper; else synthesize.
            k = 1
            batches = list(getattr(master, "batchBlocks", None) or [])
            batches = sorted(
                batches,
                key=lambda b: (int(getattr(b, "order", 0) or 0), str(getattr(b, "createdAt", "") or "")),
            )
            for i, b in enumerate(batches):
                if str(getattr(b, "status", "") or "") == "NeedsDialogueRetake":
                    k = i + 1
                    break
            lines = [ln for ln in lines if "Repairing Batch" not in str(ln)]
            lines.append(f"Repairing Batch {k}…")
            out["statusLines"] = lines
    elif not overlay_active and not queue_busy:
        # Idle Ready / complete with no Final Check open: drop stale Repairing/QC fail chrome
        lines = [str(ln) for ln in (out.get("statusLines") or [])]
        if any(
            ("Repairing Batch" in ln)
            or ("Scene Not Finished" in ln)
            or ln.startswith("Dialogue QC")
            for ln in lines
        ):
            # Keep overall K/N only if present; drop QC/Repairing stale lines
            kept = [ln for ln in lines if "batches complete" in ln]
            out["statusLines"] = kept
            out["dialogueQcLabel"] = None

    return out


# ---------------------------------------------------------------------------
# Live auto-loop hookup helpers (reuse consume_dialogue_retake_repair / retake_range)
# ---------------------------------------------------------------------------

def build_manifest_retake_repair_from_pack(
    retake_pack: dict[str, Any] | None,
    findings: list[dict[str, Any]] | None = None,
    *,
    batch: Any = None,
) -> dict[str, Any]:
    """Shape Final Check PRESERVE pack as dialogueRetakeRepair so retake_range
    / consume_dialogue_retake_repair stay ONE stack — no second retake path.
    """
    pack = dict(retake_pack or {})
    findings = list(findings or [])
    what_change = str(pack.get("WHAT_CHANGE") or pack.get("whatChange") or "").strip()
    what_preserve = str(pack.get("WHAT_PRESERVE") or pack.get("whatPreserve") or "").strip()
    what_wrong = pack.get("WHAT_WRONG") or pack.get("whatWrong") or []
    window = pack.get("WINDOW") or pack.get("window") or {}
    authorities = pack.get("AUTHORITIES") or pack.get("authorities") or []

    # Prefer Manifest script lines when present so dialogue authority still owns words.
    script_lines: list[dict[str, Any]] = []
    language = None
    manifest_id = None
    if batch is not None:
        try:
            from .generation.dialogue_authority import get_manifest_from_batch

            manif = get_manifest_from_batch(batch)
            if manif:
                language = manif.get("language")
                manifest_id = manif.get("manifestId") or manif.get("id")
                for ln in manif.get("lines") or []:
                    if not isinstance(ln, dict):
                        continue
                    t = str(ln.get("text") or "").strip()
                    if not t:
                        continue
                    script_lines.append(
                        {
                            "speakerId": ln.get("speakerId"),
                            "speakerName": ln.get("speakerName"),
                            "text": t,
                            "language": ln.get("language") or language,
                        }
                    )
        except Exception:
            pass

    delta_parts: list[str] = []
    if what_change:
        delta_parts.append(what_change)
    if what_preserve:
        delta_parts.append(f"PRESERVE: {what_preserve}")
    if what_wrong:
        delta_parts.append("WRONG: " + "; ".join(str(x) for x in what_wrong[:6]))
    # Equipment authority crew-out reinforcement (prompt-law; never invent).
    codes = {str(f.get("code") or "") for f in findings}
    if codes & EQUIPMENT_HARD_CODES or "UNAUTHORIZED_PRODUCTION_EQUIPMENT" in codes:
        delta_parts.append(
            "Film crew, documentary crew, interviewer, camera operators, and boom mic "
            "stay OUT OF FRAME for the entire repair window — remove diegetic crew only."
        )
    if codes & CONTINUITY_HARD_CODES:
        delta_parts.append(
            "Restore continuity vs established Narrative canon (teleport/sides/wardrobe/env). "
            "Do not invent continuity from bad frames."
        )
    for sl in script_lines:
        name = sl.get("speakerName") or sl.get("speakerId") or "Speaker"
        delta_parts.append(f'{name} says:\n"{sl.get("text")}"')

    text = "\n\n".join(delta_parts).strip()
    start = 0.0
    length = None
    if isinstance(window, dict):
        try:
            start = float(window.get("start") or window.get("startSec") or 0.0)
        except (TypeError, ValueError):
            start = 0.0
        try:
            length = float(window.get("length") or window.get("durationSec") or 0.0) or None
        except (TypeError, ValueError):
            length = None

    return {
        "kind": "dialogueRetakeRepair",
        "source": "final_check_retake_pack",
        "manifestId": manifest_id,
        "language": language,
        "scriptLines": script_lines,
        "userCorrection": {
            "delta": text,
            "prompt": text,
            "text": text,
            "source": "final_check_retake_pack",
            "language": language,
            "exactScriptDialogue": bool(script_lines),
        },
        "retakePack": pack,
        "window": {"start": start, "length": length},
        "findings": [
            {"code": f.get("code"), "category": f.get("category"), "message": f.get("message")}
            for f in findings[:12]
        ],
        "preserve": what_preserve,
        "method": pack.get("METHOD") or pack.get("method"),
        "neverInventAuthorityFromBadOutput": True,
        "keepTimelineR2V": True,
        "reviveLipSync": False,
        "createdAt": _now(),
    }


def attach_retake_repair_from_pack(
    batch: Any,
    retake_pack: dict[str, Any] | None,
    findings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Persist dialogueRetakeRepair shaped from Final Check PRESERVE pack."""
    repair = build_manifest_retake_repair_from_pack(retake_pack, findings, batch=batch)
    refs = [
        r
        for r in (getattr(batch, "references", None) or [])
        if not (isinstance(r, dict) and r.get("kind") == "dialogueRetakeRepair")
    ]
    refs.append(repair)
    batch.references = refs
    return repair


def plan_local_auto_repair_from_final_check(
    master: Any,
    *,
    max_loops: int = DEFAULT_MAX_RETAKE_LOOPS,
) -> dict[str, Any]:
    """Decide whether local Final Check should auto-enter REPAIRING + retake.

    Does NOT invent Omni results. Consumes open Final Check state only.
    API runtime still requires ask-once (permission=required) — this planner
    returns needs_api_ask for that case.
    """
    fc = getattr(master, "sceneFinalCheck", None)
    if fc is None:
        return {"shouldAutoRetake": False, "reason": "NO_FINAL_CHECK"}
    dump = fc.model_dump() if hasattr(fc, "model_dump") else (fc if isinstance(fc, dict) else {})
    gate = dump.get("repairGate") or {}
    if hasattr(gate, "model_dump"):
        gate = gate.model_dump()
    runtime = str(gate.get("runtimeKind") or dump.get("runtimeKind") or "api")
    eligible_count = int(dump.get("autoRepairEligibleCount") or 0)
    pack = dump.get("retakePack")
    loop_count = int(dump.get("retakeLoopCount") or 0)
    max_l = int(dump.get("maxRetakeLoops") or max_loops)

    if eligible_count <= 0 or not pack:
        return {
            "shouldAutoRetake": False,
            "reason": "NO_AUTO_ELIGIBLE",
            "runtimeKind": runtime,
            "retakeLoopCount": loop_count,
        }
    if loop_count >= max_l:
        return {
            "shouldAutoRetake": False,
            "cleanupFailed": True,
            "message": "AUTOMATIC CLEANUP COULD NOT RESOLVE",
            "lifecycleStatus": "SCENE_NOT_FINISHED",
            "reason": "MAX_LOOPS",
            "runtimeKind": runtime,
            "retakeLoopCount": loop_count,
            "retakePack": pack,
        }
    if runtime != "local":
        return {
            "shouldAutoRetake": False,
            "needsApiAsk": True,
            "reason": "API_ASK_ONCE",
            "runtimeKind": runtime,
            "retakeLoopCount": loop_count,
            "retakePack": pack,
            "autoRepairEligibleCount": eligible_count,
        }

    categories = dump.get("categories") or []
    auto_eligible: list[dict[str, Any]] = []
    for cat in categories:
        if not isinstance(cat, dict):
            continue
        for f in cat.get("findings") or []:
            if isinstance(f, dict) and f.get("retakeEligible") and f.get("taxonomy") == "Hard":
                conf = str(f.get("confidence") or "high").lower()
                if conf == "high":
                    auto_eligible.append(f)

    return {
        "shouldAutoRetake": True,
        "reason": "LOCAL_HIGH_CONF_HARD",
        "runtimeKind": "local",
        "retakeLoopCount": loop_count,
        "maxRetakeLoops": max_l,
        "retakePack": pack,
        "autoRepairEligibleCount": eligible_count,
        "findings": auto_eligible,
        "lifecycleStatus": "REPAIRING",
    }


def apply_planned_local_auto_repair_to_final_check(
    master: Any,
    plan: dict[str, Any],
) -> dict[str, Any]:
    """Mutate master.sceneFinalCheck into REPAIRING (or cleanup-failed) from plan."""
    from .contracts import SceneFinalCheck, SceneFinalCheckRepairGate

    fc = getattr(master, "sceneFinalCheck", None)
    if fc is None:
        return {"ok": False, "error": "NO_FINAL_CHECK"}
    dump = fc.model_dump() if hasattr(fc, "model_dump") else dict(fc)
    if plan.get("cleanupFailed"):
        dump["lifecycleStatus"] = "SCENE_NOT_FINISHED"
        dump["creatorVerdict"] = VERDICT_FOUND_ISSUES
        dump["unresolvedBlocking"] = True
        dump["cleanupFailed"] = True
        dump["cleanupMessage"] = "AUTOMATIC CLEANUP COULD NOT RESOLVE"
        dump["retakeLoopCount"] = int(plan.get("retakeLoopCount") or dump.get("retakeLoopCount") or 0)
        master.sceneFinalCheck = SceneFinalCheck.model_validate(dump)
        return {"ok": False, "cleanupFailed": True, "message": "AUTOMATIC CLEANUP COULD NOT RESOLVE", "sceneFinalCheck": dump}

    gate = dump.get("repairGate") or {}
    if hasattr(gate, "model_dump"):
        gate = gate.model_dump()
    updated = apply_local_auto_repair(gate)
    dump["repairGate"] = updated
    dump["lifecycleStatus"] = "REPAIRING"
    dump["retakeLoopCount"] = int(plan.get("retakeLoopCount") or 0) + 1
    dump["unresolvedBlocking"] = True
    # Attach repair packs onto batches that carry auto-eligible findings.
    findings = list(plan.get("findings") or [])
    pack = plan.get("retakePack")
    attached: list[str] = []
    for batch in getattr(master, "batchBlocks", None) or []:
        # Attach to every batch that has equipment/continuity QC FAIL or any Hard eligible.
        has_hard = False
        for r in getattr(batch, "references", None) or []:
            if not isinstance(r, dict):
                continue
            if r.get("kind") in {
                "omniEquipmentDiagnostics",
                "equipmentQcDiagnostics",
                "omniContinuityDiagnostics",
                "continuityQcDiagnostics",
                "dialogueQcDiagnostics",
            } and str(r.get("verdict") or "").upper() == "FAIL":
                has_hard = True
                break
        if not has_hard and findings:
            # Still attach when scene-level pack exists (Final Check grouped).
            has_hard = True
        if has_hard:
            attach_retake_repair_from_pack(batch, pack, findings)
            attached.append(str(getattr(batch, "id", "")))
    master.sceneFinalCheck = SceneFinalCheck.model_validate(dump)
    return {
        "ok": True,
        "lifecycleStatus": "REPAIRING",
        "retakeLoopCount": dump["retakeLoopCount"],
        "attachedBatchIds": attached,
        "retakePack": pack,
        "sceneFinalCheck": dump,
    }


def mark_final_check_reverify(
    master: Any,
    *,
    pass_reverify: bool,
) -> dict[str, Any]:
    """Advance Final Check after a repair attempt (bounded loop)."""
    from .contracts import SceneFinalCheck

    fc = getattr(master, "sceneFinalCheck", None)
    if fc is None:
        return {"ok": False, "error": "NO_FINAL_CHECK"}
    dump = fc.model_dump() if hasattr(fc, "model_dump") else dict(fc)
    loop_count = int(dump.get("retakeLoopCount") or 0)
    max_loops = int(dump.get("maxRetakeLoops") or DEFAULT_MAX_RETAKE_LOOPS)
    advanced = advance_after_repair(
        pass_reverify=pass_reverify, loop_count=loop_count, max_loops=max_loops
    )
    dump["lifecycleStatus"] = advanced["lifecycleStatus"]
    dump["creatorVerdict"] = advanced.get("creatorVerdict")
    dump["retakeLoopCount"] = advanced.get("retakeLoopCount", loop_count)
    dump["cleanupFailed"] = bool(advanced.get("cleanupFailed"))
    if advanced.get("message"):
        dump["cleanupMessage"] = advanced["message"]
    if advanced["lifecycleStatus"] in {
        "SCENE_FINISHED",
        "SCENE_FINISHED_WITH_ACCEPTED_ISSUES",
    }:
        dump["closedAt"] = _now()
        dump["unresolvedBlocking"] = False
    elif advanced.get("cleanupFailed"):
        dump["unresolvedBlocking"] = True
        dump["closedAt"] = None
    else:
        dump["unresolvedBlocking"] = True
    master.sceneFinalCheck = SceneFinalCheck.model_validate(dump)
    return {"ok": True, **advanced, "sceneFinalCheck": dump}


def execute_local_auto_retakes(
    db: Any,
    project_id: str,
    scene_id: str,
    master: Any,
    *,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fire Manifest-driven retake_range for batches with attached PRESERVE repair.

    Reuses orchestrator.retake_range / consume_dialogue_retake_repair — ONE stack.
    Caller must already have applied plan (REPAIRING + dialogueRetakeRepair attached).
    Does not invent Omni findings. Safe no-op when nothing attached.
    """
    plan = plan or plan_local_auto_repair_from_final_check(master)
    if plan.get("cleanupFailed"):
        return {
            "ok": False,
            "cleanupFailed": True,
            "message": "AUTOMATIC CLEANUP COULD NOT RESOLVE",
            "retakes": [],
        }
    if not plan.get("shouldAutoRetake") and str(
        getattr(getattr(master, "sceneFinalCheck", None), "lifecycleStatus", "") or ""
    ) != "REPAIRING":
        # Allow execute when already REPAIRING (pack attached this turn).
        fc = getattr(master, "sceneFinalCheck", None)
        life = ""
        if fc is not None:
            life = str(getattr(fc, "lifecycleStatus", "") or "")
            if isinstance(fc, dict):
                life = str(fc.get("lifecycleStatus") or "")
        if life != "REPAIRING":
            return {"ok": False, "reason": plan.get("reason") or "NOT_REPAIRING", "retakes": []}

    from .orchestrator import retake_range

    retakes: list[dict[str, Any]] = []
    pack = plan.get("retakePack") or {}
    window = pack.get("WINDOW") or pack.get("window") or {}
    try:
        start = float(window.get("start") or window.get("startSec") or 0.0)
    except (TypeError, ValueError):
        start = 0.0
    try:
        length = float(window.get("length") or window.get("durationSec") or 0.0)
    except (TypeError, ValueError):
        length = 0.0

    for batch in getattr(master, "batchBlocks", None) or []:
        repair = None
        for r in getattr(batch, "references", None) or []:
            if isinstance(r, dict) and r.get("kind") == "dialogueRetakeRepair":
                if r.get("source") == "final_check_retake_pack" or r.get("retakePack"):
                    repair = r
                    break
        if repair is None:
            continue
        win = repair.get("window") if isinstance(repair.get("window"), dict) else {}
        b_start = start
        b_len = length
        try:
            if win.get("start") is not None:
                b_start = float(win.get("start") or 0.0)
            if win.get("length"):
                b_len = float(win.get("length") or 0.0)
        except (TypeError, ValueError):
            pass
        if b_len < 0.15:
            planned = float(getattr(getattr(batch, "duration", None), "plannedDuration", 0) or 0)
            b_len = planned if planned >= 0.15 else 15.0
        delta = ""
        uc = repair.get("userCorrection") if isinstance(repair.get("userCorrection"), dict) else {}
        delta = str(uc.get("delta") or uc.get("prompt") or uc.get("text") or "").strip()
        if not delta:
            delta = str(pack.get("WHAT_CHANGE") or pack.get("whatChange") or "Restore approved production intent").strip()
        try:
            result = retake_range(
                db,
                project_id,
                scene_id,
                str(getattr(batch, "id", "")),
                start=b_start,
                length=b_len,
                prompt=delta,
            )
        except Exception as exc:  # noqa: BLE001
            result = {"ok": False, "error": "AUTO_RETAKE_EXCEPTION", "detail": str(exc)[:400]}
        retakes.append(
            {
                "batchId": str(getattr(batch, "id", "")),
                "start": b_start,
                "length": b_len,
                "result": result,
            }
        )

    any_ok = any(bool((r.get("result") or {}).get("ok")) for r in retakes)
    return {
        "ok": any_ok or not retakes,
        "reason": "LOCAL_AUTO_RETAKE" if retakes else "NO_ATTACHED_REPAIR",
        "retakes": retakes,
        "retakeLoopCount": plan.get("retakeLoopCount"),
    }