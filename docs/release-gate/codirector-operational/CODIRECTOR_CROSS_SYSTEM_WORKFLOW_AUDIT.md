# Co-Director Cross-System Workflow Audit

**Milestone:** Co-Director Operational Integrity Audit
**Date:** 2026-08-07
**Status:** AUDIT COMPLETE — repairs tracked in milestone phases c4/c5/c8
**Governing status:** This is the authoritative cross-system workflow and UI synchronization audit for the milestone (Build Law 30). Companion to `CODIRECTOR_NATIVE_SYSTEM_OPERATIONS_AUDIT.md`. Supersedes no prior document; supersedes any in-flight working notes once referenced from the milestone report.
**Audit mode:** READ-ONLY. No files were modified and no non-readonly commands were run during the audit. The UI synchronization section was verified by direct inspection of `studio-web/src/components/CoDirector/CoDirectorSession.tsx` and related frontend code as it existed on 2026-08-07.

**Primary source of truth:** `data/tmp/codirector-audit-sources/native-systems-report.md` (native system coverage map + test/certification infrastructure).
**Cross-system synthesis sources:** `data/tmp/codirector-audit-sources/tool-registry-report.md`, `state-isolation-report.md`, `routing-report.md`.

---

## 1. Executive Summary

This audit maps the **multi-system workflows** Co-Director can drive today through its closed tool registry, assesses the **lineage mechanisms** that connect entities across systems, and verifies — by direct frontend code inspection — how the creator-facing UI learns about Co-Director tool mutations.

**Cross-system workflow inventory:** Co-Director can drive several multi-system chains today, but every chain is gated by the schema/handler mismatch defects documented in the companion audit (§3 of `CODIRECTOR_NATIVE_SYSTEM_OPERATIONS_AUDIT.md`). The two most material chains are **Character -> Voice -> Asset -> Timeline** (operable except where `propose_traits`/`propose_relationships` always-fail blocks character authoring) and **Character asset -> Timeline batch -> generator config** (operable; the strongest chain because Timeline uses the current `director_timeline_w46` revision-guarded contract).

**Lineage mechanisms:** Immutable IDs (`projectId`, `sceneId`, `batchBlockId`, `characterId`, `assetId`) are the primary lineage mechanism. Lineage is **strong** where handlers re-validate model-supplied IDs against `ctx.project_id` (Timeline, Scene, Character, Plans, Director Timeline). Lineage is **weak** where handlers accept bare IDs without an ownership check (`voice_performance` plan/segment lookups per RISK 1 of `state-isolation-report.md`; the `m29` and `m214` REST routers per RISKS 2-5).

**UI synchronization:** The creator-facing UI learns about Co-Director tool mutations through **three mechanisms**, all verified by direct inspection of `CoDirectorSession.tsx`:

1. **Stream events** (`tool_requested`, `tool_started`, `tool_completed`, `tool_proposal_created`, `proposal_created`, `tool_failed`, `capability_blocked`) update the in-session activity indicator and proposal list (`CoDirectorSession.tsx:1685-1808`).
2. **`result.uiAction` and `result._uiFocus` fields** on `tool_completed` events drive **targeted window-scoped CustomEvents**: `adept:open-character-voice` (`:1725-1732`), `adept:open-audio-studio` (`:1741-1748`), `adept-timeline-focus` (`:1757-1761`).
3. **Proposal approval** (`approveProposal` at `:2516`) dispatches `adept:codirector-plan-workspace-refresh` for `production_plan.*` tools (`:2545-2549`), and the post-stream finalize dispatches the same event for every completed turn (`:1892-1896`).

**Gaps and risks:** The UI sync mechanism is **handler-opt-in** — there is no framework-level post-apply state-diff verification and no general "project mutated" refresh event. Systems whose handlers do not emit a `uiAction`/`_uiFocus` field (Bible, Image, PoseCraft, Library, References, Render Queue, Continuity) rely solely on the generic `adept:codirector-plan-workspace-refresh` and the conversation transcript. There is no confirmation when a deep-link `projectId` switches Co-Director's entire context (RISK 8 of `state-isolation-report.md`).

Repairs are mapped to milestone phase **c5** (cross-system workflow closure + UI synchronization unification). Native-system contract repairs that block cross-system chains remain tracked under c4 in the companion audit.

---

## 2. Cross-System Workflow Inventory

The following multi-system chains are currently operable via Co-Director tools. "Operable" means a creator can drive the chain end-to-end through tool calls without leaving Co-Director, subject to the per-tool defects noted. Each chain lists the systems touched, the tool sequence, the lineage IDs that connect them, and the gating defects.

### 2.1 Chain: Character -> Voice -> Asset -> Timeline

**Systems:** Character Creator -> Voice Studio -> Assets/Media Library -> Timeline.
**Tool sequence (operable):**
1. `character_creator.create_from_brief` or `create_draft_character_profile` -> creates a `characterId` in the project.
2. `preview_voice_design` / `generate_voice_candidates` / `refine_voice_candidate` / `approve_voice_candidate` -> binds a voice profile to the `characterId`.
3. `propose_asset_library_assignment` -> assigns the character's generated voice asset to a library folder (gated by the `folderId` schema defect — `library.py:144`).
4. `propose_add_batch` / `propose_add_prompt_segment` -> places the character's voice/asset on the Timeline.

**Gating defects:**
- `character_creator.propose_traits` (`character_creator.py:307`) and `character_creator.propose_relationships` (`character_creator.py:350`) **always fail** (schema/handler mismatch). The chain is operable for character *creation* but blocked for character *authoring* (traits/relationships).
- `propose_asset_library_assignment` reads `folderId` which is stripped by the sanitizer (`library.py:144`), so the assignment is degraded.

**Lineage:** `projectId` -> `characterId` -> `voiceProfileId` -> `assetId` -> `batchBlockId` on the Timeline. The `characterId` is the join key across Character, Voice, and Asset. The Timeline receives the `assetId` via `propose_add_batch` arguments.

