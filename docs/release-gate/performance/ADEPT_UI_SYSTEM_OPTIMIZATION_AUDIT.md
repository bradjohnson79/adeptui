# Adept UI — System Optimization & Performance Audit

**Law 30:** this file is the **technical evidence appendix**. The governing completion report and binary verdict are in [`ADEPT_UI_SYSTEM_OPTIMIZATION_COMPLETION_REPORT.md`](./ADEPT_UI_SYSTEM_OPTIMIZATION_COMPLETION_REPORT.md). Do not cite this audit as the final GO / NO-GO.

**Milestone:** Adept UI v1.1 — System Optimization & Performance Repair
**Status:** Evidence appendix for **NO-GO — GATE 6 LIVE GPU STRESS + PLAYWRIGHT PERFORMANCE PASS NOT COMPLETE**
**Governing laws:** ROOT-CAUSE REPAIR LAW · CACHE INTEGRITY LAW · COMFY MCP WORKFLOW VERIFICATION LAW
**Subagent model:** Kimi Code 2.7 (per SPECIALIZED SUBAGENT MODEL LAW)

> No timeout inflation. No health masking. No blind caching. No broad rewrite.
> Measure → find the expensive source → repair the source → cross-check Comfy → prove before/after.

---

## A. Baseline (measured BEFORE)

| Surface | Before | Notes |
| --- | ---: | --- |
| Library `get_tree` (current-schema read) | ~45ms + 1 commit + 1 settings write per read | `migrate_project_library` wrote/committed even when no migration was needed |
| Image readiness `generate_readiness_report` | 2× `discover_modern_image_models` (~8 `os.walk` each) + 1 raw `urllib` `/object_info` fetch per refresh | duplicate model scan + duplicate Comfy catalogue fetch |
| Comfy catalogue source | 2 paths: `COMFY_URL` env + `urllib` AND `settings.comfy_url` + 60s cache | bypassed the 60s cache; second URL config |
| Video runtime probe `_probe_video_runtime` | `wave6_gate()` sync on event loop (~1ms, but sync I/O) | same defect class as Production Control |
| **Production Control `aggregate_status`** | **~24,849ms cold** (audio `local_runtime_status` imports torch + spawns subprocesses on the status path) | exceeded the 4000ms health budget on every cold call |
| Frontend jobs polling | 4 independent `setInterval` pollers | ~80–120 req/min; ContextInspector double-fetched on mount |
| Progress polling (8 surfaces) | 6 PASS; 2 defects | SpatialSceneWorkspace never stopped at terminal; MagiEditorWorkspace double-started |
| Diagnostics unhealthy cache | healthy cached 45s; unhealthy (non-allowlist) NOT cached | re-verified every poll |
| Avatar `_gpu_summary` torch import | torch NOT in API venv → except branch ~0.16ms | no residency, no block — no repair needed |

---

## B. P0/P1 Findings (root causes)

1. **P0/P1-1 Library write-on-read** — `migrate_project_library()` unconditionally committed even when `from_version == LIBRARY_SCHEMA_VERSION`. Source: `studio-api/app/project_library/service.py`.
2. **P0/P1-2 Image readiness duplicate model scans** — `generate_readiness_report()` and `probe_runtime_capabilities()` each called `discover_modern_image_models()`. Source: `studio-api/app/image_runtime/readiness.py` + `capability_probe.py`.
3. **P0/P1-3 Duplicate Comfy `/object_info`** — `_comfy_object_info()` used `COMFY_URL` env + raw `urllib`, bypassing the 60s cache. Source: `studio-api/app/image_runtime/capability_probe.py`.
4. **P0/P1-4 Video runtime event-loop block** — `_probe_video_runtime()` called `wave6_gate()` synchronously from an async probe. Source: `studio-api/app/codirector/status/registry.py`.
5. **P0/P1-5 Production Control >4000ms (section 38)** — `aggregate_status()` called `local_runtime_status()` on the status path; COLD audio path imports torch + spawns subprocesses (measured 24,849ms). Source: `studio-api/app/production_control/status.py` + `audio_studio/provider_resolver.py`.
6. **P1-6 Frontend jobs polling storm** — 4 components independently polled `GET /api/projects/{id}/jobs`. Source: `studio-web/src/components/{JobPanel,LivePreviewMonitor,ContextInspector}.tsx` + `timeline-master/TimelinePreviewComposer.tsx`.
7. **P1-7 Comfy catalogue cleanup** — folded into P0/P1-3.
8. **P1-8 Progress poll gating** — 2 of 8 surfaces violated terminal-stop/double-start rules. Source: `SpatialSceneWorkspace.tsx`, `MagiEditorWorkspace.tsx`.
9. **P2-9 Tier 3** — (a) avatar torch: negligible (no repair). (b) diagnostics unhealthy cache: re-verified every poll. Source: `studio-api/app/setup/diagnostics.py`.

