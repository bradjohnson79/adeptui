# Adept UI — Automatic Runtime Boot — Journey 1 Architecture Map

**Date:** 2026-09-03
**Phase:** Journey 1 — Walk current boot experience + classify.

## Current cold-start experience (as observed)

When the Alienware reboots and the creator opens Adept UI (Vite `:5173`):

1. Vite dev server starts. It only proxies `/api` → Studio API `:8758`. **It does not spawn any runtime.**
2. The frontend mounts. `useStudioHealth` polls `GET /api/health` (Studio API) + Comfy health.
3. If the Background Services manager is **not** running, Studio API is down → the frontend shows the `StudioApiOutageBanner` ("Studio API Offline" + a manual **Retry** button). Nothing auto-starts.
4. The creator must manually start the runtime: either run `run_runtime_supervisor.py serve` in a terminal, or open the Setup Wizard → Background Services → "Enable Recommended" / "Start Services".

So today the boot is **manual**. The historical "open Adept, then spend minutes launching services by hand" experience is exactly what this mission removes.

## Component classification

| # | Component | Location | State | Notes |
|---|---|---|---|---|
| 1 | Runtime Supervisor (canonical lifecycle) | `studio-api/runtime_supervisor/` | **EXISTS** | Registry, ownership (owned/reused/external), health, GPU admission, headless Comfy, control plane, Windows task. Robust. |
| 2 | Background Services Manager (`serve_forever`) | `runtime_supervisor/serve.py` | **EXISTS** (running, PID 71956, `:8759`) | Owns Studio API `:8758` + headless Comfy `:8188` as children; watch loop. |
| 3 | Control Plane (token-gated, loopback) | `runtime_supervisor/control_plane.py` | **EXISTS** (`:8759`) | `GET /status`, `POST /start /stop /restart /start-api /restart-api /start-comfy /restart-comfy /repair /request-qwen`. |
| 4 | Studio API runtime-manager API | `studio-api/app/runtime_manager/router.py` | **EXISTS** | `/api/runtime-manager/{status,start,stop,restart,enable-recommended,restart-api,restart-comfy,repair,preferences}`. Proxies to control plane. |
| 5 | Runtime status contract | `runtime_manager/service.py` `get_status` → `RuntimeManagerStatus` | **EXISTS** | `comfyui/studioApi/ollama/tunnel/gpu/routeA/gpuAdmission/preferences/adeptRuntime` with `ServiceStatus` (RUNNING/STARTING/STOPPED/ERROR/NOT_CONFIGURED) + ownership. |
| 6 | Frontend runtime health hook | `studio-web/src/hooks/useStudioHealth.ts` | **EXISTS** (observe-only) | Polls `/api/health` + comfy health. No boot trigger. |
| 7 | Studio API outage banner | `studio-web/src/components/StudioApiOutageBanner.tsx` | **EXISTS** | Non-modal banner + manual Retry. Not a startup gauge. |
| 8 | Setup Wizard Background Services section | `studio-web/src/components/SetupWizard.tsx` | **EXISTS** | Manual lifecycle UI using the same `/api/runtime-manager/*` contract. |
| 9 | Windows logon task infrastructure | `runtime_supervisor/windows_task.py`, `bootstrap.enable_recommended` | **EXISTS** | `install-task` / `enable` / `enable-recommended`. |
| 10 | Headless Comfy (canonical, ownership-verified) | `runtime_supervisor/headless_comfy/` | **EXISTS** | Never adopts Desktop; reuses owned/healthy. |
| 11 | Vite dev bootstrap plugin | `studio-web/vite.config.ts` | **MISSING** | Vite only proxies `/api`; spawns nothing. |
| 12 | Frontend Startup Systems Gauge modal | — | **MISSING** | No cinematic auto-closing startup modal. |
| 13 | Windows logon task registration | `AdeptRuntimeService` | **DISCONNECTED** | Infrastructure exists but task is **not registered** → no auto-start on reboot. |
| 14 | Frontend → bootstrap auto-invocation | — | **DISCONNECTED** | Frontend only observes; never triggers the bootstrap on launch. |
| 15 | Electron-ready `runtime.start()` contract | — | **MISSING** | No shared Node bootstrap module. |
| 16 | Post-startup health supervision | supervisor `watch_once` + `useStudioHealth` | **EXISTS** | Bounded watch loop (storm-guarded). |

## Dependency graph (boot order)

```
Adept UI launch (Vite dev / future Electron)
  └─ runtime.start()  [MISSING — to add]
       └─ probe :8759 control plane
            ├─ reachable → REUSE manager (warm)        [Phase A]
            └─ down → spawn run_runtime_supervisor.py serve  [Phase B]
                 ├─ manager starts Studio API :8758 (child)
                 │    └─ /api/healthz  [required]
                 ├─ manager starts headless Comfy :8188 (reuse if healthy)  [required]
                 │    └─ /system_stats  [required]
                 ├─ Ollama :11434 — external, reused (not killed)  [optional]
                 ├─ cloudflared tunnel — optional
                 └─ Route A :8192 — on-demand (GPU admission)  [optional]
       └─ Comfy MCP — waits for canonical Comfy readiness  [Phase C]
```

## What already auto-starts
- Nothing on Adept UI launch. The Background Services manager only runs because it was manually started (or by a registered Windows task, which is currently **not** registered).

## What requires manual startup
- The Background Services manager (`run_runtime_supervisor.py serve`) or the Setup Wizard "Start Services" button.

## What takes the longest
- Comfy readiness (up to `COMFY_READY_TIMEOUT_SEC = 45s`) when cold. Studio API `API_READY_TIMEOUT_SEC = 120s`.

## What can start concurrently
- Studio API and Comfy are independent children of the manager and can start in parallel. Ollama/tunnel are independent. Route A is on-demand.

## Stale process / PID handling
- `SupervisorState` tracks PIDs with `owned` flag; `verify_identity` re-verifies before any stop; stale-PID removal is safe. EXISTS and robust.

## Duplicate service-management systems
- The Setup Wizard and the supervisor share the **same** `/api/runtime-manager/*` contract → one canonical service definition. No duplicate Comfy installations found. The outage banner is observe-only (not a competing authority).

## Conclusion (pre-implementation)

The canonical lifecycle layer **already EXISTS** and is robust. The mission is **not** a rebuild — it is to **connect** the missing pieces:
1. **Auto-invoke** the canonical bootstrap when Adept UI launches (Vite dev plugin now; Electron main later) — J3/J10.
2. **Register** the Windows logon task so reboot auto-starts the manager — J8.
3. **Add** the Startup Systems Gauge modal that polls the existing status contract and auto-closes — J5–J7.
4. **Converge** with the Setup Wizard (same contract) — J12 (largely already true).
5. Process ownership, post-startup health, parallel boot — J9/J13/J4 (largely EXISTS).

ComfyUI Protection Law: the bootstrap must **reuse** an already-healthy `:8188` (never restart/adopt/kill). The canonical supervisor already does this. The Vite plugin must probe `:8759` and only spawn when the manager is down.
