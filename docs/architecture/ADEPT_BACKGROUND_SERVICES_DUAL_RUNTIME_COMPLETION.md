# Adept Background Services Dual-Runtime — Completion

Governing doc: `docs/architecture/ADEPT_ALWAYS_ON_RUNTIME_SERVICE.md`  
Plan: `c:\Users\bradj\.cursor\plans\dual_background_services_70dd5400.plan.md` (not edited)

## Live PIDs (observed)

| Role | Port | PID | Notes |
| --- | --- | --- | --- |
| Manager `runtime_supervisor serve` | 8759 | **62224** | `owned` parent |
| Studio API Worker | 8758 | **76456** | `owned:true`, no `--workers 1` |
| Comfy Worker | 8188 | **77152** | `owned:true` after explicit Comfy isolation |
| Vite creator UI | 5173 | 62868 | HMR only |

Session isolation:

| Action | API PID | Comfy PID | Manager PID |
| --- | --- | --- | --- |
| Control-plane API restarts | 48524 → 71516 → 26200 → 75048 → **76456** | 22220 unchanged until Comfy test | 62224 unchanged |
| Explicit `POST :8759/restart-comfy` | 76456 unchanged | 22220 → **77152** | 62224 unchanged |
| `npm --prefix studio-web run build` | unchanged at that moment | unchanged | unchanged |

`GET http://127.0.0.1:8758/api/runtime-manager/status` (this session):

- `adeptRuntime.taskRegistered`: **false**
- `startWithWindows`: **false**
- `studioApiOwned`: true, health `healthy`
- `comfyPid`: 77152, `owned`: true
- creator copy: `Local image runtime is ready.`

`schtasks /Query /TN AdeptRuntimeService`: **not found** (`PrivilegeRequired` on register).  
`AdeptBetaBackendManager`: **still Ready** — not retired because the new task was never proven.

## Isolation

- Stale shim + live Adept listener: stop inspects `:8758` (unit).
- Foreign `:8758`: `PORT_CONFLICT`, no adopt (unit + live leftover class was the prior recycle defect).
- Frontend `npm --prefix studio-web run build`: manager/API/Comfy PIDs unchanged. `tsc -b` failed on **pre-existing unrelated** Character/Timeline/Spatial Map types. Vite/HMR does not restart runtimes.
- Playwright: Setup Wizard Adept Background Services section **passed**. Restart-API UI test raced the recycle (`ECONNRESET`); control-plane `POST /restart-api` is the authority proof.
- Reboot/logon: **E2E BLOCKED — reboot/logon not performed**. `AdeptRuntimeService` is not registered. Competing `AdeptBetaBackendManager` remains.

Setup/Settings copy when the task is missing: **“Not set to start when you sign in.”** It does not fake Start with Windows on.

## Co-Director corridor (managed API)

Project reused (not created): **Korri Anadriya** `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`.

- Non-stream `POST /api/codirector/chat` talked (“Generating”) but did **not** enqueue (`toolInvocations: []`).
- Product stream `POST /api/codirector/chat/stream`: “generating that locally at 16:9”
- Job `cb5ff152-7545-4356-9809-33d2ff514491`
- Params: `qwen2512`, 1920×1080, 16:9, `image.generate`
- Comfy prompt `fcef0291-91e6-4606-b567-392ce091351b` → `done`
- Asset `data/projects/beffd3d8-791d-4adf-9c4d-681ec9d4efb0/assets/imagegen_edit_95734457.png`
- Library `ab340a15-018b-4801-9265-41325495c2e2`

Co-Director routing was not changed. Stream is the certified product path.

## Tests

`56 passed` — `test_dual_background_services.py` + `test_runtime_supervisor_lifecycle.py` + `test_adept_runtime_service.py`.

Playwright `tests/e2e/setup/adept-runtime-service.spec.ts`: wizard section **passed**; Restart API / Restart Comfy UI tests **failed** (recycle race / afterEach `:8758` refuse). Isolation stands on control-plane PID proof.

## Health (handoff)

