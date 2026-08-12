"""Promote / rollback category-scoped certification evidence overlays."""

from __future__ import annotations

from typing import Any, Optional

from .benchmark_eval import CERTIFICATION_SAMPLE_THRESHOLD, evaluate_category
from .benchmark_models import (
    CategoryEvidence,
    CertificationStatusV2,
    EvidenceOverlay,
    PromptStrategyRecommendation,
)
from .benchmark_store import load_evidence, load_overlay, save_evidence, save_overlay
from .errors import PromptIntelligenceError
from .models import utc_now_iso
from .profiles import resolve_profile

INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
CERTIFICATION_REFUSED = "CERTIFICATION_REFUSED"
EVIDENCE_NOT_FOUND = "EVIDENCE_NOT_FOUND"
ROLLBACK_UNAVAILABLE = "ROLLBACK_UNAVAILABLE"

_STRATEGY_TO_STATUS: dict[str, CertificationStatusV2] = {
    "bilingual-subtle": "certified_subtle",
    "bilingual-balanced": "certified_balanced",
    "bilingual-strong": "certified_strong",
    "refined-english": "english_preferred",
    "creator": "english_preferred",
}


def promote_strategy(
    *,
    provider_id: str,
    model_revision: str,
    domain: str,
    category: str,
    strategy: str,
    profile_id: Optional[str] = None,
    profile_version: Optional[str] = None,
    force: bool = False,
) -> dict[str, Any]:
    evidence = load_evidence(provider_id, model_revision, domain, category)
    if not evidence:
        evidence = evaluate_category(
            provider_id=provider_id,
            model_revision=model_revision,
            domain=domain,
            category=category,
        )
    if evidence.stale and not force:
        raise PromptIntelligenceError(
            CERTIFICATION_REFUSED,
            "Evidence is stale after model/workflow revision change; revalidate first.",
            details={"status": evidence.status},
        )
    thin = (
        evidence.status == "insufficient_evidence"
        or evidence.sampleCount < CERTIFICATION_SAMPLE_THRESHOLD
    )
    if thin and not force:
        raise PromptIntelligenceError(
            INSUFFICIENT_EVIDENCE,
            f"Promotion refused: need>={CERTIFICATION_SAMPLE_THRESHOLD} samples/strategy.",
            details={
                "sampleCount": evidence.sampleCount,
                "status": evidence.status,
                "scoresByStrategy": evidence.scoresByStrategy,
            },
        )
    if strategy.startswith("bilingual-") and evidence.status in ("not_tested", "benchmarking") and not force:
        raise PromptIntelligenceError(
            CERTIFICATION_REFUSED,
            "Cannot promote bilingual without evaluation evidence.",
            details={"status": evidence.status},
        )

    profile = resolve_profile(provider_id=provider_id, model_version=model_revision, domain=domain)  # type: ignore[arg-type]
    pid = profile_id or profile.profileId
    pver = profile_version or profile.profileVersion

    prior_overlay = load_overlay(pid, pver)
    previous = evidence.model_dump(mode="json")

    new_status = _STRATEGY_TO_STATUS.get(strategy, "experimental")
    evidence.status = new_status
    evidence.recommendedStrategy = strategy  # type: ignore[assignment]
    evidence.promotedAt = utc_now_iso()
    evidence.previousOverlay = prior_overlay
    evidence.stale = False
    evidence.auditLog.append(
        {
            "at": utc_now_iso(),
            "action": "promote",
            "strategy": strategy,
            "status": new_status,
            "profileId": pid,
            "profileVersion": pver,
        }
    )
    save_evidence(evidence)

    rec = PromptStrategyRecommendation(
        strategy=strategy,  # type: ignore[arg-type]
        status=new_status,
        confidence=evidence.confidence,
        sampleCount=evidence.sampleCount,
        reason=f"Promoted {strategy} for {domain}/{category}",
        evidenceVersion=evidence.evidenceVersion,
        category=category,
        domain=domain,
        providerId=provider_id,
        modelRevision=model_revision,
    )
    # Merge into overlay
    existing_recs = []
    if prior_overlay and isinstance(prior_overlay.get("recommendations"), list):
        existing_recs = [
            r
            for r in prior_overlay["recommendations"]
            if not (
                r.get("category") == category
                and r.get("domain") == domain
                and r.get("providerId") == provider_id
                and r.get("modelRevision") == model_revision
            )
        ]
    existing_recs.append(rec.model_dump(mode="json"))
    overlay = EvidenceOverlay(
        profileId=pid,
        profileVersion=pver,
        recommendations=[PromptStrategyRecommendation.model_validate(r) for r in existing_recs],
        updatedAt=utc_now_iso(),
    )
    path = save_overlay(overlay.model_dump(mode="json"))
    return {
        "ok": True,
        "evidence": evidence.model_dump(mode="json"),
        "overlayPath": str(path),
        "recommendation": rec.model_dump(mode="json"),
        "previousOverlay": previous.get("previousOverlay"),
    }


def rollback_strategy(
    *,
    provider_id: str,
    model_revision: str,
    domain: str,
    category: str,
    profile_id: Optional[str] = None,
    profile_version: Optional[str] = None,
) -> dict[str, Any]:
    evidence = load_evidence(provider_id, model_revision, domain, category)
    if not evidence:
        raise PromptIntelligenceError(EVIDENCE_NOT_FOUND, "No evidence to rollback.", details={})
    prior = evidence.previousOverlay
    if not prior:
        # Soft rollback: reset to not_tested
        evidence.status = "not_tested"
        evidence.recommendedStrategy = None
        evidence.auditLog.append({"at": utc_now_iso(), "action": "rollback", "mode": "reset_not_tested"})
        save_evidence(evidence)
        profile = resolve_profile(provider_id=provider_id, model_version=model_revision, domain=domain)  # type: ignore[arg-type]
        pid = profile_id or profile.profileId
        pver = profile_version or profile.profileVersion
        overlay = load_overlay(pid, pver) or {"profileId": pid, "profileVersion": pver, "recommendations": []}
        recs = [
            r
            for r in (overlay.get("recommendations") or [])
            if not (
                r.get("category") == category
                and r.get("domain") == domain
                and r.get("providerId") == provider_id
                and r.get("modelRevision") == model_revision
            )
        ]
        overlay["recommendations"] = recs
        path = save_overlay(overlay)
        return {
            "ok": True,
            "mode": "reset_not_tested",
            "evidence": evidence.model_dump(mode="json"),
            "overlayPath": str(path),
        }

    profile = resolve_profile(provider_id=provider_id, model_version=model_revision, domain=domain)  # type: ignore[arg-type]
    pid = profile_id or profile.profileId
    pver = profile_version or profile.profileVersion
    path = save_overlay(prior)
    evidence.status = "not_tested"
    evidence.recommendedStrategy = None
    evidence.previousOverlay = None
    evidence.auditLog.append({"at": utc_now_iso(), "action": "rollback", "mode": "restore_prior_overlay"})
    save_evidence(evidence)
    return {
        "ok": True,
        "mode": "restore_prior_overlay",
        "evidence": evidence.model_dump(mode="json"),
        "overlayPath": str(path),
    }


def certification_status(
    *,
    provider_id: str,
    model_revision: str,
    domain: str,
    category: str,
) -> dict[str, Any]:
    evidence = load_evidence(provider_id, model_revision, domain, category)
    if not evidence:
        return {
            "ok": True,
            "status": "not_tested",
            "providerId": provider_id,
            "modelRevision": model_revision,
            "domain": domain,
            "category": category,
        }
    return {"ok": True, "evidence": evidence.model_dump(mode="json")}