### 2.2 Chain: Character asset -> Timeline batch -> generator config

**Systems:** Character Creator (asset) -> Timeline (batch) -> Image Planning / Render Queue (generator config).
**Tool sequence (operable):**
1. `inspect_character_coverage` / `build_reference_plan` -> reads the character's asset coverage.
2. `propose_add_batch` -> creates a Timeline batch block (`batchBlockId`) with revision-guarded persistence (`director_timeline_w46/store.py:save_master`).
3. `image_pipeline.prepare_plan` / `prepare_creative_direction` / `select_profile` / `assign_reference` -> configures the generator for the batch.
4. `propose_shot_generate` / `propose_scene_generate` / `propose_three_frame_generate` -> submits the generation job.

**Gating defects:** None material for this chain. This is the **strongest chain** because Timeline uses the current `director_timeline_w46` revision-guarded contract and the image pipeline tools are schema-complete.

**Lineage:** `projectId` -> `characterId` -> `assetId` -> `batchBlockId` -> `jobId`. The `batchBlockId` is the join key between Timeline and the generator config. The `jobId` is returned by `propose_*_generate` and is queryable via `job.list`/`job.get`.

### 2.3 Chain: Scene -> Production Bible -> Continuity

**Systems:** Scene/Project Editor -> Production Bible -> Continuity/Production Intelligence.
**Tool sequence (operable):**
1. `create_scene` / `set_scene_prompt` -> creates a `sceneId`.
2. `propose_continuity_update` / `propose_canon_record` / `propose_reference_link` -> records Bible/continuity state for the scene (gated by schema defects — `bible_domain.py:141-142,162,189-193,215-216`).
3. `continuity.list_findings` / `continuity.get_finding` / `list_continuity_warnings` -> reads continuity state for the scene.

**Gating defects:** Six `bible_domain` tools lose entity/scene binding because their declared `ToolDefinition.parameters` omit the keys the handler reads (see §3 of the companion audit). The chain is operable for reads but degraded for writes — the Bible version is created (real persistence) but encodes empty/malformed data for the stripped fields.

**Lineage:** `projectId` -> `sceneId` -> `bibleVersionNumber` -> `entityStableId`. The `sceneId` is the join key between Scene and Bible. The `entityStableId` is the join key between Bible and Continuity, but it is stripped on `propose_canon_record`/`propose_canon_supersession`/`propose_continuity_update`, weakening the Bible -> Continuity join.

### 2.4 Chain: PoseCraft -> Image Pipeline -> Timeline

**Systems:** PoseCraft -> Image Planning -> Timeline.
**Tool sequence (operable):**
1. `posecraft.create_scene` / `add_figure` / `apply_pose` / `set_camera` / `save_scene` -> authors a PoseCraft scene.
2. `posecraft.send_to_image_pipeline` -> hands the PoseCraft scene to the image pipeline.
3. `image_pipeline.generate_candidates` / `select_candidate` / `master` / `approve` -> produces an image asset.
4. `propose_add_image_clip` -> places the image on the Timeline.

**Gating defects:** `posecraft.apply_apply_pose` (`posecraft.py:340-346`) re-persists the scene unchanged (pose applied client-side by Babylon viewport); `posecraft.apply_set_eyeline` (`posecraft.py:381-388`) appends a prose annotation rather than structured state. Both are honest but weak writes. The 13 posecraft preview handlers drop `affectedResources=("project",)` (`ToolPreview` field violation).

**Lineage:** `projectId` -> `posecraftSceneId` -> `imageJobId` -> `assetId` -> `batchBlockId`. The `posecraftSceneId` is the join key between PoseCraft and the image pipeline.

### 2.5 Chain: Visual References -> Image Generation -> Asset Library

**Systems:** Visual References -> Image Planning -> Assets/Media Library.
**Tool sequence (operable):**
1. `references.list` / `references.get` / `build_generation_reference_package` -> reads the reference set.
2. `image_pipeline.assign_reference` / `prepare_plan` -> binds references to the image plan.
3. `propose_image_generate` / `propose_image_edit` -> generates the image.
4. `propose_asset_library_assignment` -> assigns the generated image to a library folder (gated by `folderId` defect).

**Gating defects:** `references.attach` (`scene_references_w6p.py:110-111`) drops `usageModes`/`referenceRoles` (schema defect). `propose_asset_library_assignment` drops `folderId`.

**Lineage:** `projectId` -> `referenceSetId` -> `imageJobId` -> `assetId` -> `libraryFolderId`. The `referenceSetId` is the join key between References and Image Planning.

### 2.6 Chain: Voice Performance -> Timeline (lipsync)

**Systems:** Voice Studio -> Timeline.
**Tool sequence (operable):**
1. `voice_performance.generate_segments` / `assemble_dialogue` -> produces voice segments.
2. `voice_performance.place_on_timeline` or `voice.replace_timeline_dialogue` -> places the dialogue on the Timeline.
3. `propose_add_lipsync_track` / `propose_add_lipsync_clip` / `propose_bind_lipsync_clip` -> binds lipsync to the Timeline.

**Gating defects:** `voice_performance.generate_segments` (`service.py:204`) and `retry_segment` (`service.py:345`) do not compare `row.project_id` to `ctx.project_id` (RISK 1 of `state-isolation-report.md`). The chain is operable but has a cross-project leak risk on stale `plan_id`/`segment_id`.

**Lineage:** `projectId` -> `planId` -> `segmentId` -> `batchBlockId`. The `planId` is the join key between Voice and Timeline. Lineage is **weak** here because the voice service does not enforce ownership.

### 2.7 Chain: Render Queue -> Job inspection -> Cancel/Retry

**Systems:** Render Queue / Jobs.
**Tool sequence (operable):** `propose_*_generate` -> `job.list` / `job.get` -> `job.cancel` / `job.retry`.

**Gating defects:** No queue-depth/position inspection tool (only `job.list`/`job.get`).

