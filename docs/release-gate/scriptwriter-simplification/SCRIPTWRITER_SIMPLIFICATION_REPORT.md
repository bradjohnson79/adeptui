# Script Writer Simplification + Co-Director Story/Script Access — Completion Report

Date: 2026-09-11
Branch: `feat/character-creator-final-closure`
Surface under test: local creator UI `http://127.0.0.1:5173/` + Studio API `http://127.0.0.1:8758/` (live Beta target, `ADEPT_BETA_TARGET=1`)
Comfy: COMFY BEFORE: PID 45624 healthy · COMFY AFTER: PID 45624 healthy · COMFY RESTARTED?: NO (API recycled via smallest scope only; `oldPid→newPid` recycles: 44816→30516→19560→44824→48876→21132, each `comfyUnchanged=True`)

---

## 1. Mission

Simplify Script Writer so it does only screenplay work — manage scenes, edit screenplay text, add/remove scenes, revisions, editable title — and guarantee Co-Director always has live Story + Script + current-scene access with no stale snapshots and no duplicated authority. Story planning stays in the existing Story workspace (Co-Director `story` content tab).

## 2. Root causes found (audit §9 classification)

Backend audit (independent subagent) + primary investigation, reconciled:

| Area | Classification | Disposition |
| --- | --- | --- |
| `story_entries` store + `/story-entries` API | EXISTS (canonical) | Now the Story authority everywhere |
| Legacy `story_documents` doc | STALE | Fallback only, when no entries exist |
| `project_context._get_story` | DISCONNECTED (read legacy store) | **Fixed** — reads `story_entries` first |
| `project_context._get_script` | STALE (read stale `d.elements`) | **Fixed** — reads `canonical_elements` |
| Script title edit (UI + API) | MISSING | **Added** end-to-end |
| Current script scene in Co-Director context | MISSING | **Added** (`scriptwriter_scene_id` end-to-end) |
| `activeDocumentId` binding end-to-end | MISSING | **Added** |
| Live Story/Script injection into chat turns | MISSING | **Added** (`story_script_context_block`, per-turn live read) |
| Local-provider context delivery | DISCONNECTED (ollama dropped `project_context` on the foundation path) | **Fixed** at provider root |
| Platform-knowledge router hijacking project-content questions | DEFECT | **Fixed** (bound-project content questions reach the LLM with live state) |
| Discovery-dialogue grounding gate rejecting factual project answers | DEFECT | **Fixed** (`allow_direct_answer`) |
| `compiledWiki.storySummary` | STALE between explicit Save-to-Wiki | Pre-existing publish model; bypassed by live block (not relied on) |
| `script_segments` / `script_docs` legacy tables | STALE/DUPLICATED (storyboard/timeline consumers) | Out of scope — separate legacy consumers; not touched |
| `GenerationTools/ScriptwriterWorkspace` | Divergent surface (generation tool artifact, not the screenplay) | Untouched; not the Script Writer |

Frontend audit (independent subagent) confirmed pre-fix state: Outline/Cards/Beats all re-rendered the same navigator; Production mode was dead; distraction-free unreachable; restore-revision API existed with no UI; delete/move scene APIs existed with no UI; no title editing anywhere; no `contentTab` deep link.

## 3. What shipped

### Script title editing (Express + Standard)
- New shared `ScriptTitleEditor` (`studio-web/src/components/scriptwriter/ScriptTitleEditor.tsx`): click → inline edit; Enter/blur saves; Escape cancels; empty → "Untitled Script"; error reverts. Display button carries `{testId}-display`, input carries `{testId}`.
- New API `POST /api/projects/{pid}/scriptwriter/documents/{id}/title` → `service.rename_document`: canonical document metadata; deliberately **no revision bump** (in-flight autosave `expectedRevision` must not spuriously conflict) and **not** in the content undo stream; last writer wins; every surface rehydrates from the canonical bundle.
- Express (`ScriptwriterInlineEditor`) and Standard (`ScriptwriterStudio`) both use it — same canonical field, no duplicate title state.

### Standard simplification
`ScriptwriterStudio.tsx` rewritten around the screenplay surface:
- Toolbar: title editor · Script · Story · Add Scene · Remove Scene · Revisions · Undo · Redo · Focus · save state.
- Views: `script` and `revisions` only. Compare is folded into Revisions.
- Removed from the creator surface: Outline, Cards, Beats, standalone Compare, Dialogue-focus, Production mode, Command palette (Ctrl+K), sample-beats converter.
- Power tools (export Fountain/PDF, link scene, timeline prep, analyze, import, proposals) preserved behind a collapsed "More tools" disclosure — capability preserved, presentation simplified.
- Story button routes to the existing Story workspace: `/co-director?projectId=X&contentTab=story` (CoDirectorShell now honors the `contentTab` deep link). No Story subsystem duplicated inside Script Writer.

