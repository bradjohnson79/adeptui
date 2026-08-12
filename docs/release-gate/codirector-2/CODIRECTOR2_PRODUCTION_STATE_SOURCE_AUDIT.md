# CO-DIRECTOR 2.0 — PRODUCTION STATE PROJECTION / AUTHORITATIVE STORES SOURCE AUDIT

| Field | Value |
|---|---|
| Phase | 1 (read-only architecture audit) |
| Date | 2026-08-08 |
| Status | Complete |
| Scope | Authoritative stores feeding a projection-only **Production State** (Law 4). Build WITHOUT duplication. |
| Method | Direct source reads. All citations are `file:line`. |

> Purpose: The 2.0 architecture adds a *Production State Projection* that is **projection-only** (Law 4):
> it may compose authoritative info but must NOT become a second writable copy of any authoritative store.
> This audit inventories every authoritative store per domain, classifies each proposed Production State
> field by allowed source, identifies mutation→invalidation attach points, and flags existing parallel-copy risks.

---

## 1. Authoritative store inventory

### 1.1 Project title / format / runtime / fps (project model)

| Item | Detail |
|---|---|
| Store | `projects` table — `app/db.py:16` `class Project`, `__tablename__="projects"`. Title = `name` (`db.py:20`), fps = `fps` (`db.py:26`), width/height (`db.py:24-25`), **format = `primary_project_type`** (`db.py:46`, M3.1a source of truth; `defaults_json.production_type` is deprecated soft metadata `db.py:45`), `project_traits_json` (`db.py:47`), `resolved_profile_json` (`db.py:48`). |
| Write API | `routers/api.py:466` `create_project` (POST `/projects`); `routers/api.py:850` `update_project` (PATCH `/projects/{id}`) — generic attribute write loop (`api.py:857-858`). Schemas: `ProjectCreate` `schemas.py:221`, `ProjectUpdate` `schemas.py:246`, `ProjectOut` `schemas.py:277`. |
| Read API | `routers/api.py:448` list, `:543` get; shared read service `project_service.py` (status_label `:60`, project_profile). `project_library/service.py:55` `init_project_library` on create. |
| Description | **The single writable project model.** Authoritative for title, fps, format. Runtime is not stored as a scalar — it is derived from scene durations / MAGI sequence `durationFrames`. |

### 1.2 Characters (character records / character creator persistence)

| Item | Detail |
|---|---|
| Store | `character_profiles` (`character_identity/models.py:12` `CharacterProfileRow`) with `character_versions` (`:44`), `character_reference_assets` (`:61`), `character_traits` (`:79`), `character_wardrobes` (`:94`), `character_props` (`:117`), `voice_profiles` (`:139`), `voice_consent_records` (`:177`). |
| Write API | `character_identity/service.py:204` `create_profile`, `:254` `update_profile` (rename path sets `name` at `:290-305`), `:438` `approve_version`; `character_identity/api.py:57` `create_character`, `:87` `approve_version`, `:150` `upsert_trait`, `:164` `create_voice`, `:184` `approve_voice`. |
| Read API | `character_identity/api.py` list/get; Co-Director read tools `character_identity.list_character_profiles` / `inspect_character_profile` (`tools/registry.py`). |
| Related | Cross-project DNA library `profile_items` (`profiles.py:30`, kind incl. `"character"` `profiles.py:20`); `production_bible_entities` entity_type=`"character"` carries a mirror (see 1.6 + §4). |
| Description | Character creator persistence — the authoritative per-project character record store. |

### 1.3 Locations / settings

| Item | Detail |
|---|---|
| Store | No dedicated `locations` table. Locations live in two primary places: (a) **Bible typed entities** `production_bible_entities` entity_type=`"location"` (`db.py:243`) with `LocationData` payload (`bible/domain/schemas.py:64`); (b) **Environment Reference Sheets** JSON under `data/environment_reference_sheet/{project}/sheets/*.json` (`environment_reference_sheet/store.py:55` `save_sheet`, `:59` `load_sheet`). |
| Write API | `bible/domain_service.py` / `bible/proposals.py` (propose/approve location mutation); `environment_reference_sheet/orchestrator.py` (`build_directional_view_image_plan` `:173`), `environment_reference_sheet/api.py`. |
| Read API | `bible_read.get_location_bible_context`, `bible_domain.get_location_bible_context` (registry), `environment_reference_sheet/api.py`; `voice_environment.inspect_location`. |
| Related | Per-scene `spatial_scenes` (`spatial_scene.py:176`, `map_json`) is spatial staging, not a location canon record. |
| Description | Location canon is Bible-typed entities + Environment Reference Sheets; no standalone location table. |

