# Co-Director 2.0 — Script Writer / Wiki UI Audit

**Milestone:** Co-Director 2.0 — Professional Creative Producer Intelligence (frozen architecture)
**Audit domain:** Script Writer integration into the creator workflow (Story destination), Story/Production dropdowns in the Wiki UI, verified "Open Script Writer" navigation
**Auditor role:** READ-ONLY Phase 1 audit subagent (no product code modified)
**Status:** Phase 1 audit complete — findings only. Subagent returns `READY FOR PRIMARY REVIEW`.

---

## 0. Executive summary

The 2.0 architecture goal is to **reuse, not rebuild**. The audit finds:

- **Backend Script Writer is real and complete.** All 15 modules in `studio-api/app/scriptwriter/` exist and are wired (`app/main.py:286-291`). 28 REST routes under `/api/projects/{project_id}/scriptwriter`, a per-project document store, Fountain import/export, PDF export, continuity checks, Bible detection, undoable transactions, revision sets, and migration from the legacy `script_storyboard` model are all present.
- **Co-Director script tools exist and are proposal-gated.** `codirector/tools/handlers/scriptwriter_tools.py` registers 9 read tools + 7 mutating (MutationHandler) tools (`tools/registry.py:202-211, 705-725`). All mutations flow through preview → proposal → approval → `apply_codirector_proposal`.
- **Frontend Script Writer exists AND is reachable** as a first-class project workspace (`?workspace=scriptwriter`), Production menu entry, and workspace registry entry — but **not reachable from the Wiki UI / Co-Director navigation**. There is no "Open Script Writer" action anywhere in the Co-Director frontend; the backend's `recommended_action="open_scriptwriter"` hint is dead (never dispatched).
- **Wiki UI dropdowns** (Story / Production groups in the Project Content tab bar) render but carry real defects: CSS clipping (`overflow`), stale-open state, no click-outside/Escape close, no keyboard menu contract, and a `normalizeContentTab` coercion that makes the `production` and `development` panels unreachable.

---

## 1. Backend inventory — `studio-api/app/scriptwriter/`

All files verified present on disk. Router registered under `/api` at `studio-api/app/main.py:286-291` (wrapped in try/except — silent absence if import fails, see Risk R8).

### 1.1 `api.py` (295 lines) — HTTP API surface
Role: FastAPI router (`prefix="/projects/{project_id}/scriptwriter"`, `api.py:17`). 28 routes:

| Route | File:line | Purpose |
|---|---|---|
| `GET ""` | `api.py:99-105` | Get-or-create the default document + full bundle (stats, navigator, continuity, bible candidates, revisions, transactions, transitions, recovery) |
| `GET /documents` | `api.py:108-113` | List all script documents for the project |
| `GET /documents/{id}` | `api.py:116-121` | Full document bundle |
| `POST /documents/{id}/autosave` | `api.py:124-129` | Autosave element batch with optimistic-revision check |
| `POST /documents/{id}/scenes/insert` | `api.py:132-137` | Insert scene heading + action |
| `POST /documents/{id}/scenes/delete` | `api.py:140-145` | Delete scene (omits when production numbers locked) |
| `POST /documents/{id}/scenes/move` | `api.py:148-153` | Reorder scene block |
| `POST /documents/{id}/revisions` | `api.py:156-161` | Snapshot a revision set (blue/pink/etc.) |
| `POST /documents/{id}/revisions/compare` | `api.py:164-169` | Diff two revision snapshots |
| `POST /documents/{id}/revisions/restore` | `api.py:172-177` | Restore snapshot as an undoable tx |
| `POST /documents/{id}/import` | `api.py:180-185` | Fountain/plain import |
| `GET /documents/{id}/export/fountain` | `api.py:188-193` | Fountain export |
| `POST /documents/{id}/export/pdf` | `api.py:196-203` | PDF export → `artifacts/m47/pdf` |
| `POST /documents/{id}/proposals/apply` | `api.py:206-211` | **Co-Director proposal application** |
| `POST /documents/{id}/outline/convert` | `api.py:214-219` | Outline beats → scenes |
| `POST /documents/{id}/scenes/link` | `api.py:222-227` | Link script scene ↔ project scene |
| `POST /documents/{id}/timeline/prepare` | `api.py:230-235` | Build Timeline prep proposal (no clip auto-apply) |
| `POST /documents/{id}/timeline/apply-metadata` | `api.py:238-243` | Store timeline prep metadata + mark synced |
| `POST /documents/{id}/analyze/scene` | `api.py:246-251` | Scene analysis |
| `POST /documents/{id}/production-lock` | `api.py:254-259` | Lock/unlock production scene numbers |
| `POST /documents/{id}/undo` | `api.py:262-267` | Undo last reversible transaction |
| `POST /documents/{id}/search-replace` | `api.py:270-277` | Typed search/replace |
| `POST /documents/{id}/bible/propose` | `api.py:280-285` | Bible entity proposals (never silent write) |
| `GET /migration/preview` | `api.py:288-290` | Legacy migration preview |
| `POST /migration/run` | `api.py:293-295` | Run legacy migration |