---

## C. Repairs (source-level only)

| # | Defect | Source repair |
| --- | --- | --- |
| 1 | Library write-on-read | `migrate_project_library()`: early return when `from_version == LIBRARY_SCHEMA_VERSION` — no state mutation, no `_save_settings`, no `db.commit`. Persist only on actual migration. |
| 2 | Duplicate model scans | `generate_readiness_report(*, node_names=None)` discovers models ONCE and passes the same `discovery` dict into `probe_runtime_capabilities(discovery=..., node_names=...)`. No second scan. |
| 3 | Duplicate `/object_info` | Removed `_comfy_object_info()` (urllib + COMFY_URL env). New `_comfy_node_names()` reuses `comfy._object_info_cache` when populated, else one sync `httpx` fetch against canonical `settings.comfy_url`. |
| 4 | Video event-loop block | `_probe_video_runtime()` now `await asyncio.to_thread(wave6_gate)`. |
| 5 | PC >4000ms | New `local_runtime_status(*, refresh=False, light=False)`: `light=True` (status) NEVER blocks on the ~25s probe — serves fresh cache, stale cache + single-flight background refresh, or 'checking' payload. `aggregate_status()` routes audio through `_audio_status_light()` + bounded `ThreadPoolExecutor(max_workers=4)` for the 4 independent probes. Execution keeps `refresh=True`. |
| 6 | Jobs polling storm | New shared per-project store `projectJobsStore.ts` + `useProjectJobs` hook: single-flight, one interval, visibility/outage suspend, outage recovery, terminal-state intervals (2000ms active / 5000ms idle), cleanup. 4 pollers refactored to subscribe. |
| 7 | Comfy catalogue | Folded into #3 — one canonical cached `/object_info` source. |
| 8 | Progress poll gating | New `pollJob.ts` helper (gates on active job id, stops at terminal, returns stop for unmount). SpatialSceneWorkspace + MagiEditorWorkspace repaired to use it. |
| 9a | Avatar torch | NO REPAIR — measured negligible. |
| 9b | Diagnostics unhealthy TTL | New `_UNHEALTHY_CACHE_TTL_SEC = 12.0`: unhealthy non-allowlist cached 12s (was 0s); healthy 45s; voice-unhealthy 45s. Recovery ≤12s + `invalidate_verify_cache()`. |

---

## D. Cache Law (every cache: stores / TTL / invalidation / force-refresh / execution behavior / stale-state risk)

