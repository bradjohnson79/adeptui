# Co-Director Full Production Orchestrator — Capability Reuse Map

**Milestone:** Co-Director Full Production Orchestrator
**Date:** 2026-08-18
**Branch:** feat/lora-support — HEAD 31e6e48f (working tree carries the in-flight Spatial-Map save-gate + ERS wave; this map was verified against the live beta backend on :8758)

## Method

Direct source audit of `studio-api/app` (FastAPI), `studio-web/src` (React), the live SQLite DB (`data/studio.db`, 156 tables), the running backend, and prior certification reports. Four broad audit subagents were attempted and hit context limits; findings below were verified first-hand by the primary agent (files, routes, live API probes, DB queries).

## 1. Runtime truth (live)

| Item | State |
|---|---|
| Studio API | uvicorn on 127.0.0.1:8758, Python 3.11 (uv), healthy, feature flags ON: PRODUCTION_EXECUTIVE_V1, DIRECTOR_TIMELINE_V1, IMAGE/FRAME/VIDEO/AUDIO/EDITING/RENDER_PRODUCTION_V1, CODIRECTOR_PRODUCTION_CONTROL_V1, CODIRECTOR_PRODUCTION_INTELLIGENCE_V1, ADAPTIVE_LEARNING_V1, OPERATIONAL_AGENT_V1, MINIMAX_H3_PRIVATE_LOCAL |
| DB | `data/studio.db` (sqlite via `settings.data_dir`), migrations applied at import (m001..m033) |
| Frontend | Vite dev :5173 (proxies /api to 8758), React 19 |
| ComfyUI :8188, Ollama :11434 | healthy |
| Schnick Coffee project | `2347bf46-3762-4763-86c5-4a6032522278`, 1 scene, 186 assets, Spatial Map scene doc v138, ERS sheet `db095959` (views_pending), 21 conversation events, scene_creator_mini candidates (tags `scene_creator_mini_<n>_C<cam>_<variant>`), 5 scene reference bindings |

## 2. Capability inventory (REUSE / EXTEND / MISSING)

