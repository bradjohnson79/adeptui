# Adept UI — Playwright & Setup Wizard Summary Report

**Date:** 2026-07-24  
**Working branch:** `phase1b/download-queue-install-receipts`  
**Backup branch:** `audit/pre-playwright-functional-audit`  
**Overall verdict:** PASS — Phase 0.5 + 1A preserved; Phase 1B download queue gated at **20/20** `@critical`  

**Phase 1:** See `docs/architecture/SOURCE_MANAGER_PHASE1_PLAN.md` and `PHASE1B_DOWNLOAD_ENGINE_PLAN.md`.  
Phase 1A: source records + Source Manager route.  
Phase 1B: persistent download queue, real progress/ETA, receipts, Active Downloads / Install History — report in `docs/audit/PHASE1B_DOWNLOAD_QUEUE_IMPLEMENTATION_REPORT.md`.

---

## 1. Executive summary

This report consolidates Phase 0.5 Playwright functional audit work and Setup Wizard product work completed on Adept UI (Gen Studio). The outcome is a deterministic browser test harness, a green critical suite (17 tests), durable pack-install workflows, Download Sources (GitHub / Hugging Face CLI + manual URL), and several defect fixes proven under clean-room restart conditions.

| Area | Outcome |
|------|---------|
| Playwright harness | Delivered and documented |
| Critical E2E suite | **17 passed / 0 failed** |
| Full deterministic E2E | **17 passed / 0 failed** (same suite; all specs tagged `@critical @isolated`) |
| Setup Wizard packs | Empty-folder install, link-existing, fail/retry, interrupt recovery |
| Download Sources | CLI cards + Add Source URL verify-before-save |
| Clean-room validation | Stop → ports free → fresh start → suites pass; API stayed alive |
| Unit tests (download sources) | **19 passed** |
| Production model downloads | None performed (fixture ZIPs only) |

---

## 2. Scope of work

### 2.1 Playwright functional audit (Phase 0.5)

Goals achieved:

1. Backup branch + architecture documentation  
2. E2E-only browse path (`STUDIO_E2E` + `forced_path`)  
3. Mock pack provider (`fixture_http` + local fixture HTTP server)  
4. Root Playwright config, scripts, AuditObserver, artifacts  
5. Critical specs: smoke, setup/packs, projects, Co-Director, GPU, nav, a11y, responsive  
6. Fix loop with evidence  
7. Clean-room final validation + reports  

### 2.2 Setup Wizard product work (related)

1. Split empty-folder install destination vs link-existing `pack.json` validation  
2. UI actions: Download and Install, Choose Location, Link Existing, Check Again  
3. Richer release diagnostics (no tokens)  
4. Operation failure isolation + stale configuring recovery + FE backoff  
5. Download Sources: GitHub CLI / Hugging Face CLI / manual URL / overrides / security  

---

## 3. Architecture

### 3.1 Runtime stack under test

| Layer | Detail |
|-------|--------|
| Frontend | React 19 + Vite 8 — `http://127.0.0.1:5173` |
| Backend | FastAPI + uvicorn — `http://127.0.0.1:8742` (no `--reload` in E2E) |
| Fixture pack server | `http://127.0.0.1:8765` (`ADEPT_PACK_PROVIDER=fixture_http`) |
| Data | Isolated `STUDIO_DATA_DIR` (never user `data/`) |
| Setup entry | `/project/{id}?workspace=setup` (no standalone `/setup` route) |

### 3.2 Harness commands

```bash
npm run e2e:stop          # free ports 5173, 8742, 8765
npm run e2e:start         # fixture + API + Vite; ready gate
npx playwright test --grep "@critical" --retries=0
npx playwright test --retries=0
npm run test:e2e:critical
npm run audit:functional
```

### 3.3 Key environment variables

| Variable | Role |
|----------|------|
| `STUDIO_E2E=1` | Forced browse path + `/api/e2e/*` controls |
| `STUDIO_DATA_DIR` | Temp isolated studio data |
| `ADEPT_PACK_PROVIDER=fixture_http` | Deterministic pack releases |
| `ADEPT_PACK_FIXTURE_BASE_URL` | Fixture server base |
| `ADEPT_CLI_MOCK_JSON` / `POST /api/e2e/cli-mock` | Mock GitHub/HF CLI detection for E2E |
| `PLAYWRIGHT_BASE_URL` | Default `http://127.0.0.1:5173` |