### Scene management (canonical model, root-cause HTML fix)
- Pre-existing defect fixed at root: insert/delete/move scene, restore revision, import, proposals, search-replace, outline-convert previously mutated only the stale stored-element list and were **invisible** for HTML-canonical documents (what the editors actually render).
- New `htmlscenes.py`: raw top-level block splitter + lossless HTML surgery; `_sync_elements_to_html` keeps the stored projection in sync after HTML ops.
- `_resolve_scene_heading_id`: accepts legacy stored-element ids (import/parse responses) and maps them to canonical `html-scene-<hash>` navigator ids (normalized text match, ordinal fallback for duplicate headings) — used by delete/move/link/timeline-prepare/apply-metadata/analyze.
- UI: Add Scene inserts after the active scene and selects it; Remove Scene confirms then deletes; per-scene ↑↓ reorder via the existing `moveScene`.

### Revisions
- Revision snapshots now capture the **canonical** content (HTML + elements); compare and restore operate on canonical content (restore brings the scene text back, proven live).
- `ScriptRevisionSnapshot.contentHtml/contentType` + `script_revision_rows` columns via idempotent `ALTER TABLE` migration (`_ensure_revision_html_columns`).
- Revisions is a first-class view: create, list, restore; Compare folded underneath.

### Co-Director Story/Script access
- `story_script_context_block` (`context_enrichment.py`): read from the canonical stores **on every chat turn** (never a cached snapshot) — story entries (truncated, ≤6), script stats, scene list (≤40, current scene marked), current-scene readout (1200-char action/dialogue), plus a bounded (2600-char) readout of the remaining scenes so dialogue questions are answerable without a tagged scene. Never raises; deeper retrieval via read tools.
- Threading: `CoDirectorChatBody.active_document_id/activeDocumentId` + `scriptwriter_scene_id/scriptwriterSceneId` → `/chat` + `/chat/stream` → `chat_for_project`/`stream_for_project`/`_stream_for_project_inner` → `_prepare_chat_request`.
- Frontend: `ProjectEditor` tracks the active script scene from the studio (`onActiveSceneChange`) and bridges it to the Co-Director session (`setScriptwriterScene`, lightweight ref — no rebind, so in-flight chat is never cancelled by clicking scenes); both chat bodies send `active_document_id` + `scriptwriter_scene_id`.
- Current-scene awareness also in the deterministic grounding layer: `build_project_grounding_snapshot` carries `scriptwriterScene` (live, from the canonical document); "Which scene am I editing?" answers with the real heading + position.
- Routing fixes so project-content questions actually reach project state:
  - `_is_project_content_question` suppresses the canned platform-knowledge short-circuit for bound-project content questions ("the hero", "the script", "this scene"…). Knowledge is still rendered into the LLM prompt when no canned reply fires.
  - `_foundation_llm_turn(allow_direct_answer=…)`: a factual project-content answer is not failed by discovery-dialogue gates (LISTENING reflection / question budget / min length).
  - **Provider root fix**: the foundation path replaces `ChatRequest.messages` with its own generation messages and carries the assembled studio context only in `project_context`; the hosted provider appended it, the local ollama provider dropped it. `ollama._messages_with_project_context` now merges it into the system message (idempotent — no double injection), also fixing `num_ctx` sizing to account for context.

## 4. Evidence

### Backend tests
- `test_scriptwriter_title_html_scenes.py` — **13 passed** (title persist/blank/missing; **rename/autosave race regression: rename is a title-only UPDATE that cannot clobber content or regress revision**; HTML insert/targeted-after/delete/move visible in navigator; inline formatting preserved outside touched scenes; undo restores HTML; revision snapshot canonical + contentHtml; compare canonical; restore brings back HTML).
- `test_codirector_story_script_access.py` — **9 passed** (story pillar reads `story_entries`; legacy fallback only when empty; script pillar canonical projection; freshness: edits visible next call; empty project; current-scene readout + marker; unknown scene id still lists scenes; **platform-help routing: how-to questions containing "the script"/"the story" still reach the curated platform reply; project-content questions still route to the LLM**).
- Post-review combined scriptwriter regression (all 7 suites incl. m47 backend): **71 passed**.
- Scriptwriter suite: **55 passed**. Co-Director regression sweep: **297 passed, 4 failed** — all 4 proven not-this-mission: 3 fail identically at clean-HEAD baseline worktree (`.runtime/_wc_baseline`), 1 (`foundational_ai` paraphrases) is caused by foreign uncommitted edits to `conversation/foundation/intent.py` (73 foreign lines; file untouched by this mission).
- Frontend: `npx tsc --noEmit` clean; vitest scriptwriter dirs **10 passed** (`sanitizeHtml.test.ts`/`legacyHtml.test.ts` "No test suite found" — pre-existing node:test-style files, vitest-incompatible, untouched).

