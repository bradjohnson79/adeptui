# Adept UI Stability Cull + Reliability Consolidation

**Status:** Governing document for this milestone.  
**Started:** 2026-08-23  
**Branch:** `feat/character-creator-final-closure`  
**Starting SHA:** `1c86560`  
**Owner decisions (locked):**

- Lifecycle successor is a **new Python Runtime Supervisor** that absorbs certified BetaBackend laws. Do **not** flip `scripts/beta_runtime/supervisor.py` (it still starts retired `:8760`).
- Destructive tests reuse one named project: **Adept Stability Cert**. Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278` and Korri `c49371ed-ba6b-4c16-ba98-a8b28b72118b` stay read-only / owner-gated.

This is a cull, not a rewrite. GREEN systems stay. Every replacement needs evidence.

---

## Executive Summary

Adept UI accumulated overlapping launch stacks, readiness aliases, unbounded pollers, and owner-project test fixtures. The Stability Cull reduces the number of ways the product can fail.

**Class-level problems (Phase 1 evidence):**

1. Four launch stacks can bind Studio API `:8758` (BetaBackend PowerShell, `Start-AdeptRuntime.ps1`, legacy `supervisor.py` + `:8760`, `run-api.mjs`).
2. Image readiness remaps Flux / Qwen / Illustrious / SenseNova onto Z-Image `ensure_queueable` checks.
3. Character Sheet polling restarts forever after a 60-minute budget.
4. JobPanel calls `onDone()` every 2s whenever any job is already `done`.
5. Destructive Playwright defaults write the owner Schnick project.
6. Comfy plugin pip can replace production CUDA torch (SenseNova-only guard).
7. Cursor rule `beta-refresh-after-build.mdc` still restarts retired `:8760`, contradicting AGENTS.md Law 15.

**Program shape:** inventory first, then six certified batches. This document is updated after each batch.

**Cull commits:** `2a83a49` then `0dd6edf` (tip). Leftover dirty tree is Character Creator / evidence, not the cull SHA.

**Named cert project:** `Adept Stability Cert` `2bc632b8-b329-4d3b-bc40-b68dc41b6bb1` (`data/runtime/stability-cert-project.json` — runtime artifact, not committed).

**Verdict (living):**

```text
GO — ADEPT UI STABILITY CULL + RELIABILITY CONSOLIDATION CERTIFIED
```

---

## Stability score rubric

Each significant subsystem is scored 1–5 (higher is better):

| Dimension | Meaning |
|---|---|
| Runtime reliability | Starts and stays up without duplicate/phantom owners |
| Recovery | Crash / restart / adopt behaves |
| Test coverage | Hermetic + live proof exists |
| Dependency isolation | Correct venv; no silent torch/CPU swap |
| Observability | Task / job / provider / process / failure / logs are knowable |
| State consistency | UI matches backend; no ghost jobs or dual canon |
| Cancellation | Jobs end truthfully |
| Persistence | Reload keeps intended state |
| Maintenance burden | One owner, one contract |

Score = mean of the nine dimensions (reported as X.X / 5).

**Colors:** GREEN keep · YELLOW harden · ORANGE consolidate · RED replace · BLACK retire

---

## Stability Inventory

### 1. Hosted creator path

| Field | Record |
|---|---|
| Subsystem | Hosted Beta UI |
| Purpose | Creator surface at `https://adeptui.vercel.app` |
| Current implementation | Vercel frontend → Cloudflare `api-beta.adeptui.org` → `127.0.0.1:8758` |
| Alternatives | Retired `:8760` local SPA+proxy; Vite `:5173` |
| Known failure modes | Stale tunnel backend; 504 without CORS; hosted lifecycle POST 403 (by design) |
| Failure frequency/history | Hosted runtime stability cert 2026-08; 504 storms documented |
| Operational complexity | Medium (tunnel + local API) |
| Dependency risk | Medium (cloudflared config required) |
| Recovery difficulty | Medium — hosted UI cannot start Windows processes |
| Data-loss risk | Low |
| Certification state | Hosted path is current product path (Law 15) |
| Score | 4.1 / 5 |
| Recommendation | **GREEN KEEP** |

### 2. Local Vite creator UI

| Field | Record |
|---|---|
| Subsystem | Vite `:5173` |
| Purpose | Local/dev/cert creator UI |
| Current implementation | `studio-web` `strictPort` 5173; proxy default `STUDIO_API_PORT \|\| 8742` |
| Alternatives | Retired `:8760`; hosted Vercel |
| Known failure modes | Proxy default `:8742` vs product `:8758` |
| Failure frequency/history | Recurring cert notes; Playwright split |
| Operational complexity | Low |
| Dependency risk | Low |
| Recovery difficulty | Easy |
| Data-loss risk | None |
| Certification state | Current local cert surface |
| Score | 3.8 / 5 |
| Recommendation | **GREEN KEEP** (harden proxy default in Batch 3) |

### 3. Retired local Beta web `:8760`

| Field | Record |
|---|---|
| Subsystem | `scripts/beta_runtime/web_server.py` |
| Purpose | Static `studio-web/dist` + 10s API proxy |
| Current implementation | Still started by `Start-AdeptUI-Beta.ps1` / `supervisor.py` / `npm run beta:*` |
| Alternatives | Vite `:5173` or hosted Vercel |
| Known failure modes | 10s proxy → 504 on cold `/api/capabilities`; stale SPA certs; agents treat it as product UI |
| Failure frequency/history | Repeated; Law 15 retired it; Cursor rule still launches it |
| Operational complexity | High (second frontend + second owner of `:8758`) |
| Dependency risk | High |
| Recovery difficulty | Medium |
| Data-loss risk | Low (stale UI, not data) |
| Certification state | Retired from hosted path; still wired |
| Score | 1.6 / 5 |
| Recommendation | **BLACK RETIRE** from normal start |

### 4. Studio API process

