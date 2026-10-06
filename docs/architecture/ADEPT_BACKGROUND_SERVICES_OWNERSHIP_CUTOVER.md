# Adept Background Services — ownership cutover evidence

Governing: `docs/architecture/ADEPT_ALWAYS_ON_RUNTIME_SERVICE.md`

## Implementation (this session)

- `windows_task.register_task` tries current-user Task Scheduler, then `schtasks`, then one UAC `install-task`. Success only if `query_task().exists`.
- `start_all` / `restart_all` / `stop_all` delegate to `:8759` or fail closed. They do not spawn API or Comfy when the manager is absent.
- CLI `watch` is diagnostic only. Manager `watch_once` (inside `serve`) is unchanged.
- Preferences persist `startWithWindows` from `query_task()` only.
- `Register-AdeptBetaBackendStartup.ps1` refuses to create `AdeptBetaBackendManager`.
- Retired `BetaBackendCommon.Start-StudioApiAuthoritative` and `beta_runtime.supervisor.start_api` refuse to spawn `:8758`.

Unit tests: **68 passed** (`test_dual_background_services`, `test_adept_runtime_service`, `test_runtime_supervisor_lifecycle`, `test_background_manager_recovery`).

## Live scheduler (this session)

`schtasks /Query /TN AdeptRuntimeService` → **not found**.

Current-user `Register-ScheduledTask` → Access Denied (`0x80070005`).

UAC elevation was shown. Result: **cancelled** (`The operation was canceled by the user`). Registration was **not** faked.

`AdeptBetaBackendManager` remains **Ready**. It was **not** retired because the new task is not proven.

## Live children (unchanged)

| Role | Port | PID |
| --- | --- | --- |
| Manager | 8759 | 62224 |
| Studio API | 8758 | 76456 |
| Comfy | 8188 | 77152 |

`COMFY BEFORE: PID 77152 / health 200`  
`COMFY AFTER: PID 77152 / health 200`  
`COMFY RESTARTED?: NO`  
`WHY?:` ownership cutover did not recycle GPU runtimes.

## Required proof block

- AdeptRuntimeService registered: **NO**
- AdeptBetaBackendManager active: **YES** (left in place until the new task exists)
- beta:start independent owner: **NO** (code: fail-closed / manager client)
- start_all independent owner: **NO** (code)
- watch independent owner: **NO** (code: CLI diagnostic only)
- Manager auto-started after logon: **NO** (logon not performed; task missing)
- API owned by manager: **YES** (this session: 76456 owned)
- Comfy owned by manager: **YES** (this session: 77152 owned)

## Verdict

**NO-GO — AdeptRuntimeService not registered (UAC cancelled / Access Denied). AdeptBetaBackendManager still the logon task.**

Approve the one Windows permission prompt for AdeptRuntimeService, then reboot with Cursor closed. After login, re-query the proof block.

## Deferred (not this gate)

Non-stream `POST /api/codirector/chat` can talk without enqueueing. Stream `/chat/stream` is the proven product path.
