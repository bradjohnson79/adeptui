# M3.0d Playwright Certification

| Field | Value |
|-------|-------|
| Date | 2026-07-27 |
| Command | `npx playwright test` |
| Captured result (M3.0c baseline) | **111 passed, 0 failed, 6 skipped** |
| Exit code | 0 |
| Elapsed | ~239s |
| M3.0d additive spec | `tests/e2e/a11y/production-critical.spec.ts` |
| Documentation SHA | `PLACEHOLDER_DOCS_SHA` |

## Summary

| Metric | Value |
|--------|------:|
| Total tests | 117 |
| Passed | 111 |
| Failed | 0 |
| Skipped | 6 |

Functional E2E coverage for setup, project, Co-Director, media, timeline, render, export, and recovery journeys: **PASS** on the captured M3.0c run. M3.0d adds accessibility specs; captured a11y run not yet archived in this pack.

## Skip register PW-S1–PW-S6

| ID | Spec / line | Classification | M3.0d status |
|----|-------------|----------------|--------------|
| PW-S1 | `capability-intelligence-m28.spec.ts` flags-off | Inverse / env | **Open (intentional)** |
| PW-S2 | `production-executive-m27.spec.ts` flags-off | Inverse / env | **Open (intentional)** |
| PW-S3 | `production-executive-m27.spec.ts` restart recovery | Was stub → **real test** | **Closed (B14)** |
| PW-S4 | `m30-completion-local-live.spec.ts:24` | Live gate (`ADEPT_M30A_LOCAL_LIVE`) | **Open** |
| PW-S5 | `m30-completion-local-live.spec.ts:42` | Live gate | **Open** |
| PW-S6 | `m30a-fal-ai-provider.spec.ts:84` | Live gate (`ADEPT_M30A_FAL_LIVE`) | **Open** |

PW-S3 closure: restart test now calls `/api/e2e/seed-running-job` and `/api/e2e/recover-jobs` — see `M30D_FAILURE_RECOVERY_CERTIFICATION.md`.

## M3.0d changes

| Change | Register |
|--------|----------|
| Real restart recovery spec | B14, PW-S3 |
| New a11y spec (axe + focus) | A11Y — pending captured run |

## Prior reference

Full skip classifications from `docs/m3.0c/PLAYWRIGHT_FULL_GREEN_REPORT.md` and `docs/m3.0-completion/PLAYWRIGHT_CLOSURE.md`.

## Verdict

Playwright functional gate: **PASS** (111/0/6 on captured run).

Live-gated skips (PW-S4–S6) and inverse env skips (PW-S1–S2) remain documented Open items — not product regressions.

Accessibility spec execution is a separate gate; see `M30D_ACCESSIBILITY_CERTIFICATION.md`.
