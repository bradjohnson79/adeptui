# Image Runtime Health — Production ComfyUI (:8188)

> Phase A evidence for the Adept UI Creator Pipeline focused recovery.
> Authority spec: `tests/e2e/integration/adept-ui-full-creator-pipeline.spec.ts`
> Addendum: automatic production ComfyUI startup (MANDATORY).

**Captured:** 2026-08-04T06:41Z (local 2026-08-03 23:41)
**Verdict: HEALTHY — production image runtime READY**

## Runtime distinction (honoured)

| Runtime | URL | Status |
| --- | --- | --- |
| Production ComfyUI | `http://127.0.0.1:8188` | READY (started during recovery) |
| MiniMax H3 Route A | `http://127.0.0.1:8192` | READY (separate; never substituted) |

Production was started on its canonical port 8188 only. H3 Route A was never used as a substitute, and no production instance was started on an alternate port.

## Ensure protocol executed (Addendum steps 1–6)

1. **Probe `GET /system_stats`** → initially UNHEALTHY (connection refused) even though a port listener existed.
2. **Reuse?** No — the existing ComfyUI Desktop server (PID 47092) was wedged: port 8188 bound but HTTP refused, working set 29 MB (paged out), 2761 s CPU accumulated. Not reusable.
3. **Start approved production Comfy** via `ADEPT_COMFY_LAUNCH` (set in `config/beta-local.local.env`, gitignored) — the Addendum-approved path. Same ComfyUI-Desktop venv + `main.py` + shared model paths used by the user's ComfyUI Desktop, launched on `127.0.0.1:8188` with `--disable-auto-launch --enable-manager`. A wedged ComfyUI Desktop respawn on port 8189 (DB-lock fallback) was cleared first so production could reclaim 8188 and the `comfyui.db` lock.
4. **Wait for readiness** → `/system_stats`, `/object_info`, GPU, queue all confirmed.
5. **No failure** — runtime came up cleanly; no `IMAGE_RUNTIME_STARTUP_FAILED` issued.
6. **Leave-running** — the recovery-started Comfy is left running for Beta continuity. ComfyUI Desktop's electron shell remains open but is no longer owning the server.

## Evidence

### `GET http://127.0.0.1:8188/system_stats` → 200

- `comfyui_version`: 0.28.2
- `pytorch_version`: 2.10.0+cu130
- `python_version`: 3.13.12
- `deploy_environment`: local-desktop2-standalone
- Device: `cuda:0 NVIDIA GeForce RTX 5090 : cudaMallocAsync`
- VRAM total: 34,190,458,880 B (~32.6 GB); free at probe: ~32.5 GB (server idle, models offloaded)

### `GET http://127.0.0.1:8188/object_info` → 200

- Node catalog available; `nodeTypeCount`: **1900** (via Adept `/api/health`).

### `GET http://127.0.0.1:8188/queue` → 200

- Queue running: **0** | pending: **0** — queue ready.

### GPU (nvidia-smi)

- `NVIDIA GeForce RTX 5090`, 32607 MiB total, 18311 MiB used, 13877 MiB free, 0 % util.
- H3 Route A models resident/idle (~18 GB); production Comfy has ~14 GB free plus async weight offloading + DynamicVRAM — sufficient for image generation.

### Adept API `/api/health` → 200 (`comfy_reachable: true`)

- `comfy.status`: `ready`
- `comfy.version`: `0.28.2`
- `comfy.nodeCatalogAvailable`: `true`
- `comfy.nodeTypeCount`: `1900`
- `comfy.devices[0].vramFreeMb`: `30991`
- Models all present: `ltx_checkpoint` (required, present), `wan_models`, `ltx23_ic_lora_ingredients`, `zimage_models`.
- `missing_model_component_ids`: `[]`
- `packBlockers`: `[]` (previously 7 `comfyui.*` / `workflows.*` blockers — all cleared)
- `operator.comfy`: `reachable`; `operator.api`: `ok`
- `registry`: callable 55, blocked 1 (down from 22), locally_verified 54.

### Beta supervisor status (`data/runtime/beta/status.json`)

- `state`: **READY**
- `ports`: web 8760, api 8758, comfy 8188
- `services.api.ok`: true (pid 39128, studio-api + in-process queue worker)
- `services.worker.ok`: true (in-process JobQueue + Production Executive)
- `services.web.ok`: true (pid 45248, production static+proxy)
- `services.comfy.ok`: true (external ComfyUI, url `http://127.0.0.1:8188`)
- `uiUrl`: `http://127.0.0.1:8760/`
- `apiUrl`: `http://127.0.0.1:8758/api/health`

## Reused vs started

**Started** during recovery (not reused). The user's ComfyUI Desktop server was wedged (port bound, HTTP dead) and could not be reused. A fresh production ComfyUI was launched on 8188 via the Addendum-approved `ADEPT_COMFY_LAUNCH` mechanism using the same ComfyUI-Desktop install (venv, `main.py`, shared model paths). `config/beta-local.local.env` now persists `ADEPT_COMFY_LAUNCH` so future supervisor runs auto-ensure Comfy.

## Process ownership

- Port 8188 owner: PID 44624 (live server).
- Helper PID 1176 (CPU idle; ComfyUI spawn).
- ComfyUI Desktop electron shell still running (no server child); will not reclaim 8188 while the recovery server holds the port + `comfyui.db` lock.

## GO | NO-GO

**GO** for Phase B (image pipeline). Production image runtime is reachable, on GPU, with node catalog, empty queue, and all required models present.
