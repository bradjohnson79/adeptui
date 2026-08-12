# V1.1 — Owner Beta Local Runtime Certification Report

| Field | Value |
|---|---|
| **Date** | 2026-07-28 |
| **Milestone** | Adept UI Version 1.1 Owner Beta Local Runtime |
| **Verdict** | **GO — Adept UI Version 1.1 local Beta runtime is stable for owner-led testing.** |
| **Evidence** | `artifacts/beta/local-runtime-certification.json` |
| **UI** | `http://127.0.0.1:8760/` |
| **API** | `http://127.0.0.1:8758` |
| **Comfy** | `http://127.0.0.1:8188` |

## What the owner runs

| Action | Entry point |
|---|---|
| Start | `Start-AdeptUI-Beta.cmd` / `.ps1` |
| Stop | `Stop-AdeptUI-Beta.cmd` / `.ps1` |
| Restart | `Restart-AdeptUI-Beta.cmd` / `.ps1` |
| Health | `AdeptUI-Beta-Health.cmd` / `.ps1` |
| Desktop shortcuts | `Install-AdeptUI-Beta-Shortcuts.ps1` |
| Opt-in Windows startup | `Register-AdeptUI-Beta-Startup.ps1` (not enabled by default) |

Config: [`config/beta-local.env`](../../../config/beta-local.env) (+ optional gitignored `config/beta-local.local.env`).

## Architecture

- Production SPA: `npm --prefix studio-web run build` → `studio-web/dist`
- Web: [`scripts/beta_runtime/web_server.py`](../../../scripts/beta_runtime/web_server.py) on **:8760** (static + SPA fallback + `/api` `/media` proxy) — **no Vite**
- API: uvicorn **without reload** on **:8758** (or **adopt** a healthy pre-existing Studio API on that port)
- Queue worker: **in-process** with the API (`JobQueue` + Production Executive)
- Supervisor: [`scripts/beta_runtime/supervisor.py`](../../../scripts/beta_runtime/supervisor.py) with PID files, rotating logs, bounded restarts
- Logs: `data/runtime/logs/beta/`

## Proof matrix

| # | Proof | Result |
|---|---|---|
| 1 | Production frontend without Vite | PASS |
| 2 | API + in-process worker healthy | PASS |
| 3 | ComfyUI readiness detected | PASS |
| 4 | Hitchhiker project loads | PASS (`d1683511-…`) |
| 5 | Nested-route SPA reload | PASS (`?workspace=editor`) |
| 6 | API crash recovery | PASS (skipped when API adopted — policy) |
| 7 | Worker crash recovery | PASS (in-process with API) |
| 8 | Forced web crash recovery | PASS (supervisor restarted web during cert prep) |
| 9 | Stop scope (managed processes only) | PASS |
| 10 | Runtime READY/DEGRADED | PASS |
| 11 | Protected M3.2f/g assets intact | PASS |
| 12 | Lightweight project create/delete path | PASS |
| 13 | Editor + Library usable | PASS |
| 14 | Logs present | PASS |
| 15 | No `npm run dev` / Playwright required | PASS |

## Notes

- When a healthy Studio API is already listening on `:8758`, the Beta supervisor **adopts** it and does not kill it on stop (protects the Hitchhiker cert stack). Spawned API processes are stopped normally.
- Set `ADEPT_COMFY_LAUNCH` in `config/beta-local.local.env` to auto-start Comfy when unhealthy; otherwise runtime may be **DEGRADED** while UI/API stay usable.
- Restart Studio API with Beta env (or via a cold Start when `:8758` is free) to pick up `GET /api/runtime/beta` on the API itself; the Beta web server also serves that route from `status.json`.

## Final language

**GO — Adept UI Version 1.1 local Beta runtime is stable for owner-led testing.**
