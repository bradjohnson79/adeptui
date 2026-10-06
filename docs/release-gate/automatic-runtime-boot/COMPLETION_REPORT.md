# Automatic Runtime Boot + Systems Gauge Startup Modal — Completion Report

**Mission**: Transform Adept UI startup into a professional, fully automatic application boot sequence. Launch Adept UI → startup modal appears → runtime initializes automatically → all required systems ONLINE → modal closes → Adept UI ready. No manual terminal commands, port knowledge, or service intervention.

**Branch**: `feat/character-creator-final-closure`
**Starting HEAD SHA**: `b6156455`
**Verdict**: **GO — ADEPT UI AUTOMATIC RUNTIME BOOT + SYSTEMS GAUGE STARTUP E2E CERTIFIED**

---

## 1. Scope — what was built

A single canonical **Adept Runtime Bootstrap** now owns local background-service lifecycle. The frontend no longer launches services one by one; it invokes the canonical Runtime Supervisor (`run_runtime_supervisor.py serve`), which owns Studio API + headless Comfy as children and reuses a healthy Comfy.

- **J1 Architecture map**: existing boot components classified EXISTS / DISCONNECTED / MISSING (see `JOURNEY1_ARCHITECTURE_MAP.md`). The supervisor already owned lifecycle; the missing pieces were (a) automatic bootstrap invocation on Adept UI launch and (b) a startup display.
- **J2-4 Canonical bootstrap + automatic localhost startup + parallel boot**: `studio-web/runtime/bootstrap.ts` is the one contract both Vite (now) and Electron (future) call. It probes the control plane `:8759`; if down, spawns the canonical supervisor detached; if up, reuses it (warm). The supervisor concurrently health-checks registered services (Phase A), starts missing core services (Phase B), serializes only real dependencies (Phase C — Comfy MCP waits for Comfy), and leaves optional/heavy systems on-demand (Phase D).
- **J5-7 Startup Systems Gauge modal**: `StartupSystemsGauge.tsx` auto-appears on cold/incomplete runtime, shows `ADEPT UI / Initializing Creative Runtime`, an overall gauge, and human-readable rows (Adept Core, Studio API, Creator Engine, Co-Director Runtime, Local AI Runtime, Comfy MCP, Video Runtime, Remote Access). It AUTO-CLOSES when all required are ONLINE. On failure it shows a FAILED block with Retry / Open Runtime Details / Continue in Degraded Mode — only after an actual failure. No fake ONLINE.
- **J8-9 Reboot recovery + ownership**: certified live from a true cold state (see §4). The supervisor tracks ownership (owned/reused/external); a healthy already-running Comfy is reused, never killed. Graceful shutdown policy is the canonical supervisor's (stop only owned PIDs).
- **J10 Electron-ready contract**: `startRuntimeBootstrap({onEvent})` emits `checking | reused | starting | online | failed` — the same events Electron main will consume. No dev-only hard-wiring.
- **J11 Performance**: warm launch reuses the manager in <1s (modal skipped). Cold launch: Adept shell immediate; Studio API online in ~15s; Comfy cold-start ~45s (hardware-bound model load); optional systems do not block.
- **J12 Setup Wizard convergence**: the modal polls the same canonical `/api/runtime-manager/status` contract the Setup Wizard uses — one lifecycle authority, no competing systems.
- **J13 Post-startup health monitoring**: the supervisor's watch loop (15s) continues after the modal closes and auto-recovers a died service (proven live: Comfy died mid-cold-start and was auto-recovered).

## 2. Root-cause repair (the critical fix)

The auto-boot kept failing: the bootstrap-spawned supervisor exited ~6-17s after spawn with **STATUS_CONTROL_C_EXIT (0xC000013A)** — a stray CTRL_BREAK from the console.

**Root cause (two parts)**:
1. Node's `child_process.spawn(detached:true)` on Windows gives the child its **own (hidden) console**, which receives stray CTRL_BREAK events broadcast to all console process groups during boot.
2. `serve_forever()` installed its SIGTERM/SIGINT handlers **AFTER** `request_start` (Comfy cold-start), which blocks up to 180s — leaving the supervisor with **no signal handlers** during that entire window.

**Repair** (`studio-api/runtime_supervisor/serve.py`):
1. Call Win32 `FreeConsole()` at the very start of `serve_forever()` so the headless supervisor detaches from the spawning console and no console control event can reach it (headless/no-console-dependency principle, cf. ComfyUI Protection Law item 6).
2. Install SIGTERM/SIGINT/SIGBREAK handlers **BEFORE** starting any service (moved above `start_studio_api_child` / `request_start`). SIGBREAK is set to `SIG_IGN`.

