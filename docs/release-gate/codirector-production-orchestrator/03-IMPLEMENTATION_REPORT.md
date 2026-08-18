# Co-Director Full Production Orchestrator — Implementation Report

**Date:** 2026-08-18 (live verification session)
**Branch:** feat/lora-support (working tree carries the pre-existing Spatial-Map save-gate + ERS wave)

## 1. What was implemented

### Backend
1. **Production event stream** (mission Part 2, 27, 39-42):
   - New table `production_events` (migration m034) + module `studio-api/app/production_events.py` (record/list/recent + bounded prompt block; recording is best-effort and never blocks production).
   - Hooks in: CD timeline tools (clip_added / prompt_added, actor=codirector), w46 service (batch_created/deleted/duplicated), w46 orchestrator (generation_started/completed, candidate approved/rejected, retake_started, clip_added), spatial map service (spatial_map.saved/updated, camera.created/updated/deleted), ERS handler (ers.generation_started), scene handler (scene_creator.generation_started), queue_worker imagegen commit (candidate.generated / ers.generation_completed), library (library.asset_ingested). Events now commit immediately so awareness is real-time.
2. **Production State Snapshot** (mission Part 1, 55):
   - `codirector/production_state/snapshot.py`: compact snapshot (project, scene, spatial map saved/current version + dirty, cameras, ERS sheet + status, candidates with C1-A style parsing, timeline revision + batches, active jobs, recent events).
   - Auto-injected into every chat context after the wiki block (`service.py _prepare_chat_request`), bounded ~2400 chars.
   - Read tool `project.production_snapshot` + REST `GET /api/codirector/projects/{id}/production-snapshot`.
3. **Production memory + reference resolution** (mission Parts 3-4, 54, 56):
   - `codirector/production_state/memory.py`: recent CD tool actions (from codirector_tool_invocations) + events + snapshot; `resolve_reference` handles C1-A tags, ordinals ("the first C2 shot", "shot frame 1"), camera labels ("the close-up"), and ambiguity flags.
   - Injected into chat context (bounded); tools `production.memory` / `production.resolve_reference` / `candidate.list` / `candidate.resolve`; REST endpoints.