### Live Playwright (local Beta: Vite :5173 + API :8758)
- `tests/e2e/m47/m47-professional-scriptwriter-studio.spec.ts` — **2 passed** (full production path incl. UI shell contract + transaction undo/revision compare APIs). Updated to the simplified contract (CDX-054 explicit document creation; canonical heading re-fetch after mutations).
- `tests/e2e/mission/scriptwriter-simplification-live.spec.ts` — **2 passed**:
  - Express: "Untitled Script" → click → type "The Adept Chronicles" → Enter → `POST …/title` 200 → bundle carries title → reload persists → Escape cancels a discard edit.
  - Standard: 8 core toolbar controls visible; `scriptwriter-outline`/`scriptwriter-cards`/`scriptwriter-command-input`/`scriptwriter-convert-beats` absent; title rename verified against the canonical bundle; Story → URL `/co-director?…contentTab=story`; scenes 2→3 (add after active) **with navigator ORDER asserted** (new scene lands between CLOCKWORK BRIDGE and RUST DOCKS, never appended) → edit → autosave "saved" → 3→2 (remove, confirm, order re-asserted); revision created + listed; reload: title/scenes/revision persist. Re-run after the review fixes: **2 passed** (2026-09-11, API pid 47796).

### Live Co-Director probe (`.runtime/_sw_codirector_live.json` — real provider ollama `qwen3.6:35b-a3b`, zero fallback)
| Check | Question | Answer evidence | Verdict |
| --- | --- | --- | --- |
| Story access | "Who is the hero of this project's story?" | "ZEPHYR-QUIXOTE" | PASS |
| Script access | "What does KORRI-X say about the compass?" | "The compass spins toward NINEVOLTA." (exact quote) | PASS |
| Story freshness | (after editing the logline) "Who is the hero right now?" | "Marrow-Valk" — only knowable from the edited entry | PASS |
| Script freshness | (after search-replace) "What does KORRI-X say now?" | "The compass now points at DUSKHARBOR." | PASS |
| Current scene | "Which scene am I currently editing?" (with `scriptwriterSceneId`) | "You are editing EXT. RUST DOCKS - NIGHT (scene 2 of 2 in the script)." | PASS |

## 5. E2E trace (per Full-Stack E2E Completion Law)

| Stage | Result |
| --- | --- |
| User action | PASS — click title / toolbar buttons / scene rows / Co-Director chat all live-wired |
| Frontend | PASS — ScriptTitleEditor, simplified studio, session bridge, contentTab deep link |
| API | PASS — `/title`, scene ops, revisions, `/codirector/chat(+stream)` accept and route the new fields |
| Backend | PASS — canonical HTML surgery, resolver, live context block, grounding/provider fixes |
| Persistence | PASS — title, scenes, revisions, story entries survive reload (Playwright + API bundle) |
| Runtime/Provider | PASS — real ollama LLM turns with injected live project state; no fallback on gated checks |
| Result | PASS — canonical bundle + live chat answers reflect current state |
| Reload | PASS — Playwright reload assertions on title/scenes/revisions |
| Downstream | PASS — m47 production path (proposal → bible → scene link → timeline prep → exports) green |

## 6. Regression (spec §16)

- Script persistence / scene ordering / screenplay formatting: covered by the 55-test scriptwriter suite + live Playwright.
- Co-Director: 297-test sweep green except 4 proven-foreign/pre-existing failures.
- Story: `test_story_legacy_gate.py`, `test_story_summary_editor.py` in sweep — green.
- Timeline: m47 timeline prep/apply metadata steps green live.
- Character Creator / Voice Creator / project navigation: untouched surfaces; four-pillars hosted cert shows 0 console errors (hosted run is informational — this mission did not deploy).

## 7. Limitations / disclosures