Errors: `api.py:20-21` maps `ScriptwriterError` → HTTP 400 with `{code, message, details, recoveryAction}`.

### 1.2 `service.py` (626 lines) — orchestration layer
Role: all business logic. Key functions:

| Function | File:line | Purpose |
|---|---|---|
| `get_or_create_document` | `service.py:49-67` | Returns `docs[0]` (latest-updated) or migrates legacy then creates blank doc |
| `autosave_elements` | `service.py:77-100` | Optimistic-revision autosave; conflict → recovery blob + `SCRIPT_CONFLICT` |
| `insert_scene` | `service.py:103-121` | Scene insert with scene numbering |
| `delete_scene` | `service.py:124-147` | Delete or omit-if-locked |
| `move_scene` | `service.py:150-172` | Reorder blocks |
| `create_revision_set` / `compare_revisions` / `restore_revision` | `service.py:175-224` | Revision snapshot lifecycle |
| `import_text` | `service.py:227-237` | Fountain parse → elements |
| `export_fountain` / `export_pdf_file` | `service.py:240-254` | Exports |
| `apply_codirector_proposal` | `service.py:257-291` | Applies op `replace/insert/delete` or full-element array; records tx `source="codirector"`; honors `element.locked` |
| `convert_outline_to_scenes` | `service.py:294-323` | Beat → scene conversion |
| `link_scene` | `service.py:326-344` | Scene-link + `sceneSync` status |
| `prepare_timeline` | `service.py:347-406` | Timeline prep proposal (read-only, `appliesClipsAutomatically: False`) |
| `apply_timeline_prep_metadata` | `service.py:409-421` | Persist prep metadata, mark `synced` |
| `analyze_scene` | `service.py:424-443` | Heuristic analysis |
| `lock_production_numbers` | `service.py:446-452` | Lock + renumber |
| `navigator_scenes` | `service.py:455-474` | Navigator index (pages est., continuity count, sync status) |
| `document_bundle` | `service.py:477-494` | Full API payload |
| `undo` | `service.py:497-499` | Delegates to transaction layer |
| `propose_bible_entities` | `service.py:502-528` | Creates Bible **proposals** via `ProposalService` |
| `search_replace` | `service.py:531-553` | Typed replace |

### 1.3 `store.py` (336 lines) — SQLAlchemy persistence
Tables: `script_documents_v2` (`store.py:27-45`), `script_transactions` (`48-60`), `script_revision_snapshots` (`63-74`), `script_notes` (`77-88`), `script_migration_backups` (`91-98`). Key functions: `ensure_scriptwriter_tables` (`101-111`), `save_document` (`135-158`), `load_document` (`161-163`), `list_documents` (`166-173`, per `project_id`, newest-first), `save_transaction`/`list_transactions` (`176-220`), `latest_reversible` (`223-227`), `save_revision`/`list_revisions`/`load_revision` (`230-289`), recovery get/set/clear (`292-310`), migration backups (`313-332`).

### 1.4 `models.py` (168 lines) — Pydantic models
`ScriptDocument` (`87-102`) with `projectId`, `elements`, `revision`, `revisionSetId`, `productionNumbersLocked`, `sceneSync`; `ScriptElement` (`72-84`) with `type` (12 screenplay types, `24-37`), `sceneId`, `characterId`, `sceneNumber`, `revisionColor`, `locked`, `omitted`, `metadata`; `ScriptTransaction` (`105-116`) with `source: TransactionSource` (`38`, `creator/codirector/migration/import/system`); `ScriptRevisionSnapshot` (`119-129`); `ScriptNote` (`132-141`) with `author` default `"creator"`; `ScriptStats` (`144-152`); `DEFAULT_REVISION_COLORS` (`155-167`).