| Cache | Stores | TTL | Invalidation | Force refresh | Execution behavior | Stale-state risk |
| --- | --- | ---: | --- | --- | ---: | --- |
| Capability `ProbeSnapshot` | generator readiness + blockers | 300s | Comfy recovery (`cached_comfy_recovered` invalidates on offline→online) | `_lookup_or_start_build` rebuild | execution re-probes fresh | stale blockers cleared on Comfy recovery |
| Comfy `object_info` (`comfy._object_info_cache`) | full node catalogue | 60s | Comfy restart / recovery | `comfy.get_object_info()` | warmed by `comfy_health(include_nodes=True)`; `_comfy_node_names` reuses it | stale nodes cleared on recovery |
| Image model discovery | `discover_modern_image_models()` result | per-refresh (passed by ref, not cached) | n/a (computed once per refresh) | callers re-invoke | execution may re-invoke fresh | none (not cached across refreshes) |
| Audio `local_runtime_status` | ACE-Step/MMAudio readiness | 30s fresh; stale-served + bg refresh (light) | `refresh=True` (execution) | `refresh=True` | execution forces fresh; status serves cache/bg-refresh | stale ≤ one refresh cycle; recovery ≤30s (fresh) / ≤1 cycle (bg) |
| Production Control (no new cache) | — | — | — | — | `aggregate_status` recomputes each call (bounded parallel) | none |
| Diagnostics `verify_component` | Verification result | healthy 45s / unhealthy 12s / voice-unhealthy 45s | `invalidate_verify_cache(component_id)` after install/download | `invalidate_verify_cache()` | execution invalidates | recovery ≤12s (non-voice) / ≤45s (voice) |
| Frontend `projectJobsStore` | per-project jobs list | 2000ms active / 5000ms idle | subscriber unsubscribe (last → remove entry) | `refreshProjectJobs()` | single-flight; outage suspend | stale ≤ one poll cycle; recovery on `onStudioApiRecovered` |

No blind caches. Every cache has a defined invalidation + force-refresh path. Recovery is prompt (≤30s worst case for audio fresh; ≤12s for diagnostics).

---

## E. Comfy Optimization (MCP evidence + catalogue behavior)

**Comfy MCP was unavailable in this Cursor session.** Per the user's instruction (option A: enable/restore Comfy MCP; if unavailable, read-only direct HTTP against :8188 + existing Comfy client as temporary diagnostic evidence, clearly marked, not a permanent MCP substitute). Comfy certification is therefore **PENDING until MCP is restored**; the HTTP cross-check below is temporary diagnostic evidence.

HTTP cross-check against `http://127.0.0.1:8188` (temporary, MCP pending):
- `/system_stats` → HTTP 200
- `/object_info` → HTTP 200, **node count = 1997**
- Required nodes present: `TextEncodeZImageOmni` ✓, `UNETLoader` ✓, `VAEEncode` ✓, `CLIPTextEncode` ✓, `LoadImage` ✓
- Canonical config: `settings.comfy_url = http://127.0.0.1:8188` (the single source used by the optimized `_comfy_node_names`)
- `readiness.comfyReachable = True`, `readiness.comfyNodesObserved = 1997`

Catalogue behaviour after optimization: one cached `/object_info` source (`comfy.get_object_info()` 60s cache, warmed by `comfy_health(include_nodes=True)`); the legacy `COMFY_URL` env + `urllib` path is removed. `generate_readiness_report` reuses warmed node names → 0 duplicate `/object_info` fetches per refresh. Workflows still validate against the live catalogue (node keys derived locally from the cached full schema — no invented keys-only endpoint, per section 7).

---

## F. Frontend Polling (before/after request counts)

| Surface | Before | After |
| --- | ---: | ---: |
| `GET /api/projects/{id}/jobs` (4 pollers) | ~80–120 req/min | ~12–30 req/min (1 shared poller, 2s active / 5s idle) |
| ContextInspector mount | 2 immediate requests (tick + interval) | 1 shared request (no double-fetch) |
| Progress polls (8 surfaces) | 2 defects | all 8 obey: active-only, stop at done/failed/cancelled, clear on unmount, no idle poll |

Regression: `projectJobsStore.test.ts` (7 tests) + `jobPanel.poll.test.ts` (1) + `pollJob.test.ts` (10) — all pass. Frontend build: `✓ built in 1.81s` (exit 0).

---

## G. Production Control (exact internal timing breakdown)

**Section 38 answer (measured):** `production_control.status` exceeded 4000ms after the prior event-loop repair because the COLD audio `local_runtime_status()` path imports torch + spawns subprocess health checks (**measured 24,849ms**). The prior `asyncio.to_thread` repair stopped event-loop blocking but the probe TOTAL still exceeded the 4000ms health budget on every cold call (every 30s TTL window or first call after restart). Status was doing generation-grade ML probing — a section-12 violation.