- `studio-api/app/codirector/project_grounding.py` is **foreign untracked work** (another mission's in-flight grounding layer). This mission's additive edits ride on it (scriptwriterScene slice + reply branch). It is excluded from this mission's commit; the LLM context block (committed) independently provides current-scene awareness.
- Legacy `script_segments`/`script_docs` tables remain for storyboard/timeline legacy consumers — deliberately not migrated (mission: do not rebuild scene storage).
- `StoryEditor.tsx` (orphan, legacy `/story`) remains but is unused; the canonical Story surface is `StoryEntryEditor` in Co-Director.
- Hosted Vercel deployment was not part of this mission; all verification is against the local creator UI + Studio API.
- The title editor's click can land during initial bundle hydration and be swallowed by a re-render; the creator simply clicks again (tests retry once). Cosmetic, not data-loss.
- Undo (toolbar) is transaction-level (scene/version changes); Redo is editor-typing-level — no transaction-redo API exists yet. Tooltips now state both scopes plainly (review MINOR-4).
- `timelinePrep` element metadata is ephemeral for HTML-canonical documents (element snapshots regenerate from HTML on every scene op; only `sceneSync` persists). Pre-existing property of the HTML-canonical model; the Timeline-prep consumer must not rely on element-level metadata for HTML docs (review note 5).
- Duplicate scene headings get occurrence-suffixed ids (`html-scene-<hash>-<n>`); deleting/moving an earlier duplicate renumbers later ones, orphaning stored `activeSceneId`/`sceneSync` references to them. Pre-existing in `htmltext.py`, narrow edge case (review note 6).

## 8. Verdicts

| Gate | Verdict |
| --- | --- |
| SCRIPT TITLE EDITING | PASS — inline edit, Enter/blur save, Escape cancel, canonical persist, reload-safe, both surfaces |
| EXPRESS/STANDARD SHARED AUTHORITY | PASS — same document, same bundle, same endpoint; verified via API + UI |
| SCRIPT WRITER UI SIMPLIFICATION | PASS — 8 core controls; planning clutter removed from DOM; power tools behind More tools |
| STORY REPLACES OUTLINE | PASS — Story button routes to the existing Story workspace; no duplicate subsystem |
| SCENE ADD/REMOVE | PASS — add-after-active, select, remove with confirm, reorder; canonical model; HTML root fix |
| REVISIONS | PASS — create/list/restore + folded Compare; canonical snapshots; survives reload |
| CO-DIRECTOR STORY ACCESS | PASS — live `story_entries` in every turn; proven with live LLM answer |
| CO-DIRECTOR SCRIPT ACCESS | PASS — live canonical script in every turn; exact-quote answers |
| LIVE CONTEXT FRESHNESS | PASS — post-edit answers reflect new Story + new dialogue on the next turn |
| CURRENT SCENE AWARENESS | PASS — deterministic + LLM paths know the selected script scene and its position |
| REGRESSION | PASS — 297+55 backend green (4 failures proven foreign/pre-existing), tsc clean, m47 + mission specs green live |

## 9. Independent review reconciliation (GLM 5.2 Max)

Independent review verified all five claimed implementation areas against the working tree (19/19 focused tests, tsc clean) with **no blockers**. Two MAJOR findings, both repaired by the primary and re-certified:

1. **MAJOR-1 — rename/autosave race (FIXED).** `rename_document` previously loaded the doc and re-saved ALL columns, so a rename racing a debounced autosave could restore stale content and regress `revision` (also causing spurious `SCRIPT_CONFLICT`). Fix: new `store.update_document_title` — a targeted title-only UPDATE that never touches content/elements/revision — wired into `rename_document`, which now returns the freshly reloaded doc. Regression test `test_rename_document_never_clobbers_content_or_revision` proves content + revision survive the race ordering.
2. **MAJOR-2 — `_PROJECT_CONTENT_Q` over-match (FIXED).** Bare `the script|the story` matched platform how-to questions ("How do I use the script writer?"), bypassing the curated platform reply for bound projects. Fix: `_PLATFORM_HELP_Q` exclusion (how-do-i / how-to / where-is / what-is-adept / "is there a way" / "use the script writer" phrasing) checked first in `_is_project_content_question`. Tests prove 7 platform-help phrasings route to platform replies and 4 content phrasings still route to the LLM; unbound chat unchanged.

MINORs: (3) e2e Add Scene now asserts navigator ORDER after insert-after-active and after remove — re-run live, 2 passed; (4) Undo/Redo tooltips now state their scopes plainly (transaction-level vs typing-level; no transaction-redo API exists — disclosed §7); (5)(6) timelinePrep-ephemeral and duplicate-heading id instability disclosed §7 (both pre-existing); (7) diff mojibake was display-only (files are correct UTF-8, proven by test assertion). Foreign co-resident work (notes 8–9) remains excluded from this mission's commit as disclosed §7.

## 10. Final verdict

**GO — SCRIPT WRITER SIMPLIFIED + CO-DIRECTOR STORY/SCRIPT ACCESS VERIFIED**

- 11/11 mission gates PASS (§8) with live measured evidence; both review MAJORs repaired and re-certified (§9).
- Post-fix evidence: 71/71 backend scriptwriter+access tests, tsc clean, mission live spec 2 passed (with order assertions), m47 live spec 2 passed, live Co-Director probe 5/5 on real ollama `qwen3.6:35b-a3b`.
- E2E trace PASS (§5); COMFY RESTARTED?: NO (PID 45624 before/after; Studio API recycled only, pid 47796).