### 1.5 `fountain.py` (119 lines) — Fountain import/export
`parse_fountain` (`fountain.py:17-79`) regex-based line parser (scene heading, transition, character, parenthetical, dialogue, note, section, act_break, action). `to_fountain` (`82-118`) serializer.

### 1.6 `pdf_export.py` (104 lines) — PDF export
`export_pdf` (`pdf_export.py:13-104`) — reportlab if importable; **honest fallback**: writes `.fountain.txt` and raises `SCRIPT_EXPORT_FAILED` (`95-103`) if reportlab absent. Risk R9.

### 1.7 `transactions.py` (113 lines) — undoable transaction layer
`commit_transaction` (`transactions.py:22-67`) snapshots `beforeElements` + `beforeSceneSync` into payload, bumps revision, records row. `undo_last` (`70-109`) restores before-state, marks original `undone`. `history` (`112-113`).

### 1.8 `continuity.py` (70 lines) — continuity checks
`analyze_continuity` (`continuity.py:10-70`) heuristic findings: consecutive same-location (`SAME_LOCATION_SEQUENCE`), dialogue without prior character cue (`DIALOGUE_BEFORE_CHARACTER_CUED`), similar opening phrasing (`SIMILAR_OPENING_DIALOGUE`). Documented as recommendations, not judgments.

### 1.9 `bible_detect.py` (45 lines) — Bible entity detection
`detect_entities` (`bible_detect.py:13-45`) extracts characters and locations from elements. Never writes — feeds proposals.

### 1.10 `stats.py` (38 lines) — statistics
`compute_stats` (`stats.py:8-38`) word/page/runtime estimates (runtime always labeled estimated).

### 1.11 `migration.py` (204 lines) — legacy `script_storyboard` migration
`preview_migration` (`migration.py:33-66`), `run_migration` (`69-145`) convert `script_docs`/`script_segments` (`..script_storyboard`) → `ScriptDocument`, with full backup (`save_migration_backup`) + migration transaction. `_segments_to_elements` (`148-204`) type-maps legacy segment types.

### 1.12 `transitions.py` (53 lines) — screenplay typing rules
`ENTER_NEXT` (`transitions.py:8-21`), `TAB_CYCLE` (`24-31`), `next_on_enter`/`cycle_type` (`34-43`), `SHORTCUT_MAP` (`46-52`).

### 1.13 `errors.py` (39 lines) — typed errors
`ScriptwriterError` dataclass (`errors.py:26-39`) with `code/message/details/recovery_action`. Codes at `errors.py:9-23`.

### 1.14 `__init__.py` (6 lines)
Exposes `scriptwriter_router`, `ensure_scriptwriter_tables`.

---

## 2. Co-Director script tools — `codirector/tools/handlers/scriptwriter_tools.py` (346 lines)

### 2.1 Read-only tools (kind="read", registry `tools/registry.py:202-211`; definitions `tools/definitions.py`)

| Tool | Handler | Purpose |
|---|---|---|
| `script.inspect` | `scriptwriter_tools.py:45-58` | Doc summary + stats |
| `script.scene_context` | `scriptwriter_tools.py:61-75` | Full element block for a scene |
| `script.character_context` | `scriptwriter_tools.py:78-99` | Dialogue lines per character (voice guidance, non-stereotyping note) |
| `script.analyze_structure` | `scriptwriter_tools.py:102-114` | Navigator-based act estimate |
| `script.analyze_scene` | `scriptwriter_tools.py:117-120` | Delegates `service.analyze_scene` |
| `script.analyze_dialogue` | `scriptwriter_tools.py:123-136` | Dialogue metrics + recommendations |
| `script.analyze_continuity` | `scriptwriter_tools.py:139-146` | Continuity findings |
| `script.suggest_revision` | `scriptwriter_tools.py:149-168` | Suggestion only — explicit note "apply via script.propose_replace after review" (`165`) |
| `script.generate_outline` / `script.generate_beat_sheet` | `scriptwriter_tools.py:171-185` | Derived outlines |

### 2.2 Mutating tools (MutationHandler = preview + apply, kind="mutating")

Registered at `tools/registry.py:705-725` as `MutationHandler(preview_*, apply_*)`; definitions at `tools/definitions.py:1572-1610+` mark them `kind="mutating"`, `pinned_resources=("project",)`.