### 1.4 Script (scriptwriter store + sequence)

| Item | Detail |
|---|---|
| Store | `script_documents_v2` (`scriptwriter/store.py:27` `ScriptDocumentRow`; content in `elements_json`), `script_transactions` (`:48`), `script_revision_snapshots` (`:63`), `script_notes` (`:77`). Sequence = `scene_sync_json` (`store.py:40`). Legacy store `script_docs` / `script_segments` (`script_storyboard.py:46`, `:59`) + `storyboard_panels` (`:87`). |
| Write API | `scriptwriter/store.py:135` `save_document`, `:176` `save_transaction`, `:230` `save_revision`, `:446` `lock_production_numbers`; `scriptwriter/service.py:257` `apply_codirector_proposal`, `:175` `create_revision_set`; HTTP `scriptwriter/api.py` (create_revision `:157`, apply_proposal `:207`, delete_scene `:141`). |
| Read API | `scriptwriter/store.py` row→doc loaders; script endpoint `routers/api.py:1583` (GET script). |
| Description | Scriptwriter store + scene sequence; `draft_status` (`models.py:23` `DraftStatus` = outline/first-draft/revision/locked/production) is the script-progress authority. |

### 1.5 Scenes (scene model + scene store)

| Item | Detail |
|---|---|
| Store | `scenes` table — `db.py:58` `class Scene`: `summary` (`db.py:67`), `prompt` (`db.py:69`), `duration_sec` (`db.py:70`), `director_json` (`db.py:80`, embeds W46 timeline master), `continuity_json` (`db.py:81`), `fps`/`fps_mode` (`db.py:87-88`), `aspect_ratio` (`db.py:84`), `production_unit_id` (`db.py:89`). |
| Write API | `scene_service.py:53` `create_scene`, `:99` `update_scene_fields` (router wrapper `routers/api.py:892` POST, `:898` PATCH, `:1056` DELETE). |
| Read API | `scene_service.py:36` `list_scenes`, `:44` `get_scene`; routers `:880`/`:887`. |
| Description | Scene model + store. Per-scene runtime (duration_sec), fps, aspect, and timeline master all live here. |

### 1.6 Production Bible (`codirector/bible/` incl. `domain/`)

| Item | Detail |
|---|---|
| Store | `production_bibles` (`db.py:213`), `production_bible_versions` (immutable snapshots, `db.py:223`), `production_bible_entities` (`db.py:238`, entity_type/entity_key/display_name/lifecycle_status), `production_bible_facts` (`db.py:274`), `bible_audit_events` (`db.py:255`). Typed domain payloads: `bible/domain/schemas.py` — `ProjectOverviewData` (`:19`, incl. `genre`/`tone`/`logline`/`fps`/`aspect`), `CharacterData` (`:31`), `LocationData` (`:64`), `ProductionObjectData` (`:90`), `WardrobeData` (`:108`), `VisualLanguageData`, `TimelineEntryData`, `CanonRecordData`, `ProductionDecisionData`, `RelationshipData`, `ContinuityStateData`, `AppearanceStateData` (exported `bible/domain/__init__.py:4-18`). |
| Write API | `bible/service.py` `ProductionBibleService` (direct version creation); **proposal-driven writes only** through `bible/proposals.py` `ProposalService` (`create_proposal` `:130`, `approve` `:365`, `request_revision` `:329`) → `bible/operations.py:195` `apply_mutation_set`. Mutations flow: proposal → approval → new immutable version + execution receipt (`db.py:315`). |
| Read API | `bible_read.*` / `bible_domain.*` tool handlers; `bible/api_domain.py:144` `approve_character`. |
| Description | Versioned, immutable, **the** canonical story/world canon store; entities carry lifecycle (`draft/approved/superseded`). |

### 1.7 Canon / Wiki (`codirector/wiki.py`, `wiki_export.py`, wiki persistence)

