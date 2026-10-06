# Setup Wizard Convergence Addendum

Governing report for removing the Setup Wizard as a second runtime authority.

**Verdict: GO — SETUP WIZARD NO LONGER A SECOND RUNTIME AUTHORITY**

One setup authority. One runtime authority. No overlap.a

| Authority | Owns |
|---|---|
| Setup Wizard | Install, paths, providers, presence checks, repair/reinstall, configuration diagnostics |
| Adept Runtime Supervisor | Start, stop, restart, health, recovery, lifecycle |

## Scope landed

Setup Wizard `BackgroundServicesSection` no longer exposes Start / Stop / Restart Studio API / Restart Comfy. Those calls are gone from `SetupWizard.tsx`.

Replaced with:

- **Adept Runtime — Managed Automatically**
- **Validate Runtime Configuration** — `GET /api/runtime-manager/validate-config` (paths only; does not start services)
- **Enable Recommended** — writes recommended supervisor config / Windows autostart
- **Repair Configuration** — existing repair workflow
- Windows autostart preference

Preserved elsewhere:

- Component install, missing-dependency cards, Advanced verify/repair/update/remove
- Startup modal auto-boot (`StartupSystemsGauge` still calls `runtimeManagerStart`)
- Settings → Local Runtime still reads health and remains a supervisor client for Advanced lifecycle
- Install-complete **Restart ComfyUI** on `InstallProgressCard` (reinstall handoff, not a Setup service manager)

## Live verification

| Check | Result |
|---|---|
| First-time / catalog setup still renders | PASS — Guided/Manual/AI-Guided still install; Runtime section now on all modes |
| Missing dependencies still detected | PASS — live Setup showed `42 Ready / 6 Not Installed / 6 Needs Attention` |
| Repair workflow still wired | PASS — Repair Configuration → `runtimeManagerRepair` |
| Startup modal still auto-boots | PASS — source contract: `StartupSystemsGauge` still calls `runtimeManagerStart` |
| No feature loses health | PASS — Settings Local Runtime still shows Start/Stop/Restart + health |
| No Setup lifecycle duplicate | PASS — live DOM: start/stop/restart-api/restart-comfy absent |
| Validate is not a launcher | PASS — unit: validate never calls start/stop/restart; source has no Setup start/stop/restart |

Playwright `tests/e2e/setup/adept-runtime-service.spec.ts` (`ADEPT_BETA_TARGET=1`):

- `1 passed` — Setup does not own lifecycle; Enable Recommended does not POST `/start` or `/restart-*`
- `1 skipped` — live `GET /validate-config` not loaded on current Studio API PID **62552** (no `--reload`)

Live Validate button on Vite `:5173` correctly reported **Could not check runtime configuration** (404). It did not POST start/stop/restart.

## Limitation

`GET /api/runtime-manager/validate-config` is implemented and covered by hermetic tests. The running Studio API process was started without reload (`uvicorn app.main:app --host 127.0.0.1 --port 8758`, PID **62552**). Canonical recycle (`scripts/restart_studio_api_only.py` and `POST /api/runtime-manager/restart-api`) reported the control plane as not running from this agent. Comfy was left untouched.

After the next authorized Studio API-only recycle, Validate will hit the new route. Do not restart Comfy to pick up this change.

## Tests

- `studio-api/tests/test_adept_runtime_service.py` — wizard source, startup modal auto-boot, validate-config does not start services
- `studio-api/tests/test_dual_background_services.py::test_settings_and_wizard_use_manager_actions`
- `studio-web/src/components/SetupWizard.comfyStart.test.ts` — **6 passed**
- Playwright setup runtime spec — **1 passed, 1 skipped**

## Runtime observe

| | |
|---|---|
| Review UI | `http://127.0.0.1:5173/` |
| Studio API | `http://127.0.0.1:8758/` PID **62552** |
| COMFY BEFORE | PID **74356** / health 200 / ready |
| COMFY AFTER | PID **74356** / health 200 / ready |
| COMFY RESTARTED? | **NO** |
| WHY? | Setup UI/API contract work only. Supervisor recycle was not available; Comfy was not touched. |

## Files

- `studio-web/src/components/SetupWizard.tsx`
- `studio-web/src/api.ts`
- `studio-web/src/components/SetupWizard.comfyStart.test.ts`
- `studio-api/app/runtime_manager/router.py`
- `studio-api/app/runtime_manager/service.py`
- `studio-api/app/runtime_manager/schemas.py`
- `studio-api/tests/test_adept_runtime_service.py`
- `studio-api/tests/test_dual_background_services.py`
- `tests/e2e/setup/adept-runtime-service.spec.ts`
