# Adept UI — System Optimization & Performance Repair

**Law 2 unified completion report.**  
**Law 30:** this is the governing completion report for the System Optimization & Performance Repair milestone. Technical evidence appendix: [`ADEPT_UI_SYSTEM_OPTIMIZATION_AUDIT.md`](./ADEPT_UI_SYSTEM_OPTIMIZATION_AUDIT.md). Do not cite the audit as the final verdict.

| Field | Value |
| --- | --- |
| Date | 2026-08-24 |
| Milestone | Adept UI v1.1 — System Optimization & Performance Repair |
| Branch | `feat/character-creator-final-closure` |
| Starting / recorded HEAD SHA | `b6156455e643d5fa430784b3130756f2d8038651` |
| Working tree | **Dirty** — repairs are implemented locally and are **not committed** |
| Subagent model | Kimi Code 2.7 (SPECIALIZED SUBAGENT MODEL LAW) |
| Peer Review A | Claude Fable 5 Thinking — FAIL → repaired |
| Peer Review B | Kimi K3 Max — FAIL → repaired |
| Creator UI | http://127.0.0.1:5173/ |
| Studio API | http://127.0.0.1:8758/ |
| ComfyUI | http://127.0.0.1:8188/ |
| Retired | `:8760` (do not use) |

---

## Verdict

**NO-GO — GATE 6 LIVE GPU STRESS + PLAYWRIGHT PERFORMANCE PASS NOT COMPLETE**

Repairs 1–9 and both peer-review blocker sets are implemented at source, regression-tested, and live on the local runtime. Five of six hard gates are GO. The milestone cannot be certified complete because:

1. Gate 6 still lacks the required one-GPU-generation live stress and Playwright network-capture pass.
2. Comfy MCP was unavailable; HTTP `:8188` was used as temporary diagnostic evidence only.
3. The working tree is uncommitted, so this report is **not** a clean-clone / deployable SHA.

This is not a Conditional GO. Remaining work is listed under Limitations.

---

## How to review (10 minutes)

1. Confirm Studio API: http://127.0.0.1:8758/api/healthz → `{"status":"ok"}`.
2. Confirm Creator UI: http://127.0.0.1:5173/ → HTTP 200.
3. Confirm Comfy: http://127.0.0.1:8188/system_stats → HTTP 200.
4. Open Production Control / Co-Director status. Status should return in well under 4 seconds (measured warm PC status 21–38 ms).
5. Open Timeline Preview. The Preview Monitor must not spin or throw “Maximum update depth exceeded” (D1 repair).
6. Leave a project idle ~30 s. Jobs polling should be one shared stream, not four independent `GET /jobs` timers.
7. Do **not** treat this report as Character Creator visual certification. That work remains paused.

Do not launch ComfyUI, Ollama, or Uvicorn from a terminal. Adept owns those runtimes.

---

## Objective

Repair the measured hot paths that made Adept UI heavier, more sluggish, or more failure-prone than necessary.

This was **not** a redesign, feature expansion, or broad refactor. Governing laws:

- **ROOT-CAUSE REPAIR LAW** — measure the expensive source; repair the source; no timeout inflation, no health masking, no compensating caches.
- **CACHE INTEGRITY LAW** — every cache must define stores, TTL, invalidation, force-refresh, execution behavior, and stale-state risk.
- **COMFY MCP WORKFLOW VERIFICATION LAW** — Comfy catalogue / readiness optimizations must be cross-checked against live `:8188`. MCP was unavailable; HTTP is marked temporary.

---

## Scope completed