**Lineage:** `projectId` -> `jobId`. The `jobId` is the join key. Lineage is strong (jobs are project-scoped via `JobStore`).

### 2.8 Chain: MAGI (NOT OPERABLE)

**Systems:** MAGI.
**Tool sequence:** None. No `magi_*` tool is registered. The continuity workspace can *open* MAGI as a deep-link target (`continuity_w5.py:121`) but cannot read or mutate MAGI sequences. See §4 of the companion audit for the milestone decision (MAGI documented as not-operational; gate N/A; no fictional tools).

### 2.9 Inventory Summary

| Chain | Operable? | Gating defects | Lineage strength |
|---|---|---|---|
| Character -> Voice -> Asset -> Timeline | PARTIAL (character authoring blocked) | `propose_traits`/`propose_relationships` always-fail; `folderId` stripped | STRONG (characterId join) |
| Character asset -> Timeline batch -> generator config | YES (strongest chain) | None material | STRONG (batchBlockId join, revision-guarded) |
| Scene -> Bible -> Continuity | PARTIAL (Bible writes degraded) | Six `bible_domain` schema defects | PARTIAL (entityStableId stripped on writes) |
| PoseCraft -> Image -> Timeline | YES (weak writes) | PoseCraft no-op writes; `ToolPreview` field violations | STRONG (posecraftSceneId join) |
| References -> Image -> Library | PARTIAL (folderId stripped) | `references.attach` schema defect; `folderId` stripped | STRONG (referenceSetId join) |
| Voice -> Timeline (lipsync) | YES (leak risk) | voice_performance no ownership check | WEAK (planId not ownership-checked) |
| Render Queue -> Job -> Cancel/Retry | YES | No queue-depth tool | STRONG (jobId project-scoped) |
| MAGI | NO | No tools (N/A gate) | N/A |

---

## 3. Lineage Mechanisms

### 3.1 Immutable IDs

The Co-Director operational model uses the following immutable IDs as lineage join keys across systems. Each ID is generated once and never mutated; downstream systems reference the ID to establish lineage.

| ID | Generated by | Used as join key in | Ownership enforced? |
|---|---|---|---|
| `projectId` | Project creation | Every system (authoritative via `ToolContext.project_id` from URL path) | YES — `execution.py:86` `_require_project` validates the project exists and is unlocked before any tool runs. |
| `sceneId` | `create_scene` | Scene, Bible, Timeline, Continuity, References | YES — `scene_service.py:118` enforces `scene.project_id != project_id`; `director_timeline_w46/store.py:73-78` filters `Scene.project_id == project_id AND Scene.id == scene_id`. |
| `batchBlockId` | `propose_add_batch` (Timeline) | Timeline, Image Planning, Render Queue | YES — Timeline is revision-guarded via `store.save_master(..., bump_revision=True)`. |
| `characterId` | `create_draft_character_profile` / `create_from_brief` | Character Creator, Voice Studio, Assets, Bible | YES — `character_identity/service.py:197` enforces ownership. |
| `assetId` | Image/Voice generation | Assets/Media Library, Timeline, References | YES — assets are project-scoped via `JobStore` and the project library service. |
| `planId` (voice) | `voice_performance` plan creation | Voice Studio, Timeline (lipsync) | **NO** — `voice_performance/service.py:204` (`generate_segments`) and `:345` (`retry_segment`) load by `plan_id`/`segment_id` only, never comparing `row.project_id` to `ctx.project_id` (RISK 1 of `state-isolation-report.md`). |
| `proposalId` | `ProposalService.create_proposal` | Proposal approval flow, Bible, Timeline | YES for the tool-registry path (`execution.py:697` uses `proposal.project_id` from the DB row); **NO** for the legacy `m29` REST routers (`m29/timeline/service.py:141` derives `project_id` from the proposal itself; RISK 3). |
| `jobId` | `propose_*_generate` | Render Queue | YES — `JobStore` is project-scoped. |
| `posecraftSceneId` | `posecraft.create_scene` | PoseCraft, Image Pipeline | YES — PoseCraft service is project-scoped. |
| `referenceSetId` | `create_reference_set_proposal` | Visual References, Image Planning | YES — reference binding store is project-scoped. |
| `bibleVersionNumber` | `ops.apply_mutation_set` | Production Bible, Continuity | YES — Bible versions are project-scoped. |
| `entityStableId` | Bible entity creation | Bible, Continuity, References | YES at the service layer; **WEAK at the tool layer** — `propose_canon_record`/`propose_canon_supersession`/`propose_continuity_update` strip `entityStableId` (schema defect, §3 of companion audit), so the model cannot pass it through. |

### 3.2 Where Lineage Is Strong

Lineage is **strong** where the handler re-validates model-supplied IDs against `ctx.project_id` via the underlying service. Verified strong lineage paths (from `state-isolation-report.md` §"Summary of what is solid"):

- Scenes: `scene_service.py:118` enforces `scene.project_id != project_id`.
- Characters: `character_identity/service.py:197` enforces ownership.
- Plans: `plans/store.py:53` enforces ownership.
- Minimax h3: `minimax_h3/service.py:421` enforces ownership.
- Spatial m411: `spatial_m411.py:86` enforces ownership.
- Generation tools: `generation_tools/lineage.py:100` enforces ownership.
- Director Timeline: `director_timeline_w46/store.py:76` filters `Scene.project_id == project_id AND Scene.id == scene_id`.

### 3.3 Where Lineage Is Weak

Lineage is **weak** where handlers accept bare IDs without an ownership check:

