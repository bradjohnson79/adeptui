# Co-Director Operational Integrity Audit — State & Context Isolation

**Milestone:** Co-Director Operational Integrity Audit
**Date:** 2026-08-07
**Status:** AUDIT COMPLETE — repairs tracked in milestone phases c2/c3
**Repo:** `C:\AdeptFilmWorks\AIVideoStudio`
**Audit scope:** READ-ONLY audit of how Co-Director resolves and maintains Project/Scene/Character/Batch/Workspace operational context, and every cross-project / stale-context leak risk.
**Audit mode:** READ-ONLY. No files were modified; no non-readonly commands were run during the source investigation.
**Governing instrument:** This document is the governing audit for project/scene/workspace context isolation under Build Law 30. Supersedes any prior informal isolation notes for this milestone. Routing-pipeline defects are governed by the companion `CODIRECTOR_ROUTING_AUDIT.md`.

---

## 1. Executive Summary

Backend conversation storage and the core tool-registry path are strongly project-isolated. `codirector_conversations.project_id` is the primary key (`db.py:140`), and the core tool path (`/projects/{project_id}/tools/*` → `ToolContext` → handlers) re-derives `project_id` from the URL on every call and re-validates via `_require_project` (`execution.py:86`). Scenes, characters, plans, minimax h3, spatial m411, generation lineage, and director timeline all enforce `entity.project_id == ctx.project_id`.

**However, several service-layer handlers in `voice_performance` and the `m29`/`m214` REST routers look up entities by bare ID without a `project_id` filter**, creating real cross-project leak paths when the model emits a stale entity ID. These routers are standalone REST endpoints that either trust client-supplied `projectId` in the body (and then discard it) or ignore it entirely; they are not part of the `ToolExecutionService` `ToolContext` path, so the authoritative `ToolContext.project_id` guarantee does not apply to them.

The audit classifies leak risks into three severities:

- **HIGH (3):** `voice_performance` plan/segment lookups ignore `project_id`; `m29` image approve/reject/publish-reference discard `projectId`; `m29` timeline proposal approve/reject/apply derive `project_id` from the proposal itself.
- **MEDIUM (2):** `m29` control plan / render manifest / frame-bind lookups ignore `projectId`; `m214` storyteller / sound / attachment approve/confirm endpoints ignore `projectId`.
- **LOW (3):** `scene_id` is model-supplied and only re-validated per-handler; compiled context carries entity IDs from conversation history (stale-within-project); deep-link `projectId` vs conversation `project_id` mismatch silently rebinds context.

The single most direct leak is RISK 1: `voice_performance.generate_segments`/`retry_segment` operate on a plan/segment by bare ID across all projects — the "Dreamweaver scene ID written into another project" class of leak. Repairs for all eight risks are mapped to milestone phase c3 in §5.

## 2. Context Resolution Flow (Frontend → API → Tool Handler)

### 2.1 Frontend binds workspace context

`studio-web/src/components/CoDirector/CoDirectorSession.tsx`
- `useBindCoDirectorWorkspace(bindings)` (`CoDirectorSession.tsx:3180`) calls `bindWorkspace(bindings)` in an effect keyed on stable binding fields (`projectId`, `sceneId`, `workspaceTab`, …).
- `bindWorkspace` (`CoDirectorSession.tsx:1082`) stores bindings into `bindingsRef.current` and `uiContext`. **On project change it calls `cancelInFlightForProjectSwitch()`** (`:1085`) to abort any in-flight request for the old project.
- `syncProjectIdentity` (`:603`) updates `bindingsRef.current.projectId`/`projectName` and persists a "last bound project" suggestion to `localStorage`.

`studio-web/src/pages/ProjectEditor.tsx`
- `CoDirectorProvider value={{ projectId: project.id, projectName: project.name, sceneId: selectedScene, ... }}` (`:635`) — authoritative `project.id` from the active project. (The `value={{...}}` prop begins at `:636`; the `<CoDirectorProvider` element opens at `:635`.)
- `ProjectCoDirectorBridge` calls `useBindCoDirectorWorkspace({ projectId: project.id, sceneId, workspaceTab, ... })` (`:853`).

