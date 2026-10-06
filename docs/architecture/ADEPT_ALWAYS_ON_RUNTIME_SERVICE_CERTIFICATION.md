# Adept Always-On Runtime Service — Certification

Governing architecture: `docs/architecture/ADEPT_ALWAYS_ON_RUNTIME_SERVICE.md`

Branch: `feat/character-creator-final-closure`  
HEAD: `b6156455e643d5fa430784b3130756f2d8038651`  
Date: 2026-08-31 (local 2026-08-30 evening continue)

No commit / no push.

## Verdict

**NO-GO — ADEPT ALWAYS-ON BACKGROUND RUNTIME SERVICE NOT FULLY CERTIFIED**

Exact blockers:

1. **Task Scheduler registration** — `AdeptRuntimeService` does not exist. Canonical registrar (`runtime_supervisor.windows_task.register_task`) was run. Windows returned Access Denied for both current-user `Register-ScheduledTask` and `schtasks /Create /SC ONLOGON`. Product raised `PrivilegeRequired` and did **not** fall back to Startup-folder, Desktop Comfy, Cursor ownership, or a second supervisor.
2. **NO-GO — REBOOT/LOGON AUTO-START NOT CERTIFIED** — this session did not reboot or prove AtLogOn start. That gate cannot pass until the task exists and a real logon is observed.

## Live authority preserved

| Role | PID | Result |
| --- | --- | --- |
| Runtime Service (`python -m runtime_supervisor serve`) | **75888** | Alive through API recycles, Qwen, and Playwright |
| Owned Comfy `:8188` | **22220** | Healthy, `owned:true`, same PID after API recycle and Qwen |
| Studio API `:8758` | recycled (last listener 70988) | Client only; reconnects to control plane `:8759` |

Original user authority Comfy **42496** was already dead before this continue (forensic `forrtl` window-CLOSE / owned-not-alive). Serve had recovered to **22220**. This certification used **22220** as the continuity baseline. Continuity was **not** claimed for 42496 → 22220.

`COMFY BEFORE: PID 22220`  
`COMFY AFTER: PID 22220`  
`COMFY RESTARTED?: NO`  
`WHY?:` API-only recycle and Qwen request. Serve 75888 left running.

GPU observe (read-only): Comfy 0.32.0, `cuda:0 NVIDIA GeForce RTX 5090`.

## Gate results

### Task Scheduler — FAIL (privilege)

Observed:

```text
Register-ScheduledTask : Access is denied.
schtasks /Create /SC ONLOGON → Access is denied.
schtasks /Query /TN AdeptRuntimeService → The system cannot find the file specified.
```

Product path: `PrivilegeRequired` / creator copy “Windows needs permission to start Background Services when you sign in. Approve that once. Adept will not use a weaker startup method.”

Legacy task still present (not retired — new task is not proven):

- `AdeptBetaBackendManager` — exists, Enabled, At logon, last run 2026-08-14. Comment still claims it starts Studio API + Comfy. Registrar must not silently replace this until `AdeptRuntimeService` is registered.

### API recycle continuity — PASS

Recycled Studio API only (`stop`/`start_studio_api`). Never `restart_all`, never Comfy stop/start.

- Serve remained **75888**
- Comfy remained **22220**, `:8188` healthy
- Control plane `GET /status` still `servicePid=75888`, `comfyPid=22220`, `owned=true`
- API reconnected to the existing control plane; it did not spawn Comfy

API process death during a later Qwen load also left serve + Comfy unchanged. API was started again as a client only.

### Setup Wizard E2E — PASS (wizard path)

```text
npm run test:e2e:beta -- tests/e2e/setup/adept-runtime-service.spec.ts --project=chromium --retries=0
1 passed (55.5s)
```

- Enable Recommended calls `POST /api/runtime-manager/enable-recommended`
- Does **not** call `POST /api/runtime-manager/start` / `start_all`
- UI `background-services-task-state` reports real Task Scheduler language (not registered / needs permission once)
- No second `:8188` owner appeared (still PID 22220)

### Qwen same-PID continuity — PASS

After API recycle:

- In-process `request_qwen()` → `ok`, `samePid=true`, `comfyPid=22220`, “Qwen Image Edit is ready.” (4.6s)
- `POST /api/runtime-manager/request-qwen` → HTTP 200, `success=true`, same message (4.4s)
- Live queue on **22220** ran a real Qwen Image Edit graph (`UNETLoader` + `TextEncodeQwenImageEditPlus`) and returned to idle. Same Comfy PID. Serve 75888 unchanged.