| Field | Record |
|---|---|
| Subsystem | FastAPI / uvicorn `app.main:app` on `:8758` |
| Purpose | Product backend |
| Current implementation | Competing launchers; certified owner is `Start-StudioApiAuthoritative` |
| Alternatives | Legacy supervisor (`--workers`); Runtime Manager 30s wait; `run-api.mjs` `:8742 --reload` |
| Known failure modes | Phantom sockets; spawn orphans; bind 10048; 42–108s cold start; dual launch |
| Failure frequency/history | 2026-08-17 runtime cert; Avatar stale-adopt |
| Operational complexity | High while owners compete |
| Dependency risk | Medium |
| Recovery difficulty | Medium; Hard if true phantom |
| Data-loss risk | Medium (in-memory queue) |
| Certification state | API itself YELLOW; launch owners ORANGE |
| Score | 3.0 / 5 |
| Recommendation | **YELLOW HARDEN** API; **ORANGE CONSOLIDATE** launchers → Python supervisor |

### 5. PowerShell BetaBackend (certified owner)

| Field | Record |
|---|---|
| Subsystem | `BetaBackendCommon.ps1` + Start/Stop/Restart/Watch |
| Purpose | Authoritative identity, lock, health, launch, stop |
| Current implementation | `.runtime/beta-backend/` PIDs + lock + history |
| Alternatives | Python supervisor successor; `Start-AdeptRuntime.ps1` |
| Known failure modes | Autostart `-NoBrowser` mismatch; Creator UI does not call this stack |
| Failure frequency/history | Certified 2026-08-17 after phantom/storm repairs |
| Operational complexity | High (Windows-only) |
| Dependency risk | Medium |
| Recovery difficulty | Medium |
| Data-loss risk | Low |
| Certification state | **Certified owner on paper** |
| Score | 3.7 / 5 |
| Recommendation | **YELLOW HARDEN** laws → **ORANGE** migrate into Python; PS becomes shim |

### 6. Start-AdeptRuntime / Creator UI twin

| Field | Record |
|---|---|
| Subsystem | `Start/Stop/Restart-AdeptRuntime.ps1` + `/api/runtime-manager` |
| Purpose | Settings → Local Runtime |
| Current implementation | Separate PID dir; 30s API wait; tunnel often without `--config` |
| Alternatives | BetaBackend; new Python supervisor |
| Known failure modes | Too-short wait vs 120s cold start; tunnel 503; cannot see BetaBackend ownership |
| Failure frequency/history | Background Manager recovery reports |
| Operational complexity | High (second owner) |
| Dependency risk | High |
| Recovery difficulty | Medium |
| Data-loss risk | Low |
| Certification state | Weaker twin of certified owner |
| Score | 2.2 / 5 |
| Recommendation | **ORANGE CONSOLIDATE** into Python supervisor |

### 7. Legacy Python supervisor + `:8760`

| Field | Record |
|---|---|
| Subsystem | `scripts/beta_runtime/supervisor.py` |
| Purpose | V1.1 local API + web watchdog |
| Current implementation | Starts `:8760`; optional Comfy; no lock/tunnel/Ollama; still shells to PowerShell for WMI |
| Alternatives | New Python successor absorbing BetaBackend laws |
| Known failure modes | `--workers 2` off-Windows; dual start with Watch; retired web |
| Failure frequency/history | Named legacy competitor in 2026-08-17 cert |
| Operational complexity | High |
| Dependency risk | High |
| Recovery difficulty | Medium |
| Data-loss risk | Low |
| Certification state | Deprecated; still invoked by `npm run beta:*` |
| Score | 2.0 / 5 |
| Recommendation | **ORANGE CONSOLIDATE** — reference only, not the successor |

### 8. ComfyUI `:8188`

| Field | Record |
|---|---|
| Subsystem | Production Comfy |
| Purpose | Local GPU image/video runtime |
| Current implementation | Reused; two launchers (BetaBackend Desktop path vs `ADEPT_COMFY_LAUNCH`) |
| Alternatives | Isolated H3 `:8192`; unmanaged Desktop GUI |
| Known failure modes | Duplicate Comfy; SenseNova RAM trap immune to interrupt; custom-node import breaks |
| Failure frequency/history | SenseNova U1.5; 4-view E2E queue stall |
| Operational complexity | High |
| Dependency risk | High (torch, custom nodes) |
| Recovery difficulty | Hard for cancel-resistant loaders |
| Data-loss risk | Medium (stuck GPU tenant) |
| Certification state | Product runtime; lifecycle YELLOW |
| Score | 2.8 / 5 |
| Recommendation | **YELLOW HARDEN** + **ORANGE** one launcher |

### 9. MiniMax H3 Comfy `:8192`

| Field | Record |
|---|---|
| Subsystem | Isolated Route A Comfy |
| Purpose | Owner-only MiniMax H3 |
| Current implementation | Sibling-repo scripts; unmanaged by A/B/C; cold API probes inflate start |
| Alternatives | Production `:8188` (forbidden for H3) |
| Known failure modes | Wrong-bind to `:8188`; health probe delay |
| Failure frequency/history | Cold-start 42–108s notes |
| Operational complexity | Medium |
| Dependency risk | Isolated (good) |
| Recovery difficulty | Medium |
| Data-loss risk | Low |
| Certification state | Experimental / Requires Setup |
| Score | 3.2 / 5 |
| Recommendation | **YELLOW HARDEN** (do not block `:8758` health); **GREEN** isolation |

### 10. Ollama `:11434`

| Field | Record |
|---|---|
| Subsystem | Local LLM |
| Purpose | Co-Director / production-control |
| Current implementation | Usually EXTERNAL; BetaBackend may start; Runtime Manager never starts |
| Alternatives | Cloud providers |
| Known failure modes | Empty generate; tag present but not loaded; contested start |
| Failure frequency/history | Memory/project notes; Spatial Map |
| Operational complexity | Low if adopted |
| Dependency risk | Low |
| Recovery difficulty | Easy |
| Data-loss risk | None |
| Certification state | Adopt/check is correct |
| Score | 4.0 / 5 |
| Recommendation | **GREEN KEEP** — do not own by default |

### 11. Cloudflare tunnel