| Item | Detail |
|---|---|
| Store | **`knowledgeEntries` inside the Project Intelligence Snapshot**, persisted in `project.settings_json["projectIntelligence"]` — `snapshot.py:13` `_SETTINGS_KEY="projectIntelligence"`, `conversation/schemas.py:86` `knowledgeEntries: list[WikiCandidate]`. Compiled Wiki Bible cache = `snapshot.compiledWiki` (`schemas.py:90`), written by `wiki_intelligence/compiled/page_compiler.py:208`/`:246`. |
| Read API | `wiki.py:330` `build_project_wiki` — canonical UI source `projectIntelligence.knowledgeEntries` (+ decisions) per `wiki.py:3,415,542`; export `wiki_export.py`; router `routers/codirector.py:1006` GET wiki, `:1023` promote, `:1044` compile. |
| Write API | `conversation/knowledge.py:52` `apply_wiki_candidates` (supersede/reject lifecycle); `conversation/orchestrate.py:634,734`; `notes/service.py:153` `promote_note_to_wiki` (`authority="USER_EXPLICIT_WIKI_WRITE"`); wiki correction `wiki_intelligence/correction/apply.py:187`; reorganize `wiki_intelligence/reorganize.py:552-556`. |
| Description | Canon/lore is the `knowledgeEntries` list in the snapshot (settings_json). The Wiki *is already a projection* of it (`sourceOfTruth="projectIntelligence.knowledgeEntries"`). |

### 1.8 Decisions / approved decisions (DecisionRecordStore, project_decisions tools, proposals/approvals)

| Item | Detail |
|---|---|
| Store | `m211_decision_records` (migration `migrations/m014_production_intelligence.py:31`) with `approval_status`; plus durable proposal/approval tables `codirector_proposals` (`db.py:286`), `codirector_approvals` (`db.py:304`), `codirector_execution_receipts` (`db.py:315`). |
| Write API | `codirector/m211/decisions.py:22` `DecisionRecordStore.create`, `:117` `set_approval`; tool handlers `codirector/tools/handlers/project_decisions.py:73` `apply_record_production_decision` (also renames project `:81-84`); `bible/proposals.py:365` `ProposalService.approve`; orchestrator-generated decisions `m211/orchestrator.py:403`. |
| Read API | `m211/api.py:174` GET `/decisions`, `:188` approve; `wiki.py:340` `DecisionRecordStore.list_for_project` feeds Wiki `productionDecisions`. |
| Description | Decision record store (M2.11) + proposal/approval ledger. Approved decisions are durable, explainability-bearing, and feed the Wiki. |

### 1.9 Timeline / sequences (MAGI sequence store, timeline handoff)

| Item | Detail |
|---|---|
| Store | **MAGI sequence** JSON `data/magi/sequences/{project}/sequence.json` (`magi/sequence/store.py:32-37` `_seq_dir`/`_seq_path`; `save_sequence` `:138`, `get_sequence` `:67`, `record_export_ledger` `:100`). **W46 Timeline Master** embedded in `scenes.director_json.timelineMaster` — `director_timeline_w46/store.py:1` (COW), `:109` `save_master`. Legacy `director_sequences` / `editor_projects` (`editor_sequences.py:27`, `:41`). |
| Write API | `magi/sequence/store.py:138` `save_sequence`; `director_timeline_w46/service.py:83` `add_batch`, `:119` `duplicate_batch`, `:152` `delete_batch`; `director_timeline_w46/orchestrator.py:562` `add_clip_to_batch`; MAGI↔Timeline handoff `magi/timeline_handoff.py` (`export_to_timeline`, `import_timeline_asset` `:45`). |
| Read API | `magi/api.py` router; `magi/sequence/store.py` reads; `director_timeline_w46/router.py` (add_batch `:75`, add_clip `:133`); `timeline_references.*` tools. |
| Description | Sequence = per-project MAGI JSON document; timeline = per-scene `director_json.timelineMaster` (W46 contract). `settings_json["timeline"]` is explicitly NON-authoritative (`magi/timeline_handoff.py:14-15`). |

### 1.10 Image Planning (shot planning stores)

| Item | Detail |
|---|---|
| Store | JSON under `data/image_pipeline/{project}/plans/*.json` (`image_pipeline/store.py:55` `save_plan`, `ImageGenerationPlan`), `candidate_groups/*.json` (`:70`). |
| Write API | `image_pipeline/orchestrator.py` `prepare_plan`; `image_pipeline/multi_shot/service.py` (below); env sheet tool `codirector/tools/handlers/environment_reference_sheet.py:180`. |
| Read API | `image_pipeline/store.py` load_plan/load_candidate_group. |
| Description | Per-project image generation / candidate-group planning store. |

### 1.11 Multi-Shot (multi_shot tools/store)