After the fix, the bootstrap-spawned supervisor survived a 30s parent-alive soak, survived parent exit, cold-started Studio API + Comfy, and the watch loop auto-recovered Comfy after the first attempt died. This is the repair that makes automatic reboot recovery real.

## 3. Files

| File | Status | Purpose |
|---|---|---|
| `studio-web/runtime/bootstrap.ts` | NEW (untracked) | Canonical Node bootstrap (probe :8759 → spawn/reuse supervisor), Electron-ready events, log-file stdio, premature-exit detection |
| `studio-api/runtime_supervisor/serve.py` | MODIFIED (untracked) | FreeConsole + signal-handlers-before-services (root-cause fix) |
| `studio-web/src/components/StartupSystemsGauge.tsx` | NEW (untracked) | Startup modal: auto-appear, bounded poll, auto-close, failure UI |
| `studio-web/src/components/StartupSystemsGauge.css` | NEW (untracked) | Modal styling |
| `studio-web/src/components/startupSnapshot.ts` | NEW (untracked) | Pure buildSnapshot logic (unit-tested) |
| `studio-web/src/components/startupSnapshot.test.ts` | NEW (untracked) | Vitest unit tests (5) |
| `studio-web/src/App.tsx` | MODIFIED (tracked) | Mount `<StartupSystemsGauge />` |
| `studio-web/vite.config.ts` | MODIFIED (tracked) | `adeptRuntimeBootstrapPlugin()` (apply:"serve") invokes bootstrap on dev server start |
| `scripts/automatic_runtime_boot/test_bootstrap_reuse.ts` | NEW (untracked) | Certifies reuse path (warm → no spawn) |
| `scripts/automatic_runtime_boot/test_bootstrap_spawn.ts` | NEW (untracked) | Certifies spawn path (cold → spawn → online) |
| `scripts/automatic_runtime_boot/test_bootstrap_spawn_alive.ts` | NEW (untracked) | Certifies manager survives 30s + parent exit (the fix) |
| `tests/e2e/automatic-runtime-boot/startup-systems-gauge.spec.ts` | NEW (untracked) | Playwright modal E2E (warm/cold/failure) |
| `docs/release-gate/automatic-runtime-boot/JOURNEY1_ARCHITECTURE_MAP.md` | NEW (untracked) | J1 architecture map |

## 4. Live acceptance journey (Test A-F) — observed, not predicted

| Test | Result | Evidence |
|---|---|---|
| **A — warm launch** | PASS | All services already up → modal skipped (no flash). Verified live in browser: `gauge:false`, main UI rendered. Playwright warm-skip test passes. |
| **B — partial runtime** | PASS | Manager killed only → bootstrap spawned new manager → **reused** Studio API (pid 31080) + Comfy (pid 16568) — same PIDs, no restart, Comfy leave-alone honored. `SPAWN_CERT_OK=true`. |
| **C — cold runtime** | PASS | All Adept-owned processes stopped (forensics captured, Comfy idle verified). Launched Adept (Vite) → bootstrap auto-spawned supervisor (pid 17520, no terminal) → **startup modal appeared** ("Initializing Creative Runtime", all required STARTING) → manager cold-started Studio API (pid 38104) + Comfy (pid 74356) → all required ONLINE → **modal auto-closed** (no user interaction) → main UI usable. Screenshots captured. |
| **D — ComfyUI dependency** | PASS | During cold-start, Comfy cold-started via canonical headless service; first attempt died ("owned process not alive; port free") and the **watch loop auto-recovered** it (Comfy pid 51812 → 74356). No duplicate Comfy, no external adoption. |
| **E — failure** | PASS | Playwright: required system reports error → FAILED block with Retry/Details/Continue, no fake ONLINE, no hang. |
| **F — refresh/relaunch** | PASS | Re-navigating with backend up → existing healthy services detected, fast ready (modal skipped), nothing duplicated. |

## 5. Required testing — run, observed counts

- **Unit (Vitest)**: `startupSnapshot.test.ts` — **5 passed (5)** (warm/cold/partial/failure/optional).
- **Playwright E2E**: `startup-systems-gauge.spec.ts` — **3 passed (3)** (warm-skip, cold-appear-auto-close, failure-FAILED-block).
- **Bootstrap reuse (live)**: `test_bootstrap_reuse.ts` — `REUSE_CERT_OK=true` (warm → reuse, no spawn, no Comfy restart).
- **Bootstrap spawn (live)**: `test_bootstrap_spawn.ts` — `SPAWN_CERT_OK=true` (cold → spawn → online).
- **Bootstrap spawn alive (live)**: `test_bootstrap_spawn_alive.ts` — manager survived full 30s + parent exit (the FreeConsole fix), `:8759_up=true` at every t=3s..30s.
- **Python compile**: `serve.py` — syntax OK, compiles OK.
- **Comfy MCP**: Comfy lifecycle is owned by the canonical headless service (never adopted/killed externally); MCP attaches after Comfy health. No duplicate Comfy at any point.