`studio-web/src/pages/CoDirectorPage.tsx`
- `const projectId = params.get("projectId")` (`:10`) from the URL, then `bindWorkspace({ projectId, ... })` (`:52`). The URL `projectId` is the source of truth for the full-screen page.

### 2.2 Frontend sends context with each message

`studio-web/src/components/CoDirector/CoDirectorSession.tsx`
- `send` (`:2177`) captures `const projectId = bindingsRef.current.projectId` **at send time** and passes it into `performSend`. The request body to `/api/codirector/chat` (or `/chat/stream`) carries `projectId` + `sceneId`.

### 2.3 API router derives authoritative `project_id`

`studio-api/app/routers/codirector.py`
- `/chat` and `/chat/stream` take `project_id` and `scene_id` from the **request body**.
- Tool endpoints `/projects/{project_id}/tools/read|audited|proposals` take `project_id` from the **URL path** (authoritative), and `sceneId`/`arguments` from the body.

### 2.4 Service layer threads context into the model + tools

`studio-api/app/codirector/service.py`
- `_prepare_chat_request` / `_interpret_reply` receive `project_id` (from path) and `scene_id` (from chat body) and pass them to `_run_read_tool` / `_propose_tool_call`.
- `_safe_append_tool_event(db, project_id, ...)` (`:597`, `:783`) and `append_assistant_completion(db, project_id, ...)` (`:2246`) log events against the path-derived `project_id`.

`studio-api/app/codirector/tools/execution.py`
- `ToolContext(db=db, project_id=project_id, scene_id=scene_id, request_id=request_id, capabilities=...)` is constructed with `project_id` from the path (`:301`, `:504`, `:713`).
- `_require_project(db, project_id, ...)` (`:86`) validates the project exists and is unlocked before any tool runs.
- `execute_approved_proposal` (`:697`) derives `ctx.project_id` from `proposal.project_id` (DB-stored), and `scene_id` from `payload.arguments.get("sceneId")`.

### 2.5 Tool handlers resolve sub-entities

`studio-api/app/codirector/tools/handlers/*.py`
- Handlers receive `ctx.project_id` (authoritative) and pull `sceneId`/`characterId`/`batchId`/`planId` from `args` (model-supplied).
- Most handlers re-validate those IDs against `ctx.project_id` via the underlying services (see §3).

### 2.6 Authoritative source of `projectId` / `sceneId` for tool execution