| Item | Detail |
|---|---|
| Store | `multi_shot_plans` (`image_pipeline/multi_shot/models.py:26`), `multi_shots` (`:49`, incl. `timeline_batch_block_id` `:74`), `multi_shot_candidates` (`:79`, append-only candidate history). |
| Write API | `image_pipeline/multi_shot/api.py` (create plan `:76`, update `:112`, delete `:125`), `service.py` (`create_plan` `:208`, `add_shot` `:293`, `reorder_shots` `:363`, `add_candidate` `:395`); Co-Director tools `codirector/tools/handlers/multi_shot_tools.py`. |
| Read API | `image_pipeline/multi_shot/api.py` list/get; `service.py` list_plans `:234`. |
| Description | Shot planning/decomposition store; per-shot approved assets feed Timeline batches (lineage `timeline_batch_block_id`). |

### 1.12 MAGI (read-only operational surface)

| Item | Detail |
|---|---|
| Surface | `magi/api.py` router prefix `/api/magi` — readiness `:26`, wave4b/wave5/wave4c gates `:31-53`, deferred surfaces honest-refuse `:56`. `magi/readiness.py` (`readiness_payload`, `korri_policy` `:120`, `magi_actions_catalog` `:148`). `magi/production_gate.py`, `magi/composition/*`, `magi/overlays/*`. |
| Writes | Sequence writes go through `magi/sequence/store.py` (1.9). MAGI itself exposes no independent canonical store — it consumes Project Bible / Timeline / sequences and is gate/readiness governed. |
| Description | **Read-only operational surface** for the projection: readiness + gates + action catalog. |

### 1.13 Current workspace + active selection (session-level)

| Item | Detail |
|---|---|
| Location | **Not persisted.** `codirector/session_context.py:26` `build_session_context(project_id, active_document_id, active_scene_id, active_workspace, selected_assets, …)` returns a composed dict (`:84-104`) — a per-request assembly, explicitly "composed; not a duplicate project store" (`session_context.py:1`). Served at `routers/codirector.py:194` GET `/session-context`. `status/types.py:126,140` carry `workspace` per status check; `status/registry.py:222` `active_workspace=ctx.workspace`. |
| Cached echoes | `ProjectIntelligenceCache.activeSceneId` (`conversation/project_cache.py:54`) — a projection cache field, not authoritative. |
| Description | Session-level ephemeral context; lives in per-request args / URL query. No durable store. |

### 1.14 Production status / lifecycle (candidate stage-evidence inputs)

| Item | Detail |
|---|---|
| `production_lifecycle/` | `ProjectProductionLifecycle` (`contracts.py:64`) — `currentStage` (STORY→COMPLETE `:10-20`), `scriptStatus`, `castingStatus`, `productionStatus`, `postStatus`, `formatProfile`, `characterCasting`, `scenes` readiness, `stageHistory`. **Persisted inside the conversation snapshot**: `production_lifecycle/service.py:44-48` `_save_life` → `snapshot.productionLifecycle` → `settings_json["projectIntelligence"]`. Router endpoints in `routers/codirector.py` (`/production-lifecycle`, `/script`, `/casting`, `/scenes`, `/complete`, `/reopen`, `/final-qc`, `/timeline-ready`, `/post`, `/story-ready`). |
| `production_intent/` | `ProductionIntent` (`production_intent/schemas.py:92`) with `executionState`, `approvalPolicy`; persisted to **JSON** `data/production_intents/{project}/{intent}.json` (`production_intent/store.py:12-13`, `save` `:28`, `update_state` `:53`, handoffs `:96`). |
| `conversation/discovery/temperature.py` | `assess_creative_temperature` (`:16`) → `CreativeTemperature.stage` (EMERGENCE/EXPLORATION/FORMATION/EVALUATION/PRODUCTION) — **heuristic per-turn, not itself persisted** as stage (bundle persisted at `discovery/persistence.py:41`). |
| `conversation/partnership/journey.py` | `update_journey` (`:14`) → `ProductionJourneyState.current_stage` (INITIAL_IDEA/DISCOVERY/TREATMENT/SCREENPLAY/PITCH_PACKAGE/…) — keyword-driven, persisted inside partnership bundle (`partnership/persistence.py:71`). |
| `conversation/creative_state.py` | `update_creative_state` (`:114`) → keyword-inferred stage/substate; persisted as `snapshot.currentStage/currentSubstate` + `snapshot.director.creativeStage` (`conversation/schemas.py:84-85,65-66`; `snapshot.py:149-151`). |
| `conversation/project_cache.py` | `developmentStage` (`:52`) persisted in settings cache. |
| `m214` | `m214_project_stages` table (`m214/db.py`), `M214Store.upsert_stage` (`m214/store.py:54`), `get_stage` (`:84`); `idea_first.advance_depth` (`:63`). |