| Tool | Preview / Apply | Purpose |
|---|---|---|
| `script.propose_insert` | `scriptwriter_tools.py:198-215` | insert element → `apply_codirector_proposal` |
| `script.propose_replace` | `scriptwriter_tools.py:218-233` | replace element text |
| `script.propose_delete` | `scriptwriter_tools.py:236-243` | delete element |
| `script.propose_scene` | `scriptwriter_tools.py:246-262` | insert scene (via `service.insert_scene`) |
| `script.convert_outline_to_scenes` | `scriptwriter_tools.py:265-287` | outline beats → scenes |
| `script.sync_production_bible` | `scriptwriter_tools.py:290-327` | creates Bible **proposals** only (`appliesAutomatically: False`) |
| `script.prepare_timeline` | `scriptwriter_tools.py:330-345` | timeline prep proposal + metadata (no clip auto-apply) |

**Proposal/approval flow — confirmed.** All script mutations are preview+apply `MutationHandler`s; `ToolPreview` warnings state "Applies only after approval via ScriptTransaction" (`scriptwriter_tools.py:188-195`). The apply path records a `ScriptTransaction` with `source="codirector"` (`service.py:290`). Additionally `scriptwriter_tools.py:16-38` (`_doc_id`) resolves `documentId`/`scriptId` or falls back to the project's first document; when **no document exists** it raises `TOOL_TARGET_NOT_FOUND` with `recommended_action="open_scriptwriter"` (`scriptwriter_tools.py:22-28`).

### 2.3 Existing "Open Script Writer" signaling — backend only, currently dead
- Only reference: `scriptwriter_tools.py:27` `recommended_action="open_scriptwriter"` in the no-document error path.
- The frontend preserves `recommendedAction` as a string (`api.ts:766-767`, `classifyCoDirectorError` `api.ts:730-799`) but **never dispatches navigation** on it. No `uiAction: "open_scriptwriter"` is emitted by any tool (contrast `audio_studio_tools.py:284-285` and `voice_performance.py:115-118` which emit `uiAction` + `workspaceUrl`).
- No `open_scriptwriter` branch in `CoDirectorSession.tsx` tool-result handling (`1710-1762` handles only `open_voice_performance`, `open_voice_creator`, `open_audio_studio`, `_uiFocus`→timeline).

---

## 3. Project ↔ Script relationship

### 3.1 Model
- **Multiple documents per project are supported** by the store (`list_documents` filters on `project_id`, `store.py:166-173`).
- **But the studio uses only the first document.** `service.get_or_create_document` returns `docs[0]` (`service.py:49-53`), and `ScriptwriterStudio.tsx` calls `api.scriptwriter.studio(project.id)` (`ScriptwriterStudio.tsx:76`), which hits `GET /api/projects/{project_id}/scriptwriter` → `get_or_create_document` → `docs[0]`. The `/documents` list endpoint (`api.py:108-113`) is called only by `AvatarStudioWorkspace.tsx:501` — there is **no document selector in the Script Writer UI**. Effectively 1 active script per project today.
- Legacy model: `script_docs`/`script_segments` (`script_storyboard.py:45-83`), one default doc per project (`get_or_create_script_doc` returns first, `script_storyboard.py:230-243`). Migrated on first access (`migration.py:69-145`).
- **Scene linkage:** script scene ↔ project scene via `service.link_scene` (`service.py:326-344`) and `ScriptElement.sceneId` (`models.py:77`); sync status in `ScriptDocument.sceneSync` (`models.py:98`).

### 3.2 Revisions
Revision sets + color snapshots: `create_revision_set`/`compare_revisions`/`restore_revision` (`service.py:175-224`), persisted in `script_revision_snapshots` (`store.py:63-74`), plus undoable transaction history (`transactions.py`).

### 3.3 Author attribution (creator-authored vs AI-drafted)
- **Transaction-level only.** `ScriptTransaction.source` ∈ `creator|codirector|migration|import|system` (`models.py:38`, recorded at `service.py:98,120,…290`). Autosave/creator edits → `source="creator"`; proposal apply → `source="codirector"`.
- **No persistent per-element or per-document author field.** `ScriptElement` (`models.py:72-84`) and `ScriptDocument` (`87-102`) have none. Only `ScriptNote.author` defaults to `"creator"` (`models.py:140`, `store.py:87`).
- **Gap for 2.0:** "creator-authored vs AI-drafted" is reconstructible only by replaying `script_transactions`, not by inspecting the document. ADAPT/EXTEND required if persistent attribution is a requirement.

