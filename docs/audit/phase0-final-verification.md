# Phase 0 Final Verification Record

**Date/time (local):** 2026-07-23  
**Branch:** `feat/director-workspace`  
**Commit:** `2c5f61d574f27aed8c4f4adc70e9c993bb862aa1`  
**Working tree dirty:** yes (intentionally; broad uncommitted Phase 0 / Setup / Co-Director work)  
**OS:** Windows 10 (win32 10.0.26200)  
**Python:** 3.11.15 (`studio-api/.venv`)  
**Node:** v22.23.1  
**npm:** 10.9.8  

## Commands

| Command | Exit | Result |
|---------|------|--------|
| `python -m compileall app tests` (studio-api) | 0 | Compiled |
| `python -m pytest tests/test_setup_refactor.py -q --tb=short` (initial) | 0 | 19 passed, 5 warnings |
| `python -m pytest -q --tb=short` (initial full) | 0 | 28 passed, 5 warnings |
| `npx tsc -b` (studio-web) | 0 | 0 diagnostics (prior 15 baseline **resolved**) |
| `npm run lint` focused SetupWizard/App/ProjectEditor/api/setup | 0 | eslint absent; oxlint used |
| `npm run build` (studio-web) | 0 | production build OK |
| `python -m pytest tests/test_setup_refactor.py` (after diagnostic fix) | 0 | **20** passed, 5 warnings |
| `python -m pytest -q --tb=short` (after fix) | 0 | **29** passed, 5 warnings |

Supporting logs: `_gate_identity.txt`, `_gate_backend.txt`, `_gate_frontend.txt`, `_gate_backend_after_fix.txt`, `_gate_backend_full_after_fix.txt`, `_gate_api_json/`.

## Isolation audit

`tests/test_setup_refactor.py` fixture `setup_data_dir` uses `tmp_path` and monkeypatches `settings.data_dir` / `comfy_input_dir` (and clears `comfy_models_dir`). Focused tests do not write production `setup_state.json` or real user model trees as the fixture root.

## Read-only Setup API probes

Servers via `npm run dev` / `dev:restart` (`:8742`, `:5173`). **No** live `POST /api/setup/prepare`. **No** native `POST /api/setup/browse-path`.

| Endpoint | HTTP | Notes |
|----------|------|-------|
| `GET /api/health` | 200 | OK |
| `GET /api/setup/status` | 200 | `overall=ready` / Ready to Generate; counts ready=6, not_installed=4 |
| `GET /api/setup/detect` | 200 | Legacy compat |
| `GET /api/setup/state` | 200 | No secret-like values observed |
| `POST /api/setup/prepare/plan` | 200 | `required_actions=[]`, `can_run_unattended=true` (planning only) |
| `GET /api/setup/components/{id}/suggested-path` | 200 | Photoreal suggested path returned |
| OpenAPI | 200 | `browse-path`, `prepare/plan`, `status` registered |

Readiness honesty after fix: optional packs with configured empty dirs report `required_files_missing` (not `path_not_configured`); optional components do not force overall away from `ready`.

Path persistence: `PUT /api/setup/model-locations` with `{ "<component_id>": "<path>" }` persists into `model_locations` (exit/HTTP 200). Checkpoint Continue UI path covered by dialog open + Escape cancel in browser; recommended-path value confirmed via suggested-path API.

## Browser Setup Wizard

Verified against Vite `:5173` + live API during this gate session (before MCP browser became unavailable after `dev:restart`):

- Setup workspace opens for project (`?workspace=setup`); no blank legacy route
- Hierarchy: readiness (“Ready to Generate”) → System Status counts → Required → Optional → Advanced collapsed by default
- Ready cards (Python/FFmpeg/ComfyUI/LTX/Ollama/WAN): no primary Install/maintenance actions
- Optional Not Installed packs: single Install action
- Advanced `<details>` default `open=false`; summary keyboard-focusable
- Path checkpoint dialog: opened from Install; recommended path control + Continue/Cancel/Close present; Escape closed dialog (`dialogOpen=false`)
- Status region exposes counts via accessible name (not color-only); `aria-live` present on setup surface

Deferred (non-blocking):

- Native OS Browse dialog (`POST /api/setup/browse-path`) — not exercised interactively
- 200% zoom spot-check — not re-captured after restart
- Needs Attention / Update Available live UI states — statically inspected in `SetupWizard.tsx` / status primary-action rules (machine was overall ready)

## Defects found / fixes applied

### Stale diagnostic honesty (blocking → fixed)

**Before:** Live `GET /api/setup/status` could show `installation_path` set for an optional pack while `issue_code=path_not_configured` (“has no configured path”) because `build_status` reused a cached diagnostic that no longer matched `verify_component`.

**Fix:** `studio-api/app/setup/status.py` reconciles cached diagnostics against live verification (`_reconcile_diagnostic`); clears diagnostics when healthy; refreshes when `issue_code` diverges.

**Regression:** `test_status_refreshes_stale_path_not_configured_diagnostic`  
**After:** Photoreal reports `required_files_missing` / “directory is empty” with path set. Focused 20/20, full 29/29.

## Scenario classification

| Scenario | Classification |
|----------|----------------|
| Backend compile + focused/full pytest | automated and passed |
| Frontend tsc / oxlint / build | automated and passed |
| Read-only Setup API probes | automated and passed |
| Optional vs required readiness honesty | automated and passed (after fix) |
| Setup Wizard hierarchy / Ready / Advanced collapsed | manually verified |
| Path chooser Escape / Cancel / Close | manually verified |
| Recommended path + model_locations persistence | automated and passed (API) + manually verified (dialog chrome) |
| Native Browse dialog | deferred and non-blocking |
| Update Available / Needs Attention live cards | statically inspected |
| Live prepare / real installs | deferred and non-blocking (hard constraint) |
| Disk/permission failure matrix | statically inspected / deferred and non-blocking |
| 200% zoom a11y | deferred and non-blocking |

## Authorization recommendation

**Outcome B — GRANTED WITH CONDITIONS**

All blocking automated gates passed with captured exit codes. One honesty defect was found and fixed with a focused regression. Remaining gaps are bounded and non-blocking (native Browse, some failure-state UI live exercises, zoom re-check).