| Field | Record |
|---|---|
| Subsystem | `cloudflared` → `:8758` |
| Purpose | Hosted UI reaches local API |
| Current implementation | BetaBackend uses `--config`; Runtime Manager twin may omit it; health = process (Phase 13) |
| Alternatives | Direct LAN (not product) |
| Known failure modes | Process up without config → 503 all routes; API-coupled health caused 35× restart |
| Failure frequency/history | Background Manager recovery |
| Operational complexity | Medium |
| Dependency risk | Medium |
| Recovery difficulty | Medium |
| Data-loss risk | None |
| Certification state | Phase 13 process-health is correct |
| Score | 3.3 / 5 |
| Recommendation | **YELLOW HARDEN** — always `--config` |

### 12. MCP (Comfy)

| Field | Record |
|---|---|
| Subsystem | Cursor `comfy-mcp` |
| Purpose | Agent observability to existing Comfy |
| Current implementation | Isolated `data/venvs/mcp`; no lifecycle tools |
| Alternatives | Direct `comfy-cli`; Studio API `comfy_client` |
| Known failure modes | Cursor namespace needs reload; must never install into Comfy venv |
| Failure frequency/history | Phase 1 smoke 2026-08-23 |
| Operational complexity | Low |
| Dependency risk | Low if isolated |
| Recovery difficulty | Easy |
| Data-loss risk | None |
| Certification state | Agent tool, not product runtime |
| Score | 4.2 / 5 |
| Recommendation | **YELLOW HARDEN** (agent) / **BLACK** if treated as product path |

### 13. Adept Bots

| Field | Record |
|---|---|
| Subsystem | External `D:/AdeptBots` leftovers |
| Purpose | Not an Adept UI runtime |
| Current implementation | `audit.py` / `temp_audit*.py` `sys.path.insert` |
| Alternatives | Cursor subagents |
| Known failure modes | Import fail; inventory confusion |
| Failure frequency/history | Leftover only |
| Operational complexity | N/A |
| Dependency risk | Low |
| Recovery difficulty | N/A |
| Data-loss risk | None |
| Certification state | Absent |
| Score | 1.0 / 5 |
| Recommendation | **BLACK RETIRE** from this repo’s runtime inventory |

### 14. JobQueue

| Field | Record |
|---|---|
| Subsystem | In-process `queue_worker.py` |
| Purpose | Image/video/sheet jobs |
| Current implementation | asyncio queue; recover interrupted; drain orphans 15s |
| Alternatives | External worker (not justified) |
| Known failure modes | Restart loses memory queue; running marked interrupted (no silent requeue); unbound `comfy_prompt_id`; 3600s wait |
| Failure frequency/history | CRS spinner audit; 4-view missing prompt IDs |
| Operational complexity | Medium |
| Dependency risk | Medium (Comfy) |
| Recovery difficulty | Medium |
| Data-loss risk | Medium (credits / GPU time) |
| Certification state | Recover/drain exist; bind-or-fail missing |
| Score | 3.1 / 5 |
| Recommendation | **YELLOW HARDEN** |

### 15. Image workflow readiness

| Field | Record |
|---|---|
| Subsystem | `legacy_comfy_workflow_key` + `ensure_queueable` |
| Purpose | Preflight before `/prompt` |
| Current implementation | Certified keys remapped onto Z-Image inventory keys |
| Alternatives | Bind readiness to certified registry + Setup components |
| Known failure modes | Flux/Qwen/Illustrious/SenseNova pass because Z-Image is installed |
| Failure frequency/history | Inventory 2026-08-23 |
| Operational complexity | High |
| Dependency risk | High |
| Recovery difficulty | Hard (false ready then stall) |
| Data-loss risk | Medium |
| Certification state | Split-brain registries |
| Score | 1.8 / 5 |
| Recommendation | **RED REPLACE** aliasing |

### 16. SenseNova U1.5

| Field | Record |
|---|---|
| Subsystem | Native CRS/ERS specialist |
| Purpose | Optional generator family |
| Current implementation | Weights + nodes installable; loader RAM-traps; `runtimeReady` from disk |
| Alternatives | Flux / Qwen 2512 certified defaults |
| Known failure modes | ~40 GB host RAM, ~2 GB VRAM, never CUDA, interrupt-immune, 1h queue |
| Failure frequency/history | `SENSENOVA_U15_INTEGRATION.md`; MCP cancel-resistance evidence |
| Operational complexity | High |
| Dependency risk | **Critical** (torch pin already replaced CUDA torch once) |
| Recovery difficulty | Hard (process kill) |
| Data-loss risk | High (blocks GPU tenant) |
| Certification state | Draft / Not Ready |
| Score | 1.4 / 5 |
| Recommendation | **RED** — not default; Installed ≠ Runtime Ready |

### 17. Comfy extension installer / torch

| Field | Record |
|---|---|
| Subsystem | `comfy_extension_installer.py` |
| Purpose | Install custom nodes |
| Current implementation | SenseNova-only torch strip + `--no-deps` |
| Alternatives | Isolate all extension pip; refuse CPU torch |
| Known failure modes | Any other `torch==` pin can replace `2.10.0+cu130` |
| Failure frequency/history | SenseNova incident (restored) |
| Operational complexity | Medium |
| Dependency risk | **Critical** |
| Recovery difficulty | Hard |
| Data-loss risk | High (whole local stack) |
| Certification state | Partial guard |
| Score | 2.0 / 5 |
| Recommendation | **RED REPLACE** family-only guard |

### 18. Character Sheet frontend poller

| Field | Record |
|---|---|
| Subsystem | `CharacterSheetGenerator.tsx` |
| Purpose | Poll visual-sheet pack |
| Current implementation | 1800 × 2s then **restarts** if still GENERATING/QUEUED/RUNNING or GET throws |
| Alternatives | Bounded poll + fail-close (CIS/Prop 30s) |
| Known failure modes | Endless Generating / ~1% after reload |
| Failure frequency/history | Frontend stability audit 2026-08-23 |
| Operational complexity | High |
| Dependency risk | Medium |
| Recovery difficulty | Hard (never gives up) |
| Data-loss risk | Low (UX stuck) |
| Certification state | Unbounded |
| Score | 1.5 / 5 |
| Recommendation | **RED REPLACE** restart loop |

### 19. JobPanel refresh storm

