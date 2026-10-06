# Adept Background Services — Dual Runtime (canonical)

One manager owns two independent children. Do not add a fourth owner.

## Authority map

**CANONICAL owner:** `python -m runtime_supervisor serve` (AdeptRuntimeService).

The manager:

1. Validates `%LOCALAPPDATA%\Adept\Runtime\runtime.json`.
2. Starts the loopback control plane on `:8759`.
3. Starts **owned** Studio API Worker (`127.0.0.1:8758`) when `studioApi.enabled`.
4. Starts **owned** headless Comfy Worker (`127.0.0.1:8188`) when configured.
5. Watches each child independently. API crash recovers API only. Comfy crash recovers Comfy only. Busy Comfy is not dead.

**One Task Scheduler entry:** `AdeptRuntimeService` starts the manager only. The manager starts the children. Registration uses `runtime_supervisor.windows_task.register_task`. If Windows denies current-user create, the registrar shows one UAC prompt. Success is only `schtasks /Query /TN AdeptRuntimeService`. Never fake Start with Windows from a preference file.

**MUST RETIRE as production owners** (thin-client or diagnostic only):

- `scripts/beta_runtime/supervisor.py` (`--workers 1`, `data/runtime/beta/status.json`)
- `scripts/beta-backend/BetaBackendCommon.ps1`
- Scheduled task `AdeptBetaBackendManager` and `.runtime/beta-backend/autostart_bootstrap.ps1`
- Standalone CLI `watch` / `Watch-AdeptBetaBackend.ps1` beside serve — diagnostic status only; they do not start children
- `npm run beta:start` / `start_all` / `restart_all` / `stop_all` — thin clients of `:8759`. If the manager is down they may `start_task()` (manager only) or fail closed. They must not spawn uvicorn or Comfy.
- `scripts/restart_studio_api_only.py` as a spawn owner — it is a thin client of `POST :8759/restart-api`
- Repo leftover PID stores (`.runtime/supervisor`, `pids/studio_api.pid`) as authority

**DIAGNOSTIC ONLY:** health probes, Get-Adept*Status, MCP. MCP does not own or restart Comfy.

**MiniMax `:8192`:** observe only. Do not absorb.

## Isolation contract

- `POST /restart-api` must change only the Studio API PID. Comfy PID stays the same.
- `POST /restart-comfy` must change only the Comfy PID. API PID stays the same.
- Foreign port owners are never adopted or killed. Healthy unknown `:8758` / `:8188` is `PORT_CONFLICT`.
- Frontend builds and Vite/HMR restart neither child.
- Production config writers must not hardcode `C:\Users\bradj` or `D:\01_Models`.

## Stale-PID contract

1. Record the **port-owner PID** after bind, not the venv shim.
2. Spawn uses `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP`. Do **not** use `DETACHED_PROCESS`.
3. Canonical API command: `studio-api/.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8758`. No `--workers 1`.
4. If the recorded PID is gone, classify `:8758`. Free → clear. Adept uvicorn that this manager started (or owner-authorized migration) → treat as the child. Foreign → `PORT_CONFLICT`.
5. Never write `owned=false` reuse as success.

## Control plane

Loopback `:8759` + token. Hosted Origin remains 403.

- `GET /status` — manager + API + Comfy
- `POST /start-api` `/stop-api` `/restart-api`
- `POST /start-comfy` `/stop-comfy` `/restart-comfy`
- `POST /start` `/stop` — both children independently

Studio API `/api/runtime-manager/*` **proxies** these. The API must not kill itself.

## Creator surfaces

Setup Wizard and Settings show **Adept Background Services**: Manager, Studio API, Comfy, Start with Windows. Actions: Enable Recommended, Start, Stop, Restart Studio API, Restart Comfy, Repair.

## Fail closed

Manager unavailable → report Background Services unavailable → Start or Repair. Not: silently launch another uvicorn or Comfy.

`Register-AdeptBetaBackendStartup.ps1` must not recreate `AdeptBetaBackendManager`. Retire that task only after `AdeptRuntimeService` exists.

## Certification

Ownership cutover GO requires the proof block in `docs/architecture/ADEPT_BACKGROUND_SERVICES_OWNERSHIP_CUTOVER.md`. Isolation GOs stay separate. Co-Director image E2E is a separate gate.

Deferred (not this gate): non-stream `POST /api/codirector/chat` can talk without enqueueing. Stream `/chat/stream` is the proven product path.