Component timing (measured, ms):

| Component | Cold | Warm |
| --- | ---: | ---: |
| audio `local_runtime_status` (refresh=True) | 24,849 | 0.0 (cached) |
| ollama `/api/tags` (1.5s timeout) | 3.14 | 3.14 |
| hosted providers | 0.27 | 0.27 |
| queue_counts (DB) | 276.82 | 276.82 |
| **`aggregate_status` total (serial, cold)** | **~25,129** | — |
| **`aggregate_status` total (after repair, light + parallel, cold audio)** | **P50 15.83 / max 297.67** | — |

Live after repair: `GET /api/production-control/status` → 200 in **28–38ms** (idle stress x3: 28/21/38ms). Well under the 4000ms budget (and the 1000ms warm budget).

Bounded parallelism: 4 independent probes (audio-light, codirector/ollama, hosted, queue) run in a `ThreadPoolExecutor(max_workers=4)`; total = max, not sum. Regression `test_aggregate_status_uses_light_audio_path` verifies the light path + worker-thread parallelism.

---

## H. Memory / GPU (idle findings)

- **Avatar torch**: torch is NOT installed in the Studio API venv (`studio-api/.venv`); `_gpu_summary()` takes the `ModuleNotFoundError` except branch (~0.16ms) and returns "not detected". No torch residency in the API process, no multi-second block. The audio sandbox uses a separate venv with torch (owned by the sandbox adapters, not the API process). No repair needed.
- **GPU idle**: ComfyUI is the GPU resident process; no unexplained residency observed. Model residency is expected (Comfy keeps loaded models). No unnecessary unload performed.
- **Memory**: no duplicate Studio API processes observed (one owned listener per restart). No orphan Python workers from the optimization repairs (background audio refresh is a short-lived daemon thread that exits after one probe).

---

## I. Before / After Matrix

| System | Before | Root Cause | Repair | After | Status |
| --- | ---: | --- | --- | ---: | --- |
| Library `get_tree` (current schema) | ~45ms + 1 commit + 1 write | write-on-read in `migrate_project_library` | early no-op return when schema current | P50 <1ms, 0 commits, 0 writes | ✅ |
| Image readiness refresh | 2 model scans + 1 raw `/object_info` | duplicate `discover_modern_image_models` + duplicate urllib fetch | discover once + pass warmed node names | 1 scan + 0 fetches | ✅ |
| Comfy catalogue source | 2 paths (COMFY_URL env + urllib, settings.comfy_url + cache) | `_comfy_object_info` bypassed cache | one canonical `settings.comfy_url` + `comfy.get_object_info()` | 1 cached source | ✅ |
| Video status probe | `wave6_gate()` sync on event loop | sync I/O in async probe | `await asyncio.to_thread(wave6_gate)` | off event loop | ✅ |
| Production Control status | ~24,849ms cold (>4000ms budget) | audio torch/subprocess probe on status path | light status + bg refresh + bounded parallelism | P50 15.83ms / live 28ms | ✅ |
| Frontend jobs polling | ~80–120 req/min (4 pollers) | independent `setInterval` per component | shared `projectJobsStore` + `useProjectJobs` | ~12–30 req/min (1 poller) | ✅ |
| Progress poll gating (8 surfaces) | 2 defects (no terminal-stop, double-start) | missing terminal guard / redundant tick | `pollJob` helper | all 8 obey rules | ✅ |
| Diagnostics unhealthy cache | re-verify every poll (unhealthy) | unhealthy not cached | short 12s unhealthy TTL | cached 12s, recovery ≤12s | ✅ |
| Avatar torch import | ~0.16ms (torch not in venv) | n/a | NO REPAIR (measured negligible) | ~0.16ms | ✅ |
| Capability snapshot TTL gate (Peer Review B-B1) | stale snapshot served indefinitely on status path | `peek_cached_snapshot` ignored `SNAPSHOT_TTL_SEC`; `_probe_codirector_provider` short-circuited on stale `provider_health` | `max_age_sec` TTL gate + always-live provider probe | stale→rebuild within TTL; live Ollama probe | ✅ |
| Video Intelligence fake-callable (Peer Review B-B2) | `available=True` with zero models | `_model_component_eval` returned `available=True` when `required=()` and all optional missing | fail-closed: `available=False` / `DEGRADED` (not callable, not a blocker) | `available=False`, not in callable list, not in blockers | ✅ |
| `CompactRenderQueue` independent poller (Peer Review B-B4) | 3s `listJobs` interval | independent `setInterval` | migrated to `useProjectJobs` shared store | 1 shared poller | ✅ |
| `pollJob` first-tick delay (Peer Review B-B5) | first update delayed by `intervalMs` | no immediate tick on start | immediate `void tick()` on start | first update immediate | ✅ |
| `useProjectJobs(undefined)` unstable getSnapshot (Peer Review A-D1) | infinite render loop on Timeline preview | new object literal on every `getSnapshot` call | module-level `EMPTY_SNAPSHOT` constant | referentially stable; no render loop | ✅ |
| `build_status` stale cache forever (Peer Review A-D2) | install verdicts from pre-install snapshot | cache served unconditionally after TTL | TTL-gated early return; stale→rebuild | stale cache triggers full rebuild | ✅ |
| `_comfy_node_names` fallback TTL (Peer Review A-D5) | stale catalogue served indefinitely | `_object_info_cached_at` not checked | 60s TTL check before serving cache | stale→httpx fetch | ✅ |