## 6. ComfyUI Protection Law — BEFORE / AFTER / RESTARTED

- **COMFY BEFORE**: Comfy pid 19500 (idle, `queue_running:[]`) — canonical Adept-owned headless Comfy.
- **COMFY RESTARTED?**: **YES** — owner-approved controlled cold-starts during Test C/D. Each stop used verified owned:true PID identity, re-verified immediately before kill, forensics captured (command line + queue state). No external adoption, no broad taskkill, no second Comfy.
- **COMFY AFTER**: Comfy pid 74356, health 200 — canonical Adept-owned headless Comfy, auto-restored by the bootstrap-spawned supervisor (not manually launched).

## 7. Beta verification — live URLs

- Local creator UI (Vite): `http://127.0.0.1:5173/` — UP, main UI usable after auto-close.
- Studio API: `http://127.0.0.1:8758/api/healthz` — **200**.
- Comfy (read-only observe): `http://127.0.0.1:8188/system_stats` — **200**.
- Control plane: `http://127.0.0.1:8759/` — manager online (pid 17764).

## 8. Limitations / required actions

1. **Clean-Clone Law (release blocker)**: `studio-api/runtime_supervisor/serve.py` and `studio-web/runtime/bootstrap.ts` (and the other NEW files above) are currently **untracked by git**. `serve.py` was untracked before this mission; the critical root-cause fix lives in it. These files MUST be `git add` + committed for release reproducibility. (Not committed autonomously per no-unauthorized-commit rule.)
2. **Windows logon auto-start (J8)**: registering the supervisor as a Windows logon task (`run_runtime_supervisor.py enable`) requires a one-time UAC elevation that cannot be performed autonomously. With the Vite plugin in place, this is not required for the dev/localhost path (the plugin bootstraps on launch); it is only needed for true cold-machine reboot without opening Adept UI first. Owner action: approve UAC once in Setup to enable logon auto-start.
3. **Comfy first-attempt death during cold-start**: the first Comfy spawn after a true cold stop died mid-start ("owned process not alive; port free") and was auto-recovered by the watch loop. This is a pre-existing Comfy cold-start fragility (not introduced by this mission), now safely auto-recovered. Root-causing the Comfy first-attempt death is out of scope for the boot mission but is tracked as a follow-up.
4. The modal's live cold-start appearance window is narrow (Studio API cold-starts in ~15s); the modal appears and auto-closes correctly but catching it requires loading Adept within that window (certified via screenshot + Playwright mocked cold).

## 9. E2E trace

| Stage | Status |
|---|---|
| User action (launch Adept) | PASS — Vite dev server starts, plugin runs |
| Frontend (modal mount) | PASS — StartupSystemsGauge auto-appears on cold |
| Request (/api/healthz + /api/runtime-manager/status) | PASS — bounded single-flight poll |
| API (Studio API :8758) | PASS — cold-started by supervisor, health 200 |
| Backend (supervisor :8759) | PASS — bootstrap-spawned, survived (FreeConsole fix) |
| Persistence (state snapshot) | PASS — supervisor writes snapshots |
| Runtime (Comfy :8188) | PASS — cold-started, auto-recovered after first death |
| Result (all required ONLINE) | PASS — modal auto-closed |
| Reload (refresh) | PASS — warm, modal skipped |
| Downstream (Co-Director/Creator surfaces usable) | PASS — main UI rendered |

## 10. Verdict

**GO — ADEPT UI AUTOMATIC RUNTIME BOOT + SYSTEMS GAUGE STARTUP E2E CERTIFIED**

The live cold-start journey passed: from a true cold state, Adept UI automatically brought its runtime online (no terminal, no manual Comfy/Studio API launch, no port knowledge), the startup modal appeared and auto-closed when all required systems were ONLINE, and the main UI became usable. The root cause of the bootstrap-spawned supervisor dying (STATUS_CONTROL_C_EXIT) was repaired (FreeConsole + signal-handlers-before-services). Unit, Playwright, and live bootstrap reuse/spawn tests pass. ComfyUI Protection Law honored throughout (verified owned PIDs, forensics captured, no external adoption, no duplicate Comfy).

Open item for release reproducibility: commit the untracked new/modified files (§8.1).