### 3.4 Verbatim storage of creator-pasted content
- **Not stored verbatim as raw text.** Pasting → `import_text` → `parse_fountain` (`service.py:227-237`, `fountain.py:17-79`) → structured `ScriptElement[]`.
- Typed editor content → autosave stores elements **exactly as the frontend sends them** (element-level, structured) via `autosave_elements` (`service.py:94-100`).
- Legacy `import_plain_text` (`script_storyboard.py:250-309`) also tokenizes into segments.
- `script_documents_v2` has no raw-text column (`store.py:27-45`) — only `elements_json`. If 2.0 requires a verbatim creator source copy, that is a NEW capability (EXTEND).

---

## 4. Frontend — Wiki UI

### 4.1 Where the Wiki UI lives
- Route `/co-director` → `pages/CoDirectorPage.tsx` → `CoDirectorFullScreen` → `CoDirectorShell` (`components/CoDirector/CoDirectorShell.tsx`) → `CoDirectorProjectContent` (secondary SplitPane, `CoDirectorShell.tsx:268`).
- The **Wiki tab bar** is `CoDirectorProjectContent.tsx:226-296` driven by `CONTENT_NAV` (`navEntries.ts:40-65`). Tab state managed in `CoDirectorShell` (`contentTabState`, `CoDirectorShell.tsx:91`, persisted to localStorage `adept_codirector_content_tab`, `CoDirectorShell.tsx:29,50-64`; reset to `"wiki"` on project switch, `CoDirectorShell.tsx:130-132`).

### 4.2 Tab architecture (CONTENT_NAV)
- Tabs (direct): `wiki`, `notes`, `casting`, `library` (`navEntries.ts:41-43,54`).
- **Story group** (`navEntries.ts:44-53`): children `vision` (Vision), `pitch` (Pitch & Launch), `bible` (Bible).
- **Production group** (`navEntries.ts:55-64`): children `plans` (Plans), `approvals` (Approvals), `jobs` (Jobs).
- Comment at `navEntries.ts:39`: "Story/Production are groups, not pages."
- Panels rendered by `tab` in `CoDirectorProjectContent.tsx:298-429` (`wiki` → `ProjectWikiPanel`, `notes` → `NotesPanel`, `casting` → `CastingPanel`, `library` → `ProjectRetrievalPanel`, `production` → `StageList`, `plans`, `bible`, `approvals`, `jobs`, `development`, `vision`, `pitch`).
- Wiki content itself: `ProjectWikiPanel.tsx` (section grid, TOC, export, refine/reorganize/rebuild, compiled-pages mode via `wiki/CompiledWikiReader.tsx`).

### 4.3 Story dropdown — what it does and failure analysis
Rendering: `CoDirectorProjectContent.tsx:246-294`. Trigger button (`item.id === "story"`) toggles `openGroup` (`:255`); expanded → absolute-positioned `role="menu"` (`:259-292`) with `role="menuitem"` children (Vision, Pitch & Launch, Bible). Child click → `onTabChange(child.id); setOpenGroup(null)` (`:282-285`).

**What it does today:** opens/closes a menu on click; children navigate to Vision/Pitch/Bible panels. It does **not** contain a Script Writer entry.

**What could break it / defects:**

