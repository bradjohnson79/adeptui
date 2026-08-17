# Studio API Runtime Stability — Certification

**Status:** Governing document for this remediation milestone.
**Date:** 2026-08-17
**Branch:** beta
**Service:** Studio API http://127.0.0.1:8758 · Health GET /api/health (liveness GET /api/healthz)

---

## Root cause (proven from logs + code + runtime)

The Studio API instability traces to an **orphaned socket on :8758 owned by a phantom PID** (in netstat as LISTENING but with no live process; taskkill returns Access denied — the owner is in a session/elevation the operator shell cannot reach). Every lifecycle path then behaved badly:

| Failure | Evidence |
| --- | --- |
| **Restart loop (watchdog)** | studio_api.log: attempting restart #13..#20, each "Port 8758 held by PID 25408 - not studio uvicorn, leaving it." then "Restart failed." — repeated every backoff cycle because the phantom never clears |
| **Tunnel/API coupling** | manager.log: cloudflared restart #33..#35 — the tunnel health check depends on the API, so API-down drives tunnel restart churn |
| **Port-ownership misdetection** | Clear-StalePortOwner used Get-CimInstance Win32_Process which returns null for a phantom → command line empty → misclassified "not studio uvicorn" → returned false → caller ignored the value → started uvicorn → bind 10048 → false "Did not become healthy" |
| **Stop never verifies port release** | Stop-OwnedService removed the PID file after process death but never checked the socket was freed, so a phantom socket survived and poisoned the next start |
| **Multiple lifecycle owners** | supervisor.py (legacy V1.1, spawns uvicorn --workers 2), BetaBackendCommon.ps1 + Restart|Watch|Start-AdeptBetaBackend.ps1 (current), run-api.mjs (dev, uvicorn --reload), plus a Cursor-agent-launched web_server.py proxy — four independent launch/health/PID implementations |
| **Orphaned socket held by spawn children of a dead parent** | After killing the stale supervisor (9856) and its uvicorn children (21584/23660/43064/45676), the :8758 Listen socket persisted. Root cause was NOT a kernel orphan: two live orphaned multiprocessing.spawn workers (PID 22768 and 372, cmdline "from multiprocessing.spawn import spawn_main; spawn_main(parent_pid=25408, ...)") inherited the listening socket handle from their dead uvicorn parent 25408. netstat/Get-NetTCPConnection attribute the socket to the original creator (25408), which was absent from Get-Process/taskkill - so it read as a phantom. Fix: targeted taskkill /F on PIDs 22768 and 372 released the port immediately (verified port 8758 FREE). Root-cause lesson: an inherited-socket holder may outlive its recorded owner; lifecycle must kill process TREES (taskkill /T) and verify port release. |
| **False health via wrong regex** | Get-PortOwnerPid regex did not match the real netstat shape → returned wrong/unrelated PID |

## Previous topology (who could start/stop the API)

supervisor.py (legacy)         -> uvicorn :8758 --workers 2   (own PID + health + stop)
BetaBackendCommon + Restart    -> uvicorn :8758               (own PID + health)
Watch-AdeptBetaBackend        -> restarts on health miss      (own PID + backoff)
Start-AdeptBetaBackend        -> uvicorn :8758                (own PID + health)
run-api.mjs (npm run api)      -> uvicorn :8758 --reload      (dev launcher)
beta_health_monitor.py         -> observes only, never restarts

Three independent implementations of PID detection / launch / health / kill existed.

## Final topology (one authoritative owner)

BetaBackendCommon.ps1  (authoritative: identity, port, health, launch, stop, lock)
        |
        +-- Start-AdeptBetaBackend.ps1     -> Start-StudioApiAuthoritative (idempotent)
        +-- Restart-AdeptBetaBackend.ps1   -> port-release verify + authoritative start
        +-- Watch-AdeptBetaBackend.ps1     -> authoritative start (fails closed)
        +-- Stop-AdeptBetaBackend.ps1      -> Stop-OwnedService (verifies port release)
        +-- Get-AdeptBetaBackendStatus.ps1 -> shared health

One port (8758), one owner, one start path. supervisor.py is the legacy competitor (deprecated; not in the normal path). run-api.mjs remains the dev-mode launcher only.

## Process law (Phase 6)

Get-StudioApiPortState classifies the :8758 owner as one of:

  healthy   - reachable process answering /api/healthz  -> reuse (no-op)
  starting  - reachable uvicorn, not yet healthy        -> wait bounded readiness
  free      - no listener                                -> launch exactly one
  phantom   - in netstat, NOT in Get-Process            -> FAIL CLOSED + actionable message
  unrelated - reachable process, not uvicorn            -> FAIL CLOSED (never kill arbitrary)

A PID file is never treated as authority alone (Phase 6): identity requires PID + live process + command-line signature + health where applicable.

## Fixes shipped

