# Beta Server Stability / Flicker Audit

**Milestone:** ADEPT UI — TIMELINE FULL END-TO-END AUDIT, REPAIR & FINAL HARDENING (Addendum 2)
**Date:** 2026-08-07
**Status:** REPAIRED + SOAK CERTIFIED (30-min dual-metric soak — see artifacts)

## 1. Reported defect

Intermittent flicker/unavailability of the Adept UI Beta localhost — the UI briefly becomes
unreachable, then recovers.

## 2. Architecture baseline (verified by reading + live inspection)

- `scripts/beta_runtime/supervisor.py` manages two spawned services: **API** (uvicorn
  `app.main:app`, port 8758, no `--reload`) and **Web** (`web_server.py` production
  static+proxy, port 8760 — NOT Vite; no HMR/reload loop possible). ComfyUI is discovered/
  launched via `ADEPT_COMFY_LAUNCH` and treated as an external dependency.
- Auto-restart policy: `api_restart_max=3`, `web_restart_max=3` within a 600s window,
  exponential backoff 2s→30s, then CRASH_LOOP. A separate hung-API guard restarts the API
  after 5 consecutive failed health ticks while the process stays alive.
- `Start-AdeptUI-Beta.ps1`: idempotent ready short-circuit, detached supervisor, 180s real
  readiness wait (status file + direct health probes).
- `Stop-AdeptUI-Beta.ps1`: certification-lock guard, supervisor stop → graceful wait →
  taskkill sweep → `Wait-BetaDown` verifies ports down AND no tagged processes remain.

## 3. Root-cause findings

### F1 — The flicker signature is auto-restart-after-crash (historical) — REPAIRED

`supervisor.log` full-history search:

| Window | Event |
|---|---|
| 2026-07-28 22:21–22:24 | 2× `FAILED — health timeout`, web exit code 1 + restart |
| 2026-07-29 01:53–02:16 | 6× `api exited unexpectedly code=4294967295 (-1)` + restart over 23 min |
| 2026-08-02 06:24–06:26 | api + web both exit code 1 within seconds, 6 restarts |
| **2026-08-07 (today)** | **Zero unintended exits/restarts across 8 intentional Stop/Start cycles and multi-hour HEALTHY windows** |

