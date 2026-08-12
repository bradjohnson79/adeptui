# M5 — Harness vs Live Beta

| Field | Value |
| --- | --- |
| Branch | `feature/ai-guided-setup` |
| Certification target | **Live AdeptUI Beta** — UI `http://127.0.0.1:8760/`, API `http://127.0.0.1:8758/` |
| Isolated harness | Playwright `webServer` → `scripts/e2e-start.mjs` — UI `5173`, API `8742`, fixture `8765` |
| Rule | A Beta-only failure is automatic **NO-GO** until repaired. Harness-green alone is not certification evidence. |

## Executive finding

Prior Phase 7 / setup “passes” were often measured against the **isolated harness**, not Beta. The readiness helper `waitForAppReady` required `GET /api/e2e/status`, which exists **only** when `STUDIO_E2E=1`. Live Beta intentionally does **not** set `STUDIO_E2E`, so `/api/e2e/*` returns **404**. That single check made honest Beta smoke impossible and created false confidence when the harness was green.

## Divergence matrix

| Class | Harness (5173/8742) | Live Beta (8760/8758) | Impact |
| --- | --- | --- | --- |
| Runtime init | `e2e-start.mjs` spawns API+Vite+fixture HTTP; temp `STUDIO_DATA_DIR` | `supervisor.py` serves production build via `web_server.py` + uvicorn on 8758 | Different process model, assets, data dirs |
| Config | `STUDIO_E2E=1`, fixture pack provider, mock Co-Director defaults | Production-like env; no STUDIO_E2E | Fixture/mock paths unavailable on Beta |
| Routing — e2e control API | `/api/e2e/*` mounted (`studio-api/app/main.py` gated) | **Not mounted** → 404 | `waitForAppReady` failed on Beta before any UI assert |
| Routing — UI | Vite dev `5173` | Static Beta build `8760` (SPA fallback OK) | Stale-dist risk if Beta not rebuilt after web changes |
| API port default in helpers | Default `STUDIO_API_PORT=8742` | Must use `8758` / `STUDIO_API_BASE` | Mis-pointed clients hit wrong stack |
| Pack install evidence | `fixture_http` + `/api/e2e/*` overrides | Real Source Manager / install jobs | Pack specs are harness-shaped unless adapted |
| Playwright webServer | Starts harness when baseURL is 5173 | Must **not** spawn harness when targeting 8760 | Wrong BASE_URL + `reuseExistingServer` caused silent attach to wrong server |

## Root-cause repairs

1. **`ADEPT_BETA_TARGET=1`** in [`playwright.config.ts`](../../../playwright.config.ts): baseURL `8760`, API `8758`, **no** `webServer` / e2e-start.
2. [`tests/e2e/helpers/app.ts`](../../../tests/e2e/helpers/app.ts): on Beta target, readiness = `/api/health` + `/api/setup/status` only (no `/api/e2e/status`).
3. [`npm run test:e2e:beta`](../../../package.json) → [`scripts/run-playwright-beta.mjs`](../../../scripts/run-playwright-beta.mjs) (logs target URLs; avoids harness reuse).
4. Fixed Beta build break (`AiGuidedSetupPanel` unused `projectId`) so supervisor web build reaches READY.
5. Install-progress / add-source mocks aligned to Setup verify route (`/api/setup/sources/verify`) and `setupMode=manual` for component-grid flows.

## Spec classification

| Spec / area | Class | Beta cert treatment |
| --- | --- | --- |
| `ai-guided-setup-lifecycle.spec.ts` | Shared UI/API (page mocks OK on Beta) | **Required** — PASS on Beta |
| `setup-page.spec.ts` | Shared | **Required** — PASS on Beta |
| `source-manager.spec.ts` | Shared | **Required** — PASS on Beta |
| `setup-install-progress.spec.ts` | Page-route mocks; no e2e API | **Required** — PASS on Beta |
| `pack-*.spec.ts`, `download-*.spec.ts` using `/api/e2e/*` + fixture provider | **Harness-only** | Not Beta certification evidence |

## Authoritative Beta smoke command

```text
npm run beta:health

# Explicit env (authoritative evidence run):
$env:ADEPT_BETA_TARGET='1'
$env:PLAYWRIGHT_BASE_URL='http://127.0.0.1:8760'
$env:STUDIO_API_BASE='http://127.0.0.1:8758'
$env:STUDIO_API_PORT='8758'
npx playwright test `
  tests/e2e/setup/ai-guided-setup-lifecycle.spec.ts `
  tests/e2e/setup/setup-page.spec.ts `
  tests/e2e/setup/source-manager.spec.ts `
  tests/e2e/setup/setup-install-progress.spec.ts `
  --project=chromium