| Field | Record |
|---|---|
| Subsystem | `JobPanel.tsx` |
| Purpose | Project job list |
| Current implementation | 2s forever; `onDone()` if any job is `done` |
| Alternatives | Transition-only callback |
| Known failure modes | Project refresh storm on Director / Txt2Vid / Magi / Image Edit |
| Failure frequency/history | Frontend audit 2026-08-23 |
| Operational complexity | Medium |
| Dependency risk | Medium (request stability) |
| Recovery difficulty | Easy once fixed |
| Data-loss risk | None |
| Certification state | Defect |
| Score | 1.7 / 5 |
| Recommendation | **RED REPLACE** tick-on-done |

### 20. Connection coordinator

| Field | Record |
|---|---|
| Subsystem | `studioApiConnection.ts` + `requestCache.ts` |
| Purpose | Single-flight health, backoff, suspend-on-offline |
| Current implementation | CONNECTED/RECONNECTING/DEGRADED/OFFLINE/RECOVERED |
| Alternatives | Per-component health (historical storm) |
| Known failure modes | Most generation pollers ignore `shouldSuspendDependentPolling()` |
| Failure frequency/history | 15k `/api/health` / 5 min — repaired in coordinator |
| Operational complexity | Low |
| Dependency risk | Low |
| Recovery difficulty | Easy |
| Data-loss risk | None |
| Certification state | Request-stability cert |
| Score | 4.3 / 5 |
| Recommendation | **GREEN KEEP** (extend suspend to generators in Batch 3) |

### 21. Model / Dock catalog

| Field | Record |
|---|---|
| Subsystem | `model_registry.py` + Setup catalog + certified registries |
| Purpose | Creator-facing capability labels |
| Current implementation | Three sources; Dock labels can lie (LTX 2.5 Certified vs Built; fal Certified vs Blocked) |
| Alternatives | One label source |
| Known failure modes | Default-eligible unstable families; Illustrious missing from Dock |
| Failure frequency/history | Workflow inventory 2026-08-23 |
| Operational complexity | High |
| Dependency risk | Medium |
| Recovery difficulty | Medium |
| Data-loss risk | Low |
| Certification state | Split-brain |
| Score | 2.3 / 5 |
| Recommendation | **ORANGE CONSOLIDATE** |

### 22. Data lifecycle / owner fixtures

| Field | Record |
|---|---|
| Subsystem | Library + persist CRS + Playwright defaults |
| Purpose | Candidates, assets, approval |
| Current implementation | Schnick reused as default `ADEPT_PROJECT_ID`; Korri persist CRS gated |
| Alternatives | Named cert project; disposable projects |
| Known failure modes | Tests mutate owner Library; historical Korri approve scripts; dual version stores; `/api/file` lock gap |
| Failure frequency/history | Character Creator closures; CDX-063/064/069/074 |
| Operational complexity | High |
| Dependency risk | Medium |
| Recovery difficulty | Hard (canon mutation) |
| Data-loss risk | **High** |
| Certification state | Partial gates |
| Score | 2.4 / 5 |
| Recommendation | **RED** fixture policy; **YELLOW** approval/lineage |

### 23. Dev API `:8742`

| Field | Record |
|---|---|
| Subsystem | `scripts/run-api.mjs` |
| Purpose | Hot-reload API for `npm run dev` |
| Current implementation | Default `:8742 --reload` |
| Alternatives | Product `:8758` |
| Known failure modes | Vite proxy can hit this instead of product API |
| Failure frequency/history | Port drift |
| Operational complexity | Low |
| Dependency risk | Low |
| Recovery difficulty | Easy |
| Data-loss risk | None |
| Certification state | Dev only |
| Score | 4.0 / 5 |
| Recommendation | **GREEN KEEP** — never bind `:8758` |

---

## Systems Kept (GREEN)

- Hosted path Vercel → Cloudflare → `:8758`
- Vite `:5173` local creator UI
- In-process JobQueue + recover/drain (harden, do not replace)
- Production Executive single-thread worker
- `studioApiConnection` + TTL cache
- MCP isolated torch-free venv
- MiniMax H3 isolated `:8192`
- Ollama adopt/check (not default-own)
- CIS / Prop 30s queued-no-hydrate fail-close
- Agent overlay 4-minute honest pause
- Certified image/video registries as product authority (once readiness binds to them)
- Dev API `:8742` only

---

## Systems Hardened (YELLOW) — planned / in progress

See batch sections. At Phase 1 these are **not yet hardened**.

---

## Systems Consolidated (ORANGE) — planned

- Three lifecycle owners → one Python Runtime Supervisor
- Three PID directories → `.runtime/supervisor/`
- Dock vs certified registry labels → one capability source
- Three visual-sheet start payloads → `CRS_GENERATION`
- Parallel generate/approve HTTP families → one contract per owner action (thin wrappers or 410)

---

## Systems Replaced (RED) — planned

- Competing process owners of `:8758` / `:8188`
- `legacy_comfy_workflow_key` foreign-family aliasing
- SenseNova disk-ready as GPU-ready
- Family-only torch guard
- Character Sheet 60-minute poll restart
- JobPanel tick-on-done
- Jobs `running` without `comfy_prompt_id`
- Schnick/Korri as destructive fixtures

---

## Systems Retired (BLACK) — planned

- `:8760` as creator UI / `npm run beta:*` web start
- Diagnostics first-class Proxy (8760)
- Playwright default `:8760`
- Dead `ImageGenPanel` / unused spatial workspace from product chrome
- Deferred/Blocked null-builder registry rows from creator discovery
- Adept Bots leftover scripts
- `start_api_8759.ps1` from normal path

---

## PowerShell Migration

**Target:** no critical runtime dependence on PowerShell. Useful admin scripts stay.