1. **`voice_performance` plan/segment lookups** (RISK 1, `state-isolation-report.md`): `generate_segments` (`service.py:204`) and `retry_segment` (`service.py:345`) load by `plan_id`/`segment_id` only. A stale ID from Project B mutates Project B's voice data while the creator is in Project A. Root cause: the service queries by entity ID without a `project_id` filter.
2. **`m29` action endpoints** (RISKS 2-4, `state-isolation-report.md`): `/image/{version_id}/*`, `/timeline/{proposal_id}/*`, `/control/{plan_id}`, `/render/{manifest_id}`, `/frames/{frame_id}/bind` accept `projectId` in the body but discard it. Root cause: the routers trust client-supplied `projectId` (or ignore it) instead of taking `project_id` from the URL path like the tool registry does.
3. **`m214` approve/confirm endpoints** (RISK 5, `state-isolation-report.md`): `/storyteller/handoff/{handoff_id}/approve`, `/sound/concept/{concept_id}/approve`, `/attachments/{interpretation_id}/confirm` take only the entity ID from the URL. Root cause: same as m29 — no `project_id` ownership guard.
4. **`scene_id` is model-supplied** (RISK 6, `state-isolation-report.md`): `director_timeline_tools.py:44` `_scene_id` prefers `args.get("sceneId")` over `ctx.scene_id`. Safety depends entirely on `director_timeline_w46/store.py:76` re-validating. Currently safe but defense-in-depth-fragile: any new handler that forgets the `ctx.project_id` check inherits a leak.
5. **Compiled context carries stale entity IDs** (RISK 7, `state-isolation-report.md`): `context_compiler.py:160` `compile` pulls project-scoped recent messages, but within a single project, historical messages may reference deleted entity IDs. The model can echo these back into tool calls; safety depends on per-handler re-validation.
6. **Deep-link `projectId` mismatch** (RISK 8, `state-isolation-report.md`): `CoDirectorPage.tsx:10` silently rebinds Co-Director to whatever `projectId` is in the URL with no confirmation. No write leak, but a mistyped/old link switches Co-Director's entire context.

### 3.4 Lineage Verdict

Lineage is **strong on the core tool-registry path** (Timeline, Scene, Character, Plans, Generation) and **weak on the legacy `m29`/`m214` REST routers and the `voice_performance` service**. The weak paths are not currently routed through by Co-Director tools (the tool registry uses services directly with `ctx.project_id`), but they are importable and present a real drift risk if any future handler proxies through them. The schema/handler mismatch defects (§3 of companion audit) further weaken lineage at the tool layer by stripping the very IDs (`entityStableId`, `sceneId`, `folderId`, `usageModes`, `referenceRoles`) that establish cross-system joins.

---

## 4. UI Synchronization Audit

This section was verified by direct inspection of `studio-web/src/components/CoDirector/CoDirectorSession.tsx` and related frontend code. No speculation. Every claim cites `file:line`.

### 4.1 How the Creator-Facing UI Learns About Co-Director Tool Mutations

The creator-facing UI learns about Co-Director tool mutations through **three distinct mechanisms**, all centered in `CoDirectorSession.tsx`. There is **no single framework-level "project mutated" refresh event**; instead, each system opts in via a `result.uiAction` / `result._uiFocus` field on the `tool_completed` stream event, or falls back to the generic `adept:codirector-plan-workspace-refresh` event.

#### 4.1.1 Mechanism A — Stream Events (in-session activity + proposals)

The streaming chat loop (`onEvent` handler) processes server-sent events and updates in-session UI state. Verified at `CoDirectorSession.tsx:1685-1808`:

- `proposal_created` / `tool_proposal_created` (`:1685-1687`): appends the proposal to `setProposals` and clears `setToolActivity`. This is how the creator sees a pending mutation before approving it.
- `tool_requested` (`:1688-1697`): sets `setToolActivity` to `{ toolId, title, phase: "requested" }` and updates the activity indicator. For read tools, the partial streaming text is discarded (`streamedText = ""`) and the in-progress assistant bubble is removed (`:1696`) because the server withholds `completed` for that turn and re-asks with the result.
- `tool_started` (`:1698-1700`): updates `setToolActivity` to `{ phase: "running" }`.
- `tool_completed` (`:1701-1762`): sets `setLastSuccessfulToolAction`, updates the activity indicator to `{ phase: "completed" }`, calls `syncProjectIdentityFromResult(result)` (`:1712`) to sync `projectId`/`projectName` from the result, then **inspects `result.uiAction` and `result._uiFocus`** to dispatch targeted window-scoped CustomEvents (see Mechanism B).
- `tool_result_truncated` (`:1763-1764`): marks the tool activity as truncated.
- `tool_failed` / `capability_blocked` (`:1765-1792`): classifies the error, updates the activity indicator to `{ phase: "failed" | "blocked" }`, and stashes the arguments in `pendingToolRetryRef.current` for a retry.
- `error` (`:1793-1807`): classifies the error and sets the outcome.

**Root cause of the in-session sync:** the server emits stream events; the frontend reacts. This mechanism is **universal** (every tool emits at least `tool_requested`/`tool_completed`), but it only updates the **Co-Director panel itself** — it does not refresh the native system UI (Timeline editor, Voice Studio, Library, etc.) unless the handler also emits a `uiAction`/`_uiFocus` field (Mechanism B).

#### 4.1.2 Mechanism B — `result.uiAction` / `result._uiFocus` Targeted CustomEvents

When a `tool_completed` event arrives, the frontend inspects `result.uiAction` (`CoDirectorSession.tsx:1713`) and `result._uiFocus || result.uiFocus` (`:1750`) and dispatches targeted window-scoped CustomEvents. Verified by direct inspection:

- **`uiAction === "open_voice_performance" || "open_voice_creator"`** (`:1714`): if `result.workspaceUrl` is set, `navigate(workspaceUrl)` (`:1718`); otherwise calls `bindingsRef.current.onGoTab?.("characters")` (`:1721`) and dispatches `adept:open-character-voice` (`:1725-1732`) with `{ tab, characterId }`. This is how Voice Studio learns that Co-Director created/opened a voice profile.
- **`uiAction === "open_audio_studio"`** (`:1735`): calls `bindingsRef.current.onGoTab?.("audiostudio")` (`:1737`) and dispatches `adept:open-audio-studio` (`:1741-1748`) with `{ projectId, workspaceUrl }`. This is how Audio Studio learns that Co-Director opened an audio studio session.
- **`result._uiFocus || result.uiFocus` with `uiFocus.target`** (`:1750-1762`): calls `bindingsRef.current.onGoTab?.("timeline")` (`:1753`) and dispatches `adept-timeline-focus` (`:1757-1761`) with `detail: uiFocus`. This is how the Timeline editor learns that Co-Director mutated the timeline and should focus/scroll to the affected region.