### 3.4 Folder picker in E2E

Production uses native OS dialogs via `POST /api/setup/browse-path`.  
With `STUDIO_E2E=1`, the same endpoint accepts `forced_path`. The UI sends it only when Playwright sets `window.__ADEPT_E2E_FORCED_PATH__`.

---

## 4. Playwright suite inventory

All current specs are tagged `@critical @isolated` (17 tests after Download Sources).

| Spec | Coverage |
|------|----------|
| `smoke/startup.spec.ts` | App shell, healthy API, no render-phase warnings |
| `setup/setup-page.spec.ts` | Setup cards render; details expand |
| `setup/pack-install.spec.ts` | Empty folder accepted for download+install; persist |
| `setup/pack-link.spec.ts` | Empty rejected; valid link; wrong pack id rejected |
| `setup/pack-fail-retry.spec.ts` | Failed download keeps API alive; UI retry succeeds |
| `setup/pack-interrupt.spec.ts` | Stale configuring → interrupted / recoverable |
| `setup/pack-release-diagnostics.spec.ts` | No releases / no matching asset diagnostics |
| `setup/download-sources.spec.ts` | CLI cards + Add Source URL verify-before-save |
| `projects/project-crud.spec.ts` | Create, open, rename, persist, cleanup |
| `codirector/provider-states.spec.ts` | Survives unavailable Ollama without crash |
| `resilience/gpu-comfy.spec.ts` | GPU/health tolerate optional services |
| `resilience/navigation.spec.ts` | Major routes, refresh, back/forward |
| `a11y/critical.spec.ts` | Axe critical violations on setup |
| `responsive/viewports.spec.ts` | 1920 / 1440 / 1280 / 1024 |

### Tags (future / opt-in)

- `@local` — optional local services  
- `@external` — live GitHub / HF / Ollama / Comfy  
- `@large-download` — disabled by default  

---

## 5. Final validation results

### 5.1 Clean-room procedure (executed)

1. `npm run e2e:stop`  
2. Confirmed ports **5173 / 8742 / 8765 FREE**  
3. `npm run e2e:start` with new `STUDIO_DATA_DIR`  
4. Ready gate: health, setup status, fixture, Vite  
5. Critical suite → **17/17**  
6. Full deterministic suite → **17/17**  
7. API health **200** after both runs; api.log Traceback **0**

### 5.2 Signal checks (final clean-room observer)

| Check | Result |
|-------|--------|
| React duplicate-key warnings | 0 |
| Render-phase state updates | 0 |
| Console `Failed to fetch` | 0 (was 18 before AbortController fix) |
| Page errors | 0 |
| API 5xx | 0 |
| Stuck Configuring / installing | 0 |
| Active / orphaned setup ops | none |
| `net::ERR_ABORTED` | Expected on SPA navigation (not app errors) |

### 5.3 Supporting gates

| Gate | Result |
|------|--------|
| `pytest` pack suites (earlier) | 33 passed |
| `pytest test_download_sources.py` | 19 passed |
| `studio-web` lint | exit 0 (pre-existing hook warnings) |
| `studio-web` tsc / build | pass |

---

## 6. Defects found and corrected

### 6.1 Harness / platform

| Defect | Fix |
|--------|-----|
| Windows spawn of Vite/`npm.cmd` unreliable | Spawn via `node …/vite.js`, `shell: true` |
| API `--reload` flaky under E2E | `e2e-start` runs uvicorn without reload |
| Broad locators flaky (`Setup Wizard`, Create) | Scope to `.setup-wizard-page`, explicit labels |
| Checkpoint confirm assumed “Continue” | Click dialog `.row-actions button.primary` (“Download and Install”) |
| Stale setup dialogs block clicks | `dismissSetupDialogs` helper |

### 6.2 Pack install / status

| Defect | Fix |
|--------|-----|
| Empty install dest vs link-existing conflated | Split validation paths |
| Fixture packs shown `download_unavailable` | Cached fixture release → installable `not_installed` |
| Duplicate React key `ltx23_ic_lora_ingredients` | Removed duplicate catalog entry |
| Fail-retry false positive on word “download” | Wait on operation id → `failed`, then UI retry |
| Install stuck / race on API checkpoint | Prefer UI path; wait for terminal op status |

### 6.3 Frontend resilience

