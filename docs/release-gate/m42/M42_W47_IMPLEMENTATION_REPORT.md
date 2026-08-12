# M42 W47 — Implementation Report

**Branch:** `phase2/m42-docker-runtime-extensions`  
**Law:** 27 — isolated Docker installs; no core mutation; no React→Docker  
**Gate:** `dockerRuntimeExtensionsGo` (binary)

## Delivered

### Backend (`studio-api/app/docker_runtime/`)

| Module | Role |
| --- | --- |
| `contracts.py` | Frozen schema_version 1 types |
| `platform.py` | Docker / WSL2 / NVIDIA toolkit / host GPU detect |
| `manager.py` | pull/build/create/start/stop/restart/remove/inspect/logs (+ simulate) |
| `manifest.py` | AdeptRuntimeManifest parse/validate/defaults |
| `security.py` | Default-deny privileged, host network, docker.sock, unpinned `:latest` |
| `storage.py` | core / shared_optional / private + refcounts |
| `registry.py` | Persisted registry under `data/docker_runtime/` + core seeds |
| `gpu_preflight.py` / `health.py` | Law 26-style GPU + HTTP health |
| `service.py` | Install/update/repair/uninstall/workflow import |
| `queue_hooks.py` | waiting_for_runtime / waiting_for_gpu / no silent fallback |
| `api.py` | `/api/docker-runtime/*` |
| `gate.py` | `dockerRuntimeExtensionsGo` |

### Wave 2 — Dock / resolver / queue

- `ModelDescriptor.executionClass` + `runtimeId` (additive)
- `list_models` merges Docker dock entries (user_added never Certified)
- `resolve.py` `_refresh_docker_executable` — Start Runtime / Requires Repair; no substitute
- `queue_worker.py` gates docker-runtime model jobs with provenance

### Wave 3 — UI

- Setup Wizard: **Add Custom Capability** + Runtime Manager link
- `/runtime-manager` — Runtime Manager + uninstall options
- Production Dock: **Native Local / Docker Local / Hosted API** sections + Start Runtime

### Wave 4 — Co-Director

Closed tools (proposal-gated mutators):  
`runtime.list|inspect|test|open_manager|preview_install|install|preview_update|update|preview_repair|repair|preview_uninstall|uninstall|start|stop|restart`

## Architecture invariants held

1. All Docker ops via backend only  
2. Core Comfy/LTX seeded as `core_mandatory` native — Uninstall blocked  
3. User-added readiness never auto-Certified  
4. Uninstall preserves project assets / provenance / shared files; failed uninstall rolls back registry  