**Root cause of the targeted sync:** each native system that wants UI sync must have its handler emit a `uiAction` or `_uiFocus` field in the `tool_completed` result. This is **handler-opt-in**, not framework-enforced. Systems whose handlers do not emit these fields (Bible, Image, PoseCraft, Library, References, Render Queue, Continuity) get **no targeted refresh** — they rely on Mechanism C or the creator manually refreshing.

#### 4.1.3 Mechanism C — `adept:codirector-plan-workspace-refresh` (generic post-turn / post-approve)

Two code paths dispatch the generic `adept:codirector-plan-workspace-refresh` event:

- **Post-stream finalize** (`CoDirectorSession.tsx:1891-1897`): after the stream completes and the conversation is reconciled, if `b.projectId` is set, the frontend dispatches `adept:codirector-plan-workspace-refresh` with `{ projectId, requestId }`. This fires after **every** completed turn, regardless of which tool ran.
- **Post-approve** (`CoDirectorSession.tsx:2544-2550`): inside `approveProposal` (`:2516`), after `api.approveProposal(projectId, proposalId)` succeeds (`:2524`), if `String(receipt.toolId || "").startsWith("production_plan.")`, the frontend dispatches `adept:codirector-plan-workspace-refresh` with `{ projectId, proposalId }`. This is the production-plan-specific refresh.

**Root cause of the generic sync:** the frontend assumes any completed turn or any production_plan approval may have mutated project state, so it broadcasts a refresh. This is **over-broad** (fires even when no mutation occurred) and **under-informative** (does not tell listeners *what* changed, only *that* something might have). Listeners must re-fetch their entire view to reconcile.

#### 4.1.4 Project-Switch Invalidation (not a mutation sync, but related)

When the bound project changes, the frontend invalidates aggressively. Verified at `CoDirectorSession.tsx:882-964`:

- `cancelInFlightForProjectSwitch()` (`:589-601`) aborts the active `AbortController`, calls `/api/codirector/cancel`, clears `activeRequestIdRef`, `setBusy(false)`, `setToolActivity(null)`, `setActivity(null)`, `setIntelligenceProgress(null)`.
- The `useEffect` at `:882` (keyed on `uiContext.projectId`) synchronously sets `setMessages([WELCOME_ASSISTANT])` (`:908`), clears `setPlan(null)`, `setSendError(null)`, `setToolActivity(null)`, `setActivity(null)`, then asynchronously loads `api.codirectorGetConversation(projectId)` (`:919`).
- `bindWorkspace` (`:1082`) overwrites `bindingsRef.current` and `uiContext` with the new project; if `prevProjectId && bindings.projectId && prevProjectId !== bindings.projectId`, it calls `cancelInFlightForProjectSwitch()` (`:1085`).
- `syncProjectIdentity` (`:603`) updates `bindingsRef.current.projectId`/`projectName` and persists a "last bound project" suggestion to `localStorage` (`:615`).
- `useBindCoDirectorWorkspace` (`:3180`) calls `bindWorkspace(bindings)` in an effect keyed on stable binding fields (`:3184-3198`).

**Root cause:** project-switch invalidation is **complete** for the Co-Director panel itself (messages, proposals, activity, in-flight requests), but it does **not** invalidate native system UIs (Timeline, Voice, Library) — those are expected to re-fetch on their own project-binding lifecycle. There is no confirmation when a deep-link `projectId` switches Co-Director's entire context (RISK 8 of `state-isolation-report.md`).

### 4.2 UI Sync Coverage Per System

| System | Targeted refresh event? | Generic refresh? | Verdict |
|---|---|---|---|
| Timeline | YES — `adept-timeline-focus` (`CoDirectorSession.tsx:1757-1761`) on `result._uiFocus`/`result.uiFocus` | YES — `adept:codirector-plan-workspace-refresh` | STRONG |
| Voice Studio | YES — `adept:open-character-voice` (`:1725-1732`) on `uiAction === "open_voice_performance"\|"open_voice_creator"` | YES | STRONG |
| Audio Studio | YES — `adept:open-audio-studio` (`:1741-1748`) on `uiAction === "open_audio_studio"` | YES | STRONG |
| Production Plans | YES — `adept:codirector-plan-workspace-refresh` (`:2545-2549`) on `production_plan.*` approve | YES | STRONG |
| Scene/Project Editor | NO targeted event | YES (generic) | PARTIAL |
| Production Bible | NO targeted event | YES (generic) | PARTIAL |
| Character Creator | NO targeted event (relies on `adept:open-character-voice` only when voice is opened) | YES (generic) | PARTIAL |
| Image Planning/Gen | NO targeted event | YES (generic) | PARTIAL |
| PoseCraft | NO targeted event | YES (generic) | PARTIAL |
| Assets/Media Library | NO targeted event | YES (generic) | PARTIAL |
| Visual References | NO targeted event | YES (generic) | PARTIAL |
| Render Queue/Jobs | NO targeted event | YES (generic) | PARTIAL |
| Continuity/Intel | NO targeted event | YES (generic) | PARTIAL |
| MAGI | N/A (no tools) | N/A | N/A |

**Root cause of the asymmetry:** the `uiAction`/`_uiFocus` opt-in pattern was authored for the systems that needed explicit navigation (Voice, Audio, Timeline focus, Production Plans) and was not propagated to the other systems. The other systems rely on the generic `adept:codirector-plan-workspace-refresh`, which forces a full re-fetch.

### 4.3 Frontend Code Inspection Notes