| Area | Status |
| --- | --- |
| P0/P1-1 Library write-on-read | IMPLEMENTED + TESTED + LIVE MEASURED |
| P0/P1-2 Image readiness duplicate model discovery | IMPLEMENTED + TESTED + LIVE MEASURED |
| P0/P1-3 Duplicate Comfy `/object_info` | IMPLEMENTED + TESTED + LIVE MEASURED |
| P0/P1-4 Video runtime event-loop block | IMPLEMENTED + TESTED |
| P0/P1-5 Production Control >4000 ms | IMPLEMENTED + TESTED + LIVE MEASURED |
| P1-6 Shared frontend jobs poll store | IMPLEMENTED + TESTED + BUILD PASSED |
| P1-7 Comfy catalogue one-source cleanup | IMPLEMENTED (folded into P0/P1-3) |
| P1-8 Progress poll gating | IMPLEMENTED + TESTED |
| P2-9 Avatar torch | MEASURED — no repair (0.16 ms exception path) |
| P2-9 Unhealthy component TTL | IMPLEMENTED + TESTED |
| Peer Review B blockers B1–B2 + minors B3–B5, B7 | IMPLEMENTED + TESTED + LIVE CHECKED |
| Peer Review A blockers D1–D3 + D5 | IMPLEMENTED + TESTED + LIVE CHECKED |
| Full-platform measurement + cache/event-loop/memory/GPU/serialized-gen audits | DOCUMENTED in the audit appendix |
| Gate 6 GPU-generation stress | NOT VERIFIED |
| Gate 6 Playwright performance pass | NOT VERIFIED |
| Comfy MCP cross-check | BLOCKED — MCP unavailable this session |

---

## Architecture (reuse, not redesign)

```text
Library read
  get_tree → migrate_project_library
    if schema current → no write, no commit
    else → migrate + persist

Image readiness
  discover_modern_image_models() once
    → generate_readiness_report(discovery)
    → probe_runtime_capabilities(discovery, warmed node names)

Comfy catalogue
  settings.comfy_url + comfy.get_object_info() (60 s TTL)
    → _comfy_node_names() reuses cache only when age < 60 s
    → no COMFY_URL / urllib second path

Status vs execution
  status: light / cached / off event loop
  execution: refresh=True / fresh probe

Frontend jobs
  ProjectJobsStore (one interval per project)
    → JobPanel, LivePreviewMonitor, TimelinePreviewComposer,
      ContextInspector, CompactRenderQueue
```

---

## Files (milestone-owned)

### Backend

| File | Change |
| --- | --- |
| `studio-api/app/project_library/service.py` | Early no-op when library schema is current |
| `studio-api/app/image_runtime/readiness.py` | Discover models once; accept warmed node names |
| `studio-api/app/image_runtime/capability_probe.py` | Canonical `_comfy_node_names()`; 60 s TTL on cache reuse |
| `studio-api/app/comfy_client.py` | Removed dead `health()` no-op |
| `studio-api/app/codirector/status/registry.py` | `wave6_gate` off event loop; live Co-Director provider probe |
| `studio-api/app/codirector/status/probe_context.py` | Capability peek honors `SNAPSHOT_TTL_SEC` |
| `studio-api/app/production_control/status.py` | Light audio path + bounded parallelism; CPU-only label gated |
| `studio-api/app/production_control/resolve.py` | Execution keeps `local_runtime_status(refresh=True)` |
| `studio-api/app/audio_studio/provider_resolver.py` | 30 s cache; `light=True` never blocks on the ~25 s probe |
| `studio-api/app/capabilities/service.py` | `max_age_sec` peek; optional-all-missing is not callable |
| `studio-api/app/setup/status.py` | Stale cache rebuilds; 30 s build budget |
| `studio-api/app/setup/diagnostics.py` | 12 s unhealthy TTL |

### Frontend

| File | Change |
| --- | --- |
| `studio-web/src/runtime/projectJobsStore.ts` | Shared per-project jobs store; stable `EMPTY_SNAPSHOT` |
| `studio-web/src/utils/pollJob.ts` | Terminal-gated progress poller; immediate first tick |
| `studio-web/src/components/JobPanel.tsx` | Uses `useProjectJobs` |
| `studio-web/src/components/LivePreviewMonitor.tsx` | Uses `useProjectJobs` (undefined when composed) |
| `studio-web/src/components/ContextInspector.tsx` | Uses `useProjectJobs` (no double-fetch) |
| `studio-web/src/components/timeline-master/TimelinePreviewComposer.tsx` | Uses `useProjectJobs` |
| `studio-web/src/components/timeline-master/CompactRenderQueue.tsx` | Migrated off independent 3 s poller |
| `studio-web/src/components/SpatialSceneWorkspace.tsx` | Uses `pollJob` |
| `studio-web/src/components/magi/MagiEditorWorkspace.tsx` | Uses `pollJob` |

### Tests + evidence

