# CO-DIRECTOR 2.0 — PHASE 5 SCRIPT WRITER + WIKI INTEGRATION CONTRACT (FREEZE)

| Field | Value |
|---|---|
| Phase | 5 (implementation) |
| Date | 2026-08-08 |
| Status | **FROZEN** — governing contract for Phase 5 source edits. |
| Dependency | `GO — CO-DIRECTOR 2.0 PHASE 4 STORY INTELLIGENCE COMPILER CERTIFIED` |
| Governing evidence | Phase 1 `CODIRECTOR2_SCRIPTWRITER_WIKI_AUDIT.md`, Phase 2-4 contracts |

---

## 1. Current Wiki architecture (verified against live source)

| Component | File | Role |
|---|---|---|
| Content tab nav | `navEntries.ts:40-65` | `CONTENT_NAV` — Wiki, Notes, Casting, Story group (Vision/Pitch/Bible), Library, Production group (Plans/Approvals/Jobs) |
| Tab bar + dropdowns | `CoDirectorProjectContent.tsx:225-295` | Renders tabs and group menus; inline sidebar panels below |
| Tab state | `CoDirectorShell.tsx:29-64` | `normalizeContentTab`, localStorage persistence `adept_codirector_content_tab`, reset on project switch |
| Sidebar panels | `CoDirectorProjectContent.tsx:297-429` | wiki→ProjectWikiPanel, notes→NotesPanel, casting→CastingPanel, library→ProjectRetrievalPanel, bible→Bible, plans, approvals, jobs, vision, pitch |
| `ContentTab` type | `navEntries.ts:1-13` | 13 union members — **no `scriptwriter`** |
| Dropdown CSS | `codirector-cinematic.css` | `.codirector-content-tabs overflow-x:auto` clips absolute-positioned menus |

### Current dropdown defects

| # | Defect | Root cause | Fix |
|---|---|---|---|
| D1 | CSS clipping | `.codirector-content-tabs { overflow-x:auto }` → overflow-y also auto → clips `position:absolute; top:100%` menu | Render menu with `position:fixed` positioned from trigger's `getBoundingClientRect()`, or set parent overflow to `visible` |
| D2 | Stale-open state | `onTabChange` for direct tabs doesn't clear `openGroup` | Add `setOpenGroup(null)` in tab click handler |
| D3 | No close-on-outside/Escape | No document-level click listener, no `onKeyDown`/Escape | Add `useEffect` with outside-click listener + Escape handler |
| D4 | Keyboard gaps | No arrow keys, no focus management | Add arrow key navigation + focus tracking |
| D5 | `normalizeContentTab` coercion | `"production"`→`"wiki"`, `"development"`→`"wiki"` makes StageList unreachable | Remove unused coercion; add `"scriptwriter"` to allowed list |

---

## 2. Script Writer backend ownership (KEEP, do NOT rebuild)

| Module | File | Role |
|---|---|---|
| API | `scriptwriter/api.py` | 28 REST routes under `/projects/{id}/scriptwriter` |
| Service | `scriptwriter/service.py` | Orchestration: get/create doc, autosave, insert/delete/move scene, revision, import/export, proposal apply |
| Store | `scriptwriter/store.py` | SQLAlchemy: `script_documents_v2`, transactions, revision snapshots, notes |
| Models | `scriptwriter/models.py` | ScriptDocument, ScriptElement (12 screenplay types), ScriptTransaction, ScriptRevisionSnapshot |
| Fountain | `scriptwriter/fountain.py` | Regex-based line parser (scene heading, character, dialogue, action, parenthetical, transition) |
| Transactions | `scriptwriter/transactions.py` | Undoable transaction layer with before-state snapshot |
| Co-Director tools | `scriptwriter_tools.py` | 9 read + 7 mutating tools, all proposal-gated |

All KEEP. No rebuild.

---

## 3. Operator target contract

| Field | Value |
|---|---|
| Tool id | `workspace.open_scriptwriter` |
| kind | `read` |
| Handler | Returns `{ok, uiAction:"open_scriptwriter", workspaceUrl, _evidence}` |
| Registry | Add to `registry.py` read handlers dict |
| OPERATOR_TOOLS | Add `"workspace.open_scriptwriter"` |
| _NAVIGATE_TARGET_TO_TOOL | `"script_writer": "workspace.open_scriptwriter"` |
| Frontend action | `navigate(workspaceUrl)` or `onGoTab("scriptwriter")` |
| Operator lifecycle | Standard: request → pending → frontend mount ACK → acknowledged |

---

## 4. Ownership map (who owns what)

| Artifact | Authority | Phase 5 change |
|---|---|---|
| Screenplay | Script Writer (`scriptwriter/store.py`) | None — already authoritative |
| Logline | Phase 4 Story Intelligence (`compiledWiki["storySummary"]["logline"]`) | Proposal flow (CURRENT/PROPOSED) |
| Short Summary | Phase 4 Story Intelligence (`compiledWiki["storySummary"]["shortSummary"]`) | Proposal flow |
| Long Summary | Phase 4 Story Intelligence (`compiledWiki["storySummary"]["longSummary"]`) | Proposal flow |
| Bible canon | Production Bible (`production_bible_entities`) | None |
| Production State | Phase 2 projection (`production_state/`) | Add invalidation after script/Wiki writes |
| Tab preference | localStorage `adept_codirector_content_tab` | Add scriptwriter tab stability |

---

## 5. Subagent plan

1. **Agent A** — Wiki frontend repairs (navEntries.ts, CoDirectorProjectContent.tsx, CoDirectorShell.tsx, CSS)
2. **Agent B** — Script Writer tool (workspace.open_scriptwriter handler, registry, definitions, OPERATOR_TOOLS)
3. **Agent C** — Frontend operator branch + _NAVIGATE_TARGET_TO_TOOL + CoDirectorSession.tsx
4. **Agent D** — Story Intelligence integration (compiler actions from Wiki, CURRENT/PROPOSED, Accept/Reject)
5. **Agent E** — Production State invalidation hooks after script/Wiki writes
6. **Agent F** — Co-Director behavioral (truthfulness, no structured leakage)
7. **Agent G** — Playwright + regression
8. **Agent H** — Independent verifier + certification

A+B run in parallel (frontend + backend, disjoint files). C depends on B. D+E parallel. F is integration. G tests.

---

*Frozen. No Phase 5 source edit precedes this document.*
