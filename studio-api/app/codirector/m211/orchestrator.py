"""M2.11 Production Intelligence orchestrator (advise-only, smoke-friendly)."""

from __future__ import annotations

import time
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..intelligence.schemas import SpecialistFinding
from ..intelligence.specialist_runner import (
    LIMITED_ANALYSIS_MODE,
    SpecialistRunner,
    resolve_provider_for_specialists,
)
from .conflicts_bridge import bridge_specialist_conflicts
from .context_pack import build_context_pack
from .dag import DEFAULT_PIPELINE, default_stage_order, specialist_graph
from .decisions import DecisionRecordStore
from .review_loop import ReviewLoopService
from .traces import ExecutionTraceStore

SMOKE_BRIEF = 'Create a suspenseful laboratory scene where two scientists discover an alien artifact.'


def _finding_to_dict(finding: SpecialistFinding) -> dict[str, Any]:
    return finding.model_dump(mode="json")


def _is_sparse(findings: list[SpecialistFinding]) -> bool:
    if not findings:
        return True
    substantive = 0
    for f in findings:
        if len((f.recommendation or "").strip()) > 40 or len(f.requirements) > 0:
            substantive += 1
    return substantive < max(2, len(findings) // 3)


def _heuristic_enrichment(brief: str) -> dict[str, Any]:
    """Derive smoke-friendly production artifacts from the brief without an LLM."""

    text = (brief or SMOKE_BRIEF).strip()
    lowered = text.lower()
    lab = "lab" in lowered or "containment" in lowered or "server" in lowered or "laboratory" in lowered
    alien = "alien" in lowered or "artifact" in lowered
    scientists = "scientist" in lowered or "scientists" in lowered

    if not (lab or alien or scientists):
        return {
            "story": [{"beat": 1, "label": "Brief", "description": text[:240]}],
            "shotPlan": [],
            "camera": {},
            "music": {},
            "sfx": [],
            "editingBeats": [],
            "continuity": [],
            "missingAssets": [],
            "checklist": ["Validate story beats and required assets against the supplied brief"],
            "source": "limited-analysis-heuristic",
            "briefExcerpt": text[:240],
            "honesty": "limited",
            "analysisMode": LIMITED_ANALYSIS_MODE,
            "note": (
                "Limited-analysis enrichment was not specialized because the brief "
                "did not match the available scaffold."
            ),
        }

    story = [
        {"beat": 1, "label": "Entry", "description": "Talent enters sealed space / door opens."},
        {"beat": 2, "label": "Discovery", "description": "Hazard or anomaly is revealed in frame."},
        {"beat": 3, "label": "Containment", "description": "Immediate corrective action begins."},
        {"beat": 4, "label": "Callout", "description": "Radio / escalation beat closes the scene."},
    ]
    if alien and scientists:
        story = [
            {"beat": 1, "label": "Approach", "description": "Two scientists enter the laboratory under restrained suspense lighting."},
            {"beat": 2, "label": "Reveal", "description": "An alien artifact becomes readable on the examination table."},
            {"beat": 3, "label": "Reaction", "description": "Scientists exchange a tense look; one reaches to scan the object."},
            {"beat": 4, "label": "Escalation", "description": "Artifact responds; alarms / call for backup close the beat."},
        ]
    elif alien:
        story[1]["description"] = "Alien artifact is revealed with uncanny material detail."
        story[2]["description"] = "Talent attempts cautious scan / containment of the artifact."
    elif lab:
        story[1]["description"] = "Cracked containment cylinder and blue vapor become readable."
        story[2]["description"] = "Cylinder sealed; amber emergency strobes engage."

    if alien and scientists:
        shot_plan = [
            {"shotId": "S1", "framing": "wide", "purpose": "Establish laboratory geography and two-scientist blocking"},
            {"shotId": "S2", "framing": "medium two-shot", "purpose": "Scientists discover the alien artifact"},
            {"shotId": "S3", "framing": "insert", "purpose": "Alien artifact surface / unknown material detail"},
            {"shotId": "S4", "framing": "close-up reaction", "purpose": "Tense scientist reaction + escalation cue"},
        ]
        camera = {
            "lenses": ["35mm establish", "50mm two-shot", "85mm artifact insert"],
            "movement": ["slow push to table", "locked insert", "subtle handheld on reaction"],
            "lighting": ["cold lab practicals", "narrow key on artifact", "restrained face exposure"],
            "notes": "Keep artifact edge highlights readable; avoid crushing blacks on lab glass.",
        }
        music = {
            "palette": "suspenseful low pulse, sparse dissonant strings",
            "cues": [
                {"at": "approach", "idea": "quiet drone under door / footsteps"},
                {"at": "reveal", "idea": "rising harmonic cluster as artifact fills frame"},
                {"at": "escalation", "idea": "hold tension; leave space for alarm / radio"},
            ],
        }
        sfx = [
            {"id": "lab_ambience", "description": "Laboratory room tone / HVAC hum"},
            {"id": "footsteps", "description": "Two sets of cautious footsteps on hard floor"},
            {"id": "artifact_hum", "description": "Low alien artifact resonance"},
            {"id": "scanner_beep", "description": "Handheld scanner chirp"},
            {"id": "alarm", "description": "Soft alarm / radio escalation"},
        ]
        editing_beats = [
            {"from": "S1", "to": "S2", "idea": "Match on approach to table"},
            {"from": "S2", "to": "S3", "idea": "Cut on glance to artifact"},
            {"from": "S3", "to": "S4", "idea": "Smash cut to scientist reaction"},
        ]
        continuity = [
            "Keep both scientists' glove / coat state consistent across S2-S4.",
            "Artifact orientation must match between insert and two-shot.",
            "Scanner prop hand (left/right) must not flip.",
            "Alarm/strobe cues begin only after artifact response beat.",
        ]
        missing_assets = [
            "Approved scientist A/B character references",
            "Laboratory set architecture plate",
            "Alien artifact hero prop reference",
            "Handheld scanner prop reference",
            "Alarm strobe practical reference (optional)",
        ]
    else:
        shot_plan = [
            {"shotId": "S1", "framing": "wide", "purpose": "Establish lab geography and practicals"},
            {"shotId": "S2", "framing": "tracking medium", "purpose": "Follow talent through corridor"},
            {"shotId": "S3", "framing": "insert", "purpose": "Containment cylinder detail + vapor"},
            {"shotId": "S4", "framing": "medium two-shot", "purpose": "Seal action + radio callout"},
        ]
        camera = {
            "lenses": ["35mm establish", "50mm follow", "85mm insert"],
            "movement": ["slow push", "subtle handheld settle on two-shot"],
            "lighting": ["cold neon practicals", "amber strobe accents", "readable face exposure"],
            "notes": "Preserve corridor practicals; avoid crushing blacks on vapor edge.",
        }
        music = {
            "palette": "low pulse underscore, restrained tension",
            "cues": [
                {"at": "entry", "idea": "sparse drone under door seal"},
                {"at": "discovery", "idea": "rising harmonic cluster"},
                {"at": "callout", "idea": "hold drone; leave room for radio FX"},
            ],
        }
        sfx = [
            {"id": "door_seal", "description": "Blast door seal / pressure hiss"},
            {"id": "server_hum", "description": "Server rack room tone"},
            {"id": "vapor_leak", "description": "Soft vapor leak + glass stress"},
            {"id": "amber_strobe", "description": "Emergency strobe click/relay"},
            {"id": "radio", "description": "Handheld radio squelch and callout"},
        ]
        editing_beats = [
            {"from": "S1", "to": "S2", "idea": "Match on door threshold motion"},
            {"from": "S2", "to": "S3", "idea": "Cut on glance to cylinder"},
            {"from": "S3", "to": "S4", "idea": "Smash cut to seal action / strobes"},
        ]
        continuity = [
            "Keep glove / sleeve state consistent across S2-S4.",
            "Vapor volume should increase until seal, then decay.",
            "Amber strobes begin only after containment action.",
            "Radio hand props must match left/right continuity.",
        ]
        missing_assets = [
            "Approved Maya character reference",
            "Lab corridor architecture plate",
            "Containment cylinder hero prop reference",
            "Emergency strobe practical reference",
            "Radio prop + UI overlay still (optional)",
        ]

    checklist = [
        "Lock story beats against bible scene facts",
        "Confirm advise-only: no silent bible/timeline mutation",
        "Queue approval for bible-manager / continuity / QA boundaries",
        "Attach memory notes for vapor + strobe continuity" if not (alien and scientists) else "Attach memory notes for artifact orientation + scientist blocking",
        "Validate missing assets before generation handoff",
    ]
    return {
        "story": story,
        "shotPlan": shot_plan,
        "camera": camera,
        "music": music,
        "sfx": sfx,
        "editingBeats": editing_beats,
        "continuity": continuity,
        "missingAssets": missing_assets,
        "checklist": checklist,
        "source": "limited-analysis-heuristic",
        "briefExcerpt": text[:240],
        "honesty": "limited",
        "analysisMode": LIMITED_ANALYSIS_MODE,
        "note": (
            "Limited-analysis enrichment from brief keywords only — "
            "not live model reasoning or deep emotional intelligence."
        ),
    }


def _map_from_findings(findings: list[SpecialistFinding], brief: str) -> dict[str, Any]:
    by_id = {f.specialistId: f for f in findings}
    out: dict[str, Any] = {}
    if "story-analyst" in by_id:
        f = by_id["story-analyst"]
        out["story"] = [
            {"summary": f.summary, "recommendation": f.recommendation, "requirements": f.requirements}
        ]
    if "director" in by_id or "cinematographer" in by_id:
        d = by_id.get("director")
        c = by_id.get("cinematographer")
        shots = []
        if d:
            shots.append({"from": "director", "text": d.recommendation})
        if c:
            shots.append({"from": "cinematographer", "text": c.recommendation})
        out["shotPlan"] = shots
        if c:
            out["camera"] = {
                "recommendation": c.recommendation,
                "requirements": c.requirements,
                "risks": c.risks,
            }
    if "music-supervisor" in by_id:
        f = by_id["music-supervisor"]
        out["music"] = {"recommendation": f.recommendation, "requirements": f.requirements}
    if "sound-designer" in by_id:
        f = by_id["sound-designer"]
        items = [f.recommendation] + list(f.requirements or [])
        out["sfx"] = [{"description": x} for x in items if x]
    if "editor" in by_id:
        f = by_id["editor"]
        out["editingBeats"] = [{"idea": f.recommendation}] + [{"idea": r} for r in f.requirements]
    if "continuity-analyst" in by_id:
        f = by_id["continuity-analyst"]
        out["continuity"] = list(f.blockingIssues or []) + list(f.risks or []) + list(f.requirements or [])
    missing: list[str] = []
    checklist: list[str] = []
    for f in findings:
        for req in f.requirements or []:
            if any(k in req.lower() for k in ("reference", "asset", "missing", "plate", "prop")):
                missing.append(req)
            else:
                checklist.append(f"{f.specialistId}: {req}")
        for b in f.blockingIssues or []:
            checklist.append(f"BLOCKER ({f.specialistId}): {b}")
    if missing:
        out["missingAssets"] = missing
    if checklist:
        out["checklist"] = checklist
    return out


class ProductionIntelligenceOrchestrator:
    """Run DEFAULT_PIPELINE specialists with retry, decisions, traces, and review loop."""

    def __init__(self, runner: SpecialistRunner | None = None) -> None:
        self.runner = runner or SpecialistRunner()

    async def run(
        self,
        db: Session,
        project_id: str,
        brief: str,
        scene_id: Optional[str] = None,
        model_used: str = "gemma",
    ) -> dict[str, Any]:
        brief_text = (brief or "").strip() or SMOKE_BRIEF
        context_pack = build_context_pack(db, project_id, scene_id, brief_text)
        strategy_pack = context_pack.get("strategyPack")
        active_lessons = context_pack.get("activeLessons") or []
        graph = specialist_graph()
        stage_order = default_stage_order()
        provider, use_provider, analysis_mode = await resolve_provider_for_specialists()

        trace = ExecutionTraceStore.start(
            db,
            project_id=project_id,
            scene_id=scene_id,
            model_used=model_used,
            specialist_graph=graph,
            brief=brief_text,
        )
        trace_id = trace["id"]

        loop = ReviewLoopService.start(project_id, scene_id)
        ReviewLoopService.advance(loop.loop_id, action="next", note="plan complete")

        findings: list[SpecialistFinding] = []
        decisions: list[dict[str, Any]] = []
        pending_approvals: list[dict[str, Any]] = []
        explainability: list[dict[str, Any]] = []
        stage_rows: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        retries: list[dict[str, Any]] = []
        approvals: list[dict[str, Any]] = []
        durations: dict[str, Any] = {}

        ReviewLoopService.advance(loop.loop_id, action="next", note="execute specialists")

        for node in DEFAULT_PIPELINE:
            t0 = time.perf_counter()
            finding: SpecialistFinding | None = None
            last_error: str | None = None
            for attempt in (1, 2):
                try:
                    batch, errors = await self.runner.run_all(
                        db,
                        project_id=project_id,
                        user_message=brief_text,
                        specialist_ids=[node.specialist_id],
                        scene_id=scene_id,
                        model_id=model_used,
                        provider=provider,
                        use_provider=use_provider,
                    )
                    if errors and not batch:
                        err0 = errors[0]
                        msg = getattr(err0, "message", None) or str(err0)
                        raise RuntimeError(msg)
                    finding = batch[0] if batch else None
                    if finding is None:
                        raise RuntimeError(f"No finding for {node.specialist_id}")
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = str(exc)[:300]
                    if attempt == 1:
                        retries.append(
                            {
                                "stageId": node.stage_id,
                                "specialistId": node.specialist_id,
                                "attempt": attempt,
                                "error": last_error,
                            }
                        )
                    else:
                        failures.append(
                            {
                                "stageId": node.stage_id,
                                "specialistId": node.specialist_id,
                                "error": last_error,
                            }
                        )

            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            durations[node.stage_id] = elapsed_ms

            if finding is None:
                stage_rows.append(
                    {
                        "stageId": node.stage_id,
                        "specialistId": node.specialist_id,
                        "status": "failed",
                        "durationMs": elapsed_ms,
                        "error": last_error,
                    }
                )
                continue

            findings.append(finding)
            bible_refs = []
            for ref in finding.productionBibleReferences or []:
                if hasattr(ref, "stableId"):
                    bible_refs.append(ref.stableId)
                elif isinstance(ref, dict) and ref.get("stableId"):
                    bible_refs.append(ref["stableId"])
            bible_refs = [r for r in bible_refs if r]
            explain = {
                "summary": finding.summary,
                "recommendation": finding.recommendation,
                "evidence": [{"type": "requirement", "text": r} for r in finding.requirements]
                + [{"type": "risk", "text": r} for r in finding.risks],
                "bibleRefs": bible_refs,
                "specialistId": finding.specialistId,
                "confidence": finding.confidence,
                "stageId": node.stage_id,
                "blockingIssues": list(finding.blockingIssues or []),
            }
            explainability.append(explain)

            decision = DecisionRecordStore.create(
                db,
                project_id=project_id,
                scene_id=scene_id,
                category=node.stage_id,
                rationale=finding.summary or finding.recommendation,
                confidence=float(finding.confidence),
                evidence=explain["evidence"],
                bible_refs=bible_refs,
                specialist_id=finding.specialistId,
                approval_required=bool(node.approval_boundary),
                approval_status="pending" if node.approval_boundary else "not_required",
                recommendation=finding.recommendation,
                explainability=explain,
            )
            decisions.append(decision)

            if node.approval_boundary:
                approval_row = {
                    "stageId": node.stage_id,
                    "specialistId": node.specialist_id,
                    "decisionId": decision["id"],
                    "status": "pending",
                    "mutationAllowed": False,
                    "note": "Recorded approval boundary; bible/timeline not mutated.",
                }
                pending_approvals.append(approval_row)
                approvals.append(approval_row)

            stage_rows.append(
                {
                    "stageId": node.stage_id,
                    "specialistId": node.specialist_id,
                    "status": "ok",
                    "durationMs": elapsed_ms,
                    "decisionId": decision["id"],
                    "approvalBoundary": node.approval_boundary,
                }
            )

        conflicts = bridge_specialist_conflicts(db, project_id, findings, scene_id=scene_id)
        ReviewLoopService.advance(loop.loop_id, action="next", note="review assembled")
        loop_state = ReviewLoopService.get(loop.loop_id)

        enrichment = _heuristic_enrichment(brief_text) if _is_sparse(findings) else None
        mapped = _map_from_findings(findings, brief_text)
        if enrichment:
            for key in (
                "story",
                "shotPlan",
                "camera",
                "music",
                "sfx",
                "editingBeats",
                "continuity",
                "missingAssets",
                "checklist",
            ):
                if not mapped.get(key):
                    mapped[key] = enrichment[key]

        bible_finding = next((f for f in findings if f.specialistId == "bible-manager"), None)
        story_finding = next((f for f in findings if f.specialistId == "story-analyst"), None)

        status = "completed" if not failures else ("completed_with_errors" if findings else "failed")
        updated_trace = ExecutionTraceStore.update(
            db,
            project_id,
            trace_id,
            status=status,
            durations=durations,
            failures=failures,
            retries=retries,
            approvals=approvals,
            stages=stage_rows,
        )

        story_out = mapped.get("story")
        if not story_out:
            if story_finding:
                story_out = [
                    {"summary": story_finding.summary, "recommendation": story_finding.recommendation}
                ]
            elif enrichment:
                story_out = enrichment["story"]
            else:
                story_out = []

        content_dropped = any(getattr(finding, "contentDropped", False) for finding in findings)
        honesty = (
            "unavailable"
            if content_dropped
            else ("provider" if analysis_mode != LIMITED_ANALYSIS_MODE else "limited")
        )
        if content_dropped:
            honesty_notes = [
                "Provider output was repaired after substantive content was discarded; honesty is unavailable."
            ]
        elif honesty == "provider":
            honesty_notes = []
        else:
            honesty_notes = [
                "Limited-analysis / heuristic path — Co-Director provider unavailable or "
                "STUDIO_E2E is set. Specialist digests are not live model reasoning.",
            ]

        return {
            "story": story_out,
            "bible": {
                "context": context_pack.get("bible"),
                "recommendation": bible_finding.recommendation if bible_finding else None,
                "mutationPolicy": context_pack.get("mutationPolicy"),
            },
            "specialists": [_finding_to_dict(f) for f in findings],
            "shotPlan": mapped.get("shotPlan") or (enrichment["shotPlan"] if enrichment else []),
            "camera": mapped.get("camera") or (enrichment["camera"] if enrichment else {}),
            "music": mapped.get("music") or (enrichment["music"] if enrichment else {}),
            "sfx": mapped.get("sfx") or (enrichment["sfx"] if enrichment else []),
            "editingBeats": mapped.get("editingBeats") or (enrichment["editingBeats"] if enrichment else []),
            "continuity": mapped.get("continuity") or (enrichment["continuity"] if enrichment else []),
            "missingAssets": mapped.get("missingAssets") or (enrichment["missingAssets"] if enrichment else []),
            "checklist": mapped.get("checklist") or (enrichment["checklist"] if enrichment else []),
            "decisions": decisions,
            "conflicts": conflicts,
            "trace": updated_trace,
            "reviewLoop": loop_state.to_dict() if loop_state else None,
            "contextPack": context_pack,
            "strategyPack": strategy_pack,
            "activeLessons": active_lessons,
            "stageOrder": stage_order,
            "pendingApprovals": pending_approvals,
            "explainability": explainability,
            "modelUsed": model_used,
            "status": status,
            "enriched": bool(enrichment),
            "analysisMode": analysis_mode,
            "honesty": honesty,
            "honestyNotes": honesty_notes,
            "useProvider": use_provider,
        }
