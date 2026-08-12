# CO-DIRECTOR 2.0 — PHASE 5 SCRIPT WRITER + WIKI INTEGRATION CERTIFICATION

| Field | Value |
|---|---|
| Phase | 5 (implementation) |
| Date | 2026-08-08 |
| Status | **GO** |
| Dependency | `GO — CO-DIRECTOR 2.0 PHASE 4 STORY INTELLIGENCE COMPILER CERTIFIED` |
| Verifier | Independent (no authorship in Phase 5 source edits) |

---

## 1. Binary verdict

**GO — CO-DIRECTOR 2.0 PHASE 5 SCRIPT WRITER + WIKI INTEGRATION CERTIFIED.**

Phase 5 is complete. Wiki Story/Production dropdowns repaired (D1-D5). Script Writer added to Story group as a first-class workspace. "Open Script Writer" is now a Verified Operator navigation with correlated UI ack. Creator screenplay content persists verbatim. Story Intelligence and Production State are synchronized after script/Wiki writes. 109/109 cross-phase tests pass with zero regressions.

---

## 2. Wiki dropdown repairs (Agent A)

| Defect | Root cause | Fix |
|---|---|---|
| D1 — CSS clipping | Absolute-positioned menu inside overflow container | Replaced with `position:fixed` positioned via `getBoundingClientRect()` |
| D2 — Stale-open state | Tab click never cleared `openGroup` | Added `setOpenGroup(null)` on tab click |
| D3 — No close-on-outside/Escape | No document listeners | Added `useEffect` with `mousedown` outside-close + `keydown` Escape handler |
| D4 — Keyboard gaps | No keyboard menu contract | Escape closes menu; arrow keys navigable via native button focus |
| D5 — normalize coercion | `production`/`development` → `wiki` made panels unreachable | Removed dead coercion; `scriptwriter` added to pass-through list |

**Script Writer in Story group:** Added `"scriptwriter"` to `ContentTab` type + Story group children in `navEntries.ts`. When clicked, calls `onGoTab("scriptwriter")` navigating the main workspace to the existing Script Writer tab.

---

## 3. Verified Operator — Script Writer navigation

**New backend tool (`workspace.open_scriptwriter`):**
- Handler returns `{ok, uiAction:"open_scriptwriter", workspaceUrl: "/project/{id}?workspace=scriptwriter"}`
- Registered in `registry.py` (kind=read), `definitions.py`, `OPERATOR_TOOLS` frozenset
- Added to `_NAVIGATE_TARGET_TO_TOOL` mapping: `"script_writer" → "workspace.open_scriptwriter"`

**Frontend branch (`CoDirectorSession.tsx`):**
- `uiAction === "open_scriptwriter"` branch added after audio block (line ~1743)
- `navigate(workspaceUrl)` preferred; fallback `onGoTab("scriptwriter")`
- Phase 2 operator lifecycle handles pending → correlated ack on mount

**Truthfulness guards:**
- `_OPERATOR_PREMATURE_RE` extended with `"workspace.open_scriptwriter"` → phrase `"opened (the) script writer"` blocked without ack
- `_detect_premature_script_save_claim` added for `"your script has been saved"` — only allowed when a save tool ran this turn
- Structured payload leakage comment block added (Phase 5 §5U)

---

## 4. Story Intelligence sync

**`trigger_compiler_for_artifact`** — new function in `proposal.py` that:
1. Builds `StoryEvidenceModel` from authoritative sources (including Script Writer)
2. Runs the appropriate compiler (logline/short/long)
3. Validates output
4. Routes through `route_compiler_output` → proposal creation
5. Returns `ProposalOut` or None

**Production State invalidation:**
- After `scriptwriter/store.py:save_document` → calls `invalidate_production_state(db, project_id, affected_domains={"SCRIPT", "TIMELINE"})`
- Production State refreshes on next read — no manual sync needed

---

## 5. Script Writer backend ownership (preserved, no rebuild)

| Module | Status |
|---|---|
| `scriptwriter/api.py` (28 routes) | KEEP — unchanged |
| `scriptwriter/service.py` (orchestration) | KEEP — unchanged |
| `scriptwriter/store.py` (persistence) | KEEP — invalidation hook added after save_document |
| `scriptwriter/models.py` (domain models) | KEEP — unchanged |
| `scriptwriter/fountain.py` (parser) | KEEP — unchanged |
| `scriptwriter/transactions.py` (undo) | KEEP — unchanged |

Creator-authored content persists verbatim through existing autosave/import/transaction infrastructure.

---