4. **Execution authority** (mission Parts 30, 35-36; frozen contract #3 amendment):
   - `codirector/execution_authority.py`: per-project `proposals | direct` setting; `ROUTINE_TOOLS` allowlist (16 routine reversible mutations); auto-approval through the EXISTING proposal machinery when direct + chat-turn request_id. Destructive/costly tools NEVER auto-approve. REST `GET/PUT /api/codirector/projects/{id}/execution-authority`.
5. **timeline.build_shot composite tool** (mission Parts 17-22, 29):
   - Resolves the asset (project-scoped), best-effort Library durability (assign_asset), sequential placement (no float drift, round 6), exact duration, optional matched timed-prompt segment storing `userDirection` vs `productionPrompt` and verbatim `dialogue`; emits timeline.clip_added event; returns clipId/segmentId/start/duration/revision.
6. **Prompt provenance** (mission Parts 13-16, 19-20, 52):
   - `PromptSegment` + `TimelinePromptSegment` extended with userDirection / productionPrompt / dialogue; `timeline.propose_add_prompt_segment` accepts and persists them.
7. **Conversational production routing** (mission Part 6, 17-28):
   - New deterministic patterns in `routing/deterministic.py` (before the approve/reject checks): "create images from the ERS", "using the four saved cameras", timeline edit vocabulary (put/add on timeline, timed prompt, batch, generator selection, frame size, durations).
   - Capability patterns in `routing/unified_intent.py` mapping them to scene.generate / timeline.add_asset.
   - Verified: "Create images from the ERS using the four saved cameras." now routes EXECUTE_PRODUCTION -> EXECUTION(scene.generate) -> REAL imagegen job (proven live: job 5cc763cc, asset 6b46f4d0, candidate.generated event).
8. **Latency repair** (mission Part 49 + conversational usability):
   - `capabilities/service.py` SNAPSHOT_TTL_SEC 20 -> 300 (probe_setup cost ~50s made every tool-calling chat turn stall ~85s; explicit refresh endpoint unchanged).
9. **Robustness fixes found during live certification**:
   - scene_generate handler: coerce output_count=None from dispatcher (crash fix).
   - queue_worker: `uuid4` NameError in timeline batch asset registration (in-flight wave bug).

### Frontend
10. **Media result cards in chat** (mission Parts 10, 28, 31):
    - `CoDirectorMediaCardGrid.tsx` + css: renders result_asset_ids / child-job assets as a thumbnail grid with data-asset-id retention; wired into CoDirectorMessage for execution_status/completion messages. tsc clean.

## 2. Verified live (evidence)

| Item | Evidence |
|---|---|
| Snapshot on Schnick | Spatial Map v138 saved, 4 cameras C1-C4, ERS sheet, 12 candidates, timeline revision+batches, jobs, events |
| Reference resolution | C1-A / "the first C2 shot" / "shot frame 1" resolve to real asset ids; duplicate C1-A flags ambiguous |
| Direct authority | proposal completed + "Authority Test Batch" landed on timeline via auto-approval |
| Conversational generation | "Create images from the ERS using the four saved cameras." -> EXECUTE_PRODUCTION -> scene.generate -> real imagegen job -> asset + candidate.generated event |
| Honest failure | unplaced prop produced an honest creator-readable failure (no fake success) |
| Events | timeline.batch_created / clip_added / prompt_added / candidate.generated / spatial_map.saved recorded and queryable |
| pytest | 15/15 in test_codirector_production_orchestrator.py (snapshot, events, memory, authority, provenance, sequential placement) |
| Router regressions | 205 passed; 6 pre-existing failures unrelated to this milestone (working-tree in-flight code) |

## 3. Open / remaining for certification closure
- Playwright E2E re-run with warmup (in flight).
- Live chat-level scenario completion + manual-change awareness demonstration.
- Independent certifier run + final evidence bundle + binary verdict.

## 4. Addendum — fixes discovered during live certification

- **capabilities/service.py**: single-slot snapshot cache replaced with a bounded
  multi-slot cache (per project + global). The web UI polls /api/capabilities
  while Co-Director proposes with a project key; a single slot made every poll
  evict the project snapshot and re-trigger the ~50s probe on the next tool
  call (propose latency measured 75-137s -> 57ms after the fix).
- **scene_generate.py**: coerce output_count=None (dispatcher passes the kwarg
  explicitly) instead of crashing on max(1, None).
- **queue_worker.py**: fix bare uuid4 NameError in timeline batch output asset
  registration (pre-existing in-flight wave bug).
- **production_state/snapshot.py**: _timeline_state now handles Pydantic model
  bundles (load_timeline_bundle returns SceneTimelineMaster objects) and
  surfaces legacy Visual clips + Prompt segments (with userDirection /
  productionPrompt / dialogue) so CD can answer "what is on Timeline".

## 5. Scenario E live closure (batch generation)

On the live Schnick project:
- Batch 2 created with generator minimax-h3-local -> honest ADAPTER_SUBMIT_FAILED
  "MiniMax H3 private runtime is not ready right now" (H3 model not installed on
  D:\\01_Models - documented deployment prerequisite).
- Batch switched to ltx-local (first-class Timeline generator): REAL job submitted
  (job_ef7da41963e8 / dcb8ae6b-dc76-44df-ada0-4cf395cf0eb2, LTX T2V, immutable
  execution snapshot snap_8021aafd8787), event timeline.generation_started recorded.
- Full event trail on Schnick: timeline.generation_started / clip_added /
  batch_created / candidate.generated (from both conversational scene generation
  and manual-UI-equivalent operations).
- Also fixed: scene lipsync gate data (ls-missing clip speaker binding) so the
  timeline's smart gate passes - the gate itself is the pre-certified engine's.