1. Get-PortOwnerPid / Test-PortIsFree / Wait-PortReleased / Get-StudioApiPortState — authoritative identity + port helpers (correct regex).
2. Start-StudioApiAuthoritative — idempotent start: healthy → no-op; starting → wait; free → launch one; phantom/unrelated → fail closed with exact recovery command.
3. Clear-StalePortOwner — phantom now surfaces as an ERROR with taskkill guidance instead of an ignored false that caused a bind collision.
4. Stop-OwnedService — after killing, verifies :8758 is actually released; a surviving phantom is a hard failure, not a silent success.
5. Start/Restart/Watch — all route the API start through the single authoritative path; Restart refuses when :8758 is not free (no stacking).
6. Watcher law — the watchdog already required a 20-cycle busy threshold + backoff + restart lock; with fail-closed start it can no longer loop on a phantom.
7. Cloudflare tunnel decoupled from the API (Phase 13): Test-CloudflareHealth now checks the cloudflared PROCESS (pid file), not the API-through-tunnel — a dead API no longer drives cloudflared restart churn (was 35x).
8. ComfyUI port-owner call in Start-AdeptBetaBackend.ps1 migrated to the shared Get-PortOwnerPid (removed the duplicate _Get-PortOwnerPid everywhere).
9. PID identity guard (Phase 6): Stop-OwnedService now refuses to kill a pid-file PID that does not match the service signature (cmdline) or own the service port — a reused/stale PID can no longer kill an unrelated process (independent-verifier finding, fixed).
10. Storm protection bug fixed: Read-RestartHistory used @(ConvertFrom-Json) which wraps a JSON array as one element, so Test-StormProtection NEVER tripped (contributed to the watchdog restart loop). Now parses correctly; verified tripped at 6 events.
11. Start-AdeptBetaBackend.ps1 now takes the lifecycle lock (Set/Clear-BetaRestartLock) around its execute block (concurrent-start safety).
12. Regression suite is hermetic: redirects lifecycle state to an isolated TEMP dir (never mutates real beta-backend pid/lock/history files).


## Lifecycle evidence (Phase 16-17) — COMPLETE (measured)

**Phantom cleared:** on 2026-08-17 the phantom :8758 owner was cleared by killing the two orphaned spawn workers (PID 22768, 372); port verified FREE. Root cause was NOT a kernel orphan — see corrected Root cause table above.

**Measured cold-start evidence (Phase 10 — measured first, then bound):**
- Launch WITHOUT beta env: healthy in 1.4-3.3 s.
- Launch WITH beta env (production feature flags, MiniMax H3 readiness probes at 127.0.0.1:8192, audio-sandbox subprocess probes): **49.5-108 s** measured (cProfile of import alone: **62.2 s**: 36.5 s inside ensure_production_control -> warm_resolve_cache -> 12x H3 health probe ~24.6 s connect + 11.3 s subprocess sandbox probes; /api/capabilities cold first-call adds up to 51 s, cached after). This is app startup work, not a lifecycle defect (product code frozen per Phase 0).
- Bound decision: 60 s -> 90 s -> **120 s** (measured: typical 42-92 s, one 108 s observation). Still bounded and fail-closed; verified by the 10x restart run below.

**10x restart (Phase 16) — PASSED 10/10** (120 s bound; each cycle asserts old PID gone, exactly one :8758 listener, one alive owner, health 200, zero orphaned spawn children):
- Iterations 1-10: old=(alive=False), newOwner unique, listen=1, uvicorn=2 (one family: shim+child), health=200, spawn=0, restartExit=0 every cycle.
- Also verified: restart of a healthy-but-unrecorded API (no PID file, e.g. manually launched) now stops the VERIFIED port owner instead of refusing — new Stop-OwnedService fallback + Restart switch change (identity-safe, never on a number).
- Regression suite expanded to **23/23 PASS** (added: exclusive-lock second-claim refusal, stale-lock reclaim after holder death, stop-without-pid-record verified owner / phantom fail-closed / unrelated refuse).

**10x start-while-healthy (Phase 16) — PASSED 10/10:** every iteration a true no-op (same owner 46952, listen=1, health 200, ~0.5 s), judged by observable state.

**Concurrency (Phase 17) — PASSED 3/3** (two REAL separate powershell processes; Start-Job + Start-Process redirect deadlocks the child and was a harness artifact, see Known limitations):
- A restart+restart: one won, one refused (exclusive lock), final listen=1 health=200 uvicorn=2.
- B start+start: one won, one refused, final listen=1 health=200.
- C restart-during-start: one won, one refused, final listen=1 health=200.
- Phase 7 exclusive lifecycle lock implemented: Set-BetaRestartLock now atomic-claims (CreateNew) and REFUSES a live holder; Clear only releases own claim; Start/Restart/Watchdog all gate on it; stale lock (dead holder) reclaimable.

**Watcher law (Phase 8) — VERIFIED live:** watchdog running at 5 s interval during a manual restart logged "Manual restart in progress - watchdog holding" and did NOT fight; API healthy after. Watchdog's own restarts now take the same exclusive lock (try/finally), so it can never race an operator operation.

## Workload soak (Phase 18) — PASSED (measured)