| File | Change |
| --- | --- |
| `studio-api/tests/test_project_library_service.py` | Current-schema read does not commit |
| `studio-api/tests/test_image_readiness_dedup.py` | One discovery + catalogue reuse |
| `studio-api/tests/test_audio_runtime_status_cache.py` | Light audio path + parallelism |
| `studio-api/tests/test_codirector_status_cross_check.py` | Event-loop + live provider probe |
| `studio-api/tests/test_capabilities.py` | TTL peek, Comfy recovery, video-intelligence not callable |
| `studio-api/tests/test_setup_refactor.py` | Stale `build_status` rebuilds |
| `studio-api/tests/test_runtime_diagnostics_refinement.py` | Unhealthy 12 s TTL |
| `studio-web/src/runtime/projectJobsStore.test.ts` | Shared poll + stable empty snapshot |
| `studio-web/src/utils/pollJob.test.ts` | Terminal stop + immediate first tick |
| `studio-web/src/components/jobPanel.poll.test.ts` | Store-based JobPanel |
| `.runtime/_perf_*.py` | Before/after measurement scripts (local evidence, not product source) |

---

## Before / after (measured)

| System | Before | After |
| --- | ---: | ---: |
| Library `get_tree` (current schema) | ~45 ms + 1 commit + 1 settings write | P50 &lt; 1 ms, 0 commits, 0 writes |
| Image readiness refresh | 2 model scans + 1 raw `/object_info` | 1 scan + 0 fetches (warmed names) |
| Production Control `aggregate_status` | **24,849 ms** cold (audio torch/subprocess) | P50 **15.83 ms** / live **21–38 ms** |
| Frontend jobs polling | ~80–120 req/min (4 pollers) | ~12–30 req/min (1 shared poller) |
| Progress poll defects | 2 of 8 surfaces | 0 of 8 (helper + refactors) |

### Section 38 — why Production Control still exceeded 4000 ms after the prior event-loop repair

Measured: `aggregate_status()` → `local_runtime_status()` on the **status** path imported torch and spawned subprocess health checks. Cold audio probe = **24,849 ms**. Moving that work to `asyncio.to_thread` stopped event-loop blocking but the **probe total** still exceeded the 4000 ms health budget on every cold call. Status was doing generation-grade ML probing. Repair: `light=True` never blocks; execution keeps `refresh=True`.

---

## Tests (exact counts)

| Suite | Result |
| --- | --- |
| `projectJobsStore.test.ts` | **8 passed** |
| `pollJob.test.ts` | **10 passed** |
| Combined frontend jobs/progress | **18 passed** |
| `test_status_reuses_short_cache_when_idle` + `test_status_rebuilds_when_cache_is_stale` | **2 passed** |
| Capability TTL / recovery / video-intelligence / peek | **4 passed** (targeted re-run after B2 correction) |
| Frontend production build | **passed** (`tsc -b && vite build`, ~1.72 s) |
| Idle live stress | 5× Co-Director status/check HTTP 200 (777–1456 ms); 3× PC status HTTP 200 (21–38 ms) |
| Live health at report time | API `{"status":"ok"}`; UI 200; Comfy `/system_stats` 200 |
| Live video-intelligence | `available=False`; not in `callable`; not in `blockers` |

### Out of scope / pre-existing failures (not this milestone)

- `test_illustrious_routing.py` — failed on a clean stashed baseline.
- `test_comfy_health_optional_missing_does_not_degrade_runtime` and `test_health_endpoint_top_level_missing_lists_exclude_optional` — failed on a clean stashed baseline.

---

## Peer review reconciliation

Both reviewers independently failed the first pass. All **blocking** findings were repaired at source.

| Reviewer | Blocking | Repair |
| --- | --- | --- |
| Peer Review B | B1 stale capability/provider snapshot | `max_age_sec` on peek; warm path uses `SNAPSHOT_TTL_SEC`; provider probe always live |
| Peer Review B | B2 video intelligence falsely callable | `required=()` + all optional missing → `available=False`, `DEGRADED` (not a global blocker) |
| Peer Review A | D1 unstable `getSnapshot` when `projectId` is falsy | Module-level `EMPTY_SNAPSHOT` |
| Peer Review A | D2 `build_status` served cache forever | Fresh TTL serve; stale falls through to rebuild |
| Peer Review A | D3 capability TTL bypass | Same as B1 — already repaired |

Minors B3–B5, B7, and D5 were also repaired. B6/D4 timeout raises were reviewed and left as documented trade-offs outside this milestone’s locked P0/P1 order.

---

## Hard binary gates