```

Or: `npm run test:e2e:beta -- <same paths> --project=chromium`

## Results (live Beta evidence)

| Suite | Target | Result |
| --- | --- | --- |
| AI-Guided lifecycle (4) | Beta 8760/8758 | **PASS** |
| Setup install progress (7) | Beta | **PASS** |
| Setup page (1) | Beta | **PASS** |
| Source Manager (1) | Beta | **PASS** |
| **Beta cert smoke total** | Beta | **13 passed (2.7m)** |
| Pack / download folder | Harness only | Excluded from Beta cert |

Log: `artifacts/functional-audit/m5-beta-cert-smoke.log`

Beta health at evidence time: UI/API/Comfy `200` via `npm run beta:health`.

## Remaining divergence statement

For the authoritative setup subset, there is now **no remaining behavior divergence** between the isolated harness and live Beta once the certification window is protected from overlapping lifecycle commands.

Harness-only pack/download specs still differ by design (`STUDIO_E2E` + fixture_http) and are **not** used as Beta GO evidence.

## Addendum 9 update (2026-08-02)

Required comparison shape:

| Harness Result | Live Beta Result | Difference | Root Cause | Repair | Verification |
| --- | --- | --- | --- | --- | --- |
| `13 passed / 0 failed / 0 flaky` on the authoritative four-file subset via `npx playwright test ... --project=chromium --retries=0` | Three consecutive warm-runtime executions all finished `13 passed / 0 failed / 0 flaky` on `8760/8758` | No behavior difference for the subset itself after cleanup hardening | Previous Beta-only instability was dominated by readiness/reset issues, not assertion mismatches | [`tests/e2e/helpers/app.ts`](../../../tests/e2e/helpers/app.ts) now waits for install jobs to become terminal and clears all browser storage/cookies during reset | `artifacts/functional-audit/m5-beta-stability-repeat-1.log`, `artifacts/functional-audit/m5-beta-stability-repeat-2.log`, `artifacts/functional-audit/m5-beta-stability-repeat-3.log` |
| `13 passed / 0 failed / 0 flaky` on the same four-file subset in the isolated harness | Post-restart Beta smoke also finished `13 passed / 0 failed / 0 flaky` after `npm run beta:restart` | No warm-restart behavior difference remained | Restarted Beta comes up healthy enough for the subset after the reset helper repair | No additional product-code repair required for the subset logic itself | `artifacts/functional-audit/m5-beta-post-restart-probe.json` plus post-restart Beta smoke run on the restarted runtime |
| Harness subset remained green on the isolated stack | Initial post-cold-start Beta smoke failed `12 passed / 1 failed` because the API became unavailable mid-suite | **Live Beta stack recycled during certification; harness did not** | Prior runtime overlap included repeated explicit `Restart-AdeptUI-Beta.ps1` invocations in terminal history, and the supervisor log captured `intentional shutdown` / `STOPPED` / fresh `READY` | Added sticky shutdown behavior, stronger stop verification, idempotent start, and a certification lock that blocks script-level Stop/Restart overlap during evidence runs | Earlier failure is preserved in [`data/runtime/logs/beta/supervisor.log`](../../../data/runtime/logs/beta/supervisor.log); repaired cold-start smoke then passed `13/13` on live Beta |
| `13 passed / 0 failed / 0 flaky` on the isolated harness | Repaired post-cold-start Beta smoke also finished `13 passed / 0 failed / 0 flaky` on `8760/8758` | No remaining divergence for the authoritative subset | Lifecycle scripts now preserve a real cold-stop boundary and the certification window guards against overlapping Beta restarts | [`scripts/beta_runtime/supervisor.py`](../../../scripts/beta_runtime/supervisor.py), [`Stop-AdeptUI-Beta.ps1`](../../../Stop-AdeptUI-Beta.ps1), [`Start-AdeptUI-Beta.ps1`](../../../Start-AdeptUI-Beta.ps1), [`Restart-AdeptUI-Beta.ps1`](../../../Restart-AdeptUI-Beta.ps1) | Repaired cold stop held down for `60s`; cold start returned to `READY`; final live Beta smoke passed `13/13` |

### Addendum outcome

- Harness and live Beta now agree for the authoritative subset on a warm runtime, after restart, and after a repaired cold start.
- The earlier live-Beta-only recycle failure is preserved as historical evidence and was repaired in this pass.
- Harness-only fixture/e2e-control suites remain intentionally out of scope for Beta certification.