**Description:** Lifecycle stage is *persisted* (snapshot.productionLifecycle). The others are heuristics/caches. See §4 for the parallel-stage risk.

---

## 2. Production State field → allowed source classification

Source taxonomy:
- **system-derived** — computed from authoritative stores, never authored;
- **creator-stated** — typed directly by the creator into a form/field;
- **creator-approved** — proposed by the model, explicitly approved (proposal/approval ledger);
- **ai-inferred** — derived by heuristics/LLM, not yet creator-confirmed;
- **session-only** — ephemeral per-request, not durable;
- **project-persisted** — durable in a writable store.

| Field | Candidate sources today | Allowed source(s) in 2.0 | Where it must NOT be duplicated |
|---|---|---|---|
| `title` | `projects.name` (`db.py:20`, write `routers/api.py:850`); `snapshot.title` (`schemas.py:73`); wiki `knownDetails` entry `wiki.py:440`; `project_decisions` title rename (`project_decisions.py:81-84`); decision explainability `projectTitle` (`project_decisions.py:107`) | **creator-stated / creator-approved** (`projects.name` is the ONLY writable store) | snapshot.title is a derived mirror (`snapshot.py:148,193`); wiki entry is a projection; never a 2.0 writable copy |
| `format` | `projects.primary_project_type` (`db.py:46`, authoritative); `snapshot.format` (`schemas.py:74`, set `snapshot.py:224`); `production_lifecycle.formatProfile` (`contracts.py:75`, derived `format_maps.py:81`); legacy `defaults_json.production_type` (deprecated, `db.py:45`) | **creator-stated / system-derived** — `primary_project_type` authoritative | `formatProfile` must stay derived, never independently written in 2.0 |
| `runtime` | No scalar store. Derived from `scenes.duration_sec` (`db.py:70`) or MAGI `durationFrames` (`magi/sequence/store.py:54`) | **system-derived** | never stored as a scalar in the projection |
| `fps` | `projects.fps` (`db.py:26`); `scenes.fps`/`fps_mode` (`db.py:87-88`); `ProjectOverviewData.fps` (`bible/domain/schemas.py:28`) | **creator-stated / system-derived** (project-level; scene overrides are separate) | bible overview `fps` is a typed mirror of project fps — one source |
| `primaryCharacter` | `snapshot.keyCharacters` (`schemas.py:78`); `production_lifecycle.characterCasting` (`contracts.py:38`); wiki `characters` section; `project_cache.characterIndex` (`project_cache.py:55`) | **creator-stated / creator-approved** — via character casting (`service.py:168`) or bible character entity approval | projection may reference `characterId`, must NOT re-persist character identity data |
| `tone` | `ProjectOverviewData.tone` (`bible/domain/schemas.py:24`); `creative_state` "Vision/Tone" substate (`creative_state.py:34,87`); wiki `creativeFoundation` | **ai-inferred → creator-approved** (proposal path) | do not copy into snapshot as truth; only approved bible entity is canon |
| `genre` | `ProjectOverviewData.genre` (`bible/domain/schemas.py:23`); `templates_presets` project types (`templates_presets/schema.py`) | **ai-inferred → creator-approved** | single bible field; no second genre store |
| `premise` | `creative_state` Vision/Premise (`creative_state.py:87`); wiki `creativeFoundation`; `discovery` living brief | **ai-inferred → creator-approved** | canon only after approved bible/knowledge entry |
| `logline` | `ProjectOverviewData.logline` (`bible/domain/schemas.py:25`); partnership pitch (`partnership/pitch.py`) | **creator-stated / ai-inferred → creator-approved** | bible is the only durable logline store |
| `shortSummary` / `longSummary` | `compiledWiki` story summary (`page_compiler.py`; `story_summary_editor/editor.py:268` writes `snapshot.compiledWiki`); `snapshot.projectSummary` via cache | **ai-inferred → creator-approved** (story-summary editor has refine/correct endpoints `routers/codirector.py:1056,1069`) | summary lives in `compiledWiki` cache + bible story pages; projection must recompose, not own summaries |
| `currentStage` | `snapshot.currentStage/currentSubstate` (`schemas.py:84-85`); `snapshot.productionLifecycle.currentStage` (`contracts.py:66`, persisted); `project_cache.developmentStage` (`project_cache.py:52`); `m214_project_stages` (`m214/store.py:54`); temperature/journey heuristics | **system-derived** from the authoritative lifecycle store (snapshot.productionLifecycle via `production_lifecycle/service.py`) — others are candidate evidence inputs only | MUST NOT write a parallel persisted stage (see §4 — 6+ parallel sources exist) |
| `conversationGoal` | `ProjectDirectorState.currentGoal` (`schemas.py:59`); `snapshot.activeGoal` (`schemas.py:97`); `project_cache.activeGoal` (`project_cache.py:53`); session `activeGoal` | **session-only / system-derived** (derived from intent `foundation/intent.py`) | do not persist as project canon; session-scoped |
| `workspace` / `activeSceneId` / `selectedAssets` | `session_context.py:84-90` (per-request); `project_cache.activeSceneId` (`project_cache.py:54`, cached) | **session-only** | projection may carry them; must not persist |
| `productionStatus` / `postStatus` | `contracts.py:70-72` inside lifecycle blob | **system-derived** from lifecycle store | no second copy |
| `decisionCount` / `recentDecisions` | `m211_decision_records` (`decisions.py:90` list); wiki `productionDecisions` | **system-derived** (read-only count) | derive from decision store, never cache a counter |