| # | Defect | Citation | Impact |
|---|---|---|---|
| D1 | **CSS clipping.** The menu is `position:absolute; top:100%` inside `.codirector-content-tabs` which sets `overflow-x:auto`; per CSS, `overflow-y` computes to `auto`, clipping or scroll-embedding the menu instead of overlaying. Parent `.codirector-workspace-content` is `overflow:hidden`. | `codirector-cinematic.css:509` (`.codirector-workspace-content`), `:517-523` (`.codirector-content-tabs { overflow-x:auto }`), menu at `CoDirectorProjectContent.tsx:263-273` | Menu items below the tab row can be cut off or the tabs row scrolls vertically instead of the menu showing as an overlay. |
| D2 | **Stale-open state.** `openGroup` is not cleared when another tab is selected — clicking "Wiki"/"Notes"/etc. calls `onTabChange(item.id)` (`:237`) but leaves `openGroup` set. | `CoDirectorProjectContent.tsx:227-241` vs `:243-294` | The Story (or Production) menu remains open while the user has navigated to another panel. |
| D3 | **No click-outside / Escape to close.** Menu closes only by re-clicking the trigger (`:255`) or selecting a child (`:282-285`). No document-level click listener, no `onKeyDown`/Escape. | `CoDirectorProjectContent.tsx:243-294` | Menu can stay open and overlap content; pointer users must find the trigger again. |
| D4 | **Keyboard-access gaps.** `role="menu"`/`role="menuitem"` (`:260,:278`) and `aria-haspopup`/`aria-expanded` (`:250-251`) are set, but there is no arrow-key navigation, no Escape handler, no focus management, and the menu is `div`-based (`:259-291`) — screen-reader/keyboard contract is incomplete. | `CoDirectorProjectContent.tsx:250-291` | Tab+Enter can open it (native Button), but once open, keyboard users cannot move within it or dismiss it reliably. |
| D5 | **`normalizeContentTab` coercion makes the "Production" *page* unreachable.** `setContentTab` normalizes `"production"` → `"wiki"` and `"development"` → `"wiki"`. So the `tab === "production"` panel (`StageList`, `:356-361`) and `tab === "development"` panel (`:427`) can never be shown via `onTabChange`. `CoDirectorStageStrip` also calls `setContentTab("production")` (`CoDirectorShell.tsx:164-168`) — that lands on Wiki. Group children (`plans/approvals/jobs`) are unaffected (allowed list `CoDirectorShell.tsx:33-45`). | `CoDirectorShell.tsx:31-48`; stage-strip call `CoDirectorShell.tsx:164-168`; dead panels `CoDirectorProjectContent.tsx:356-361, 427` | "Production" top-level is misleading; `StageList`/`Development` are dead code today. |

### 4.4 Production dropdown
Same renderer (`CoDirectorProjectContent.tsx:246-294`, `item.id === "production"`), children Plans/Approvals/Jobs (`navEntries.ts:59-63`). All children are in the allowed list (`CoDirectorShell.tsx:33-45`), so the menu's items resolve correctly. Same defects D1–D4 apply; D5 applies to the *page* target only.

### 4.5 Script Writer frontend availability
**The Script Writer frontend EXISTS and IS reachable — but not from the Wiki UI.**
- `components/scriptwriter/ScriptwriterStudio.tsx` (669 lines) — full TipTap screenplay studio (autosave, navigator, inspector, revisions, compare, fountain/pdf export, Co-Director proposal panel, timeline prep, bible candidates, search/replace, command palette). Wired as a project workspace tab: `ProjectEditor.tsx:737-743`.
- Reachable via:
  - URL `/project/:id?workspace=scriptwriter` — route resolver `ProjectEditor.tsx:537-557` + `go()` push `:564-580`.
  - Production menu entry "Scriptwriter" (`core/productionMenu.ts:226-234`, category `pre-production`).
  - Workspace registry `workspaces.ts:428-439` (`futureDestination: "story"`, `commandPalette: true`).
  - `onGo("scriptwriter")` callers: `AvatarStudioWorkspace.tsx:1538,2285`; `storyboard-studio/StoryboardStudio.tsx:184`; `GenerationToolsHub.tsx:229-233` ("Open Scriptwriter workspace").
- **Not reachable from the Wiki UI:** the Wiki tab bar (Story group children = Vision/Pitch/Bible; Production group children = Plans/Approvals/Jobs) has **no Script Writer entry**, and there is no "Open Script Writer" action in the Co-Director session tool-result handling (`CoDirectorSession.tsx:1710-1762`).

---

## 5. Ideal integration point for "Open Script Writer" navigation

The product already has a canonical navigation channel — **mirror the voice/audio pattern**.

**Backend (add):**
- `scriptwriter_tools.py` handlers should return `uiAction: "open_scriptwriter"` + `workspaceUrl: f"/project/{ctx.project_id}?workspace=scriptwriter"` (mirror `audio_studio_tools.py:284-285`, `voice_performance.py:115-118`, `voice_environment.py:79-80`). The `recommended_action="open_scriptwriter"` error hint (`scriptwriter_tools.py:27`) stays, but a positive-path action is required.

