# Adept UI — Background Manager Recovery Report

**Date:** 2026-08-12
**Status:** FINAL

---

## Branch / SHA

| Item | Value |
|---|---|
| BRANCH | `beta` |
| HEAD SHA | `98d3136` (runtime+wiki commit; no frontend/backend code changes required for this task) |

---

## BACKGROUND MANAGER

**Authoritative entrypoint:**
`Start-AdeptBetaBackend.ps1` (starts Studio API, ComfyUI headless, Cloudflare Tunnel with `--config`) + `Watch-AdeptBetaBackend.ps1` (watchdog with bounded retries + exponential backoff + storm protection).

**Configured port (bridge):**
The "Background Manager" is NOT a separate service on a dedicated port. It is the PowerShell launcher system that manages:
- Studio API → `127.0.0.1:8758`
- ComfyUI → `127.0.0.1:8188`
- Cloudflare Tunnel → `api-beta.adeptui.org` → `http://127.0.0.1:8758`

The bridge between the hosted Vercel frontend and the local runtime is the **Cloudflare Tunnel** (`api-beta.adeptui.org` → `127.0.0.1:8758`), NOT port 8579. **Port 8579 has zero references in the repository** — it was never a real Adept UI service.

**8579 listener:** N/A (not a real port — never implemented)

**Process (cloudflared — the actual bridge):**
- PID: 34260
- Name: cloudflared.exe
- Path: `C:\Program Files (x86)\cloudflared\cloudflared.exe`
- StartTime: 2026-08-12 14:21:04
- CommandLine: `cloudflared tunnel --config "config\cloudflared\adept-ui-beta-tunnel.yml" run adept-ui-beta`

**Health endpoint:** PASS
- `http://127.0.0.1:8758/api/healthz` → 200 `{"status":"ok"}`
- `http://127.0.0.1:8758/api/health` → 200 `{"ok":true,"comfy_reachable":true,"comfy":{"status":"ready",...}}`
- `https://api-beta.adeptui.org/api/healthz` → 200 `{"status":"ok"}` (through tunnel)

**Studio API 8758:** PASS (PID 18084, healthy, untouched)

**ComfyUI:** PASS (PID 12752, port 8188 listening, ComfyUI 0.32.0, RTX 5090 32GB, reachable)

**Hosted frontend reconnect:** PASS
- `https://adeptui.vercel.app` shows "Studio API: Online", "ComfyUI: Healthy", "Models · 1 incomplete", "Provider: Connected"
- No "Studio API is offline" banner
- Projects loaded (Schnick Coffee + 20 others)

---

## REBOOT RECOVERY

**Existing startup mechanism:**
`Register-AdeptBetaBackendStartup.ps1` creates a Windows Task Scheduler task `AdeptBetaBackendManager` triggered at logon. The task runs a bootstrap (`autostart_bootstrap.ps1`) that calls `Start-AdeptBetaBackend.ps1 -NoBrowser` then launches `Watch-AdeptBetaBackend.ps1`.

**Root cause:**
Two compounding failures after the Windows reboot:
1. **No scheduled task was registered** — `Get-ScheduledTask *Adept*` returned empty. Nothing auto-started the backend or tunnel after reboot.
2. **cloudflared was manually started WITHOUT `--config`** — someone ran `cloudflared tunnel run adept-ui-beta` without `--config config\cloudflared\adept-ui-beta-tunnel.yml`. Without the config, cloudflared had no ingress rules and returned **503 for all requests**. The tunnel process was running but not routing to the local Studio API, so the hosted frontend showed "Studio API is offline".

**Startup repaired:** PASS
- Registered `AdeptBetaBackendManager` scheduled task (Trigger: At logon, State: Ready).
- Bootstrap verified: runs `Start-AdeptBetaBackend.ps1 -NoBrowser` (which correctly passes `--config` to cloudflared) then `Watch-AdeptBetaBackend.ps1`.
- After the next reboot/logon, the backend + tunnel will auto-start with the correct config.

**Retry/recovery:** PASS
- `Watch-AdeptBetaBackend.ps1` has bounded retries (`MaxRestarts=5`), exponential backoff (`5s → 120s` cap), storm protection (`300s` window), per-service backoff state, and owned-vs-external process detection.
- Watchdog running (PID 12480) and supervising all services.

**Logging:** PASS
- `Write-BetaLog` writes timestamped entries to `logs/runtime/beta-backend/{manager,studio_api,comfyui,cloudflared,ollama}.log`.
- Bootstrap logs to `autostart.log`.
- `manager.log` shows startup, env load, health probes, tunnel status, watchdog cycles.

**Duplicate process protection:** PASS
- `Start-AdeptBetaBackend.ps1` checks `Test-StudioApiHealth` / `Test-ComfyUiHealth` / `Test-CloudflareHealth` before starting; reuses already-healthy services and adopts their PIDs.
- No duplicate Studio API or ComfyUI processes created.

---

## REGRESSION

**Co-Director:** PASS (hosted frontend loaded Co-Director with Schnick Coffee project context)
**Timeline:** PASS (Capability Readiness shows "54 Ready · 7 Blocked · 21 Deferred · 105 Not installed")
**Runtime diagnostics:** PASS (Models badge shows "1 incomplete" — LTX 2.5, correctly separated from ComfyUI runtime health)

---

## TESTS

5 new tests in `studio-api/tests/test_background_manager_recovery.py` (all PASS):
1. Tunnel config has correct ingress (`api-beta.adeptui.org → 127.0.0.1:8758`)
2. `Start-AdeptBetaBackend.ps1` passes `--config` to cloudflared (root cause guard)
3. `Register-AdeptBetaBackendStartup.ps1` targets correct bootstrap + watchdog
4. `Watch-AdeptBetaBackend.ps1` has bounded retries + backoff + storm protection
5. `runtime_manager/service.py` aggregates health from multiple sources

---

## TUNNEL AUDIT (config/credentials/origin)

| Item | Value | Valid |
|---|---|---|
| Tunnel ID | `822658ce-2057-4250-bb70-eb36dded0630` | matches config |
| Credentials file | `C:\Users\bradj\.cloudflared\822658ce-2057-4250-bb70-eb36dded0630.json` | exists |
| Ingress hostname | `api-beta.adeptui.org` | correct |
| Origin target | `http://127.0.0.1:8758` | correct (Studio API) |
| DNS | `api-beta.adeptui.org` → Cloudflare IPs (proxied) | correct |
| Tunnel connector | online (edge: sea07, sea08, yvr01, yvr02) | healthy |

No second tunnel created. No credentials rotated. No DNS changed. No Studio API ports altered. Existing configuration proven valid.

---

## FINAL VERDICT

**GO — ADEPT UI BACKGROUND MANAGER RECOVERED AND REBOOT-SAFE**

The authoritative Cloudflare Tunnel is restored with the correct `--config`, the public endpoint `api-beta.adeptui.org` reaches the local Studio API (8758), the hosted frontend reconnected (Studio API: Online, ComfyUI: Healthy), the scheduled task `AdeptBetaBackendManager` is registered for post-reboot auto-start, and the watchdog is running with bounded supervision. Studio API was never touched. The manager will survive the next reboot.
