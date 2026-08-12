"""Background Creative Operating Intelligence service (never blocks TTFT)."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from .bible_steward import choose_steward_mode, run_steward
from .decision_loop import run_creative_decision_loop
from .persistence import load_bundle, save_bundle
from .script_intelligence import (
    build_installment_record,
    detect_source_role,
    parse_script_breakdown,
)

logger = logging.getLogger(__name__)


def process_creative_operating_turn(
    db: Session,
    *,
    project_id: str,
    user_message: str,
    discovery_stage: str | None = None,
    primary_project_type: str | None = None,
    snapshot_format: str | None = None,
    candidate_count: int = 0,
    specialist_positions: dict[str, str] | None = None,
    script_text: str | None = None,
    script_filename: str | None = None,
) -> dict[str, Any]:
    """Run decision loop + bible steward + optional script intelligence in background."""
    try:
        decision, bundle = run_creative_decision_loop(
            db,
            project_id=project_id,
            user_message=user_message,
            discovery_stage=discovery_stage,
            primary_project_type=primary_project_type,
            snapshot_format=snapshot_format,
            specialist_positions=specialist_positions,
            persist=True,
        )
        mode = choose_steward_mode(
            candidate_count=candidate_count,
            user_need=decision.userNeed,
            substantial_growth=candidate_count >= 6,
        )
        steward = run_steward(
            db,
            project_id=project_id,
            mode=mode,
            user_message=user_message,
            seed_texts=[k.statement for k in decision.importantNewKnowledge],
            format_label=decision.projectFormat,
        )

        script_payload: dict[str, Any] | None = None
        role = detect_source_role(filename=script_filename or "", hint=user_message)
        if script_text and role in {"script", "treatment"}:
            breakdown = parse_script_breakdown(
                script_text, alias_map=bundle.identityAliases
            )
            script_payload = {
                "role": role,
                "breakdown": breakdown,
                "installment": build_installment_record(breakdown),
            }

        return {
            "ok": True,
            "neverBlocksTtft": True,
            "decision": decision.model_dump(mode="json"),
            "steward": steward,
            "scriptIntelligence": script_payload,
            "initiativeLevel": bundle.initiativeLevel,
            "curiosityThreadCount": len(
                [t for t in bundle.curiosityThreads if t.state == "OPEN"]
            ),
            "forwardSuggestionId": decision.forwardSuggestion.id
            if decision.forwardSuggestion
            else None,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("creative operating turn failed for %s: %s", project_id, exc)
        return {"ok": False, "error": str(exc)[:300], "neverBlocksTtft": True}


def set_initiative_level(
    db: Session, project_id: str, level: str
) -> dict[str, Any]:
    allowed: set[str] = {
        "QUIET_PARTNER",
        "COLLABORATIVE_PARTNER",
        "PROACTIVE_PRODUCER",
        "HANDS_ON_CO_CREATOR",
    }
    if level not in allowed:
        return {"ok": False, "error": "Invalid initiative level"}
    bundle = load_bundle(db, project_id)
    bundle.initiativeLevel = level  # type: ignore[assignment]
    save_bundle(db, bundle)
    return {
        "ok": True,
        "projectId": project_id,
        "initiativeLevel": bundle.initiativeLevel,
        "bundle": bundle.model_dump(mode="json"),
    }


def get_creative_operating(db: Session, project_id: str) -> dict[str, Any]:
    from .contracts import INITIATIVE_LABELS, INITIATIVE_TIPS

    bundle = load_bundle(db, project_id)
    return {
        "ok": True,
        "projectId": project_id,
        "initiativeLevel": bundle.initiativeLevel,
        "initiativeLabel": INITIATIVE_LABELS.get(bundle.initiativeLevel, bundle.initiativeLevel),
        "initiativeTips": INITIATIVE_TIPS,
        "creativeStage": bundle.creativeStage,
        "projectFormat": bundle.projectFormat,
        "curiosityThreads": [
            t.model_dump(mode="json")
            for t in bundle.curiosityThreads
            if t.state in {"OPEN", "PARTIALLY_ANSWERED", "DEFERRED"}
        ][:5],
        "forwardSuggestions": [
            s.model_dump(mode="json")
            for s in bundle.forwardSuggestions
            if s.state == "ACTIVE"
        ][:3],
        "dismissedSuggestionIds": list(bundle.dismissedSuggestionIds or [])[:40],
        "lastDecision": bundle.lastDecision.model_dump(mode="json") if bundle.lastDecision else None,
        "lastDisagreement": bundle.lastDisagreement.model_dump(mode="json")
        if bundle.lastDisagreement
        else None,
        "episodeProgression": bundle.episodeProgression.model_dump(mode="json")
        if bundle.episodeProgression
        else None,
        "identityAliasCount": len(bundle.identityAliases),
        "revision": bundle.revision,
    }


def dismiss_forward_suggestion(db: Session, project_id: str, suggestion_id: str) -> dict[str, Any]:
    from .forward import dismiss_suggestion

    bundle = load_bundle(db, project_id)
    ok = dismiss_suggestion(bundle, suggestion_id)
    save_bundle(db, bundle)
    return {"ok": ok, "projectId": project_id, "suggestionId": suggestion_id}


def answer_curiosity_thread(
    db: Session, project_id: str, thread_id: str, *, dismiss: bool = False
) -> dict[str, Any]:
    from .curiosity import dismiss_thread

    bundle = load_bundle(db, project_id)
    if dismiss:
        ok = dismiss_thread(bundle, thread_id)
    else:
        ok = False
        for t in bundle.curiosityThreads:
            if t.id == thread_id:
                t.state = "ANSWERED"
                ok = True
                break
    save_bundle(db, bundle)
    return {"ok": ok, "projectId": project_id, "threadId": thread_id}


def apply_identity_correction(
    db: Session,
    project_id: str,
    *,
    surfaces: list[str],
    canonical_name: str,
) -> dict[str, Any]:
    from .identity import learn_aliases_from_correction

    bundle = load_bundle(db, project_id)
    bundle.identityAliases = learn_aliases_from_correction(
        bundle.identityAliases, surfaces=surfaces, canonical_name=canonical_name
    )
    save_bundle(db, bundle)
    # Structural wiki path: reuse reorganize undo infrastructure when available
    preview = {
        "mergeSurfaces": surfaces,
        "canonicalName": canonical_name,
        "aliasMapSize": len(bundle.identityAliases),
        "note": "Aliases learned; Wiki merge proceeds via Reorganize / correction workflow with undo.",
    }
    return {"ok": True, "projectId": project_id, "preview": preview, "undoSupported": True}
