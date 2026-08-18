# Co-Director Full Production Orchestrator — Architecture Design

**Date:** 2026-08-18 — supersedes no prior doc; additive milestone over the frozen Foundation Contracts.
**Governing laws:** CODIRECTOR_FOUNDATION_CONTRACTS.md (frozen) + mission parts 1–64.

## 0. Principles

1. Conversation Core remains the gateway (frozen law #1). No second agent framework (mission part 59).
2. Adept UI state remains production truth; Co-Director orchestrates via the existing registry/services (mission: reuse, not rebuild).
3. User creative intent is authoritative; CD intelligence enhances presentation, never continuity truth (mission parts 13–16, 52).
4. Truthful actions: every claim backed by recorded state (frozen law #4, mission part 53).
5. Project isolation (frozen law #5, mission part 57).
6. Bounded context: snapshots and memory are compact projections, not dumps (mission parts 55–56).
7. Playwright disposable-project gate for new capabilities (frozen law #9).

## 1. Capability reuse map

See `01-CAPABILITY_REUSE_MAP.md` (verified inventory: 499-tool registry, chat/SSE core, executive jobs, w46 timeline, spatial/ERS, scene creator shared engine, library, vision approvals, prompt intelligence, m211/m212 memory).

## 2. G1 — Production State Snapshot (mission parts 1, 55)

New module `studio-api/app/codirector/production_state/snapshot.py`:

`build_production_snapshot(db, project_id, scene_id=None) -> dict` returning compact state:
```json
{
  "project": {"id", "name"},
  "scene": {"id", "name", "index"} | null,
  "spatialMap": {"hasMap", "savedVersion", "currentVersion", "dirty", "cameras": [{"id","label","position","rotation"}]},
  "ers": {"sheetId", "name", "status", "updatedAt", "directionCount", "hasReference"} | null,
  "candidates": [{"assetId","tag","camera","variant","kind","approved","inLibrary","createdAt"}],  // bounded 12
  "library": {"assetCount", "recentApproved": [ids]} ,
  "timeline": {"revision", "clips": [{"id","kind","start","duration","assetId","label"}], "promptSegments": [{"id","start","duration","textPreview"}], "batches": [{"id","label","order","status","generatorId","frameSize","duration"}]},
  "jobs": {"active": [{"id","kind","status"}], "recentCompleted": [...]},  // bounded 8
  "events": [{"type","summary","actor","at"}],  // recent 10
  "asOf": "iso"
}
```
- Read from authoritative stores only (w46 store, spatial_map_documents, ERS store, assets, jobs, production_events). No new copies.
- **Injection:** appended to chat context in `codirector/service.py build_request` after the wiki block, as `PROJECT PRODUCTION STATE` section, rendered by `render_production_snapshot_block()` (bounded ≈ 2000 chars; empty when no project).
- **Tool:** read tool `project.production_snapshot` (same builder) + REST `GET /api/codirector/projects/{id}/production-snapshot`.

## 3. G2 — Production Event Stream (mission parts 2, 27, 39–42)

Migration m034 → table `production_events`:
```sql
id VARCHAR(36) PK, project_id FK, scene_id VARCHAR(64) NULL,
event_type VARCHAR(80), actor VARCHAR(16) ('user'|'codirector'|'system'),
actor_detail VARCHAR(64), subject_kind VARCHAR(32), subject_id VARCHAR(64),
summary VARCHAR(400), payload_json TEXT, created_at DATETIME
```
Module `studio-api/app/production_events.py`:
- `record_production_event(db, *, project_id, event_type, scene_id=None, actor='system', actor_detail='', subject_kind='', subject_id='', summary='', payload=None)`
- `list_production_events(db, project_id, scene_id=None, limit=50, event_types=None)`
- `recent_production_events_block(db, project_id, limit=8)` → bounded prompt text.

Event vocabulary (mission part 2): `spatial_map.saved|updated`, `camera.created|updated|deleted`, `ers.generation_started|completed|failed`, `ers.sheet_updated`, `candidate.generated|selected|approved|rejected|sent_to_library`, `library.asset_approved|unapproved`, `scene_creator.generation_started|completed|failed`, `timeline.clip_added|removed|updated`, `timeline.prompt_added|updated`, `timeline.batch_created|updated|deleted`, `timeline.generation_started|completed|failed`, `job.started|completed|failed`.

Emit hooks (minimal, in existing service functions — both manual REST and CD tool paths converge there):
- Timeline: `director_timeline_w46/service.py` (put_master → clip-level diff summary events; add_batch; generation submit/complete in orchestrator/adapters callback), router-level fallback in `routers/api.py` batch/clip endpoints if needed.
- Spatial: `spatial_map` save + camera ops (module functions where the save gate lives).
- ERS: `codirector/capabilities/handlers/ers_generate.py` (started), queue_worker imagegen commit hook (completed/failed) + `environment_reference_sheet` compose/export.
- Scene Creator: `capabilities/handlers/scene_generate.py` (started), queue_worker commit (completed) + multi_shot select/send.
- Library: project_library ingest + approval functions.
- Jobs: `executive/store.py` + `queue_worker.py` lifecycle points.
Every hook is best-effort (try/except, never breaks the operation).

## 4. G3 — Production Memory (mission parts 3, 4, 54, 56)

No new store: projection over existing authoritative stores.
Module `codirector/production_state/memory.py`:
- `build_production_memory(db, project_id, scene_id=None)` → structured records: recent CD tool actions (codirector_tool_invocations: tool_id, status, summary args/results), production events (recent), job completions (production_jobs / jobs), candidate selections (assets tags + multi_shot_candidates), timeline state deltas.
- `production_memory_block(db, project_id, limit=10)` → compact prompt lines: "CD actions", "Production events", "Jobs", "Decisions" (bounded ≈ 1200 chars).
- `resolve_reference(db, project_id, ref)` → candidate/asset resolution:
  - parse `C<n>-<V>` camera-variant tags (scene_creator/mini/multi_shot tags),
  - ordinal refs ("the first C1 shot", "shot frame 1") against ordered candidate lists,
  - "the close-up"/"the wide" via camera labels/positions,
  - returns `{matched, candidates:[{assetId,tag,label}], ambiguous}`.
- Injected into chat context after the production snapshot (bounded).
- Tool: read tool `production.memory` + `production.resolve_reference`; REST endpoints under /api/codirector/projects/{id}/production-memory.

## 5. G4 — Candidate awareness (mission parts 9, 11, 29, 30)

- Read tools: `candidate.list` (project/scene candidates: assets with candidate tags + multi_shot_candidates joined), `candidate.resolve` (uses memory.resolve_reference).
- Candidates enter the snapshot (G1) and memory (G4).
- Candidate approval: reuse existing vision/approval + library ingest paths (no shadow store).

## 6. G6 — Execution authority (mission parts 30, 35, 36; frozen law #3)

Add a **project execution-authority setting** (values `proposals` (default, unchanged) | `direct`):
- Stored in `projects.settings_json["codirector"]["executionAuthority"]`; REST `GET/PUT /api/codirector/projects/{id}/execution-authority`; UI toggle in CoDirector header (Advanced).
- When `direct`: proposals whose tool is on the **routine reversible allowlist** and that are created inside a chat turn (`request_id` present) are **auto-approved immediately** through the existing proposal machinery (preview → version pin → apply → receipt) — the user's explicit instruction in the turn is the authorization, recorded as `autoApproved=true` on the invocation/proposal audit trail.
- Routine allowlist (REST-returned, auditable): timeline.propose_add_image_clip, timeline.propose_add_prompt_segment, timeline.propose_add_batch, timeline.propose_add_camera, timeline.propose_update_camera, timeline.propose_retake (retake keeps approval: costly generation — NOT in allowlist), timeline.update_settings, timeline.set_playhead, spatial.create_camera, spatial.update_camera, spatial.place_character, spatial.place_prop, library ingest tools (editor.place_asset), candidate.select (image_pipeline.select_candidate), production_plan.create_draft (already audited).
- NEVER auto-approved: deletes (timeline.remove_item, batch delete), replaces of approved assets, generation triggers (propose_generate_scene, propose_batch_timeline, propose_shot_generate...), voice/lipsync, cloud-paid ops, bible/canon mutations, vision corrections. Those always keep the proposal card.
- New composite mutation tool `timeline.build_shot`: resolve asset/candidate → ensure library durability → compute start (explicit or end-of-timeline) → add image clip with exact duration → optionally add matched prompt segment. Auto-approvable in `direct` mode; proposal card otherwise.

## 7. G7 — Prompt refinement & provenance (mission parts 13–16, 19, 20, 52)

- Extend `TimelinePromptSegment` with optional `userDirection`, `productionPrompt`, `dialogue` fields (migration adds JSON columns to the master document? No — master is a JSON document; just extend the Pydantic model with defaults, no DB migration).
- `timeline.propose_add_prompt_segment` accepts them; when absent, the execution layer compiles via `prompt_intelligence` (REUSE `prompt.enhance` engine) producing `productionPrompt` while storing the original as `userDirection`; dialogue passes through verbatim.
- `execution/result_context.py`-style provenance: keep userDirection in the segment and in the execution snapshot compiledPrompts.
- Generation paths already preserve prompt provenance (`asset.prompt_meta_json`); verify and record `userDirection` where the request carries it.

## 8. G5 — Result presentation in chat (mission parts 10, 28, 31, 50)

Frontend `studio-web`:
- New `components/CoDirector/CoDirectorMediaCardGrid.tsx`: renders a responsive grid of asset thumbnails from `result_asset_ids` (completion/execution_status/deliverable events) via `api.assetUrl(id)`, each card data-testid + data-asset-id, click opens the asset in the Library/panel.
- `CoDirectorMessage.tsx`: render grid under ExecutionSummaryCard when result_asset_ids present and non-empty; also render when `tool_completed`/deliverable events carry media.
- Keep markdown whitelist unchanged (no raw <img> from model text — cards only come from structured events).

## 9. Testing & certification (mission parts 61–64)

- Backend pytest (new `studio-api/tests/test_codirector_production_orchestrator.py`): snapshot shape + bounds; event recording on timeline/spatial/ERS/scene/library operations (with real service functions on the test DB); memory projection + reference resolution (C1-A, ordinal, camera label); execution-authority auto-approval (allowlist + receipts + non-allowlist still proposes); prompt segment userDirection/productionPrompt/dialogue; sequential placement math (no float drift).
- Playwright `tests/e2e/codirector-production/`: brand-new disposable project (frozen law #9) or the Schnick project when the scenario requires its spatial/ERS state — scenarios A–G + manual-change tests (39–42) with real chat interactions and API/DB state verification.
- Independent certifier subagent runs the conversational scenario and verifies state through API/DB (mission part 62).
- Evidence: docs/release-gate/codirector-production-orchestrator/ with screenshots, cards, timeline before/after, batch config, generation proof, memory reload proof.

## 10. Order of implementation

1. m034 production_events + production_events.py + hooks (timeline, spatial, ERS, scene, library, jobs).
2. production_state/snapshot.py + injection + tool + endpoint.
3. production_state/memory.py + reference resolution + tools + injection.
4. candidate.list/resolve tools; timeline.build_shot; execution-authority setting + auto-approval.
5. Prompt segment fields + refinement wiring.
6. Frontend media cards + authority toggle.
7. pytest integration suite.
8. Playwright E2E (Schnick A–G, 39–42).
9. Independent certification + evidence report + GO/NO-GO.