- Run: 2026-08-17T22:07:04Z to ~23:07Z, 60 minutes, interval 15 s, **92 cycles**.
- Workload per cycle (7 endpoints x 92 = **644 calls**): /api/health, project GET, Library GET, Timeline workspace/master GET, Scene Creator workspace, Spatial Map GET, /api/capabilities (120 s timeout; cold probe 51-60 s, cached 0.1 s).
- **endpointFailures = 0** (all 644 calls returned 200).
- **unexpectedExits = 0** — same uvicorn family (owner PID 7672) alive the entire hour.
- **duplicate processes = 0** — uvicorn count stayed 2 (one shim+child family) every cycle.
- **restart loops = 0** — ownerChanges = 0; no lifecycle intervention during the hour.
- PASS criteria met exactly as specified: unexpected exits 0, duplicate processes 0, restart loops 0.
- Evidence: .runtime/cert-soak-60min.json + .runtime/cert-soak-60min.log.

## Crash count

**0 crashes / 0 unexpected exits** during the 60-minute soak (also 0 during all lifecycle certification runs).

## UI continuity (Phase 19) — MEASURED

- :8760 web server (web_server.py, PID 44752) serves the SPA root (200) and proxies API calls to :8758.
- Through the :8760 proxy (Schnick Coffee 2347bf46-3762-4763-86c5-4a6032522278): healthz 200, Library GET 200 (1.0 MB), Timeline workspace/master GET 200, Scene Creator workspace 200 (331 KB), Spatial Map GET 200, project GET 200 (1.5 MB).
- No intermittent offline banner observed at the proxy boundary during the check window (healthz through proxy 200).
- Known limitation: /api/capabilities cold read through the legacy :8760 proxy can 504 (proxy 10 s timeout vs 51-60 s cold probe; TTL 20 s). Hosted path (Vercel -> cloudflare -> :8758) and direct API unaffected. Documented; product code frozen per Phase 0.

## Final operator commands

  .\Restart-AdeptBetaBackend.ps1 -Service studio_api   # deterministic restart
  .\Start-AdeptBetaBackend.ps1                          # idempotent start (healthy -> no-op)
  .\Stop-AdeptBetaBackend.ps1                           # stop owned services
  .\Get-AdeptBetaBackendStatus.ps1                      # status
  .\Watch-AdeptBetaBackend.ps1                          # watcher (consecutive-failure recovery)

If a phantom :8758 owner is reported: taskkill /F /PID <pid> (elevated) or reboot. Note: an owner that is in netstat but whose process is absent is often a live orphaned multiprocessing.spawn child holding an inherited socket — verify with: Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'spawn_main' }.

## Known limitations

- Development-session stability is the goal; machine reboot still requires starting Beta (no OS autostart added).
- A phantom socket held by an orphaned spawn child (dead parent) is now recoverable: lifecycle stops VERIFIED owners even without a PID record, and fails closed on phantom/unrelated. A truly kernel-level orphan (absent from Get-Process and all children) still requires elevation/reboot — documented operator step, not auto-killed.
- supervisor.py remains on disk as legacy (not deleted in this milestone) but is not in the normal startup path.
- Start-Job + Start-Process -RedirectStandardOutput deadlocks the child uvicorn under this host (err log stays empty, process alive but never binds) — this was a HARNESS ARTIFACT, not a lifecycle defect. The concurrency certification therefore launches two real separate powershell.exe -File processes (operator-realistic).
- Legacy :8760 web proxy (web_server.py) has a 10 s upstream timeout while /api/capabilities cold probes take 51-60 s on this machine (SNAPSHOT_TTL_SEC = 20 s in capabilities/service.py) — a cold read through the legacy proxy returns 504 Gateway Timeout. The hosted path (Vercel -> cloudflare -> :8758) and direct API calls are unaffected (200 after the slow probe; cached reads 0.1 s). This is the retired :8760 stack (Build Law #15), not the current hosted Beta path; product code frozen per Phase 0, so no change made here — documented as a known limitation. The four mission-listed screens (Library, Timeline workspace/master, Scene Creator workspace, Spatial Map) all return 200 through the proxy.

---

**RUNTIME CERTIFICATION COMPLETE — pending independent-verifier confirmation:**

- Phantom :8758 owner cleared (orphaned spawn children 22768/372 killed; port verified FREE).
- 10x restart: PASSED (120 s bound; old PID gone, one listener, health 200, 0 orphans each cycle).
- 10x start-while-healthy: PASSED (all no-ops, same owner).
- Concurrency 3/3: PASSED (one wins + one refuses under exclusive lock; no duplicate launch).
- Watcher law: VERIFIED live (holds during manual restart; own restarts gated by exclusive lock).
- 60-min soak: PASSED (92 cycles, 644 endpoint calls, 0 failures, 0 exits, 0 duplicates, 0 restarts).
- Regression suite: 23/23 PASS.
- Code-level verifier f13b37ba previously returned VERIFIED (code-level); runtime verifier (6e58d5d5) in progress.

**FINAL VERDICT: PENDING** — set to GO/NO-GO after the independent runtime verifier confirms the measured evidence.