Live serve **75888** still has the old control-plane wrapper bug (`_payload(..., **result)` double-`ok`). Source is fixed; that handler is not reloaded without restarting the Runtime Service (forbidden for continuity). Product API path calls `request_qwen()` directly so Qwen does not require a serve restart.

### Reboot / logon — FAIL (not run)

**NO-GO — REBOOT/LOGON AUTO-START NOT CERTIFIED**

No reboot was performed. Auto-start cannot be proven while `AdeptRuntimeService` is unregistered.

## Mission report

### SETUP WIZARD LEGACY PATH FOUND

`BackgroundServicesSection` previously called `runtimeManagerStart` / `start_all`. That path is removed from the section. `start_all` no longer spawns Comfy.

### SETUP WIZARD FILES CHANGED

- `studio-web/src/components/SetupWizard.tsx` — Enable Recommended → `runtimeManagerEnableRecommended`; default Start-with-Windows on; privilege copy; live task-state line
- `studio-web/src/components/Settings/LocalRuntime.tsx` — “Starts when you sign in” from `taskRegistered`
- `studio-api/runtime_supervisor/windows_task.py` — `PrivilegeRequired`; current-user AtLogOn; no `/RU` password trap
- `studio-api/runtime_supervisor/bootstrap.py` — surfaces `needsElevation`
- `studio-api/runtime_supervisor/serve.py` — Qwen payload merge fix (needs next authorized serve start)
- `studio-api/app/runtime_manager/router.py` — `request-qwen` uses `request_qwen()` without wedging `get_status()`
- `studio-api/tests/test_adept_runtime_service.py`
- `tests/e2e/setup/adept-runtime-service.spec.ts`

### LEGACY STARTUP MIGRATION

No Startup-folder workaround. Legacy `AdeptBetaBackendManager` left in place until `AdeptRuntimeService` is registered. Retire only after the new task is proven.

### TASK SCHEDULER STATE

`AdeptRuntimeService`: **does not exist** (`needsElevation` / Access Denied).

### SETUP WIZARD E2E RESULTS

Playwright live Beta: **1 passed**. Enable Recommended ≠ `start_all`. UI shows real task state. Same Comfy PID.

### REBOOT + LOGON RESULTS

**Not run.** `NO-GO — REBOOT/LOGON AUTO-START NOT CERTIFIED`

### SINGLE-AUTHORITY VERIFICATION

- One live serve: PID 75888
- One `:8188` owner: PID 22220, owned
- Studio API is a client
- No Desktop Comfy adopted
- No Cursor-shell Comfy ownership
- Legacy scheduled task still exists and is the remaining competing *registration*, not a second live `:8188` supervisor

## Seven questions

1. **Does Setup Wizard now use AdeptRuntimeService?** Yes — Enable Recommended writes `runtime.json` and calls the canonical registrar. Registration is blocked by Windows privilege on this host.
2. **Can Setup Wizard still directly spawn Comfy anywhere?** No — wizard section does not call `start` / `start_all`; `start_all` does not spawn Comfy.
3. **Can Studio API still become Comfy owner?** No — API recycle and Qwen did not spawn or take `:8188`. Serve remains owner.
4. **Are legacy scheduled-task owners retired?** No — `AdeptBetaBackendManager` remains until the new task is registered.
5. **Do Settings and Setup Wizard use the same task registrar?** Yes — `runtime_supervisor.windows_task`.
6. **Does reboot/logon restore runtime without opening Adept UI?** **Not certified.**
7. **Is only one process authority supervising `:8188`?** Yes for the live process: serve 75888. Task Scheduler still has a legacy AtLogOn registration that must not be treated as retired.

## Tests

`pytest` `test_adept_runtime_service.py` + `test_headless_comfy.py` + `test_runtime_supervisor_lifecycle.py`: **48 passed**

Playwright: **1 passed, 0 failed** (`adept-runtime-service.spec.ts`)

## Review URLs

- Local creator UI: `http://127.0.0.1:5173/`
- Studio API: `http://127.0.0.1:8758/` (`/api/healthz` 200)

## What Windows needs next

One elevated Setup / installer registration of `AdeptRuntimeService` via the same registrar. After that, a real logon (Adept UI closed) to certify auto-start. Do not use Startup-folder or Session 0 as a substitute.