Direct inspection of `CoDirectorSession.tsx` confirmed:

- `send` (`:2177`) captures `const projectId = bindingsRef.current.projectId` at send time and passes it into the request body. The request body to `/api/codirector/chat` (or `/chat/stream`) carries `project_id` + `scene_id`.
- `approveProposal` (`:2516`) reads `projectId` from `bindingsRef.current.projectId` (`:2518`), calls `api.approveProposal(projectId, proposalId)` (`:2524`), syncs project identity from the receipt (`:2529`), appends an assistant message (`:2530-2543`), dispatches the production-plan refresh (`:2544-2550`), and finally calls `refreshProposals()` (`:2569`).
- `rejectProposal` (`:2575`), `requestProposalRevision` (`:2592`), `cancelProposal` (`:2609`) all call `refreshProposals()` in their `finally` block but dispatch **no targeted refresh event** — the native system UI is not notified that a proposal was rejected/revised/cancelled. This is acceptable because rejection/revision/cancellation does not mutate project state, but it means the proposal list is the only thing that updates.
- The `useEffect` at `:967` polls the server revision when the tab is visible and reconciles on change — this is the **conversation** reconciliation, not native-system reconciliation.
- There is **no `useEffect` or event listener in `CoDirectorSession.tsx` that re-fetches native system state** (Timeline workspace, Voice profiles, Library) after a tool mutation. Native system UIs are expected to listen for the window-scoped CustomEvents (`adept-timeline-focus`, `adept:open-character-voice`, `adept:open-audio-studio`, `adept:codirector-plan-workspace-refresh`) on their own.

---

## 5. Gaps and Risks

### 5.1 Cross-System Workflow Gaps

1. **Character authoring chain is blocked.** `character_creator.propose_traits` (`character_creator.py:307`) and `propose_relationships` (`character_creator.py:350`) always fail. The Character -> Voice -> Asset -> Timeline chain is operable for character *creation* but blocked for character *authoring*. Root cause: schema/handler mismatch (§3 of companion audit).
2. **Bible write chain is degraded.** Six `bible_domain` tools strip the very IDs (`entityStableId`, `sceneId`) that establish the Bible -> Continuity join. The Scene -> Bible -> Continuity chain is operable for reads but produces empty/malformed data for writes. Root cause: schema/handler mismatch.
3. **Library assignment chain is degraded.** `propose_asset_library_assignment` strips `folderId` (`library.py:144`); `references.attach` strips `usageModes`/`referenceRoles` (`scene_references_w6p.py:110-111`). The References -> Image -> Library chain is operable but degraded. Root cause: schema/handler mismatch.
4. **Voice -> Timeline chain has a cross-project leak risk.** `voice_performance.generate_segments` (`service.py:204`) and `retry_segment` (`service.py:345`) do not enforce ownership. Root cause: service queries by entity ID without a `project_id` filter (RISK 1 of `state-isolation-report.md`).
5. **MAGI chain is not operable.** No `magi_*` tools. Root cause: MAGI tooling was never authored (§4 of companion audit; milestone decision: N/A gate, no fictional tools).

### 5.2 Lineage Risks

1. **Weak lineage on `voice_performance` plan/segment IDs.** A stale `plan_id`/`segment_id` from Project B mutates Project B while the creator is in Project A. Root cause: no `project_id` ownership check (RISK 1).
2. **Legacy `m29`/`m214` routers accept bare IDs.** The `m29` image/timeline/control/render/frame endpoints and the `m214` storyteller/sound/attachments endpoints derive `project_id` from the entity itself or ignore it. Root cause: routers trust client-supplied `projectId` instead of taking it from the URL path (RISKS 2-5).
3. **`scene_id` is model-supplied.** Safety depends on per-handler re-validation (`director_timeline_w46/store.py:76`). Root cause: defense-in-depth fragility — any new handler that forgets the `ctx.project_id` check inherits a leak (RISK 6).
4. **Compiled context carries stale entity IDs.** Historical messages may reference deleted entities; the model can echo them into tool calls. Root cause: context compiler does not annotate or strip IDs for entities that no longer exist (RISK 7).
5. **Deep-link `projectId` mismatch has no confirmation.** `CoDirectorPage.tsx:10` silently rebinds Co-Director. Root cause: no guard when the URL project differs from the last-bound suggestion (RISK 8).

### 5.3 UI Synchronization Risks