| Context field | Authoritative source | Notes |
|---|---|---|
| `project_id` (tool execution) | **URL path** on `/projects/{project_id}/tools/*` → `ToolContext.project_id` | `execution.py:86` `_require_project` validates it. For approved proposals, it comes from `proposal.project_id` (DB row) — `execution.py:697`. |
| `project_id` (chat) | **Request body** `projectId` on `/chat` (`routers/codirector.py`), which the frontend sources from `bindingsRef.current.projectId` (`CoDirectorSession.tsx:2177`). | Body-derived, but the frontend binds it from the active project editor / URL `projectId`. |
| `scene_id` | **Model arguments** (`args.get("sceneId")`) with fallback to `ctx.scene_id` (the chat request's `scene_id`). | e.g. `director_timeline_tools.py:44` `_scene_id`. Not authoritative server-side unless re-validated by the service. |
| `characterId`, `batchId`, `planId`, `versionId`, etc. | **Model arguments** (`args.get(...)`) | Stale-risk unless the service re-checks ownership against `ctx.project_id`. |

**Key invariant:** `ToolContext.project_id` is the single authoritative project scope. Sub-entity IDs from the model are only safe if the downstream service enforces `entity.project_id == ctx.project_id`.

## 3. Isolation Strengths

The following layers are correctly isolated and should be preserved during c3 repairs:

1. **Conversation persistence is project-scoped by PK.** `codirector_conversations.project_id` is the primary key (`db.py:140`); `codirector_conversation_events.project_id` is indexed (`db.py:163`); `append_events`/`fold_events` are keyed by `project_id` (`conversation_events.py:147`, `:279`).
2. **The core tool-registry path is authoritative and well-isolated.** `/projects/{project_id}/tools/*` → `ToolContext` → handlers re-derives `project_id` from the URL on every call; `_require_project` (`execution.py:86`) re-validates. Sub-entity services enforce `entity.project_id == ctx.project_id`: scenes (`services/scene_service.py:118`), characters (`character_identity/service.py:197`), plans (`plans/store.py:53`), minimax h3 (`minimax_h3/service.py:421`), spatial m411 (`spatial_m411.py:86`), generation tools (`generation_tools/lineage.py:100`), and director timeline (`director_timeline_w46/store.py:76`).
3. **Approved-proposal replay uses the DB-stored project.** `execute_approved_proposal` (`execution.py:697`) uses `proposal.project_id` (DB row), not the model's args, so a stale model arg cannot redirect a mutation to another project on approval.
4. **Frontend invalidates in-flight requests on project switch.** `cancelInFlightForProjectSwitch()` (`CoDirectorSession.tsx:589–601`) aborts the active `AbortController`, calls `/api/codirector/cancel`, clears `activeRequestIdRef`, sets `setBusy(false)`, and clears tool/intelligence activity.
5. **Frontend messages are reset on project change.** On `uiContext.projectId` change: `setMessages([WELCOME_ASSISTANT])` synchronously, then async load `codirectorGetConversation(projectId)` (`CoDirectorSession.tsx:882–964`).
6. **Frontend `sessionStorage` keys are project-scoped.** Keys are `adept_codirector_messages_<projectId>` (`types.ts:322`); `loadPersistedMessages`/`persistMessages` key by `projectId` (`types.ts:383`, `:403`). No cross-project key reuse.
7. **Frontend bindings overwrite cleanly.** `bindWorkspace` (`CoDirectorSession.tsx:1082`) overwrites `bindingsRef.current` and `uiContext` with the new project.
8. **No server-side compiled-context cache survives a switch.** Context is recompiled per chat turn from DB, so there is no stale compiled cache to leak across projects.

### 3.1 Invalidation that exists today on project switch

| Layer | Invalidation mechanism | Citation |
|---|---|---|
| Frontend in-flight requests | `cancelInFlightForProjectSwitch()` aborts the active `AbortController`, calls `/api/codirector/cancel`, clears `activeRequestIdRef`, `setBusy(false)`, clears tool/intelligence activity. | `CoDirectorSession.tsx:589–601` |
| Frontend messages | On `uiContext.projectId` change: `setMessages([WELCOME_ASSISTANT])` synchronously, then async load `codirectorGetConversation(projectId)`. | `CoDirectorSession.tsx:882–964` |
| Frontend `sessionStorage` | Keys are project-scoped: `adept_codirector_messages_<projectId>` (`types.ts:322`); `loadPersistedMessages`/`persistMessages` key by `projectId` (`types.ts:383`, `:403`). No cross-project key reuse. | `types.ts:322,383,403` |
| Frontend bindings | `bindWorkspace` overwrites `bindingsRef.current` and `uiContext` with the new project. | `CoDirectorSession.tsx:1082` |
| Backend conversation | `codirector_conversations.project_id` is PK (`db.py:140`); `codirector_conversation_events.project_id` is indexed (`db.py:163`); `append_events`/`fold_events` are keyed by `project_id`. | `conversation_events.py:147,279` |
| Backend tool context | `ToolContext.project_id` is re-derived from the URL path on every tool call; `_require_project` re-validates. | `execution.py:86,301,504,713` |
| Backend proposals | `execute_approved_proposal` uses `proposal.project_id` (DB-stored), not the model's args. | `execution.py:697` |

**What is NOT invalidated:** There is no server-side cache of compiled context or entity IDs that survives a switch (context is recompiled per chat turn from DB), but the **model's own conversation history** (within the same project) retains old entity IDs that can resurface (RISK 7).

## 4. Leak Defects

Eight leak risks are catalogued below by severity. Each states the **root cause**, the impact, and the controlling file:line citations.

### 4.1 HIGH severity

#### RISK 1 — `voice_performance` plan/segment lookups ignore `project_id`

**Root cause:** `studio-api/app/voice_performance/service.py` resolves voice-performance plans and segments by bare ID and never compares the resolved entity's `project_id` to the caller's `ctx.project_id`. `generate_segments(db, plan_id, ...)` (`:204`) loads `PerformancePlanRow` by `plan_id` only; `_locked_project_guard(db, row.project_id, request)` (`:217`) checks whether *that plan's* project is locked — **it never compares `row.project_id` to the caller's `ctx.project_id`**. `retry_segment(db, segment_id, ...)` (`:345`) queries `PerformancePlanRow` across **all projects** (`db.query(PerformancePlanRow).order_by(...).limit(200).all()`) to find a segment by `segment_id`, then operates on that plan.

**Impact:** If the model emits a `plan_id`/`segment_id` from Project B while the creator is in Project A, the tool mutates Project B's voice performance data. This is the most direct "Dreamweaver scene ID written into another project" class of leak — a direct cross-project write leak.

#### RISK 2 — `m29` image approve/reject/publish-reference ignore `projectId`

**Root cause:** `studio-api/app/codirector/m29/api.py:261–285` — `/image/{version_id}/approve|reject|publish-reference` accept a `VersionActionBody` that **contains** `projectId` and `sceneId` (`:81–84`), but the handlers call `ImageService.approve(db, version_id, actor=...)` **without passing `projectId`** (`api.py:265`, `:274`, `:283`). Downstream, `ImageService.approve`/`reject`/`publish_reference` (`m29/image/service.py:136–156`) call `set_asset_status(db, version_id, status)` (`m29/store.py:113–126`), which updates by `version_id` only — no `project_id` filter in the UPDATE or the subsequent `get_asset_version`.

**Impact:** A stale `version_id` from another project is approved/rejected/published in that other project. Cross-project state mutation, because the body's `projectId` is accepted but discarded and the store query has no project filter.

#### RISK 3 — `m29` timeline proposal approve/reject/apply ignore `projectId`

**Root cause:** `studio-api/app/codirector/m29/api.py:539–565` routes to `m29/timeline/service.py:99–246`. `TimelineService.approve(db, proposal_id)` (`:99`) loads the proposal by `proposal_id` only and sets status. `apply` (`:133`) derives `project_id = prop["projectId"]` **from the proposal itself** (`:141`) and uses it to create a Bible handoff in *that* project. The caller's `projectId` is never compared to the proposal's `projectId`.

**Impact:** A stale `proposal_id` from Project B is approved/applied, creating a Bible handoff in Project B while the creator is in Project A. Cross-project write leak via proposal self-derivation.

### 4.2 MEDIUM severity

#### RISK 4 — `m29` control plan / render manifest / frame-bind lookups ignore `projectId`

**Root cause:** `studio-api/app/codirector/m29/api.py` exposes several endpoints that take only the entity ID from the URL path and never filter by `project_id`:
- `GET /control/{plan_id}` (`:659`) → `ControlService.get_plan(db, plan_id)` — no `project_id`.
- `POST /control/plans/{plan_id}/resume` (`:668`) — same pattern.
- `GET /render/{manifest_id}` (`:637`) → `RenderService.get_manifest(db, manifest_id)` — no `project_id`.
- `POST /frames/{frame_id}/bind` (`:310`) → `FramesService.bind_to_shot(db, frame_id, body.shotId)` — no `project_id`.

**Impact:** Read-side cross-project disclosure (control plan contents, render manifest contents) and a write-side cross-project bind (frame → shot in another project). The bind is the more severe of the two because it mutates another project's shot/frame association.

#### RISK 5 — `m214` approve/confirm endpoints ignore `projectId`

**Root cause:** `studio-api/app/codirector/m214/api.py` exposes approve/confirm endpoints that take only the entity ID from the URL:
- `POST /storyteller/handoff/{handoff_id}/approve` (`:269`) → `storyteller.approve_handoff(db, handoff_id)` — `m214/storyteller.py:127` updates by `handoff_id` only.
- `POST /sound/concept/{concept_id}/approve` (`:290`) → `sound_producer.approve_sonic_concept(db, concept_id)` — same pattern.
- `POST /attachments/{interpretation_id}/confirm` (`:225`) → `attachments.confirm_interpretation(db, interpretation_id, ...)` — no `project_id`.

**Impact:** Stale `handoff_id`/`concept_id`/`interpretation_id` from another project are approved/confirmed cross-project. Cross-project state mutation via bare-ID approve/confirm.

### 4.3 LOW severity

#### RISK 6 — `scene_id` is model-supplied and only re-validated per-handler

**Root cause:** `scene_id` is taken from model arguments with fallback to `ctx.scene_id`, and safety depends on each handler remembering to re-validate against `ctx.project_id`. `director_timeline_tools.py:44` `_scene_id` prefers `args.get("sceneId")` over `ctx.scene_id`. Safety currently holds because `director_timeline_w46/store.py:73` `get_scene` filters `Scene.project_id == project_id AND Scene.id == scene_id` (`:76`); `scenes.py:38` `_require_scene` → `SceneService.get(ctx.db, ctx.project_id, scene_id)` enforces `scene.project_id != project_id` (`services/scene_service.py:118`); `posecraft.py:473` `apply_send_to_storyboard` returns a package carrying `args.get("sceneId")` as metadata, leaving the downstream storyboard ingest to re-validate (not audited here).

**Status:** Currently safe because services re-validate, but it is **defense-in-depth-fragile**: any new handler that forgets the `ctx.project_id` check inherits a leak. There is no central "entity ownership" enforcement for model-supplied IDs.

#### RISK 7 — Compiled context carries entity IDs from conversation history (stale-within-project)

**Root cause:** `studio-api/app/codirector/intelligence/context_compiler.py:160` `compile(db, project_id, user_message, scene_id, ...)` pulls project summary, scene context, capabilities, and recent messages — all **project-scoped** (`ContextRetrievalService.project_summary(db, project_id)`, `scene_context(db, project_id, scene_id)`). Recent messages come from `fold_events(db, project_id)` (`conversation_events.py:147`), which is project-scoped.

**Status:** Not a *cross-project* leak. But within a single project, historical messages may reference entity IDs that were later deleted (stale-within-project). These can be echoed back by the model into tool calls; safety again depends on per-handler re-validation (RISK 6). The context compiler does not annotate or strip IDs for entities that no longer exist in the current project before sending to specialists.

#### RISK 8 — Deep-link `projectId` vs conversation `project_id` mismatch

**Root cause:** `studio-web/src/pages/CoDirectorPage.tsx:10–52` — the URL `projectId` drives `bindWorkspace`. `CoDirectorSession.tsx:882` reacts to `uiContext.projectId` change: it synchronously clears messages (`setMessages([WELCOME_ASSISTANT])`) then loads `api.codirectorGetConversation(projectId)`. Because `codirector_conversations.project_id` is the **primary key** (`db.py:140`), each project has exactly one conversation; a URL `projectId` mismatch simply loads a different conversation.

**Status:** No write leak — but a creator who manually edits the URL to another project's ID silently switches Co-Director's entire context with no confirmation. There is no guard comparing the URL `projectId` to the last-bound suggestion (`persistLastBoundProjectSuggestion`).

## 5. Gaps (consolidated)

1. **No `project_id` ownership check in `voice_performance` plan/segment lookups** (RISK 1). `generate_segments`/`retry_segment` should `SELECT ... WHERE id = ? AND project_id = ?` and 404 on mismatch. This is the most direct "Dreamweaver scene ID written into another project" class of leak.
2. **`m29` action endpoints accept `projectId` in the body but discard it** (RISKS 2–4). `/image/{version_id}/*`, `/timeline/{proposal_id}/*`, `/control/{plan_id}`, `/render/{manifest_id}`, `/frames/{frame_id}/bind` should either take `project_id` from the URL path (like the tool registry does) or assert `entity.project_id == body.projectId` before mutating.
3. **`m214` approve/confirm endpoints take only the entity ID from the URL** (RISK 5). `/storyteller/handoff/{handoff_id}/approve`, `/sound/concept/{concept_id}/approve`, `/attachments/{interpretation_id}/confirm` need a `project_id` ownership guard.
4. **No central "entity ownership" enforcement for model-supplied IDs.** Isolation currently relies on each handler/service remembering to filter by `project_id`. A shared helper (e.g. `require_scene_owned(ctx, scene_id)`, `require_plan_owned(ctx, plan_id)`) used uniformly would close RISK 6's defense-in-depth fragility.
5. **No confirmation on deep-link project switch.** `CoDirectorPage.tsx:10` silently rebinds Co-Director to whatever `projectId` is in the URL; a mistyped/old link switches context with no guard. Consider confirming when the URL project differs from the last-bound suggestion (`persistLastBoundProjectSuggestion`).
6. **Stale-within-project entity IDs in compiled history** (RISK 7). Recent-message context can resurface deleted scene/character/batch IDs. The context compiler could annotate or strip IDs for entities that no longer exist in the current project before sending to specialists.
7. **`m29`/`m214` routers are not part of the `ToolExecutionService` `ToolContext` path.** They are standalone REST routers that trust client-supplied `projectId` (or ignore it). If Co-Director tools ever route through them, the authoritative `ToolContext.project_id` guarantee does not apply. Worth confirming whether any tool handler proxies to these routers vs. calling services directly with `ctx.project_id`.

---

## 6. Repair Recommendations (mapped to milestone phase c3)

Phase c3 owns state/context isolation integrity. Repairs are ordered by severity, then dependency.

| # | Risk | Severity | Repair | Phase c3 sub-step |
|---|---|---|---|---|
| R1 | RISK 1 | HIGH | `voice_performance.generate_segments`/`retry_segment` must `SELECT ... WHERE id = ? AND project_id = ?` and 404 on mismatch; pass the caller's `project_id` into both functions and compare `row.project_id` to it before any mutation. | c3.1 |
| R2 | RISK 2 | HIGH | `m29` image approve/reject/publish-reference must either take `project_id` from the URL path or assert `entity.project_id == body.projectId` before calling `ImageService`; thread `project_id` into `set_asset_status` (`m29/store.py:113`) as a WHERE filter. | c3.2 |
| R3 | RISK 3 | HIGH | `m29` timeline approve/reject/apply must compare the caller's `projectId` to `prop["projectId"]` before mutating; reject with `PROPOSAL_PROJECT_MISMATCH` on mismatch. Do not derive the acting `project_id` from the proposal alone. | c3.3 |
| R4 | RISK 4 | MEDIUM | `m29` control/render/frame-bind endpoints must take `project_id` from the URL path or assert ownership; `FramesService.bind_to_shot` must verify the frame and target shot belong to the same `project_id`. | c3.4 |
| R5 | RISK 5 | MEDIUM | `m214` storyteller/sound/attachment approve/confirm endpoints must take `project_id` from the URL path or assert `entity.project_id == body.projectId` before mutating. | c3.5 |
| R6 | RISK 6 | LOW | Introduce shared `require_*_owned(ctx, entity_id)` helpers and mandate their use in every handler that accepts a model-supplied sub-entity ID; add a lint/test guard that fails when a handler accepts an entity ID without an ownership check. | c3.6 |
| R7 | RISK 7 | LOW | `context_compiler.compile` must annotate or strip IDs for entities that no longer exist in the current project before sending to specialists, so stale-within-project IDs cannot be echoed into tool calls. | c3.7 |
| R8 | RISK 8 | LOW | `CoDirectorPage.tsx` must confirm when the URL `projectId` differs from the last-bound suggestion before rebinding; surface a "switch project?" guard rather than silently rebinding. | c3.8 |
| R9 | Gap 7 | — | Confirm whether any Co-Director tool handler proxies to `m29`/`m214` routers vs. calling services directly with `ctx.project_id`; if any proxy exists, route it through `ToolContext` instead. | c3.9 |

**Phase c3 exit criteria:** all HIGH risks (R1–R3) have a cross-project isolation regression test that asserts a stale entity ID from Project B cannot mutate Project A; the shared `require_*_owned` helpers (R6) are adopted by every handler accepting a model-supplied sub-entity ID; a Playwright creator workflow verifies a project switch fully invalidates in-flight state and cannot leak across projects (Build Law 14, Build Law 31).

---

## 7. Verification log

The following source-report citations were spot-verified against the current working tree on 2026-08-07. At least 8 were checked; corrections are recorded where drift was found.

| # | Citation (as in source report) | Verified at | Result | Correction |
|---|---|---|---|---|
| V1 | `studio-web/src/components/CoDirector/CoDirectorSession.tsx:3180` (`useBindCoDirectorWorkspace`) | `CoDirectorSession.tsx:3180` | Match | — |
| V2 | `CoDirectorSession.tsx:1082` (`bindWorkspace`), `:1085` (`cancelInFlightForProjectSwitch`) | `:1082`, `:1085` | Match | — |
| V3 | `CoDirectorSession.tsx:2177` (`send`) | `:2177` | Match | — |
| V4 | `studio-web/src/pages/ProjectEditor.tsx:635` (`CoDirectorProvider value={{...}}`) | `:635` (`<CoDirectorProvider`), `:636` (`value={{`) | Minor drift | The `<CoDirectorProvider` element opens at `:635`; the `value={{...}}` prop begins at `:636`. Cited as `:635` with a clarifying note in §2.1. |
| V5 | `studio-api/app/voice_performance/service.py:204` (`generate_segments`), `:217` (`_locked_project_guard`) | `:204`, `:217` | Match | Confirms the report's claim: `_locked_project_guard` checks the plan's own project, not the caller's `ctx.project_id`. |
| V6 | `voice_performance/service.py:345` (`retry_segment`) queries across all projects | `:345–349` | Match | Confirms `db.query(PerformancePlanRow)...limit(200).all()` has no `project_id` filter. |
| V7 | `studio-api/app/codirector/m29/api.py:261–285` (image approve/reject/publish-reference) | `:261`, `:270`, `:279` | Match | Confirms `ImageService.approve(db, version_id, actor=body.actor)` is called without `projectId` (`:265`, `:274`, `:283`). |
| V8 | `m29/image/service.py:136–156` (`approve`/`reject`/`publish_reference`) | `:136`, `:142`, `:148` | Match | — |
| V9 | `m29/store.py:113–126` (`set_asset_status`) | `:113` | Match | Confirms UPDATE by `version_id` only, no `project_id` filter. |
| V10 | `m29/timeline/service.py:99` (`TimelineService.approve`), `:133`/`:141` (`apply`, `project_id = prop["projectId"]`) | `:99`, `:133`, `:141` | Match | Confirms `project_id` is derived from the proposal itself. |
| V11 | `m29/api.py:637` (`GET /render/{manifest_id}`), `:659` (`GET /control/{plan_id}`), `:310` (`POST /frames/{frame_id}/bind`) | `:637`, `:659`, `:310` | Match | — |
| V12 | `studio-api/app/codirector/m214/api.py:269` (storyteller approve), `:290` (sound approve), `:225` (attachments confirm) | `:269`, `:290`, `:225` | Match | — |
| V13 | `studio-api/app/db.py:140` (`CoDirectorConversation` PK) | `db.py:140` | Match | — |
| V14 | `studio-api/app/services/scene_service.py:118` (`SceneService.get` enforces `scene.project_id != project_id`) | `services/scene_service.py:118` | Path drift | Source report cites `scene_service.py:118`; the actual path is `studio-api/app/services/scene_service.py:118` (the `services/` segment). Cited with the full path in §3 and §4.3. |
| V15 | `CoDirectorSession.tsx:589–601` (`cancelInFlightForProjectSwitch`), `:882–964` (project-change effect) | `:589`, `:882` | Match | — |

**Summary of corrections:** two citations carried minor drift. V4 (`ProjectEditor.tsx:635`) was a JSX-element-vs-prop line distinction; clarified in §2.1 that the element opens at `:635` and `value={{` begins at `:636`. V14 (`scene_service.py:118`) was a missing `services/` directory segment; the actual path is `studio-api/app/services/scene_service.py:118`, cited with the full path in §3 and §4.3. No findings were retracted; all eight risks and their citations stand.

---

## 8. Status

**Status:** AUDIT COMPLETE — repairs tracked in milestone phases c2/c3.

This document is the governing audit for Co-Director project/scene/workspace context isolation under Build Law 30. Isolation defects RISKS 1–8 are owned by milestone phase c3 (§6). Routing-pipeline defects are owned by milestone phase c2 and governed by the companion document `CODIRECTOR_ROUTING_AUDIT.md`. No isolation defect in this audit is certified repaired; certification requires the c3 exit criteria in §6 plus binary GO per Build Law 24, with cross-project isolation regression tests (Build Law 14) and a Playwright project-switch workflow (Build Law 31).