---

## 3. Per-field provenance + freshness invalidation attach points

> Where native mutation points must invalidate which projection fields. Each mutation point cites the authoritative store write; invalidation = recompute/refresh the listed projection fields from their authoritative stores (mirrors the existing cache pattern `project_cache.invalidate_cache_sections` at `conversation/project_cache.py:100`).

| Mutation point (file:line) | Native write | Projection fields invalidated |
|---|---|---|
| `routers/api.py:850` `update_project` (PATCH) | `projects.name/fps/width/height/primary_project_type` | title, format, fps, runtime-derived, overview/summary (project header) |
| `project_decisions.py:81-84` `apply_record_production_decision` | `Project.name` rename + `DecisionRecordStore.create` | title, recentDecisions, productionDecisions wiki section |
| `routers/api.py:892` POST / `:898` PATCH scenes; `scene_service.py:53` create / `:99` update_scene_fields | `scenes.*` incl. `summary`, `duration_sec`, `fps`, `director_json` | runtime (derived), scene count, timeline index, short/long summary (scene coverage) |
| `routers/api.py:1056` DELETE scene | scenes row removal | scene count, runtime, timeline |
| `character_identity/service.py:254` `update_profile` (rename `:290-305`) | `character_profiles.name` | primaryCharacter, characters index, character wiki/bible references |
| `character_identity/service.py:438` `approve_version` | version approval | character canon state (approved) |
| `character_identity/service.py:981` `approve_voice_profile` | voice approval | casting/voice readiness, characters index |
| `production_lifecycle/service.py:135` `advance_script_status` | `snapshot.productionLifecycle.scriptStatus` + stage | currentStage, scriptStatus, storyReady, productionStatus |
| `production_lifecycle/service.py:168` `set_character_cast_status` | lifecycle `characterCasting` status | primaryCharacter, castingStatus, currentStage |
| `production_lifecycle/service.py:216` `upsert_scene_readiness` | lifecycle `scenes` readiness | per-scene readiness, productionStatus, currentStage |
| `production_lifecycle/service.py:294` `mark_timeline_ready` / `:305` `mark_post_progress` / `:317` `run_final_qc` / `:330` `mark_complete` / `:344` `reopen_complete` | lifecycle status + currentStage | currentStage, production/post/QC status, handoffs |
| `bible/proposals.py:365` `ProposalService.approve` (→ `operations.apply_mutation_set:195`) | new immutable `production_bible_versions` + entities | bible revision, canon fields (tone/genre/logline/characters/locations/summary), bibleRevision cache |
| `bible/domain_service.py:245` `approve_entity` / `bible/api_domain.py:144` `approve_character` | entity lifecycle → approved | canon state, primaryCharacter, bibleRevision |
| `m211/decisions.py:22` `DecisionRecordStore.create` | `m211_decision_records` insert | recentDecisions, productionDecisions, decisionCount |
| `m211/decisions.py:117` `set_approval` / `m211/api.py:188` approve | decision approval_status | approvedDecisions, productionDecisions |
| `conversation/knowledge.py:52` `apply_wiki_candidates` (called at `orchestrate.py:634,734`; `notes/service.py:193`; `wiki_intelligence/*`) | `snapshot.knowledgeEntries` | wiki canon, characters/locations/story indexes, summaries, currentStage evidence |
| `notes/service.py:153` `promote_note_to_wiki` | knowledgeEntries + `compiledWiki` compile (`:220`) | wiki canon, wikiRevision, summaries |
| `wiki_intelligence/compiled/page_compiler.py:208,246` (compile) | `snapshot.compiledWiki` | compiled pages, short/long summary, TOC |
| `wiki_intelligence/correction/apply.py:187` / `undo.py:40` / `reorganize.py:552-556` | knowledgeEntries state changes | wiki canon, wikiRevision |
| `scriptwriter/store.py:135` `save_document` (elements_json) / `scriptwriter/service.py:257` `apply_codirector_proposal` | `script_documents_v2` elements | script status evidence, scene sync, runtime-from-script |
| `magi/sequence/store.py:138` `save_sequence` | `data/magi/sequences/{project}/sequence.json` | runtime, timeline index, MAGI readiness |
| `director_timeline_w46/service.py:83` `add_batch`, `:119` `duplicate_batch`, `:152` `delete_batch`; `orchestrator.py:562` `add_clip_to_batch` | `scenes.director_json.timelineMaster` | timeline index, batch/clip counts, MAGI handoff readiness |
| `magi/timeline_handoff.py` `export_to_timeline` (calls `add_clip_to_batch` `:160`) | timeline master clips | timeline index, post/assembly status |
| `image_pipeline/multi_shot/service.py:208` `create_plan`, `:293` `add_shot`, `:395` `add_candidate` | `multi_shot_*` tables | shot-plan index, per-shot approved asset lineage |
| `image_pipeline/store.py:55` `save_plan` | `data/image_pipeline/{project}/plans/*.json` | image-planning index |
| `m214/store.py:54` `upsert_stage` | `m214_project_stages` | (candidate evidence; if used, must not become truth — see §4) |