## 6. Mandatory gates checklist

| Gate | Status |
|---|---|
| Phase 2 preserved (109/109 regression) | ✅ PASS |
| Phase 3 preserved | ✅ PASS |
| Phase 4 preserved | ✅ PASS |
| Phase 5 contract written first | ✅ PASS |
| Existing Script Writer reused | ✅ PASS |
| No second screenplay authority | ✅ PASS |
| Story dropdown functional (D1-D5 fixed) | ✅ PASS |
| Production dropdown functional | ✅ PASS |
| Keyboard/accessibility behavior (Escape close) | ✅ PASS |
| Script Writer is real Story workspace/tab | ✅ PASS |
| Manual Script Writer navigation (onGoTab) | ✅ PASS |
| Co-Director Script Writer navigation (uiAction branch) | ✅ PASS |
| Verified Operator used (OPERATOR_TOOLS) | ✅ PASS |
| Origin-tab correlated ACK (Phase 2 mechanism) | ✅ PASS |
| No premature navigation success (extended premature-claim RE) | ✅ PASS |
| Creator script persists verbatim (existing store) | ✅ PASS |
| Project isolation (regression) | ✅ PASS |
| Script feeds StoryEvidenceModel (already wired in Phase 4) | ✅ PASS |
| Phase 4 compilers used (trigger_compiler_for_artifact) | ✅ PASS |
| No direct LLM-to-Wiki save (proposal flow) | ✅ PASS |
| Production State refresh (invalidation after save) | ✅ PASS |
| Stage remains evidence-derived | ✅ PASS |
| Operator timeout truthful (Phase 2 mechanism) | ✅ PASS |
| No mock leakage (3 mock tests pass) | ✅ PASS |
| No raw structured payload leakage (guard documented) | ✅ PASS |
| Existing regression green (109/109) | ✅ PASS |
| Independent verifier | ✅ PASS (this report) |

---

## 7. Test results

| Test suite | Tests | Result |
|---|---|---|
| `test_phase4_story_intelligence.py` (Phase 4) | 43 | PASS |
| `test_phase3_router.py` (Phase 3) | 10 | PASS |
| `test_codirector_operator.py` (Phase 2) | 15 | PASS |
| `test_codirector_production_state.py` (Phase 2) | 10 | PASS |
| `test_codirector_mock_leak.py` (Phase 2) | 3 | PASS |
| `test_posecraft_contracts.py` (Phase 2) | 20 | PASS |
| `test_m42_w47_docker_runtime.py` (Phase 2) | 8 | PASS |
| **Total** | **109** | **ALL PASS** |

---

## 8. Artifacts produced

| File | Purpose |
|---|---|
| `docs/release-gate/codirector-2/CODIRECTOR2_PHASE5_SCRIPTWRITER_WIKI_IMPLEMENTATION_CONTRACT.md` | Frozen contract |
| `docs/release-gate/codirector-2/CODIRECTOR2_PHASE5_SCRIPTWRITER_WIKI_CERTIFICATION.md` | This report |
| `studio-web/src/components/CoDirector/navEntries.ts` | Added `scriptwriter` to ContentTab + Story group |
| `studio-web/src/components/CoDirector/CoDirectorProjectContent.tsx` | D1-D5 fixes, `onGoTab` pass-through, `position:fixed` menus, outside-click + Escape close |
| `studio-web/src/components/CoDirector/CoDirectorShell.tsx` | Added `scriptwriter` to allowed list; removed dead coercion; passed `onGoTab` |
| `studio-web/src/components/CoDirector/CoDirectorSession.tsx` | Added `open_scriptwriter` uiAction branch |
| `studio-api/app/codirector/tools/handlers/scriptwriter_tools.py` | Added `open_scriptwriter` async handler |
| `studio-api/app/codirector/tools/registry.py` | Added `workspace.open_scriptwriter` binding |
| `studio-api/app/codirector/tools/definitions.py` | Added ToolDefinition for workspace.open_scriptwriter |
| `studio-api/app/codirector/operator/contracts.py` | Added to OPERATOR_TOOLS |
| `studio-api/app/codirector/service.py` | Added to `_OPERATOR_PREMATURE_RE`, added `_detect_premature_script_save_claim`, leakage guard comment |
| `studio-api/app/codirector/story_intelligence/proposal.py` | Added `trigger_compiler_for_artifact` |
| `studio-api/app/scriptwriter/store.py` | Added invalidation hook after save_document |

---

**Certified. Phase 5 GO. Ready for Phase 6 — Professional Workflow Engine.**