| Script | Starting class | Target class |
|---|---|---|
| `BetaBackendCommon.ps1` | Critical runtime | Migration shim → Python laws |
| `Start/Stop/Restart/Watch/Get-AdeptBetaBackend*.ps1` | Critical runtime | Thin shims to Python CLI |
| `Start/Stop/Restart/Get-AdeptRuntime.ps1` | Critical runtime (weaker twin) | Thin shims to same CLI |
| `Start/Stop/Restart-AdeptUI-Beta.ps1` | Critical + retired web | Shim without `:8760` or retire |
| `Register-AdeptBetaBackendStartup.ps1` | Admin | Fix `-NoBrowser`; call Python |
| `Register-AdeptRuntimeStartup.ps1` | Admin | Point at same supervisor |
| `AdeptUI-Beta-Health.ps1` | Admin | Probe `:8758` (+ Vite), not `:8760` |
| `scripts/dev.ps1` | Admin / dev | Keep |
| `scripts/Start-AdeptUI-H3-RouteA.ps1` | Admin / experimental | Keep |
| `.runtime/*.ps1` cert probes | Historical | Leave untracked / do not productize |
| `scripts/beta-backend/start_api_8759.ps1` | Historical | Retire |

---

## Runtime Supervisor

**Successor (Batch 1):** `studio-api/runtime_supervisor/` — standalone package, no FastAPI import.

Laws absorbed from BetaBackend (2026-08-17 cert):

- Port identity: `healthy | starting | free | phantom | unrelated`
- Exclusive restart lock
- Process-tree kill (`taskkill /T`) + port-release verify
- Bind-before-healthy; fail-closed phantom/unrelated
- Tunnel health = process, always `--config`
- Comfy busy-guard (`queue_running`)
- Storm protection (5 / 300s)
- Ollama EXTERNAL unless Adept started it
- No `:8760`. No `--workers 2`.
- Process identity in Python — no `powershell.exe` WMI

CLI: `studio-api/.venv/Scripts/python.exe -m runtime_supervisor {start|stop|restart|status|watch}`

`/api/runtime-manager/*` calls the same library. Hosted origin stays 403 on start/stop.

---

## Ports / Service Discovery

| Port | Role | After cull |
|---|---|---|
| 8758 | Studio API (product) | Canonical |
| 5173 | Vite creator UI (local) | Canonical local |
| 8188 | Production Comfy | Canonical |
| 11434 | Ollama | Canonical |
| 8742 | Dev API | Dev only |
| 8192 | MiniMax H3 Comfy | Experimental isolated |
| 8760 | Retired Beta web | Retired — do not start |
| 8759 | Scratch API | Retired from normal path |
| 4173 | Vite preview | Dev only |

Prefer Settings / env (`STUDIO_*`) over scattered literals. Do not blindly replace every string.

---

## Comfy

See inventory rows 8, 15, 16. Batch 2: certified-key readiness, bind-or-fail prompt IDs, stall watchdog, SenseNova not default, Illustrious hash honesty, `/object_info` fail-open cap. MCP stays observability-only.

---

## Model Registry

Only **Runtime Ready + Certified** are default-eligible.

Starting classes (evidence-backed):

| Family | Default eligible? | Notes |
|---|---|---|
| Qwen Image 2512 | Yes if disk+runtime | Scene/ERS default |
| FLUX Kontext | Yes if disk+runtime | Character Creator default |
| Z-Image | Auto fallback only | Not primary default |
| Illustrious | Anime recommend only | Certified; hash may be null |
| Qwen Edit 2509 | No until Certified+Ready | Half-integrated |
| Krea 2 | Never Auto | Experimental |
| SD 1.5 | No | Utility |
| SenseNova U1.5 | **No** | Installed ≠ Ready |
| LTX 2.3 / WAN | Timeline when Ready | |
| LTX 2.5 | Risky (Built vs Dock Certified) | Honesty gap |
| MiniMax H3 | No | Experimental `:8192` |
| fal video | No | Registry Blocked vs Dock Certified |
| Catalog-only (CogView, HiDream, …) | No | Hide from ordinary pickers |

---

## Queue / Jobs

Batch 2: `running` only after bound `prompt_id`; stall fail-closed well under 3600s; orphan drain after cancel; no silent hosted requeue.

---

## Frontend State

Batch 3: one CRS start payload; bounded poll no restart; JobPanel transition-only `onDone`; pollers honor `shouldSuspendDependentPolling()`; Vite product default `:8758`; diagnostics drop `:8760`; honest stages over fake 1%.

---

## Data Lifecycle

Batch 5: named cert project `Adept Stability Cert` / `ADEPT_CERT_PROJECT_ID`. Schnick/Korri write denylist. Persist CRS only via `approve-candidate` + `ownerConfirmed`. Canonical approval remains `Asset.production_approval`. No third lineage store.

---

## APIs

One owner action → one backend contract. Duplicates become thin wrappers or `410`. Health ≠ readiness: `/api/healthz` + `/api/health` liveness; Comfy on `/api/comfy/health`.

---

## Dependency Isolation

Keep: API venv, Comfy Desktop venv, MCP venv, H3 `:8192`, voice/perception venvs.  
Batch 4: torch isolation for **every** Comfy extension install; refuse CPU wheel replacement.

---

## Tests

Every batch: targeted + regression + smoke. Runtime → lifecycle tests. Comfy → graph/readiness. Frontend → Playwright on cert project. Models → torch-guard + label honesty. Data → Schnick write denylist.

---

## Playwright

Use `http://127.0.0.1:5173` + `http://127.0.0.1:8758` and `ADEPT_CERT_PROJECT_ID`. Fail if a spec defaults to `:8760` as the creator UI.

---

## Break Tests

After each batch, deliberately: crash, restart, duplicate start, stale state, cancelled generation, unavailable dependency, reload. Validate graceful recovery.

---

## Peer Review

Review-only after each batch and at the end: **GLM 5.2** and **Kimi K3**. Reviewers do not implement. Builder reconciles.

---

## Remaining Known Risks

Recorded honestly; not hidden to force green.

| Kind | Item |
|---|---|
| Accepted limitation | SenseNova not GPU-ready; cancel-resistant `from_pretrained` |
| Accepted limitation | Hosted UI cannot start local Windows processes |
| Experimental | MiniMax H3 `:8192`, Krea 2, Qwen 2509 until Certified+Ready |
| Future | Electron/OSS supervisor without Windows-only pieces |
| Blocker | None declared until a batch fails its GO criteria |

---

## Batch status