**Recommendation:** invalidate/recompute at the *authoritative* mutation points above (the stores the field must not duplicate). Existing invalidation primitives to reuse: `project_cache.invalidate_cache_sections(db, project_id, sections)` (`project_cache.py:100`), `snapshot` revision bump (`snapshot.py:163`).

---

## 4. Existing "second copy" risks (parallel canonical data)

### 4.1 Parallel STAGE sources — **HIGH RISK** (currentStage)

At least **6 distinct persisted/heuristic stage representations** coexist today:

| # | Stage source | Persisted? | Location |
|---|---|---|---|
| 1 | `ProjectProductionLifecycle.currentStage` (STORY…COMPLETE) | yes | `snapshot.productionLifecycle` (`contracts.py:66`; `production_lifecycle/service.py:44-48`) |
| 2 | `snapshot.currentStage/currentSubstate` (creative_state keyword-inferred) | yes | `conversation/schemas.py:84-85`; `creative_state.py:114`; `snapshot.py:149-151` |
| 3 | `snapshot.director.creativeStage/creativeSubstate` | yes | `conversation/schemas.py:65-66` |
| 4 | `ProjectIntelligenceCache.developmentStage` | yes | `conversation/project_cache.py:52` (settings_json cache) |
| 5 | `m214_project_stages.stage` (idea_first stages) | yes | `m214/store.py:54`; `m214/db.py` |
| 6 | `discovery/temperature.stage` (EMERGENCE→PRODUCTION) | heuristic (bundle persisted) | `conversation/discovery/temperature.py:16,38-86` |
| 7 | `partnership/journey.current_stage` (INITIAL_IDEA→…) | yes (partnership bundle) | `conversation/partnership/journey.py:14,40-42`; `partnership/persistence.py:71` |