| Gate | Required language | Verdict |
| --- | --- | --- |
| 1 | GO — LIBRARY READ PATH NO-WRITE / NO-CONTENTION CERTIFIED | **GO** |
| 2 | GO — IMAGE READINESS + COMFY CATALOGUE DEDUPLICATION CERTIFIED | **GO** |
| 3 | GO — STANDARD STATUS EVENT-LOOP SAFETY CERTIFIED | **GO** |
| 4 | GO — PRODUCTION CONTROL PERFORMANCE CERTIFIED | **GO** |
| 5 | GO — FRONTEND JOB POLLING CONSOLIDATION CERTIFIED | **GO** |
| 6 | GO — ADEPT UI PERFORMANCE REGRESSION + LIVE STRESS CERTIFIED | **NO-GO** — GPU-generation stress and Playwright network-capture pass not run |

Overall required language when all six pass:

`GO — ADEPT UI SYSTEM OPTIMIZATION + PERFORMANCE HEALTH CERTIFIED`

**Not granted.**

---

## Limitations

1. **Gate 6 incomplete.** Idle stress passed. The plan requires one controlled image generation while status/Library/PC/Comfy stay responsive, plus Playwright network capture on Character Creator, Co-Director, Library, Image Generator, Scene Creator, and Timeline.
2. **Comfy MCP pending.** HTTP `:8188` proved `/system_stats` 200, `/object_info` 200, **1997** nodes, required nodes present. That is temporary diagnostic evidence, not MCP certification.
3. **Uncommitted working tree.** HEAD `b615645` does not include these repairs. A clean checkout of the recorded SHA will not contain this work.
4. **Setup `/api/setup/status` cold path ~20–30 s** remains a pre-existing Tier-3 slow path, outside the locked P0/P1 order.
5. **Scene Creator Mini** has no “1 active concept generation” busy guard. Deferred per plan (do not redesign Mini/Timeline here). Character Creator and Timeline batch already serialize.
6. **Character Creator visual certification** remains paused from the prior health-recovery instruction. This milestone does not resume it.

---

## Manual review path

| Surface | URL |
| --- | --- |
| Creator UI | http://127.0.0.1:5173/ |
| Studio API | http://127.0.0.1:8758/ |
| Health | http://127.0.0.1:8758/api/healthz |
| Production Control | http://127.0.0.1:8758/api/production-control/status |
| Comfy | http://127.0.0.1:8188/system_stats |

Runtime was left running after the last supervisor start (Studio API owned, Comfy reused, Ollama external).

---

## Remaining (authorized next work)

1. Run Gate 6: idle soak + **one** serialized GPU generation; prove status/Library/PC stay responsive.
2. Run Playwright performance pass with network capture on the six named surfaces.
3. Restore Comfy MCP and re-cross-check catalogue / readiness.
4. Commit only when the owner asks.

Until those complete, the governing verdict remains:

**NO-GO — GATE 6 LIVE GPU STRESS + PLAYWRIGHT PERFORMANCE PASS NOT COMPLETE**

---

## Mandatory completion checklist

```text
[x] Branch + starting SHA verified
[x] Contracts preserved or intentionally updated
[x] Full-stack implementation completed (P0/P1 repairs)
[x] Every visible control wired (no new dead chrome)
[x] Real runtime; no mock completion for implemented repairs
[ ] Persistence after reload verified (not in this milestone’s remaining Gate 6)
[x] Error/cancel/retry/recovery verified for repaired caches (TTL + invalidation)
[ ] Authz + project isolation verified (not in scope)
[x] Targeted unit/API/regression passed for repaired defects
[ ] Playwright creator workflow / performance pass
[x] Failures repaired and documented (peer-review blockers)
[x] Subagents second-pass + two peer reviews recorded
[x] Production frontend build passed
[x] Runtime refreshed; URLs reported
[x] Manual review path documented
[x] Evidence saved (audit appendix + this report)
[x] Unified Markdown completion report created (this file)
[x] Limitations honest
[x] Verdict: GO or NO-GO  →  NO-GO
[ ] GPU-designated workload performed accelerator preflight (Gate 6 generation not run)
[x] CPU fallback did not occur silently (no silent fallback added)
[x] Creator workflows inside Adept UI; runtimes not exposed (Law 29)
[x] One governing completion doc; audit marked as evidence appendix (Law 30)
[ ] Capability evidenced: Playwright + independent verification for Gate 6 (Law 31)
```
