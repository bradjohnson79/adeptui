# Co-Director Foundation Playwright Certification — Phases 1.5–6

**Branch:** `feature/ai-guided-setup`  
**Workspace HEAD:** `fa09c99d6395c29461cdec4555055faad116c435`  
**Beta URL:** http://127.0.0.1:8760/  
**Suite:** `tests/e2e/codirector/codirector-foundation-2-6-autonomous-cert.spec.ts`  
**Final artifact run:** `docs/release-gate/codirector-final/artifacts/autonomous-cert/CODIRECTOR-AUTONOMOUS-CERT-2026-08-03T18-23-04-439Z/`

## Exact final verdict line

GREEN — CODIRECTOR FOUNDATION READY

## Disposable project

| Role | ID | Cleanup |
|---|---|---|
| Main cert | `38d28860-8eb0-478c-8c35-37142e1d2f1f` (`CODIRECTOR-FOUNDATION-CERT-…`) | 404 |
| Isolation | `7af9189e-cd7d-40a0-a41d-b875abaaa3f4` | 404 |

Post-run `CODIRECTOR-FOUNDATION*` residue: **0**

## Scenario results

| Gate | Result |
|---|---|
| Home UI create (Series / Web Series) | PASS |
| Harbor Signal intro | PASS |
| Character assimilation | PASS |
| Premise critique (foundation specialists + knowledge) | PASS |
| Cinematic staging (cinematography-led) | PASS |
| Correction / rejection | PASS |
| Missing foundations / draft plan | PASS |
| Collaboration Compare mode UI | PASS |
| Opening comparison | PASS |
| Readiness audit (no false mutate claims) | PASS |
| Reload persistence | PASS |
| Isolation | PASS |
| Failure injection | SKIP-ENV (Beta no `/api/e2e`) |

## Evidence

- Command: `ADEPT_BETA_TARGET=1 npx playwright test tests/e2e/codirector/codirector-foundation-2-6-autonomous-cert.spec.ts --retries=0`
- Result: **1 passed** in ~1.3m
- Unit regressions: **51 passed**
- Soft skips: `failure-injection-beta-no-e2e`

## Manual review path

1. Open http://127.0.0.1:8760/
2. Create a disposable Series → Web Series project
3. Open Co-Director → introduce a premise → request critique / staging → draft plan → Options → Working style Compare
4. Confirm replies feel like one partner (no specialist dump / scores)
5. Delete the disposable project when finished