**Finding:** the same nominal concept ("where is this project") is written in 5 durable places (#1, #2, #3, #4, #5) plus two keyword heuristics (#6, #7). A projection that recomposes *any* of these must pick **exactly one authoritative persisted stage** (`snapshot.productionLifecycle.currentStage` — the gated lifecycle, written only by `production_lifecycle/service.py` mutations) and treat the rest strictly as **candidate evidence / heuristics**. Any 2.0 code that writes a *new* persisted `stage` column/blob = direct Law 4 violation.

### 4.2 Parallel character copies — **MEDIUM RISK**

Character identity exists in: `character_profiles` (canon, §1.2), `production_bible_entities` character mirror (`db.py:243`), `snapshot.keyCharacters` list (`schemas.py:78`), wiki `characters` section (projection), `project_cache.characterIndex` (`project_cache.py:55`), `production_lifecycle.characterCasting` (`contracts.py:38`). **Two durable stores** (`character_profiles` vs bible character entities) plus two caches. Projection must treat `character_profiles` as the identity canon and bible entities as canon-content, never write a third character list.

### 4.3 Parallel title copies — **LOW/MEDIUM RISK**

`projects.name` (canon) vs `snapshot.title` (`schemas.py:73`) vs wiki `project-title` entry (`wiki.py:440`) vs decision `explainability.projectTitle` (`project_decisions.py:107`). The decision tool already writes `Project.name` directly (`project_decisions.py:81-84`) — good, single source; the other copies are projections and must not become writable.

### 4.4 Parallel format copies — **MEDIUM RISK**

`projects.primary_project_type` (canon, `db.py:46`) vs `defaults_json.production_type` (deprecated soft metadata, `db.py:45`) vs `snapshot.format` (`schemas.py:74`) vs `formatProfile` (`contracts.py:75`, derived) vs `templates_presets` `resolved_profile_json` (`db.py:48`). `formatProfile` is computed via `format_maps.py:81` — keep derived.

### 4.5 Parallel timeline copies — **MEDIUM RISK**

W46 `scenes.director_json.timelineMaster` (canon per scene) vs MAGI `data/magi/sequences/*/sequence.json` (canon per project edit) vs legacy `director_sequences`/`editor_projects` (`editor_sequences.py:27,41`) vs `settings_json["timeline"]` (explicitly **non-authoritative** per `magi/timeline_handoff.py:14-15`). Two genuinely writable timeline stores with different contracts; projection must reconcile by the W46↔MAGI handoff contract, never a third timeline store.

### 4.6 Parallel wiki/canon copies — **LOW RISK (already projection-designed)**

`snapshot.knowledgeEntries` (canon) vs `snapshot.compiledWiki` (cached projection, `page_compiler.py`) vs `m211_memory_items` (`m211/memory.py:20` `ProductionMemoryStore` — a *separate* durable note store that can shadow canon) vs `notes.workingNotes` (`schemas.py:88`). The architecture already declares `knowledgeEntries` as `sourceOfTruth` (`wiki.py:415,542`); keep it that way and treat `m211_memory_items` as a side ledger, not canon.

### 4.7 Parallel discovery/relationship bundles — **LOW RISK**

`settings_json` carries many independent bundles: `projectIntelligence` (`snapshot.py:13`), `discoveryIntelligence` (`discovery/persistence.py:13`), `companionIntelligence` (`companion/persistence.py:14`), partnership bundle (`partnership/persistence.py:71`), relationship profile (`relationship/persistence.py:61`), `projectIntelligenceCache` (`project_cache.py:12`), `library` (`project_library/service.py:52`), `projectType` (`templates_presets/project_types.py:191`), `creativeConfidence` (`creative_confidence.py:65`), momentum (`momentum.py:67`). All share one JSON blob (`projects.settings_json`) — a full-project rewrite of `settings_json` (e.g., `project_library/_save_settings`, snapshot saves) is a **read-modify-write collision point**. Projection must be defensive: load-modify-save must merge, never clobber sibling keys.

---

## 5. Summary of projection rules (Law 4 conformance)

1. **Title/format/fps** → read-only from `projects`; never write a projection copy.
2. **Stage** → single authoritative persisted source = `snapshot.productionLifecycle.currentStage`; all others (#2-#7 in §4.1) are evidence inputs, never written by 2.0.
3. **Canon content (characters/locations/tone/genre/logline/summary)** → read-only from `production_bible_entities` (approved lifecycle) + `knowledgeEntries`; projection composes, does not store.
4. **Decisions** → read-only from `m211_decision_records` + `codirector_approvals`.
5. **Timeline/runtime** → derived from `scenes.director_json.timelineMaster` + `magi/sequence/store.py` via the handoff contract.
6. **Session fields (workspace/activeScene/selection/goal)** → session-only, never persisted.
7. **Invalidation** → attach at the mutation points in §3 (reuse `invalidate_cache_sections` + snapshot revision).