**Frontend (add, one branch):**
- `CoDirectorSession.tsx:1713-1762` — add `if (uiAction === "open_scriptwriter")`: prefer `navigate(result.workspaceUrl)` (navigate is in scope, used at `:1718`), else `bindingsRef.current.onGoTab?.("scriptwriter")` (binding available via `useBindCoDirectorWorkspace`, `CoDirectorSession.tsx:3191-3211`; supplied by `ProjectEditor.tsx:855-866` and `pages/Home.tsx:153`).
- Target already renders: `ProjectEditor.tsx:737-743` (`tab === "scriptwriter"` → `ScriptwriterStudio`), URL `/project/:id?workspace=scriptwriter`.

**Wiki UI (optional, product decision):** add a Script Writer entry to the Story group children in `navEntries.ts:44-53` (Story is the declared 2.0 "Story destination"), which requires no new machinery — group children already render through `CoDirectorProjectContent.tsx:275-290`.

---

## 6. Classification matrix

| Component | Current Role | File/Function citations | Classification | Target Role in 2.0 | Risk |
|---|---|---|---|---|---|
| `scriptwriter/api.py` | REST surface (28 routes) | `api.py:17,99-295`; wired `main.py:286-291` | **KEEP** | Reuse as-is; unchanged | Low (conditional import at `main.py:286-291` can silently drop the router) |
| `scriptwriter/service.py` | Orchestration | `service.py:49-67,77-100,257-291,347-406,477-494` | **KEEP** (EXTEND for attribution) | Reuse; add persistent author/source attribution if 2.0 requires per-element provenance | Med — no per-element author today (see 3.3) |
| `scriptwriter/store.py` | Persistence | `store.py:27-45,101-111,135-173` | **KEEP** | Reuse | Low |
| `scriptwriter/models.py` | Domain models | `models.py:38,72-102,105-141` | **KEEP** (EXTEND for `author`/`origin`) | Reuse; add author/source fields for creator vs AI attribution | Med — author gap |
| `scriptwriter/fountain.py` | Fountain parse/serialize | `fountain.py:17-79,82-118` | **KEEP** | Reuse for import/export | Low |
| `scriptwriter/pdf_export.py` | PDF export | `pdf_export.py:13-104` | **KEEP** | Reuse | Med — reportlab optional; falls back to `.fountain.txt` + error (`95-103`) |
| `scriptwriter/transactions.py` | Undo/transaction layer | `transactions.py:22-67,70-109` | **KEEP** | Reuse; source-tagging already present | Low |
| `scriptwriter/continuity.py` | Continuity checks | `continuity.py:10-70` | **KEEP** | Reuse (advisory only) | Low |
| `scriptwriter/bible_detect.py` | Bible entity detection | `bible_detect.py:13-45` | **KEEP** | Reuse (proposal-only) | Low |
| `scriptwriter/stats.py` | Stats | `stats.py:8-38` | **KEEP** | Reuse | Low |
| `scriptwriter/migration.py` | Legacy migration | `migration.py:33-145,148-204` | **KEEP** (SUPERSEDE once legacy retired) | Reuse; retire after all legacy rows migrated | Low-Med |
| `scriptwriter/transitions.py` | Typing rules | `transitions.py:8-52` | **KEEP** | Reuse | Low |
| `scriptwriter/errors.py` | Typed errors | `errors.py:26-39` | **KEEP** | Reuse | Low |
| `codirector/.../scriptwriter_tools.py` | Co-Director script tools (9 read + 7 mutating, proposal-gated) | `scriptwriter_tools.py:45-345`; registry `tools/registry.py:202-211,705-725`; defs `tools/definitions.py:1543-1610+` | **KEEP + EXTEND** | Reuse; **add `uiAction:"open_scriptwriter"` + `workspaceUrl`** for verified navigation | Med — "Open Script Writer" is today only a dead `recommended_action` (`:27`) |
| `ScriptwriterStudio.tsx` | Full screenplay studio frontend | `ScriptwriterStudio.tsx:21-180,353-669`; wired `ProjectEditor.tsx:737-743` | **KEEP** | Reuse as the 2.0 Script Writer | Low — single-document UX (no selector; uses `docs[0]`) |
| `workspaces.ts` (`scriptwriter` entry) | Workspace registry | `workspaces.ts:428-439`; `resolveWorkspace` `:480-492` | **KEEP** | Reuse (canonical `scriptwriter` id, `futureDestination:"story"`) | Low |
| `productionMenu.ts` (Scriptwriter entry) | Production menu catalog | `productionMenu.ts:226-234` | **KEEP** | Reuse | Low |
| `pages/ProjectEditor.tsx` (scriptwriter tab + `go`) | Workspace routing/render | `ProjectEditor.tsx:537-580,737-743`; `go` `:564-580` | **KEEP** | Reuse as the navigation target (`?workspace=scriptwriter`) | Low |
| `CoDirectorSession.tsx` (tool-result uiAction) | Co-Director → workspace navigation channel | `CoDirectorSession.tsx:1710-1762`; bindings `:3191-3211` | **EXTEND** | Add `open_scriptwriter` branch (mirror `open_audio_studio` `:1735-1749`) | Med — missing action today |
| `navEntries.ts` (CONTENT_NAV) | Wiki tab architecture | `navEntries.ts:40-65` | **ADAPT** | Add Script Writer under Story group (Story = 2.0 script destination); fix label/availability | Med |
| `CoDirectorProjectContent.tsx` (tab bar + dropdowns) | Story/Production dropdowns | `CoDirectorProjectContent.tsx:226-296` | **ADAPT** | Fix D1–D4: overflow-safe menu, close-on-outside/Escape, keyboard contract, clear `openGroup` on tab change | Med-High — dropdown UX defects |
| `CoDirectorShell.tsx` (`normalizeContentTab`) | Tab state normalization | `CoDirectorShell.tsx:29-64,164-168` | **ADAPT** | Remove `production`/`development` → `wiki` coercion or render `StageList`; fix `CoDirectorStageStrip` target | Med — dead panels `:356-361,427` |
| `ProjectWikiPanel.tsx` + `wiki/CompiledWikiReader.tsx` | Wiki content panel | `ProjectWikiPanel.tsx:140-220,298-429,854-898`; `CompiledWikiReader.tsx:20+` | **KEEP** | Reuse | Low |
| `api.ts` (`scriptwriter` client) | Frontend API client | `api.ts:4713-4910` | **KEEP** | Reuse (all 28 routes typed) | Low |

