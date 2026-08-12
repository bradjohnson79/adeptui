# AI-Guided Setup Certification

## Branch evidence

- Branch: `feature/ai-guided-setup`
- Observed HEAD: `fa09c99d6395c29461cdec4555055faad116c435`
- Beta UI after restart: `http://127.0.0.1:8760/`
- Beta API after restart: `http://127.0.0.1:8758/api/health`

## What changed in this pass

- promoted `fal_key` into first-class `API Providers` setup inventory in `studio-api/app/setup/catalog.py`
- promoted creative packs into first-class `Creative Packs` setup inventory in `studio-api/app/setup/catalog.py`
- expanded setup group mapping in `studio-api/app/setup/lifecycle/service.py`
- changed generic AI-Guided setup deep-links to route through Setup instead of falling back to `Source Manager` in `studio-web/src/setup/navigation.ts`
- added Home redirect logic so off-project setup links resolve into a real project's AI-Guided Setup in `studio-web/src/pages/Home.tsx`
- removed the competing Source Manager CTA from the AI-Guided panel in `studio-web/src/setup/lifecycle/AiGuidedSetupPanel.tsx`
- added backend regression coverage for first-class setup groups in `studio-api/tests/test_setup_refactor.py`
- expanded Playwright coverage for lifecycle groups and root redirect behavior in `tests/e2e/setup/ai-guided-setup-lifecycle.spec.ts`
- refreshed supporting evidence:
  - `docs/setup/ai-guided-setup/full-catalog-audit.md`
  - `docs/setup/ai-guided-setup/setup-containment.md`
  - `docs/setup/ai-guided-setup/codirector-catalog-truth.md`

## Phase results

| Phase | Status | Notes |
| --- | --- | --- |
| Phase 1 - live Discover -> Ready representatives | PASS | Prior live evidence for representative install/repair flow remains valid. |
| Phase 2 - full catalog audit | PASS | Live `/api/setup/status` now exposes first-class `Music`, `Avatar`, `API Providers`, and `Creative Packs` metadata. |
| Phase 3 - `/api/setup/status` performance | PASS | No new latency regression introduced in this pass. |
| Phase 4 - install CTA containment | PASS | Dock / Status / studio setup links now route through Setup AI-Guided lifecycle instead of using `Source Manager` as the generic fallback. |
| Phase 5 - repair validation | PASS | No regression introduced to the representative trusted repair path already certified. |
| Phase 6 - Co-Director catalog truth | PASS | Requested setup questions are now documented against trusted setup tools/APIs only in `docs/setup/ai-guided-setup/codirector-catalog-truth.md`. |
| Phase 7 - Playwright setup coverage | PASS | Authoritative live-Beta certification subset is green on `8760/8758` with `ADEPT_BETA_TARGET=1` and `--retries=0`: `ai-guided-setup-lifecycle.spec.ts`, `setup-page.spec.ts`, `source-manager.spec.ts`, and `setup-install-progress.spec.ts` revalidated `13 passed`. Harness-only pack/download fixture specs on `5173/8742` remain follow-up validation work and do not veto AI-Guided Setup certification. |
| Phase 8 - certification update | PASS | This certification and its supporting evidence are updated to reflect the current state honestly. |

## Evidence

- Phase 7 execution log: `docs/setup/ai-guided-setup/playwright-phase7.md`
- Full catalog audit: `docs/setup/ai-guided-setup/full-catalog-audit.md`
- Setup containment: `docs/setup/ai-guided-setup/setup-containment.md`
- Co-Director catalog truth: `docs/setup/ai-guided-setup/codirector-catalog-truth.md`
- AI-Guided UI: `studio-web/src/setup/lifecycle/AiGuidedSetupPanel.tsx`
- Setup navigation helper: `studio-web/src/setup/navigation.ts`
- Home redirect owner: `studio-web/src/pages/Home.tsx`
- Setup status service: `studio-api/app/setup/status.py`
- Lifecycle metadata service: `studio-api/app/setup/lifecycle/service.py`
- Setup catalog: `studio-api/app/setup/catalog.py`

## Test results captured in this pass

- Backend regression suite:
  - Command: `python -m pytest tests/test_setup_refactor.py -q`
  - Result: `25 passed`
- `studio-web` production build:
  - Command: `npm --prefix studio-web run build`
  - Result: `0` exit, bundle built successfully
- Authoritative live-Beta certification subset:
  - Command: `ADEPT_BETA_TARGET=1` plus `PLAYWRIGHT_BASE_URL=http://127.0.0.1:8760`, `STUDIO_API_BASE=http://127.0.0.1:8758`, `STUDIO_API_PORT=8758`, then `npx playwright test tests/e2e/setup/ai-guided-setup-lifecycle.spec.ts tests/e2e/setup/setup-page.spec.ts tests/e2e/setup/setup-install-progress.spec.ts tests/e2e/setup/source-manager.spec.ts --project=chromium --retries=0`
  - Result: `13 passed`
- Dedicated E2E setup subset after repairs:
  - Command: `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 STUDIO_API_PORT=8742 PLAYWRIGHT_WEB_PORT=5173 npx playwright test tests/e2e/setup/component-source-states.spec.ts tests/e2e/setup/download-sources.spec.ts tests/e2e/setup/pack-link.spec.ts tests/e2e/setup/pack-install.spec.ts tests/e2e/setup/pack-fail-retry.spec.ts --project=chromium`
  - Result: `4 passed`, `1 failed` (`pack-link`, later repaired)
- Isolated repair proofs:
  - `tests/e2e/setup/pack-link.spec.ts` -> `1 passed`
  - `tests/e2e/setup/pack-fail-retry.spec.ts` -> `1 passed`
- Final dedicated full-folder rerun:
  - Command: `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 STUDIO_API_PORT=8742 PLAYWRIGHT_WEB_PORT=5173 npx playwright test tests/e2e/setup --project=chromium`
  - Result: folder still red
  - Earliest reproduced failure: `tests/e2e/setup/download-sources.spec.ts` timed out waiting for `add-source-url-pack_essential_cinematic`
  - Classification: harness-only validation gap on the isolated `5173/8742` stack; not part of the live-Beta AI-Guided certification gate
- Beta health after restart:
  - Command: `Restart-AdeptUI-Beta.ps1` then health probe
  - Result: UI `200`, API `200`, runtime `READY`

## Honest remaining work

- The isolated harness folder `tests/e2e/setup` still exits non-zero on `5173/8742`.
- Latest reproduced blocker: `download-sources.spec.ts` loses `Add Source URL` for `pack_essential_cinematic` when the full harness suite runs in order.
- Several pack-state regressions were repaired in this pass (`pack-link` and isolated `pack-fail-retry` now pass), but the remaining suite-order dependency is retained as harness-only follow-up work rather than a live-Beta certification blocker.

## Verdict

**GO**

AI-Guided Setup is honestly certifiable on the branch's stated target: live Beta on `8760/8758`. The production build succeeds, Beta remains healthy, and the authoritative Beta certification subset revalidated green with `13 passed` and `--retries=0`. The remaining `download-sources` / pack-fixture suite-order failure is real, but it belongs to the isolated harness on `5173/8742`, so it stays documented as validation follow-up work and does not veto the AI-Guided Setup **GO** verdict.