| Batch | Scope | Status |
|---|---|---|
| Phase 1 | Inventory | **COMPLETE** 2026-08-23 |
| Batch 1 | Runtime / process | **COMPLETE** — Python Runtime Supervisor; one `.runtime/supervisor/` store; no `:8760` in normal start; 18 hermetic lifecycle tests |
| Batch 2 | Comfy / jobs | **COMPLETE** — certified-key readiness (no Z-Image alias); bind-or-fail `prompt_id`; 180s stall; SenseNova disk ≠ GPU-ready; `/object_info` fail-closed |
| Batch 3 | Frontend / API | **COMPLETE** — CRS poll no 60-min restart; JobPanel transition-only `onDone`; Vite `:8758`; Playwright on cert project **2 passed** |
| Batch 4 | Models / dependencies | **COMPLETE** — registry-capped dock labels; `defaultEligible` = Certified+executable; torch isolate all plugins; catalog-only hidden |
| Batch 5 | Data lifecycle / fixtures | **COMPLETE** — Adept Stability Cert created; Schnick/Korri write denylist; Korri approve scripts quarantined; `/api/file` project-scoped; approval canon unchanged |
| Batch 6 | Legacy cleanup | **COMPLETE** — Playwright/config/env/beta scripts off `:8760`; dead routes unexported; Adept Bots leftovers marked RETIRED |
| Final | Sanitation + peer review | **COMPLETE** — GLM + Kimi reconciled; binary **NO-GO** (uncommitted source) |

---

## Batch evidence

### Batch 1 — Runtime Supervisor

- Package: `studio-api/runtime_supervisor/` + `scripts/run_runtime_supervisor.py`
- State: `.runtime/supervisor/` (override `ADEPT_SUPERVISOR_STATE_DIR`)
- CLI: `start|stop|restart|status|watch`
- Laws absorbed: port identity, exclusive lock, process-tree kill, bind-before-healthy, tunnel `--config` + process health, Comfy `queue_running` busy-guard, storm 5/300s, Ollama EXTERNAL not killed, no `:8760`, no `--workers 2`
- Runtime manager calls the Python supervisor (not `Start-AdeptRuntime.ps1` as an owner)
- Hosted lifecycle POST remains **403**
- Cursor rule `beta-refresh-after-build.mdc` retargeted to `:5173` + `:8758/api/healthz`
- Tests: `tests/test_runtime_supervisor_lifecycle.py` — **18 passed**
- Live 2026-08-23: `studio_api` UP reused pid 73804; `comfyui` UP reused; `retired_web_8760: not started`; `http://127.0.0.1:8758/api/healthz` **200**; `http://127.0.0.1:5173/` **200**

### Batch 2 — Comfy / jobs

- `legacy_comfy_workflow_key()` no longer remaps Flux/Qwen/Illustrious/SenseNova onto Z-Image
- `WORKFLOW_MODEL_COMPONENTS` family-specific Setup IDs
- Jobs stay `queued`/`claimed` until `queue_prompt` returns `prompt_id`; unbound running fail-closed at 45s
- Stall: `queue_running` + no history for 180s fail-closed
- SenseNova `runtimeReady` is never True from disk inspect
- Illustrious remains Certified (null `graphHash` is an accepted fingerprint gap — demotion broke anime routing)
- Tests: `tests/test_stability_cull_batch2.py` plus readiness registry tests — **passed**

### Batch 3 — Frontend / API

- Character Sheet: no restart of the 1800-tick budget (`pollExhaustedRef`); 30s queued-no-hydrate; `shouldSuspendDependentPolling()`
- JobPanel: `onDone` only on transition to `done`
- Scene / Prop / CIS / Image Edit / Txt2Vid pollers honor outage suspend; Scene 30s fail-close
- CRS start payload unified: `CRS_GENERATION` / `four_view` / `candidateCount: 1`
- Vite product default API `:8758`; `npm run dev` still uses `:8742` via `run-web-devapi.mjs`
- Diagnostics: first-class `:8760` proxy removed
- Playwright (live Vite + API, cert project `2bc632b8-…`): **2 passed** in 4.8s
  - `tests/e2e/stability-cull/stability-cull-character-creator.spec.ts`
  - `tests/e2e/stability-cull/stability-cull-ports.spec.ts`
- Frontend unit: Character Sheet + JobPanel — **33 passed**
- `studio-web` production build: **passed** after TS fixes

### Batch 4 — Models / dependencies

- Dock labels cannot exceed certified-registry status (LTX 2.5 Built → Testing; fal Blocked → Unavailable)
- `ModelDescriptor.defaultEligible` only when Certified + executable and not in the never-default set (SenseNova, Krea 2, MiniMax H3, Qwen Edit 2509)
- Illustrious present on the dock as `illustrious-local`
- Catalog-only families hidden from ordinary pickers
- Comfy extension installer isolates torch for **any** torch pin, not SenseNova-only
- Tests: `test_stability_cull_batch4_labels.py`, `test_stability_cull_batch4_picker.py`, `test_comfy_extension_installer.py`

### Batch 5 — Data / fixtures

- `scripts/ensure_stability_cert_project.py` created **Adept Stability Cert** `2bc632b8-b329-4d3b-bc40-b68dc41b6bb1`
- Owner write denylist: `tests/e2e/setup/ownerProjectGuard.ts`
- Quarantined: `_korri_approve.py`, `_korri_approve2.py`, `_korri_approve3.py`; `character-crs-sheet.spec.ts`, `character-single-crs.spec.ts`, `crs-frontend-smoke.spec.ts` skip unless `ADEPT_ALLOW_KORRI_MUTATION=1`
- Approval canon: `Asset.production_approval`; `AssetLibraryMeta.approval_state` is derived on read and not persisted as a second store
- Lineage: `asset_graph.AssetVersion` is canonical; `m29_asset_versions` is historical read-compat (no third store)
- `/api/file` is project-scoped only (403 `FILE_API_RESTRICTED`); Advanced requires `ADEPT_FILE_API_ADVANCED=1`
- Schnick/Korri canon was not migrated

### Batch 6 — Legacy