---

## 7. Top risks

1. **R1 — "Open Script Writer" is not wired end-to-end.** Backend only exposes `recommended_action="open_scriptwriter"` on a no-document error (`scriptwriter_tools.py:27`); the frontend never dispatches it (`api.ts:730-799` preserves it as text; `CoDirectorSession.tsx:1710-1762` has no branch). Verified navigation does not exist today.
2. **R2 — Wiki dropdown defects.** Story/Production dropdown menus are clipped by `overflow` (`codirector-cinematic.css:509,517-523`), do not close on outside click/Escape, leave `openGroup` stale when switching tabs, and lack a keyboard menu contract (`CoDirectorProjectContent.tsx:243-294`). D1 is the most likely to cause an actual "won't open" symptom under narrow panes.
3. **R3 — `normalizeContentTab` coercion.** `"production"` and `"development"` map to `"wiki"` (`CoDirectorShell.tsx:31-48`), making `StageList` (`CoDirectorProjectContent.tsx:356-361`) and `Development` (`:427`) unreachable and making `CoDirectorStageStrip`'s `setContentTab("production")` (`CoDirectorShell.tsx:164-168`) land on the wrong panel.
4. **R4 — No persistent author attribution.** Creator-vs-AI authorship exists only in `script_transactions.source` (`models.py:38`), not on elements/documents (`models.py:72-102`). 2.0 provenance requirements need an EXTEND.
5. **R5 — Creator-pasted content is not stored verbatim.** Imports parse into structured screenplay elements (`service.py:227-237`, `fountain.py:17-79`); no raw-text column on `script_documents_v2` (`store.py:27-45`).
6. **R6 — Single-document UX.** Backend supports multiple documents (`store.py:166-173`) but the studio edits only `docs[0]` (`service.py:49-53`, `ScriptwriterStudio.tsx:76`); no document selector in the UI.
7. **R7 — Conditional router registration.** `main.py:286-291` wraps the scriptwriter router in try/except — a load failure silently disables the API.
8. **R8 — PDF export dependency.** `pdf_export.py:95-103` falls back to a `.fountain.txt` file and raises `SCRIPT_EXPORT_FAILED` when reportlab is missing; verify reportlab is installed in the 2.0 target environment.

---

## 8. Verification notes
- Audit was read-only; no product files modified. Only this document was written.
- All citations verified against current source as of this audit. Line numbers reference the files exactly as they exist in the repo at audit time.