### 2.1 Chat / conversation core — REUSE
- `POST /api/codirector/chat/stream` (SSE) → `codirector_service.stream_for_project` (`routers/codirector.py`, `codirector/service.py`) with rich event set: request_started, token, tool_requested/started/completed/failed, execution_started/completed/failed, execution_status, background_job, proposal_created, approval_required, completed, etc.
- `POST /api/codirector/chat`, `/cancel`, conversation CRUD + events + revision + stream + audit + compact.
- Frontend: `studio-web/src/components/CoDirector/*` (Conversation, Message, Composer, Session provider, ProposalCard, ApprovalCenter, ProductionExecutive, GenerationQueueCard).
- **Verdict: REUSE — the conversation core is the gateway (frozen contract #1).**

### 2.2 Tool / capability registry — REUSE (the mission's "capability registry" already exists)
- `codirector/tools/registry.py`: closed registry, **258 read tools + 241 mutation tools = 499 bindings**, each read tool executes immediately; each mutation tool = preview + apply via durable proposal.
- `codirector/tools/execution.py` ToolExecutionService: execute_read / propose / execute_approved_proposal / execute_audited; every attempt logged to `codirector_tool_invocations`.
- `codirector/tools/definitions.py` schemas; `capabilities.py` CapabilityAdapter (availability/readiness per project).
- REST: `GET /api/codirector/tools`, `/projects/{id}/tools`, `/tools/availability`, `POST /tools/read`, `/tools/audited`, `/tools/proposals`, `GET /tool-invocations`.
- Highlights relevant to the mission: spatial.* (map/camera/placement), ers.* (create_sheet, attach_spatial_map, generate_directional_views, approve_direction, compose_sheet), multi_shot.*, timeline.get_workspace, timeline.propose_add_image_clip / propose_add_prompt_segment / propose_add_batch / propose_retake / propose_generate_scene, timeline.update_settings, image_pipeline.* (generate_candidates, evaluate_candidates, select_candidate), library.*, editor.place_asset, minimax_h3.*, job.*, production_plan.*, prompt.enhance.
- **Verdict: REUSE. Gap: no candidate-list/resolve tool and no direct-execute path for explicitly-requested routine actions (see 2.9).**

### 2.3 Project state / context — EXTEND
- `codirector/project_context.py` `retrieve_project_context`: story, script, storyboard, characters, foundation + m413 additions: `spatial_map_summary`, `ers_packages`, `scene_batches`.
- Exposed as read tool `project.read_context` (handler `tools/handlers/project_context.py`) + `GET /api/codirector/projects/{id}/context`.
- Injected into chat today: wiki snapshot only (`context_enrichment.compact_wiki_context`). Production state is NOT auto-injected (verified in `conversation/orchestrate.py` prompt assembly).
- `conversation/snapshot.py` ProjectIntelligenceSnapshot: narrative/creative director state only.
- **Verdict: EXTEND — add a compact production-state snapshot (spatial saved/dirty/version, ERS revision/status, cameras, candidates, timeline clips/batches, active jobs, recent events) and inject it automatically; keep it bounded.**

### 2.4 Timeline — REUSE + EXTEND
- `director_timeline_w46`: SceneTimelineMaster (batchBlocks, imageClips, promptSegments, videoClips, cameras), store.load/save_master (revision bump), service (workspace, load_timeline_bundle, add_batch, put_master), orchestrator (generation), generation/adapters (minimax, ltx_local, kling, seedance, stub_cert), router mounted at /api, retakes module, migration from legacy director timeline.
- CD tools: timeline.get_workspace, timeline.propose_add_image_clip, timeline.propose_add_prompt_segment, timeline.propose_add_batch, timeline.propose_retake, timeline.propose_generate_scene, timeline.update_settings (generator/frame via settings), timeline.set_playhead, timeline.remove_item, etc.
- `codirector/timeline_context/` = Bible/wiki package FOR the timeline (not CD's view).
- `GET /api/codirector/projects/{id}/timeline-context/{scene_id}` + /scene-status + /gate.
- **Verdict: REUSE. Gap: (a) no production events emitted on timeline mutations, (b) mutation = propose→approve only (no direct-execute for explicit commands), (c) no candidate→timeline convenience flow (ensure library durability, add clip, duration, sequential placement).**

### 2.5 Spatial Map / ERS — REUSE
- `spatial_map/`: documents (spatial_map_documents table), save gate + ERS warning (uncommitted wave), cameras, placements, characters/props; `ers_projection.py` (new, uncommitted), `ers_contracts.py`, `ers_persistence.py` (load_ers_package).
- `environment_reference_sheet/`: JSON store per project (sheets dir), orchestrator, exports (render_png composition), continuity; capability handler `codirector/capabilities/handlers/ers_generate.py` (real image-product jobs, provenance, 2K).
- CD tools: spatial.* (list_maps, get_map, inspect_scene, list_cameras, get_camera_view, create_camera, update_camera...), ers.* (list_sheets, get_sheet, create_sheet, generate_directional_views, compose_sheet...).
- **Verdict: REUSE. Gap: no spatial/ERS production events; snapshot must expose saved-vs-dirty + revision (save gate law).**

### 2.6 Scene Creator / candidates — REUSE + EXTEND
- `scene_creator/`: service, router, ers_resolver; shared engine `capabilities/handlers/scene_generate.py` (CDX-085: ONE engine for Scene Creator REST + CD execution pack; real imagegen jobs; entity tags @/#; output-count law).
- `multi_shot/`: multi_shot_candidates + multi_shot_plans tables, tools multi_shot.create_plan/add_shots/send_to_timeline.
- Candidates in the wild: assets tagged `scene_creator_mini_8_C2_B` (camera+variant naming).
- **Verdict: REUSE. Gap: no generic candidate listing/resolution tool ("C1-A" → asset) in the registry; candidates not in the auto-injected snapshot.**

### 2.7 Library / approvals — REUSE
- `project_library/` + library tools (search_library_assets, get_library_folder_map, plan_library_storage, resolve_library_location, editor.place_asset); assets table (production_approval, validation_lifecycle).
- `codirector/vision/` approval engine; `codirector_approvals` table; ApprovalCenterPanel UI.
- **Verdict: REUSE.**

### 2.8 Generation / jobs / events — REUSE + EXTEND
- `queue_worker.py` (job_queue, imagegen job path, uncommitted changes), `unified_jobs.py` (to_unified_dto), `executive/` production job system (jobs, events, notifications, statistics) with feature flag ON, `production_jobs` + `production_job_events` + `production_notifications` tables.
- `image_product/` resolve_image_capability → enqueue_imagegen_job; `minimax_h3/`; `hosted_providers/` (kie adapter, fal); `image_runtime/` (fingerprints, provenance).
- **Verdict: REUSE. Gap: no project-scoped production event stream that captures manual UI actions (timeline clip added by hand, ERS completed by hand, etc.) for CD awareness (mission Parts 2, 39–42).**

### 2.9 Execution authority — EXTEND (design decision, contract-compliant)
- Today: mutation tools always propose; human approves in-chat (ProposalCard). Frozen contract: "execute-approved only". Mission: "DIRECT COMMAND → execute" for routine reversible actions.
- Existing precedent: `production_intent/approval.py` evaluates approval requirements (high-cost/identity-sensitive → required; the policy model already distinguishes required vs not-required).
- **Design: add an explicit "direct command" auto-execution path — when the user's message is an imperative direct command for a routine, reversible, non-destructive mutation, the execution engine may apply it immediately and record an audited invocation (creator-authority preserved: the user's explicit instruction IS the authorization). Destructive/high-impact/costly operations keep the proposal gate. This extends the contract with a documented additive amendment (contract-change policy requires primary approval + doc update — this milestone is the primary).**

### 2.10 Memory — EXTEND
- `codirector_tool_invocations` = full audit trail of CD actions (arguments, results, errors, capability snapshot).
- `codirector_production_plan_events`, `production_job_events`, `codirector_execution_receipts`, `m211_memory_items` (adaptive lessons).
- `conversation_memory.py` export/import (conversation+wiki+snapshot+learning).
- **Verdict: EXTEND — build a queryable production-memory projection over these stores (recent meaningful events + structured action records) with prompt injection (bounded) and reference-resolution helpers (candidate/clip/asset resolution).**

### 2.11 Prompt refinement / creative intelligence — REUSE + EXTEND
- `prompt_intelligence/` (compose, pipeline, scoring, recommendation; tools prompt.enhance / prompt.analyze) — exists and is certified per docs (M30E, prompt-intelligence-v2).
- `production_intent/compiler.py` — intent compilation.
- `execution/result_context.py` + `scene_shot_collection_builder.py`.
- **Verdict: REUSE the enhancement engine; EXTEND the execution path to store `userDirection` vs `productionPrompt` separately (mission Parts 13–16, 19, 20) when creating timeline prompt clips and generation requests; preserve dialogue verbatim.**

### 2.12 Result presentation in chat — MISSING (frontend)
- `CoDirectorMessage.tsx` renders markdown (whitelist excludes <img>) + ExecutionSummaryCard (progress + child jobs) + GenerationQueueCard (storyboard-specific).
- No generic image/media cards for `result_asset_ids` (verified).
- **Verdict: IMPLEMENT — a media-card renderer for execution/deliverable events (thumbnail grid with asset IDs retained, click to open).**

## 3. Test / certification infrastructure — REUSE
- Backend pytest: ~80 `test_codirector_*.py` incl. `test_p9_schnick_coffee.py`, `test_p10_tier_b_schnick.py` (routing-level scenario sessions, mocked LLM) + conftest.
- Frontend vitest: co-located `*.test.ts`.
- Playwright: `playwright.config.ts`, `scripts/e2e-start.mjs` boots stack, suites under `tests/e2e/` (codirector/, co-director/, timeline/, scene-creator/, spatial/, ...) with helpers `tests/helpers/e2eTest.ts` + fixtures.
- **Verdict: REUSE; add the Schnick production-orchestration specs (real backend, disposable project) per mission Parts 61–62.**

## 4. Gap summary (implementation order)

| # | Gap | Mission part | Impact |
|---|---|---|---|
| G1 | Production-state snapshot auto-injection (scene/spatial/ERS/cameras/candidates/timeline/jobs/events) | 1, 55 | HIGH |
| G2 | Project-scoped production event stream (all subsystems, incl. manual UI actions) + query | 2, 27, 39–42 | HIGH |
| G3 | Queryable production memory + bounded injection + reference resolution | 3, 4, 54, 56 | HIGH |
| G4 | Candidate listing/resolution (C1-A → asset) | 9, 11 | HIGH |
| G5 | Media result cards in chat | 10, 28, 31 | MEDIUM |
| G6 | Direct-command execution path for routine reversible mutations (contract amendment) | 35, 36 | HIGH |
| G7 | Prompt refinement wiring: userDirection vs productionPrompt stored on prompt clips + model compilation | 13–16, 19, 20 | MEDIUM |
| G8 | Timeline convenience: ensure-library → add image clip → duration → sequential placement | 17–22, 29 | MEDIUM (partly covered by existing tools) |
| G9 | Batch authority verification (generator/frame config, generate, monitor) | 23–28 | MEDIUM (verify only) |
| G10 | Integration tests + Playwright + independent certification | 61–64 | HIGH |

## 5. Frozen contracts that govern (from CODIRECTOR_FOUNDATION_CONTRACTS.md)
1. Conversation Core is the gateway — do not replace conversation/.
2. One orchestration pipeline — Domain → Knowledge → Router → Specialists → Creative Director → Synthesis → Approvals/Tools → Memory.
3. Creator authority — suggest/analyze/draft/prepare/compare/warn/execute-approved only. No silent canon, silent approve, overwrite without undo, costly generation without approval, autonomous deletion, or direction change without consent.
4. Truthful actions — never claim saved/generated/approved/uploaded/scheduled/completed until success.
5. Project isolation — no cross-project facts/assets/plans/jobs.
6. Specialist discipline — specialists return structured analysis only.
9. Playwright disposable-project gate — no capability complete until autonomous Playwright passes against a brand-new disposable project.