- `http://127.0.0.1:8758/api/healthz` → **200** `{"status":"ok"}`
- `http://127.0.0.1:5173/` → **200**
- `http://127.0.0.1:8188/system_stats` → **200** (read-only observe)

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | PASS (stream Co-Director + Settings/Wizard controls) |
| Frontend | PASS (Adept Background Services always visible; Restart API/Comfy wired) |
| API | PASS (proxies `:8759`; `restart-api` fire-and-forget) |
| Backend | PASS (one `serve` owns two children) |
| Persistence | PASS (Library asset remains on the same project) |
| Runtime | PASS (owned API + owned Comfy; Qwen job through Comfy) |
| Result | PASS (job `done`, asset on disk) |
| Reload | N/A for reboot/logon (blocked); asset file remains |
| Downstream | PASS (Library item `ab340a15-018b-4801-9265-41325495c2e2`) |

## Comfy protection

- `COMFY BEFORE: PID 22220 / health 200`
- `COMFY AFTER: PID 77152 / health 200`
- `COMFY RESTARTED?: YES`
- `WHY?:` explicit Comfy isolation test only (`POST :8759/restart-comfy`). Ordinary API/UI/build work did not restart Comfy.

## Verdicts

### Infrastructure (this session)

- One manager owns both children: **GO**
- API restart changes only API PID: **GO**
- Comfy restart changes only Comfy PID: **GO**
- Foreign ports not adopted/killed as success: **GO** (code + unit)
- Frontend build restarts neither: **GO**
- Production writers do not invent `C:\Users\bradj` / `D:\01_Models`: **GO**

### Scheduler / combined wizard

- Setup Wizard reports real Task Scheduler state: **GO** (honest “Not set…”)
- Combined reboot/logon + retire `AdeptBetaBackendManager`: **E2E BLOCKED — PrivilegeRequired; AdeptRuntimeService not registered**
- Playwright Restart API/Comfy UI: **E2E FAILED** (recycle race). Control-plane isolation still **GO**.

### Co-Director

`GO — CODIRECTOR LIVE IMAGE GENERATION ON MANAGED API E2E CERTIFIED`

Limitation: non-stream `/chat` does not attach jobs. Creator UI uses `/chat/stream`.

### Combined product

**NO-GO — FULL-STACK E2E NOT VERIFIED** for “Start with Windows / reboot owner” because the new scheduled task is not registered and the retired competing task is still present.

Session-owned dual-runtime isolation and the Co-Director stream corridor job are verified.

## Independent owner review

Law #27 requested `gpt-5.4-medium`; that slug is **unavailable**. Reviewers ran as **inherit**.

Two inherit reviewers (Law #27 `gpt-5.4-medium` unavailable):

| Q | A | B | Primary |
| --- | --- | --- | --- |
| 1 Competing owner besides `serve` | YES | YES | **YES** — `AdeptBetaBackendManager` still registered; `start_all` can spawn `:8758` if `:8759` is down; CLI `watch` can start children |
| 2 API restart changes Comfy | NO | NO | **NO** |
| 3 Comfy restart changes API | NO | NO | **NO** |
| 4 Stale shim blocks live replace | YES (required: stop retargets) | NO (does not block) | **NO** — stop inspects `:8758` and recycles |
| 5 Foreign adopt/kill as success | NO | NO | **NO** |
| 6 Fake Start with Windows | YES | NO | **NO after honesty fix** — task copy is real; checkbox no longer defaults on or trusts local merge over server `actual_start_with_windows()` |
| 7 Frontend build restarts GPU/API | NO | NO | **NO** |
| 8 Hardcoded writer paths | NO | NO | **NO** |
| 9 Unrelated product edits | NO | NO | **NO** for this mission’s files (worktree also has prior dirty Character/Timeline/CD work) |
| 10 API self-kill as owner | NO | NO | **NO** — proxies `:8759`; `restart-api` is fire-and-forget |

Blocking YES after primary reconcile: **Q1 only**.

## Residual

- Windows will not start the new manager at logon until the creator approves Task Scheduler once.
- Competing `AdeptBetaBackendManager` remains registered until that approval (plan: retire only after the new task is proven).
- `beta:start` / `start_all` still spawn Studio API directly when the manager is down (bootstrap leftover).
- Production `tsc` build is red on unrelated Character/Timeline/Spatial Map types.
- Playwright restart specs need recycle-tolerant polling (not a lifecycle-owner defect).
