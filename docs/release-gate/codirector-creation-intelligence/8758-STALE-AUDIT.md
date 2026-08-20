# :8758 stale-process audit — 2026-08-20

Observed on the live Beta machine before adoption repair.

## What answered HTTP

| Probe | Result |
|---|---|
| `GET http://127.0.0.1:8758/api/health` | 200 |
| `apiRevision` | `c8c5133` (matches `git rev-parse --short HEAD`) |
| `apiStartedAt` | `2026-08-20T06:45:22Z` |
| `GET /api/perception/capability` | **404 Not Found** |
| `netstat` LISTENING | `127.0.0.1:8758` claimed by PID **58504** |

## Process table

- `Get-Process -Id 58504` — no process
- `tasklist /FI "PID eq 58504"` — no tasks
- `Get-CimInstance Win32_Process -Filter ProcessId=58504` — empty
- `taskkill /PID 58504 /F` (prior session) — `The process "58504" not found` while netstat still listed it

## Living descendants

Two Python multiprocessing children still named the missing parent:

- PID **47560** — `multiprocessing.spawn.spawn_main(parent_pid=58504, pipe_handle=520)`
- PID **50116** — `multiprocessing.spawn.spawn_main(parent_pid=58504, pipe_handle=760)`

Interpreter: `uv` cpython 3.11. No `uvicorn app.main:app --port 8758` command line remains on any live process.

This is the orphan-multiprocessing / inherited-socket class: the parent listener PID is gone from the process table, children keep the listen socket, health still serves the **import-time** SHA from 06:45Z.

## Why supervisor adopted it

`_health_revision_current` compared `apiRevision` to git HEAD. Both were `c8c5133` because Revision B existed only in the dirty working tree. SHA match ⇒ `adopt_api = True`. Adopted listeners are never recycled.

SHA-alone is not identity. Route contract (`/api/perception/capability`) was not probed.

## Required repair

1. Health publishes a route contract, not only SHA + start time.
2. Supervisor adopts only when health + SHA **and** perception capability contract succeed.
3. Recycle Adept-owned stale APIs and their multiprocessing descendants, not just the netstat PID.