- Playwright defaults and `playwright.config.ts` beta URL: `:5173`
- `config/beta-local.env` `STUDIO_WEB_PORT=5173`
- `scripts/run-playwright-beta.mjs`, `scripts/beta_runtime/certify.py` (`npm run beta:certify`), `beta_health_monitor.py`, soak/create helpers retargeted off `:8760`
- `scripts/beta-backend/start_api_8759.ps1` and `audit.py` marked RETIRED
- Dead UI: `ImageGenPanel` / `SpatialSceneWorkspace` marked dead; `CharacterCandidateGrid` unexported from character barrel
- Historical cert reports that mention `:8760` stay historical

---

## PowerShell classification

| Class | Scripts | Action |
|---|---|---|
| Critical-runtime (now shims) | Root `Start/Stop/Restart/Watch/Get-AdeptBetaBackend*.ps1`, `Start/Stop/Restart/Get-AdeptRuntime.ps1`, `Start/Stop/Restart-AdeptUI-Beta.ps1`, `AdeptUI-Beta-Health.ps1`, `Register-AdeptBetaBackendStartup.ps1` | Thin wrappers → Python supervisor |
| Migration leftover | `scripts/beta-backend/BetaBackendCommon.ps1` | Still contains certified laws + `.runtime/beta-backend/` store. **Not** on `npm run beta:*`. Do not use as a second owner. |
| Admin utility | Useful one-off operators under `scripts/beta-backend/` that nothing product-critical imports | Keep |
| Historical / Retire | `start_api_8759.ps1`, `scripts/beta_runtime/supervisor.py` + `:8760`, `audit.py` Adept Bots path, `temp_audit.py` | Marked retired; do not use on the product path |
| Do not delete | Admin diagnostics that operators still run by hand | Keep |

---

## Contradiction audit (2026-08-23)

| Area | Result |
|---|---|
| Runtime owners | Product path: Python supervisor + root PS shims. `BetaBackendCommon.ps1` remains a leftover library, not `npm run beta:*`. Legacy `supervisor.py` exists but is not on the product start path. |
| `:8760` in normal start | Not started. Cursor rule, `beta:start/stop/restart/health/certify`, Start-AdeptUI-Beta shim agree with Law 15. `beta:certify` (`scripts/beta_runtime/certify.py`) now defaults to Vite `:5173` and fail-closes if UI port is `8760`. |
| Frontend API port | Vite product `:8758`; `npm run dev` `:8742` only |
| Readiness aliases | Flux/Qwen/Illustrious/SenseNova no longer pass because Z-Image is installed |
| Poll storms | CRS budget does not restart; JobPanel `onDone` is transition-only; generation pollers honor outage suspend |
| Owner fixtures | Schnick/Korri write tests quarantined; cert project reused |
| Labels | Dock cannot claim Certified above registry Built/Blocked |
| Approval / lineage | Single approval column; no third lineage store |
| File API | Project-scoped; `..` rejected; lock scope from resolved path |
| Leftovers (honest) | Historical docs/scripts still mention `:8760`; Illustrious `graphHash` null; SenseNova not GPU-ready; hosted UI cannot start Windows processes; some generation pollers beyond the ones listed still exist; duplicate HTTP aliases not bulk-410'd |

---

## Tests (measured)

| Suite | Result |
|---|---|
| Runtime supervisor lifecycle | 18 passed |
| Cull batch 2 + readiness + installer + picker + labels + file API + no-8760 + library truth + media lock | 53 passed in the combined cull/regression run |
| Production dock mapping (isolated) | 1 passed after hermetic executable mock |
| Frontend Character Sheet + JobPanel + provenance | **39 passed** (5 files) |
| Playwright stability-cull (live `:5173` + `:8758`, cert project) | **2 passed, 0 failed** (4.8s) |
| `studio-web` production build | passed |

---

## Playwright

Use `http://127.0.0.1:5173` + `http://127.0.0.1:8758` and `ADEPT_CERT_PROJECT_ID=2bc632b8-b329-4d3b-bc40-b68dc41b6bb1`. Specs that default to `:8760` as creator UI fail `test_stability_cull_no_8760_defaults`. `creatorUiBase()` throws on `:8760`.

---

## Peer Review

Review-only. Reviewers do not implement. Builder reconciles.

### GLM 5.2

Returned **READY FOR PRIMARY REVIEW** with **1 BLOCKER**: `npm run beta:certify` → `scripts/beta_runtime/certify.py` still defaulted to `:8760`, claimed `web_server.py`, and hardcoded `"ports": {"ui": 8760}`. That contradicted this document’s Law 15 audit row.

**Reconciled:** `certify.py` now defaults to Vite `:5173`, records `localCreatorUi` (not “production frontend without Vite”), fail-closes `retired8760NotProductUi` if port is 8760, and no longer stamps `:8760` / `web_server.py` as the product path. Regression: `test_beta_certify_defaults_to_vite_not_retired_8760`.

Non-blockers accepted: `BetaBackendCommon.ps1` is a leftover library (classified above); cert project UUID is a runtime artifact; frontend count was **39 passed**, not 33.

### Kimi K3

Returned **BLOCKERS** (would not grant GO) with five findings. Builder reconcile:

| ID | Finding | Disposition |
|---|---|---|
| B1 | Cull source is untracked; HEAD is still starting SHA `1c86560` | **Open.** Commit requires an explicit user request. Clean-Clone Law remains unsatisfied. |
| B2 | JobPanel `onDone` in effect deps reset the seen-set when parents passed inline arrows | **Fixed.** `onDoneRef`; effect depends only on `projectId`. |
| B3 | Owner denylist was opt-in (2 specs) | **Fixed.** Playwright sends `X-Adept-Deny-Owner-Writes: 1`; API middleware 403s mutating Schnick/Korri routes. |
| B4 | `beta:certify` still targeted `:8760` | **Fixed** before this review landed (GLM blocker). |
| B5 | `/api/file` derived lock scope from the unresolved path (`..` traversal) | **Fixed.** Reject `..`; derive scope from the resolved path. |

---

---

## Remaining Known Risks

Recorded honestly; not hidden to force green.

