# Adept v1.1 Production Readiness Policy

**Status:** GOVERNING for Production Assurance + Capability Registry truth  
**Policy version:** `v1.1`  
**Score meaning:** Adept Platform Production Readiness

This is the single readiness-meaning document for Status, Capability Registry, and Production Assurance. Do not encode a different meaning in UI copy, score caps, or per-file special cases.

Implementation authority: `studio-api/app/readiness/v11_policy.py`.

## Classes

| Class | Meaning | Status effect |
|---|---|---|
| **PLATFORM CRITICAL** | Adept cannot function meaningfully (API, storage). | Blocked · score ≤ 35 |
| **PRODUCTION CRITICAL** | A core v1.1 creator workflow cannot run (CREATE, local runtime, Timeline generate). | Blocked · score ≤ 35 |
| **WORKFLOW DEGRADED** | Core platform works, but a supported workflow loses meaningful capability. | Degraded · score ≤ 84 |
| **ADVISORY / REVIEW DEGRADED** | Production still functions; intelligence/review assistance is reduced. | Operational · score 85–94 · never Excellent and never 100 while the gap remains |
| **OPTIONAL** | Does not affect v1.1 readiness. | Visible note only — does not cap Excellent |

## Score labels

The gauge is **Adept Platform Production Readiness**, not infrastructure-only health.

| Band | When |
|---|---|
| Excellent | Operational and score ≥ 95 with no open registry, review, or production gaps |
| Operational | Production works; advisory/review gaps may remain (score 85–94) |
| Fair | Workflow-degraded, score 70–84 |
| Degraded | Workflow-degraded, score < 70 |
| Blocked | Platform or production-critical failure |

## VideoChat3 4B

Product contract: required for **Co-Director Temporal Continuity review**, not for Adept v1.1 core production.

- Setup catalog `videochat3_4b.required` stays `True`.
- Capability `codirector.video_intelligence.ready` stays honestly `MODEL_MISSING` / blocked when the model is absent.
- Readiness class: `advisory_review_degraded`.
- v1.1 requirement: `continuity_review`.
- Display: Temporal Continuity review is degraded. Generation still works.
- Scoring must not special-case the name VideoChat3.

Temporal Continuity law: unavailable perception must not deadlock generation.

## Fresh authority

Explicit Re-check (`forceRefresh=true`) and Deep Diagnostic invalidate the Capability Registry cache and the Status TTL cache, then consume a new snapshot.

Capability Registry blocked (any class) must appear on the same Status run. Status may not report 100 Operational while the canonical registry still has blockers after that Re-check.

Usable `DEGRADED` rows still appear. Production-class `DEGRADED` scores as workflow-degraded (≤84). Workflow/advisory `DEGRADED` scores as advisory (85–94). A Capability Registry probe timeout uses the advisory fallback so lost class cannot recreate the old “any high blocker → 84” path.

## Creator-path checks

Lightweight, no generation:

- CREATE path integrity
- Timeline generator truth
- Timeline context binding
- PoseCraft identity/navigation
- Co-Director grounded routing (knowledge foundation landed — not a second knowledge tree)

## Co-Director knowledge

A separate mission. Production Assurance only checks whether that foundation has landed. WAN answers are a live cross-check, not a knowledge rewrite.

## Deep Diagnostic

Read-only. It does not restart services, mutate config, install models, or write the score except by the same classification as a standard run.