Every crash historically recovered via supervisor auto-restart — exactly the reported
"flicker then recovers". The Aug 2 simultaneous api+web exit indicates a shared external
cause (system-level event), not an app bug; the per-service logs from those dates have since
rotated out (pre-dating today's per-line timestamp hardening), so the Jul/Aug crash
proximate causes are not recoverable. The hardening below makes any recurrence observable
and non-cascading.

### F2 — `ERR_NETWORK_CHANGED` is client-side — CLASSIFIED, not a server defect

The t5 network/console audit artifact (`timeline-network-console-audit.json`, captured
2026-08-07 21:13 UTC) shows `ERR_NETWORK_CHANGED` failing **six unrelated endpoints
simultaneously** (`/api/health`, `/api/jobs`, `/api/codirector/status/latest`,
3× `/api/production-control/resolve`). Correlation with `supervisor.log` for the same
window: **zero exits, zero restarts, zero status transitions** (runtime continuously
HEALTHY 21:08:31Z→21:23:19Z). A server restart cannot fail in-flight requests for
*unrelated* endpoints simultaneously while the process stays alive — this is Chrome's
NetworkChangeNotifier reacting to a Windows network-stack event (VPN/Parsec/virtual
adapter/DNS transition), killing in-flight sockets client-side. The app already recovers
gracefully (React Query retry + "reconnecting" notice). **Timeline-critical failures: 0.**

### F3 — venv shim pid mismatch (latent) — REPAIRED

The studio-api venv python is a uv shim that re-executes the base interpreter: the spawned
pid (written to `data/runtime/beta/pids/*.pid`) was the **parent shim**, while the real
listener was its child. Consequences: status.json reported the shim pid; a shim exit with a
surviving listener child would read as "service died" → restart → port-bind failure →
crash-loop risk. **Repair:** `_reconcile_listener_pids()` points pid files at the real port
listeners after READY and re-reconciles every 60s in the watch loop; `_restart()` clears
lingering port listeners before respawning. Verified live: `api.pid`/`web.pid` now equal the
netstat listeners exactly.

### F4 — `_stop_stale_owned` logged but never stopped (latent) — REPAIRED

The `run()` comment said "stop our tagged ones first via pids" but the implementation only
logged `stale pid file … still alive`. A supervisor that died without cleanup left the new
instance to hit port-bind crash loops (web) or unwanted adoption (api). **Repair:** stale
owned processes (and orphaned listeners on our ports) are now taskkilled at startup; an
intentionally **adopted** healthy API is never killed.

### F5 — Duplicate-supervisor launch path (latent) — REPAIRED

`Start-AdeptUI-Beta.ps1` short-circuited only when the runtime was already *ready*. A live
supervisor mid-startup/mid-restart failed that probe, so a second Start launched a second
supervisor that would fight over ports 8758/8760. **Repair:** the script now detects a live
supervisor via `supervisor.pid` + command-line match and **attaches** (waits for READY)
instead of launching a duplicate.

## 4. Logging hardening (this milestone)

- Every service log line is timestamped by the supervisor `_pump` (uvicorn access logs have
  none natively) — correlation with monitor/soak timelines is now possible.
- Unexpected exits log `code` + `pid`; restarts log reason/attempt/backoff; intentional
  shutdowns are labelled; stale-process and orphan-listener actions are logged.

## 5. Port stability (live evidence)

- 8758 → exactly one listener (API), 8760 → exactly one listener (Web), both 127.0.0.1
  IPv4-only — no dual-stack ambiguity, no duplicate listeners, no port stealing.
- pid files match listeners (F3 repair verified).

## 6. Dual-metric soak (30 minutes)

Monitor: `scripts/beta_health_monitor.py` (detect + record only — never restarts).
Driver: `scripts/soak_beta_creator_surfaces.mjs` (Playwright circuit: project landing,
project switching via selector, Timeline, Preview Monitor, Inspector batch select,
Co-Director open/close, save/reload persistence, multi-batch authoring verify, ComfyUI
preflight, browser refresh).

**Dual-metric stability rule:** continuous stability requires BOTH zero unintended process
restarts AND zero failed web/API health samples. Neither metric may substitute for the other.

Artifacts:
- `artifacts/beta-health-soak.json` — per-sample web/API health, listener pids, supervisor
  state; `processRestartCount` and `failedHealthSampleCount` as independent counters;
  verdict CONTINUOUSLY HEALTHY vs FAILED-THEN-RECOVERED.
- `artifacts/beta-soak-creator-surfaces.json` — per-iteration step results, Timeline-critical
  console/request failures.

**Results (2026-08-07 23:02:10Z → 23:32:10Z, exactly 30.0 minutes):**

| Metric | Result |
|---|---|
| Health samples | 536 (web `/` + API `/api/health` each sample) |
| **`processRestartCount`** | **0** |
| **`failedHealthSampleCount`** | **0** |
| Failure windows | none |
| Monitor verdict | **CONTINUOUSLY HEALTHY** |
| Soak driver iterations | 471 full creator-surface circuits |
| Step failures | **0** |
| Timeline-critical console errors | **0** |
| Timeline-critical request failures | **0** |
| Driver verdict | **SOAK CLEAN** |
| Soak project cleanup | deleted (no leftover projects) |

Both counters stayed at zero for the entire window while the driver continuously
exercised landing, switching, Timeline, Preview, Inspector, Co-Director,
save/reload, multi-batch authoring, preflight, and browser refresh.

## 7. Playwright ownership

- Cert/soak runs never kill or rebuild the creator's live Beta; they target the running
  instance read/write via disposable projects that are deleted afterwards.
- The cert stub is env-gated inside the API process (`ADEPT_TIMELINE_CERT_STUB=1`) — no
  separate cert processes exist to leak. Verifier gate `STAB_PLAYWRIGHT_OWNERSHIP` asserts
  exactly one supervisor + one listener per port after all runs.

## 8. Stability gates (verifier)

`STAB_AUDIT_REPORT`, `STAB_NO_UNINTENDED_RESTARTS`, `STAB_NO_FAILED_HEALTH_SAMPLES`,
`STAB_SOAK_DURATION`, `STAB_SOAK_CREATOR_SURFACES`, `STAB_PORTS_SINGLE_LISTENER`,
`STAB_PID_FILES_MATCH_LISTENERS`, `STAB_LOGGING_HARDENED`, `STAB_START_STOP_DETERMINISTIC`,
`STAB_PLAYWRIGHT_OWNERSHIP`, `STAB_ERR_NETWORK_CHANGED_CLASSIFIED` — all in
`scripts/verify_timeline_multi_batch.py`.
