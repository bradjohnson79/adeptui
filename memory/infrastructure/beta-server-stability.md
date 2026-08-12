# Beta Server Stability

## Backend Manager (NEW - replaces old :8760 supervisor)

The old `Start-AdeptUI-Beta.ps1` / `Stop-AdeptUI-Beta.ps1` supervisor (which ran the Vite dev frontend on :8760) has been **replaced** by the persistent Windows **Beta Backend Manager**.

### Scripts
- `Start-AdeptBetaBackend.ps1` - start/adopt all backend services
- `Stop-AdeptBetaBackend.ps1` - stop manager-owned processes
- `Restart-AdeptBetaBackend.ps1` - restart individual or all services
- `Get-AdeptBetaBackendStatus.ps1` - print status
- `Watch-AdeptBetaBackend.ps1` - continuous monitor + auto-restart
- `Register-AdeptBetaBackendStartup.ps1` / `Unregister-AdeptBetaBackendStartup.ps1` - opt-in Windows Task Scheduler auto-start
- `scripts/beta-backend/BetaBackendCommon.ps1` - shared module (paths, logging, PID mgmt, health checks, state, storm protection, `Import-BetaEnv`)

### Managed Services
| Service | Port | Health Check |
|---|---|---|
| Studio API (uvicorn) | 8758 | `/api/healthz` + `/api/health` |
| ComfyUI (headless) | 8188 | `/system_stats` |
| Cloudflare Tunnel (cloudflared) | - | `https://api-beta.adeptui.org/api/healthz` |
| Ollama | 11434 | `/api/tags` |

### State & Logs
- State: `.runtime/beta-backend/` (per-service PID/ownership records)
- Logs: `logs/runtime/beta-backend/` (per-service `*.log` + `*_stdout.log`)
- `.gitignore` excludes both

### Key Fixes Applied During Construction
- Em-dash (`-`) replaced with hyphen in all PowerShell string literals (TerminatorExpectedAtEndOfString)
- `RepoRoot` calculation fixed to `C:\AdeptFilmWorks\AIVideoStudio`
- `RedirectStandardOutput` changed from `*.log` to `*_stdout.log` (avoid conflict with `Write-BetaLog`)
- `--workers 2` removed from uvicorn args (caused startup failure on restart)
- Adopted services marked `owned=$true` so `Watch` manages them
- `Import-BetaEnv` added to load `config/beta-local.env` + `config/beta-local.local.env` before launching Studio API

---

## Health Architecture

```
Frontend (Vercel) -> Cloudflare Tunnel -> Studio API (8758, 1 worker)
  heartbeat: /api/healthz (fast, no deps, <5ms)
  full check: /api/health (ComfyUI, capabilities, provider)
  threshold: 5 consecutive failures -> OFFLINE banner
  retry: exponential backoff 1.2s -> 30s
  suspension: shouldSuspendDependentPolling() after 3 failures
```

### Central Connection Coordinator (`studioApiConnection.ts`)
- Single module-level state machine: CONNECTED / RECONNECTING / DEGRADED / OFFLINE / RECOVERED
- Subscriber fan-out via `subscribeStudioApiConnection()`
- `markStudioApiHealthy()` / `markStudioApiFailure()` / `markStudioApiDegraded()`
- `shouldSuspendDependentPolling()` - gates Co-Director + Production Dock polls
- `onStudioApiRecovered()` - recovery handlers
- Backoff: `nextStudioApiRetryMs()` - 1.2s base, 2^(n-1), 30s max

### Known Defects (from Frontend Request Architecture Audit, 2026-08-10)
1. **emit->refetch feedback loop**: `api.ts:939` calls `markStudioApiHealthy()` on every successful `/api/health`; `markStudioApiHealthy` emits unconditionally (no equality check); `useStudioHealth` subscriber refetches on every emit; 3x `useStudioHealth` on Home -> exponential amplification. Measured: 15,053 `/api/health` in 5 min, 1,350 concurrent (Chrome cap), `ERR_INSUFFICIENT_RESOURCES`.
2. **zombie `probeInFlight`**: cleared only in full-check `finally`, not after fast `/api/healthz` success -> monitor blind to failures after first success; Retry button neutered.
3. **suspension flag ignored by chrome pollers**: `SystemStatusStrip` (15s), `BetaRuntimeStatus` (15s), `CapabilityStatusBadge` (30s) never check `shouldSuspendDependentPolling()`.

### Fix Plan (Targeted Polling Repair - not yet implemented)
1. `studioApiConnection.ts` - emit only on actual state change (equality check in `setSnapshot`)
2. `studioApiConnection.ts` - clear `probeInFlight` in one outer `finally`
3. `useStudioHealth.ts` - refetch only on transitions into CONNECTED/RECOVERED + in-flight guard; consolidate to one instance
4. `api.ts` - single-flight + 5-15s TTL cache for `/api/health`, `/api/capabilities`, `/api/gpu/stats`, `/api/runtime/beta`
5. Chrome pollers - honor `shouldSuspendDependentPolling()`

---

## CORS Configuration (repaired 2026-08-10)
- `studio-api/app/config.py`: `cors_origins` field with explicit origins (no wildcard `*`)
- `studio-api/app/main.py`: parses `settings.cors_origins` -> `CORSMiddleware.allow_origins`
- Configurable via `STUDIO_CORS_ORIGINS` env var
- Default: `https://adeptui.vercel.app,http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8760,http://localhost:8760`

---

## TTL Cache (global checks)
- 7 check types: api.health, capabilities.registry, codirector.provider, comfy.health, production_control.status, image_runtime.readiness, video_runtime.readiness
- Success TTL: 30s, Failure TTL: 5s
- Invalidated on API failure, manual Re-check

## Soak Test Results (historical)
- Active soak: 5+ min, 0 failures
- Warm cross-check latency: 1,764ms (44% reduction from 3,150ms cold)
- Auto-check: 500ms deferred on mount, transitions to Ready automatically