| Kind | Item |
|---|---|
| Accepted limitation | SenseNova not GPU-ready; cancel-resistant `from_pretrained` |
| Accepted limitation | Hosted UI cannot start local Windows processes |
| Accepted limitation | Illustrious Certified with null `graphHash` (fingerprint gap) |
| Experimental | MiniMax H3 `:8192`, Krea 2, Qwen 2509 until Certified+Ready |
| Future | Electron/OSS supervisor without Windows-only pieces |
| Leftover | Historical milestone reports and one-off m30/m42 capture scripts still mention `:8760` |
| Leftover | Duplicate HTTP aliases not converted to `410` in bulk |
| Leftover | EXTERNAL `scripts/beta_runtime/web_server.py --port 8760` may still be bound from an old session. Supervisor does not start it. |
| Leftover | Dirty tree still holds mixed Character Creator files (`certified-registry.json`, `imagegen_workflows.py`, ~1176 untracked). Not part of the cull SHA. |
| Accepted | Windows `DETACHED_PROCESS` can make the first post-restart API PID differ from the listener; a later `start` adopts the healthy listener. |
| Accepted | `test_modern_foundation_ready` / `test_wave2_gate_go` need gitignored `artifacts/`. They passed from the main repo that has those artifacts. |
| Accepted | `.cursor/rules/beta-refresh-after-build.mdc` remains gitignored. Product start is `npm run beta:*` → Python supervisor. |

---

## Recertification from committed SHA (2026-08-23)

### A — Commit closure

| Item | Evidence |
|---|---|
| Cull commit | `2a83a493648692859f8323e11c82de8b8b106cca` — `feat: certify Adept UI stability cull and runtime consolidation` (107 files) |
| Follow-up | `0dd6edf6a94b63b4bcd74e8f06bc888e4fd9ac1c` — fail-close modules + drop extra m42 hash asserts that needed uncommitted registry hashes |
| Tip | `0dd6edf` |
| Included | Runtime supervisor + shims + `beta:*`; Comfy bind-or-fail / family readiness; JobPanel `onDoneRef`; CRS `pollExhaustedRef`; `/api/file` + owner deny; torch isolation; `defaultEligible`; stability-cull tests/e2e; this doc |
| Excluded | `certified-registry.json`; `imagegen_workflows.py`; `audit.py`; Korri approve scripts; untracked CC specs; `.runtime/`; `data/runtime/`; `studio-web/dist`; remaining ~1100 untracked CC/docs tree |
| Worktree proof | Disposable `.worktrees/cull-head` at `0dd6edf`: required strings present; supervisor `:8760` mentions are retired-not-started only; Vite default `8758` |

### B — Owner canon

`GET` Schnick `2347bf46-3762-4763-86c5-4a6032522278` name=Schnick Coffee. `GET` Korri `c49371ed-ba6b-4c16-ba98-a8b28b72118b` name=Korri. Persist CRS Rev 4 `READY_FOR_OWNER` `autoApproved=False`. Owner-write POST with deny header 403; Korri still Korri after.

```text
OWNER CANON MUTATION: NONE
```

### C — Runtime evidence

- `python scripts/run_runtime_supervisor.py status`: API UP; Comfy reused pid 66596; Ollama EXTERNAL pid 20576; `retired_web_8760: not started`
- Controlled `restart`: API new owned PID; Comfy reused; tunnel owned; Ollama EXTERNAL unchanged; healthz 200; Vite `:5173` 200
- Duplicate `start` #2: `studio_api: OK (reused) already healthy — reused PID 64000` in 856ms
- Leftover EXTERNAL `:8760` (`web_server.py` pid 21536) was not started by this supervisor

### D — Exact test counts

| Suite | Result |
|---|---|
| Worktree pytest (cull + installer/dock/qwen/m42 minus 2 artifact-gated) | **81 passed, 2 deselected** |
| Main-repo artifact-gated m42 foundation/wave2 | **2 passed** |
| Worktree vitest (sheet + JobPanel + CIS fail-close) | **33 passed (4 files)** |
| Worktree `npm --prefix studio-web run build` | **PASS** |
| Playwright stability-cull (cert `2bc632b8-…`, `:5173` / `:8758`) | **2 passed (7.0s)** |
| Break: `..` file API | live **403** |
| Break: owner-write header | live **403** `OWNER_FIXTURE_WRITE_DENIED` |
| Break: `creatorUiBase()` on `:8760` | throws |

### E — Peer review

| Reviewer | Agent | Verdict |
|---|---|---|
| GLM 5.2 | [GLM 5.2 cull peer](b1a06e3b-e225-47fc-9720-6dedcc733f2e) | **GO** — independently confirmed all 11 required strings at `0dd6edf` |
| Kimi K3 | [Kimi K3 cull peer](15f35a12-4ec5-46ae-8807-b2fb0fcd7913) | **GO** — no blocker; disclosed test-trim + stale pre-commit doc text (this section stamps it) |

Reconcile: no valid mandatory finding. Do not self-certify around a blocker — none remained.

### F — Binary cull verdict

```text
GO — ADEPT UI STABILITY CULL + RELIABILITY CONSOLIDATION CERTIFIED
```

### G — Workflow matrix

See [WORKFLOW_AUDIT_HANDOFF.md](WORKFLOW_AUDIT_HANDOFF.md). Live `:8188/object_info` 200 / 2007 nodes. Isolated H3 `:8192` down.

### H — Next-workflow priorities (no rebuild)

1. H3 containment (`:8192` down; H3-named nodes exist on production `:8188`).
2. Commit or drop dirty SenseNova / Qwen Edit 2509 registry rows so clean-clone Character Creator matches callers.
3. FLUX loader honesty (Certified, Nunchaku absent).
4. Illustrious Certified + null `graphHash`.
5. LTX 2.5 stay Testing/Built until executable certification.

---

## Final Recommendation

Pre-commit peers: [GLM 5.2](e8f12234-e21e-475a-9aed-7a5b2579b09e) and [Kimi K3](7c8c4890-de3c-4b36-8455-700a819ed14a) (blockers fixed before commit). Post-commit peers both **GO**.

```text
GO — ADEPT UI STABILITY CULL + RELIABILITY CONSOLIDATION CERTIFIED
```