| Defect | Fix |
|--------|-----|
| Blank crash screens | `ErrorBoundary` in App |
| Co-Director workspace bind instability | Bind effect deps / ref pattern |
| ProjectEditor `getProject` “Failed to fetch” on nav | `AbortController` + `isAbortError` / `isNavigationFetchFailure`; no setState after unmount; don’t log expected aborts |

### 6.4 Classification of `getProject` Failed to fetch

- **Type:** Expected request cancellation mishandled as application error  
- **Not:** API 5xx or backend exit  
- **Evidence:** Clean-room console FTF 18 → 0 after abort-aware refresh  

---

## 7. Setup Wizard — product capabilities delivered

### 7.1 Pack workflows

- **Download and Install** into empty / new folder  
- **Choose Install Location** (destination only)  
- **Link Existing Folder** (requires valid `pack.json`)  
- **Check Again** (refresh release cache)  
- Fail / retry without killing API  
- Interrupt / recover stale configuring operations  
- Release diagnostics when no release / no matching asset  

### 7.2 Download Sources (new)

Setup section **Download Sources** with cards for:

- GitHub CLI — detect, install (winget/choco guided), sign-in guide, verify  
- Hugging Face CLI — detect `hf` / `huggingface-cli`, pip-into-venv guided install, sign-in, verify  

Per pack: **Add Source URL** dialog:

1. Paste GitHub or HF URL  
2. Verify Source (no download yet)  
3. Preview files  
4. Save as source override (removable; defaults recoverable)  

Security highlights:

- HTTPS-only (localhost HTTP only in `STUDIO_E2E`)  
- Allowlisted hosts / CDN suffixes  
- Reject `file://`, SMB, private IPs  
- Block source archives as Essential pack installs  
- Never display tokens; redact auth-like strings in logs  

### 7.3 Pack source resolution order (current)

1. Verified per-component user override  
2. Explicit manifest / direct URL  
3. `fixture_http` when selected (E2E)  
4. GitHub Releases when configured  
5. Manual Add Source URL / HF path  
6. Link Existing Folder  

---

## 8. Artifacts & documentation

| Artifact | Path |
|----------|------|
| This summary | `docs/audit/PLAYWRIGHT_SETUP_WIZARD_SUMMARY_REPORT.md` |
| Playwright architecture | `docs/audit/PLAYWRIGHT_FUNCTIONAL_AUDIT_ARCHITECTURE.md` |
| Download Sources impl report | `docs/audit/DOWNLOAD_SOURCES_IMPLEMENTATION_REPORT.md` |
| Clean-room audit report | `artifacts/functional-audit/AUDIT_REPORT.md` |
| Gate JSON | `artifacts/functional-audit/gate-results.json` |
| Observer log | `artifacts/functional-audit/audit-results.json` |
| E2E logs | `artifacts/functional-audit/logs/` |
| HTML Playwright report | `playwright-report/` |
| E2E helpers / specs | `tests/e2e/` |

---

## 9. Remaining limitations & non-blockers

| Item | Severity | Notes |
|------|----------|-------|
| Axe `aria-prohibited-attr` on Setup | Medium | Observer High; critical a11y gate still green |
| Full CLI download job pipeline | Planned | Verify + override shipped; progress/cancel/resume/atomic finalize still to deepen |
| Live private GitHub/HF installs | External | Need real CLI auth; CI uses mocks |
| HF include/exclude pattern editor | UX polish | Preview list exists |
| Pre-existing oxlint hook warnings | Low | Lint exit 0 |
| `@external` / large downloads | Out of scope | Opt-in; not run in critical suite |

---

## 10. How to re-run clean-room validation

```bash
npm run e2e:stop
# confirm 5173, 8742, 8765 free
npm run e2e:start
npx playwright test --grep "@critical" --retries=0
npx playwright test --retries=0
# from studio-api:
.\.venv\Scripts\python.exe -m pytest tests\test_download_sources.py -q
# from studio-web:
npm run lint
npx tsc -b
```

**Completion criteria met:** suites passed from a fully stopped environment with a freshly started E2E stack; backend remained alive for the entire final run.

---

## 11. Related prior Setup Wizard work (context)

Earlier in the same product line (not all re-executed in the final clean-room):

- Pack install workflow fix (empty dest vs link-existing) — `docs/audit/PACK_INSTALL_WORKFLOW_FIX.md` (if present)  
- Operation crash recovery and FE polling backoff  
- GitHub release resolver diagnostics without exposing tokens  

Together with Phase 0.5 Playwright, these form the current Setup Wizard reliability baseline.
