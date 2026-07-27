# M3.0d PM Report — Manual User Beta Authorization

| Field | Value |
|-------|-------|
| Date | 2026-07-27 |
| Branch | `phase2/codirector-m2-9-production-suite` |
| Starting tip (M3.0d) | `aff00c131a464ee9cdf156fd8a2977016264b375` |
| Prior M3.0c impl / docs | `8ba6b62` / `5a854f1` |
| Provider manifest SHA (LOCKED) | `cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc` |
| Implementation SHA | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |
| Documentation SHA | `PLACEHOLDER_DOCS_SHA` |

---

## Final verdict

# NO — MANUAL USER BETA REMAINS CLOSED

---

This is a **binary** authorization decision. There is no "conditionally authorized" state for Manual User Beta.

## Rationale

### Cleared (supports future authorization)

| Gate | Evidence |
|------|----------|
| Backend final gate | 631 passed, 0 failed, 6 skipped |
| PY01–PY20 | All closed |
| Unified jobs UJ-1, UJ-2 | Inspect bridge + fal queue proof (reused) |
| Production situations S01–S12 | EXECUTED — `phase18-final-validation.json` |
| fal motion | Reused M3.0c Seedance proof — no new spend |
| B9, B13, B14, B17, B18, B19 | Closed with tests |
| Playwright functional | 111 passed, 0 failed (captured run) |
| Secret audit | CLEAN |
| Provider honesty | Local stills; fal motion; audio import-only; LTX/WAN NOT_PRODUCTION_READY |

### Blocking (prevents authorization)

| Blocker | Severity | Detail |
|---------|----------|--------|
| **Accessibility not GREEN** | **Critical for beta auth** | `M30D_ACCESSIBILITY_CERTIFICATION.md` — CONDITIONAL. Keyboard-only critical journeys and screen-reader certification not proven. axe spec added but captured green run not archived in this pack. PM rule: if a11y not fully proven GREEN → **NO**. |
| B16 live intelligence | High | Four materially different live brief digests not proven — limited-analysis code path only |
| PW-S4–S6 live gates | Medium | Local-live and fal-live Playwright specs not executed in this cert run (intentional; fal proof reused) |

## What changed in M3.0d

| Item | Outcome |
|------|---------|
| B9 | `normalize_orchestration_response` — Closed |
| B13 | syncEvent via `place_cue` Option A — Closed |
| B14 / PW-S3 | Real restart recovery via e2e endpoints — Closed |
| B19 | overrideReason required — Closed |
| Director→Editor | API handoff test — Closed |
| Backend gate | 631/0/6 — Pass |
| Accessibility spec | Added — **not sufficient for GREEN** |

## Required actions before YES

1. Execute and archive green run of `tests/e2e/a11y/production-critical.spec.ts` (axe critical=0 on all production-critical workspaces).
2. Complete keyboard-only critical journey certification across setup, Co-Director, Director, Editor, export.
3. Screen-reader spot-check on approvals and job status regions.
4. Close B16 with four live brief intelligence artifacts (or formally defer and delist claim).
5. Parent stamps `43a5c0f0152a39327e87b10de11fd55e5b16ad90` and `PLACEHOLDER_DOCS_SHA` after commit.

## Register snapshot

| Category | Closed | Open / In progress |
|----------|-------:|-------------------|
| B5–B21 (excl. B16) | 16 | B16 in progress |
| UJ-1–3 | 3 | 0 |
| PY01–20 | 20 | 0 |
| PW-S1–S6 | 1 (PW-S3) | 5 (intentional/live) |
| S01–S12 | 12 | 0 |
| A11Y | 0 | 1 (CONDITIONAL) |

## PM sign-off statement

Technical remediation substantially advanced on `phase2/codirector-m2-9-production-suite`. Backend, situations, fal motion reuse, unified jobs, and honesty fixes meet engineering gate criteria.

**Manual User Beta to external users remains CLOSED** until accessibility is proven GREEN and remaining product-evidence gaps are closed or honestly removed from beta scope.

**Authorized by:** M3.0d PM gate (documentation stamp pending)  
**Verdict:** **NO — MANUAL USER BETA REMAINS CLOSED**