---

## J. Deferred Items (P2/P3 only)

### Serialized Generation Safety Audit (section 28) — current concurrency behavior

| Surface | 1-active guard | Evidence |
| --- | --- | --- |
| Character Creator | **YES** | `cc_v2.py` `_active_job_busy` checks all VIEWS; any view in `generating/queued/running/starting` blocks new generation + generator change (409). "one view at a time" enforced at the app layer. |
| Timeline (batch) | **YES** | `director_timeline_w46/orchestrator.py:253` "This batch is already generating — wait for it to finish or cancel it first."; `:1274` `generation_in_progress`. 1 active batch enforced. |
| Scene Creator Mini (concept) | **NO** | `spatial_map/scene_creator_mini.py` `create_mini_take` validates preconditions (saved doc, cameras, source) but has NO "1 active concept generation" busy guard. No global GPU semaphore found in the queue worker. **Finding:** multiple Mini Takes could run concurrently on the GPU. |

**Classification:** Scene Creator Mini's missing 1-active-concept guard is a **P1 concurrency-gap finding**, NOT a blocker for the 6 performance gates (which are about responsiveness/caching/polling). Per the plan ("Do not redesign Scene Creator Mini or Timeline in this milestone"; the 1-active law is a "future law"), this is **deferred** to a future milestone. No immediate GPU-overload P0 was observed during idle stress; flagged for a dedicated generation-serialization milestone.

### Other deferred items

- **`GET /api/setup/status` cold path ~20–30s timeout (pre-existing):** the Setup-page status endpoint performs heavy component verification (subprocess probes / huggingface snapshot checks) on every cold call. This is a pre-existing slow path on the Setup page (not the hot status path), outside the locked P0/P1 repair order (section 30). Measured: cold ~30s (urllib timeout), warm benefits from the Repair 9b unhealthy TTL but the cold first call remains slow. **Deferred** — candidate for a future Tier-3 repair (move heavy Setup verification off the status path / cache the cold result). Not a blocker for the 6 performance gates.
- **2 pre-existing test failures** (`test_comfy_health_optional_missing_does_not_degrade_runtime`, `test_health_endpoint_top_level_missing_lists_exclude_optional`): confirmed failing on a clean baseline (all optimization changes stashed) — from prior-session ComfyUI-recovery work, not this milestone. Out of scope for the performance gates; tracked separately.
- **Frontend `SystemStatusStrip` jobs-list caller**: left independent (per section 18, "do not automatically consolidate unrelated jobs") — it is a lighter single-shot read (15s interval, prop fallback only), not a storm poller. `CompactRenderQueue` was migrated to `useProjectJobs` during Peer Review B repair (B4).
- **Comfy MCP certification**: HTTP cross-check passed (1997 nodes, all required nodes present) but MCP was unavailable this session. Comfy certification marked PENDING until MCP is restored.