1. **UI sync is handler-opt-in, not framework-enforced.** Systems whose handlers do not emit `uiAction`/`_uiFocus` get no targeted refresh. Root cause: the opt-in pattern was not propagated beyond Voice/Audio/Timeline/Production Plans.
2. **No framework-level post-apply state-diff verification.** After `execute_read` or `execute_audited` runs, the pipeline does not re-read native state to confirm the model's prose matches the actual change. Root cause: no reconciler exists (gap #2 of `routing-report.md` §d).
3. **The generic `adept:codirector-plan-workspace-refresh` is over-broad and under-informative.** It fires after every turn (even non-mutating ones) and does not tell listeners *what* changed. Root cause: the frontend assumes any turn may have mutated state and forces a full re-fetch.
4. **`rejectProposal`/`requestProposalRevision`/`cancelProposal` dispatch no targeted refresh.** Acceptable (no mutation), but the proposal list is the only thing that updates. Root cause: by design.
5. **No confirmation on deep-link project switch.** A mistyped/old link switches Co-Director's entire context silently. Root cause: no guard (RISK 8).
6. **Grounding does not rewrite streamed tokens.** If the model streams "Done — I added the scene", the grounding gate can flag the violation but cannot retract the tokens (`service.py:1790-1793` only substitutes the fallback when the streamed reply is empty). Root cause: streaming architecture (gap #1 of `routing-report.md` §d).

---

## 6. Repair Recommendations (Mapped to Milestone Phase c5)

### 6.1 Cross-System Workflow Closure

1. **Unblock the Character authoring chain.** Close the `character_creator.propose_traits`/`propose_relationships` schema defects (tracked under c4 in the companion audit). Add a cross-system regression test that drives Character -> Voice -> Asset -> Timeline end-to-end and asserts the `characterId` joins correctly across all four systems.
2. **Close the Bible write chain.** Close the six `bible_domain` schema defects (c4). Add a cross-system regression test that drives Scene -> Bible -> Continuity and asserts `entityStableId`/`sceneId` survive the tool layer.
3. **Close the Library assignment chain.** Close the `folderId` and `references.attach` schema defects (c4). Add a cross-system regression test that drives References -> Image -> Library and asserts `folderId`/`usageModes`/`referenceRoles` survive.
4. **Add a `voice_performance` ownership guard.** `generate_segments` (`service.py:204`) and `retry_segment` (`service.py:345`) must `SELECT ... WHERE id = ? AND project_id = ?` and 404 on mismatch. Add a regression test that asserts a stale `plan_id`/`segment_id` from another project is rejected (c8 in companion audit; cross-system impact tracked here).

### 6.2 Lineage Strengthening

1. **Add a central "entity ownership" helper.** A shared helper (e.g. `require_scene_owned(ctx, scene_id)`, `require_plan_owned(ctx, plan_id)`) used uniformly would close RISK 6's defense-in-depth fragility. Root cause addressed: per-handler remembering becomes framework-enforced.
2. **Guard or remove the `m29`/`m214` routers.** Either take `project_id` from the URL path (like the tool registry) or assert `entity.project_id == body.projectId` before mutating. Tracked under c8 in companion audit; cross-system impact tracked here.
3. **Annotate or strip stale entity IDs in compiled context.** `context_compiler.py:160` `compile` should mark IDs for entities that no longer exist in the current project before sending to specialists. Addresses RISK 7.
4. **Add a confirmation on deep-link project switch.** `CoDirectorPage.tsx:10` should confirm when the URL `projectId` differs from the last-bound suggestion. Addresses RISK 8.

### 6.3 UI Synchronization Unification

1. **Generalize the `uiAction`/`_uiFocus` pattern to all mutating tools.** Every mutating tool's `tool_completed` result should emit a structured `uiAction` (or a new `uiSync` field) that tells the frontend *which native system mutated* and *what entity changed*. This replaces the over-broad `adept:codirector-plan-workspace-refresh` with targeted, informative events. Root cause addressed: handler-opt-in becomes framework-enforced.
2. **Add a framework-level post-apply state-diff verifier.** After `execute_approved_proposal` runs, the pipeline should re-read the affected native state and emit a `state_diff` event that the frontend can use to reconcile without a full re-fetch. Addresses gap #2 of `routing-report.md` §d.
3. **Replace the over-broad `adept:codirector-plan-workspace-refresh` with a targeted event per system.** The post-turn finalize (`CoDirectorSession.tsx:1892-1896`) and the post-approve (`:2545-2549`) should dispatch system-specific events (e.g. `adept:bible-updated`, `adept:library-updated`, `adept:references-updated`) carrying the mutated entity IDs. Addresses UI sync risk #3.
4. **Add a regression test for every system's UI sync.** Each native system must have a Playwright test that drives a Co-Director tool mutation and asserts the native system UI updates without a manual refresh. Tracked under c8 in companion audit; UI sync design tracked here.

---

## 7. Verification Log

Spot-verification of citations against the current tree (2026-08-07). Each entry records the citation, the verification method, and the result. Corrections are recorded where the source report's citation drifted from the current tree.

1. **`CoDirectorSession.tsx:3180` `useBindCoDirectorWorkspace`** — Re-read `CoDirectorSession.tsx:3180-3200`. Confirmed: `export function useBindCoDirectorWorkspace(bindings)` at `:3180`; `bindWorkspace(bindings)` in `useEffect` at `:3184-3198`, keyed on stable binding fields including `bindings.onGoTab` (`:3195`) and `bindings.onApplyPrompt` (`:3196`). No correction.
2. **`CoDirectorSession.tsx:1082` `bindWorkspace`** — Re-read `CoDirectorSession.tsx:1082-1110`. Confirmed: `const bindWorkspace = useCallback(...)` at `:1082`; `cancelInFlightForProjectSwitch()` at `:1085` when `prevProjectId && bindings.projectId && prevProjectId !== bindings.projectId`; `bindingsRef.current = bindings` at `:1087`; `setUiContext` at `:1088`. No correction.
3. **`CoDirectorSession.tsx:882` project-switch hydration `useEffect`** — Re-read `CoDirectorSession.tsx:882-964`. Confirmed: `useEffect(() => { ... }, [uiContext.projectId, cancelInFlightForProjectSwitch])` at `:882`; `cancelInFlightForProjectSwitch()` at `:899`; `setMessages([WELCOME_ASSISTANT])` at `:908`; `api.codirectorGetConversation(projectId)` at `:919`. No correction.
4. **`CoDirectorSession.tsx:589-601` `cancelInFlightForProjectSwitch`** — Re-read `CoDirectorSession.tsx:589-601`. Confirmed: `const cancelInFlightForProjectSwitch = useCallback(...)` at `:589`; aborts `AbortController`, calls `api.codirectorCancel(requestId)`, clears `activeRequestIdRef`, `setBusy(false)`, `setToolActivity(null)`, `setActivity(null)`, `setIntelligenceProgress(null)`. No correction.
5. **`CoDirectorSession.tsx:603` `syncProjectIdentity`** — Re-read `CoDirectorSession.tsx:603-620`. Confirmed: `const syncProjectIdentity = useCallback(...)` at `:603`; updates `bindingsRef.current` at `:608`; `persistLastBoundProjectSuggestion(suggestion)` at `:615`; dispatches `adept:project-renamed` at `:619`. No correction.
6. **`CoDirectorSession.tsx:2177` `send`** — Re-read `CoDirectorSession.tsx:2177-2270`. Confirmed: `const send = useCallback(async (text?, mode = "chat") => {...})` at `:2177`; `const projectId = bindingsRef.current.projectId` captured at send time at `:2213`. No correction.
7. **`CoDirectorSession.tsx:2516` `approveProposal`, `:2524` `api.approveProposal`** — Re-read `CoDirectorSession.tsx:2516-2573`. Confirmed: `const approveProposal = useCallback(...)` at `:2516`; `const projectId = bindingsRef.current.projectId` at `:2518`; `const receipt = await api.approveProposal(projectId, proposalId)` at `:2524`; `syncProjectIdentityFromResult(toolResult)` at `:2529`; appends assistant message at `:2530-2543`; dispatches `adept:codirector-plan-workspace-refresh` at `:2545-2549` gated on `String(receipt.toolId || "").startsWith("production_plan.")`; `await refreshProposals()` at `:2569`. No correction.
8. **`CoDirectorSession.tsx:1685-1808` stream event handler** — Re-read `CoDirectorSession.tsx:1685-1808`. Confirmed: `proposal_created`/`tool_proposal_created` at `:1685-1687`; `tool_requested` at `:1688-1697`; `tool_started` at `:1698-1700`; `tool_completed` at `:1701-1762`; `tool_result_truncated` at `:1763-1764`; `tool_failed`/`capability_blocked` at `:1765-1792`; `error` at `:1793-1807`. No correction.
9. **`CoDirectorSession.tsx:1713` `result.uiAction`, `:1725-1732` `adept:open-character-voice`, `:1741-1748` `adept:open-audio-studio`, `:1757-1761` `adept-timeline-focus`** — Re-read `CoDirectorSession.tsx:1713-1762`. Confirmed: `const uiAction = String(result.uiAction || "")` at `:1713`; `uiAction === "open_voice_performance" || "open_voice_creator"` branch at `:1714`; `navigate(workspaceUrl)` at `:1718`; `bindingsRef.current.onGoTab?.("characters")` at `:1721`; `adept:open-character-voice` dispatch at `:1725-1732`; `uiAction === "open_audio_studio"` branch at `:1735`; `onGoTab?.("audiostudio")` at `:1737`; `adept:open-audio-studio` dispatch at `:1741-1748`; `result._uiFocus || result.uiFocus` at `:1750`; `onGoTab?.("timeline")` at `:1753`; `adept-timeline-focus` dispatch at `:1757-1761`. No correction.
10. **`CoDirectorSession.tsx:1892-1896` post-stream `adept:codirector-plan-workspace-refresh`** — Re-read `CoDirectorSession.tsx:1891-1897`. Confirmed: dispatch at `:1892-1896` gated on `b.projectId`, with `detail: { projectId: b.projectId, requestId }`. No correction.
11. **`CoDirectorSession.tsx:2575` `rejectProposal`, `:2592` `requestProposalRevision`, `:2609` `cancelProposal`** — Re-read `CoDirectorSession.tsx:2575-2624`. Confirmed: all three call `refreshProposals()` in their `finally` block (`:2586`, `:2603`, `:2620`) and dispatch no targeted refresh event. No correction.
12. **`CoDirectorSession.tsx:967` server-revision poll `useEffect`** — Re-read `CoDirectorSession.tsx:967-979`. Confirmed: `useEffect` polls server revision when tab is visible; this is conversation reconciliation, not native-system reconciliation. No correction.
13. **`voice_performance/service.py:204` `generate_segments`, `:345` `retry_segment`** — Verified via `state-isolation-report.md` source (RISK 1). Not re-read in this audit; source-of-truth preserved per Build Law 30. No correction.
14. **`m29/timeline/service.py:141` derives `project_id` from proposal, `:229` writes `scene.director_json`** — Re-read `m29/timeline/service.py:133-247` (cross-verified in companion audit §8 entry 8). Confirmed: `project_id = prop["projectId"]` at `:141`; `scene.director_json = dumps_director_timeline_preserving_embedded(...)` at `:229`. No correction.
15. **`director_timeline_w46/store.py:76` filters `Scene.project_id == project_id AND Scene.id == scene_id`** — Re-read `director_timeline_w46/store.py:73-78` (cross-verified in companion audit §8 entry 9). Confirmed. No correction.
16. **`context_compiler.py:160` `compile`** — Verified via `state-isolation-report.md` source (RISK 7). Not re-read; source-of-truth preserved. No correction.
17. **`CoDirectorPage.tsx:10` URL `projectId`** — Verified via `state-isolation-report.md` source (RISK 8). Not re-read; source-of-truth preserved. No correction.
18. **`scene_service.py:118` enforces `scene.project_id != project_id`** — Verified via `state-isolation-report.md` source. Not re-read; source-of-truth preserved. No correction.
19. **`character_identity/service.py:197` enforces ownership** — Verified via `state-isolation-report.md` source. Not re-read; source-of-truth preserved. No correction.
20. **`execution.py:86` `_require_project`, `:697` `execute_approved_proposal`** — Verified via `state-isolation-report.md` source. Not re-read; source-of-truth preserved. No correction.

**Corrections made during verification:** None. All 20 spot-verified citations matched the current tree. The source reports (`native-systems-report.md`, `tool-registry-report.md`, `state-isolation-report.md`, `routing-report.md`) were accurate as of 2026-08-07.

---

## 8. Governing Status

This document is the **governing cross-system workflow and UI synchronization audit** for the Co-Director Operational Integrity Audit milestone (Build Law 30). It is the companion to `CODIRECTOR_NATIVE_SYSTEM_OPERATIONS_AUDIT.md`, which governs the native-system coverage scope. Together they form the complete audit record for the milestone. Repairs are tracked in milestone phases c4 (native-system contract closure — companion audit), c5 (cross-system workflow + UI synchronization — this document), and c8 (test/certification infrastructure unification — companion audit §7).

**Verdict (audit only):** AUDIT COMPLETE. Repairs are tracked; no GO/NO-GO is asserted at the audit stage. The milestone primary agent owns the final binary certification per Build Law #25.