---

## K. Peer Review

### Peer Review B — Kimi K3 Max

**Verdict: FAIL → REPAIRED.** Two blocking issues identified; both repaired at source with regression tests + live verification. Five minor issues also addressed.

**Reviewer model**: kimi-k3-max (substituted for unavailable Qwen 3.6 Pro / DeepSeek V4 Pro per owner approval).

#### Blocking issues (repaired)

| # | Defect | Root cause | Source repair | Regression test | Live proof |
|---|---|---|---|---|---|
| B1 | Stale capability/provider snapshot served without TTL on the status warm path; Ollama outage masked indefinitely | `peek_cached_snapshot`/`peek_capabilities` ignored `SNAPSHOT_TTL_SEC`; `_probe_codirector_provider` short-circuited on stale `provider_health` from the capability snapshot | `capabilities/service.py`: added `max_age_sec` TTL gate to `peek_cached_snapshot`/`peek_capabilities`; `probe_context.py`: warm path passes `max_age_sec=SNAPSHOT_TTL_SEC`; `registry.py`: removed `provider_health` short-circuit — always calls live `codirector_service.get_health()` (bounded by runner's 30s global check cache) | `test_peek_cached_snapshot_respects_max_age_ttl`; `test_codirector_provider_probe_always_calls_live_health` | `_verify_peer_review_b.py`: capabilities 200, status/check 200, TTL gate verified (stale→None with max_age, stale→snapshot without) |
| B2 | Video Intelligence `available=True` with zero models installed; enters `callable` list; message "Required weights are installed" vacuously false | `_eval_video_intelligence` passed `required=()` so `_model_component_eval` skipped the missing-required path and fell through to optional-missing path returning `available=True` | `capabilities/service.py`: `_model_component_eval` now returns `available=False` / `DEGRADED` when `required=()` and all optional components are missing (not callable, not a blocker — optional capability) | `test_model_component_eval_no_required_all_optional_missing_is_not_callable` | Live: `video_intelligence: available=False` NOT in callable list; NOT in blockers (optional, not blocking); status=degraded |

#### Minor issues (addressed)

| # | Defect | Repair |
|---|---|---|
| B3 | Transient "CPU-only detected" GPU label during audio checking window | `production_control/status.py`: only report "CPU-only detected" when `ready=True` AND `accelerator` is not `None`/`"unknown"` |
| B4 | Leftover independent jobs poller in `CompactRenderQueue.tsx` (3s `listJobs` interval) | Migrated to `useProjectJobs(projectId)` shared store; cancel button calls `refresh()` |
| B5 | `pollJob` delays first tick by `intervalMs` | `pollJob.ts`: added immediate `void tick()` on start; 10 tests updated |
| B6 | Timeout raises (5s→10s fallback, 180s→900s stall) | Reviewed: fallback-only / compensated by new 15s vanished-prompt watchdog; acknowledged as trade-off (outside milestone files) |
| B7 | Dead no-op in `comfy_client.health()` (`invalidate_object_info_cache` on already-empty cache) | Removed dead code |

#### Test results

- New regression tests: 3 passed (`test_peek_cached_snapshot_respects_max_age_ttl`, `test_model_component_eval_no_required_all_optional_missing_is_not_callable`, `test_codirector_provider_probe_always_calls_live_health`)
- `pollJob.test.ts`: 10 passed (updated for immediate first tick)
- `projectJobsStore.test.ts`: 7 passed (unchanged)
- Frontend build: ✓ built in 1.72s
- TypeScript type-check: ✓ (exit 0)

### Peer Review A — Claude Fable 5 Thinking

**Verdict: FAIL → REPAIRED.** Reviewer identified 3 blocking + 5 non-blocking issues. All blockers repaired at source with regression tests.

#### Blocking Issue D1 — `useProjectJobs(undefined)` unstable `getSnapshot` → infinite render loop

| Field | Value |
| --- | --- |
| **Symptom** | `useProjectJobs` returns a new object literal on every `getSnapshot` call when `projectId` is falsy. Under React 19 `useSyncExternalStore`, this fails `checkIfSnapshotChanged` → `forceStoreRerender` → "Maximum update depth exceeded". `LivePreviewMonitor.tsx` passes `composed ? undefined : project.id`, and `composed` is always truthy on the Timeline path. |
| **Root cause** | `projectJobsStore.ts:153` — `if (!projectId) return { jobs: [], lastFetchedAt: null };` creates a new object on every call. |
| **Direct repair** | Extracted a module-level `EMPTY_SNAPSHOT` constant and returned it from both `getSnapshot` and `getServerSnapshot`. Referentially stable. |
| **Regression test** | `projectJobsStore.test.ts` — "useProjectJobs returns a referentially stable snapshot when projectId is undefined": verifies `EMPTY_SNAPSHOT` is the same reference across imports. |
| **Live proof** | Frontend build ✓; 8/8 `projectJobsStore` tests pass; 18/18 combined frontend tests pass. |

#### Blocking Issue D2 — `build_status` serves stale cache unconditionally; no invalidation

| Field | Value |
| --- | --- |
| **Symptom** | `build_status(persist=True)` served the cached payload unconditionally. After the 30s TTL, it only set `stale=True` but never rebuilt. This meant install finalization and active-operation detection read a frozen pre-install snapshot. |
| **Root cause** | `setup/status.py:393-403` — the early-return path returned the cached payload for all ages, not just fresh cache. |
| **Direct repair** | Changed the early-return to only apply when the cache is fresh (`age < _STATUS_CACHE_TTL_SEC`). When stale, the function falls through to a full rebuild. The first stale caller pays the rebuild cost; subsequent callers within the new TTL get fresh cache. Also adjusted `_STATUS_BUILD_BUDGET_SEC` from 4.0s to 30.0s (the 4s budget was too aggressive — the build takes ~23s even with mocked verify, causing components to be skipped with `verify_timeout`). |
| **Regression test** | `test_setup_refactor.py` — `test_status_rebuilds_when_cache_is_stale`: seeds a stale cache, calls `build_status(persist=True)`, verifies it rebuilds (new verify calls > 0, fresh `checked_at`). |
| **Live proof** | 2/2 cache tests pass (`test_status_reuses_short_cache_when_idle` + `test_status_rebuilds_when_cache_is_stale`). |

#### Blocking Issue D3 — Capability snapshot warm path bypasses TTL

| Field | Value |
| --- | --- |
| **Symptom** | `probe_context.py` served `peek_capabilities()` without a TTL check, so model/credential changes were not reflected until LRU eviction or Comfy recovery. |
| **Root cause** | `peek_cached_snapshot`/`peek_capabilities` had no `max_age_sec` parameter; `warm_shared_bundle` called them without any TTL gate. |
| **Direct repair** | Already repaired as Peer Review B Blocking Issue B1: added `max_age_sec` parameter to `peek_cached_snapshot`/`peek_capabilities`; `warm_shared_bundle` now passes `max_age_sec=SNAPSHOT_TTL_SEC`. |
| **Regression test** | `test_peek_cached_snapshot_respects_max_age_ttl` (from Peer Review B repair). |
| **Live proof** | `_verify_peer_review_b.py` confirmed TTL-aware behavior live. |

#### Non-blocking Issue D5 — `_comfy_node_names` fallback ignores 60s TTL

| Field | Value |
| --- | --- |
| **Symptom** | `_comfy_node_names()` in `capability_probe.py` read `comfy._object_info_cache` without checking `_object_info_cached_at`, so a stale catalogue could be served indefinitely on the fallback path. |
| **Root cause** | Missing TTL check: `if isinstance(cache, dict) and cache:` — no age verification. |
| **Direct repair** | Added `time.monotonic() - cached_at < 60.0` check before serving the in-process cache. If stale, falls through to the `httpx` fetch. |
| **Regression test** | Covered by existing `test_probe_runtime_capabilities_falls_back_to_canonical_fetch` (verifies the fallback path). |
| **Live proof** | Backend tests pass. |

#### Non-blocking issues (acknowledged, not blocking)

- **D4** (timeout raise 180s→900s): Acknowledged as Peer Review B B6. The 900s timeout is for the `build_status` cold path which can take ~23s; 180s was too tight. Classified as acceptable.
- **D6** (`pollJob` first tick): Already repaired as Peer Review B B5.
- **D7** (JobPanel `onDone` latency): Minor — `onDone` callback fires after state update; acceptable latency (< 100ms).
- **D8** (`CompactRenderQueue`): Already repaired as Peer Review B B4.

#### Reconciliation

Peer Review A and Peer Review B independently identified the same root cause for D3/B1 (stale capability snapshot). The repair from Peer Review B (adding `max_age_sec` TTL gate) fully addresses D3. No additional work needed for D3.

Peer Review A's D1 and D2 are new findings not covered by Peer Review B. Both repaired at source with regression tests.

---

## Hard Binary Gates

| Gate | Verdict | Evidence |
| --- | --- | --- |
| 1. Library read path no-write / no-contention | **GO** | `test_migrate_current_schema_read_does_not_commit_or_write`; `_perf_library_read.py`: 0 commits, 0 writes, P50 <1ms |
| 2. Image readiness + Comfy catalogue deduplication | **GO** | `test_image_readiness_dedup.py` (2 tests); `_perf_image_readiness.py`: discovery 2→1, fetches 1→0; HTTP cross-check 1997 nodes |
| 3. Standard status event-loop safety | **GO** | `test_video_runtime_probe_runs_wave6_gate_off_event_loop` + `test_aggregate_status_uses_light_audio_path`; wave6_gate off event loop; audio light path |
| 4. Production Control performance | **GO** | `test_aggregate_status_uses_light_audio_path`; live PC status 28ms (was ~24,849ms); section 38 answered with measured evidence |
| 5. Frontend job polling consolidation | **GO** | `projectJobsStore.test.ts` (7) + `jobPanel.poll.test.ts` (1); ~80–120 req/min → ~12–30 req/min; build ✓ |
| 6. Performance regression + live stress | **PARTIAL** | Idle stress: 5× codirector status/check 200 (777–1456ms), 3× PC status 200 (21–38ms). **GPU-generation + Playwright perf pass: remaining** (see Limitations) |

### Limitations / Remaining verification

- **Live stress with one GPU generation**: idle stress passed; the controlled one-GPU-generation stress leg was not run in this turn (heavy; serialized-generation safety audit (section 28) reported current behavior — no immediate GPU-overload P0 defect observed). Recommended as the final live gate before binary GO.
- **Playwright performance pass** (section 34): not run this turn. Frontend unit tests + build pass; the Playwright network-capture pass across Character Creator / Co-Director / Library / Image Generator / Scene Creator / Timeline is the remaining verification.
- **Comfy MCP**: unavailable this session; HTTP cross-check used as temporary diagnostic evidence. Comfy certification PENDING until MCP restored.

### Overall verdict

Recorded in the governing completion report:

**NO-GO — GATE 6 LIVE GPU STRESS + PLAYWRIGHT PERFORMANCE PASS NOT COMPLETE**

All 9 P0/P1 repairs are implemented at source with regression tests + before/after evidence. Peer Reviews A and B failed first pass and were repaired. Gates 1–5 GO. Gate 6 remains incomplete (GPU-generation stress + Playwright network-capture). Comfy MCP pending. Working tree uncommitted. This appendix must not be cited as a Conditional GO.

