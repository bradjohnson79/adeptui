# ADEPT_UI_CODIRECTOR_WIKI_USER_AUTHORITY_REPAIR — Final Evidence

## Confirmed Root Cause

Three independent paths allowed assistant scaffolding and conversation fragments to become canonical Wiki data:

| Path | Mechanism | Severity |
|------|-----------|----------|
| **A** — `page_compiler.py:116-118` fed ALL knowledgeEntry texts (not just `section="characters"`) to `resolve_characters()` | Compiled Wiki character resolution | HIGH |
| **B** — `_is_junk_name()` in `character_compiler.py` didn't catch assistant scaffolding tokens | False character name filter | HIGH |
| **C** — `story_compiler.py:63` hardcoded `narrativeFrame="Current Co-Director understanding..."` | Story summary metadata | MEDIUM |
| **D** — `documentation.py` extracted capitalized names without `is_false_character_name()` guard | Auto-extraction pipeline | MEDIUM |
| **E** — `notes/service.py:51` bridged ALL knowledgeEntries (including rejected/superseded) into Working Notes | Notes contamination vector | HIGH |
| **F** — `routers/codirector.py:1115` (correct_story_summary) appended directly, bypassing `apply_wiki_candidates()` | Write-path bypass | CRITICAL |
| **G** — `correction/classify.py:77` + `apply.py:75` text-matched against ALL entries without state filter | Correction contamination | HIGH |

## Authority Flow Before

```
Conversation
  → plan_conversation() → WikiCandidate(state="proposed")
    → orchestrate.py line 685: wiki_candidates = [] (already discarded in hot path)
  → extract_documentation() → DiscoveryWikiCandidate(status=CONFIRMED)
    → WikiCandidate(state="confirmed")
    → apply_wiki_candidates → knowledgeEntries (STATE gate: only confirmed/rejected persist)
    → page_compiler._entry_texts() → ALL entries → compile_wiki_bundle()
      → char_texts = ALL entries (not just characters section)
        → resolve_characters() → "Current Co-Director" becomes character page
      → story_texts = ALL entries → compile_story_summary()
        → narrativeFrame = "Current Co-Director understanding..." (hardcoded)
  → notes._ensure_notes_list() → ALL entries (including rejected/superseded) → WorkingNotes
  → correction._find_matching_records() → ALL entries → correction targets
  → correct_story_summary() → direct list.append (bypasses all gates)
```

## Authority Flow After

```
Conversation
  → plan_conversation() → WikiCandidate(state="proposed") → discarded at line 685 (unchanged)
  → extract_documentation() → DiscoveryWikiCandidate(status=CONFIRMED)
    → is_false_character_name() guard at extraction [FIX D]
    → WikiCandidate(state="confirmed")
    → apply_wiki_candidates → knowledgeEntries (unchanged)
    → page_compiler._entry_texts() → confirmed/approved/proposed entries
      → char_texts = ONLY section="characters" entries [FIX A]
        → resolve_characters() → _is_junk_name() expanded with 20+ scaffolding tokens [FIX B]
      → story compiler → narrativeFrame="" (dynamic, empty when no content) [FIX C]
      → _entry_texts() also excludes rejected/superseded (existing)
  → notes._ensure_notes_list() → skips rejected/superseded entries [G2 FIX]
  → correction._find_matching_records() → skips rejected/superseded entries [G3 FIX]
  → correction._find_entries_containing() → skips rejected/superseded entries [G3 FIX]
  → correct_story_summary() → routes through apply_wiki_candidates() [G1 FIX]
    → FULL gate: question check, residue check, dedup, state validation
  → build_project_wiki() → post-process strips false chars + preferences (existing)
  → FALSE_CHARACTER_TOKENS expanded: "current", "tell", "narrative", etc. [FIX F]
```

## Files Changed

| File | Fix | Purpose |
|------|-----|---------|
| `app/codirector/wiki_intelligence/compiled/page_compiler.py:116` | A | Only `section="characters"` entries feed `resolve_characters()` |
| `app/codirector/wiki_intelligence/compiled/character_compiler.py:9-22,37-58` | B | `_is_junk_name()` expanded with 20+ scaffolding tokens |
| `app/codirector/wiki_intelligence/compiled/story_compiler.py:63-72` | C | `narrativeFrame` no longer hardcoded; empty when no content |
| `app/codirector/wiki_intelligence/contracts.py:149-171` | F | `FALSE_CHARACTER_TOKENS` expanded with scaffolding tokens |
| `app/codirector/conversation/discovery/documentation.py:8,96-98` | D | `is_false_character_name()` guard at extraction time |
| `app/codirector/notes/service.py:56-58` | G2 | Skip rejected/superseded entries in Notes bridge |
| `app/codirector/wiki_intelligence/correction/classify.py:81-84` | G3 | Skip rejected/superseded in correction text matching |
| `app/codirector/wiki_intelligence/correction/apply.py:76-79` | G3 | Skip rejected/superseded in correction entry search |
| `app/routers/codirector.py:1105-1118` | G1 | Route correct_story_summary through `apply_wiki_candidates()` |
| `tests/test_wiki_intelligence_contracts.py:93-193` | — | 6 regression tests |
| `tests/test_wiki_authority_gates.py` | — | 5 regression tests (G1-G3) |

## Write-Path Protection (Phase 2 Verification)

| Path | Protected? | Mechanism |
|------|-----------|-----------|
| `plan_conversation()` → candidates | YES | `state="proposed"` → filtered by `apply_wiki_candidates` line 75 |
| `extract_documentation()` → characters | YES | `is_false_character_name()` guard at extraction |
| `apply_wiki_candidates()` → persistence | YES | Only `state="confirmed"` or `"rejected"` persist |
| Assistant onboarding | YES | Onboarding writes ONLY to `CoDirectorRelationshipProfile` |
| Generic user conversation | YES | Planner produces `state="proposed"`; discovery produces `EMERGING/INFERRED` → `"proposed"` |
| Explicit story correction | YES | Routes through `apply_wiki_candidates()` (G1) |
| Explicit wiki promote (notes) | YES | Routes through `apply_wiki_candidates()` |
| Script intake | YES | Routes through `apply_wiki_candidates()` |
| Correction apply | YES | Routes through `apply_wiki_candidates()` |

## Story Compiler Protection (Phase 2)

`compile_story_summary()` receives `story_texts` from `_entry_texts()`, which filters out rejected/superseded entries. With Fix C, `narrativeFrame` is empty when no story content exists, removing the hardcoded "Current Co-Director understanding..." text.

## Character Extraction Protection (Phase 2)

Three layers:
1. **Extraction time** (Fix D): `is_false_character_name()` called before creating DiscoveryWikiCandidate objects
2. **Compilation time** (Fix A): Only `section="characters"` entries feed `resolve_characters()`
3. **Character compiler** (Fix B): `_is_junk_name()` catches "current", "tell", "narrative", etc.
4. **Classification layer** (Fix F): `FALSE_CHARACTER_TOKENS` expanded across all consumers

## Historical Contamination Strategy (Phase 3)

**Strategy:** READ-TIME QUARANTINE. Old contaminated `knowledgeEntries` remain in the snapshot but are filtered at every read boundary.

| Consumer | Filter | Risk |
|----------|--------|------|
| `_entry_texts()` (page_compiler) | State filter + section gating | LOW |
| `build_story_summary_source()` (evidence.py) | State filter + provenance classification | LOW |
| `build_project_wiki()` (wiki.py) | Post-hoc false-char + preference strip | LOW |
| `_ensure_notes_list()` (notes/service.py) | State filter (rejected/superseded skipped) — **G2** | LOW |
| `_find_matching_records()` (correction/classify.py) | State filter — **G3** | LOW |
| `_find_entries_containing()` (correction/apply.py) | State filter — **G3** | LOW |
| `build_story_evidence()` (story_model.py) | State filter | LOW |
| `wiki_health_report()` (maintenance.py) | **No filter** — counts all entries | MEDIUM |
| `export_memory()` (conversation_memory.py) | No filter — export only | LOW |
| `correct_story_summary()` (router) | Now routes through `apply_wiki_candidates()` — **G1** | LOW |

## knowledgeEntries Consumer Audit (all 29 consumers)

Final classification: 27 SAFE / 2 MEDIUM (maintenance health report and memory export — neither mutates canonical state).

## Fresh Project Result (Phase 5)

Not executed (requires Beta server). Expected: Story=EMPTY, Characters=EMPTY.

## Explicit Story Save Result (Phase 7)

Not executed (requires Beta server). Expected: correction routes through `apply_wiki_candidates()` with full validation.

## Explicit Character Save Result (Phase 8)

Not executed (requires Beta server). Expected: character save → canonical Character → Wiki update.

## Rename/Edit/Delete Result (Phase 8)

Not executed (requires Beta server). Expected: rename → Wiki updates, edit → Wiki updates, delete → removal.

## Rebuild Result (Phase 9)

Not executed (requires Beta server). Expected: assistant scaffolding excluded, saved content preserved.

## Refine Result (Phase 10)

Not executed (requires Beta server). Expected: no silent overwrite, no invented facts.

## Reorganize Result (Phase 11)

Not executed (requires Beta server). Expected: format/order changes only, no canonical fact fabrication.

## Project Isolation Result (Phase 12)

Not executed (requires Beta server). Expected: no leakage between projects.

## Persistence Result

`apply_wiki_candidates()` + `save_snapshot()` flow remains unchanged. Compiled wiki persists through `snapshot.compiledWiki`. Unit tests verify persistence boundary.

## Regression Result

```
Wiki tests:                         64 passed, 0 failed
Core tests (CK, P10, flags, cache): 61 passed, 0 failed
G1-G3 authority gate tests:          5 passed, 0 failed
Conversation core (pre-existing):    2 failed (baseline, unrelated)
Production control (slow subset):    4 passed (inventory tests)

TOTAL:                             134 passed, 2 failed (pre-existing baseline)
```

## Playwright Result

Not executed. Requires Beta server at :8758 and Playwright setup. The Playwright flow (24 steps from fresh project through Reorganize) must be run against the live Beta.

## Beta Result

Not verified directly. Requires Beta server at :8758 + web proxy at :8760.

## Console/Network Result

Unit tests produce no console errors beyond pre-existing PydanticDeprecatedSince20 warnings. Network cleanliness requires Beta verification.

## Pre-existing Test Failures

| Test | Reason | Status |
|------|--------|--------|
| `test_correction_supersedes_old_fact` | FakeDb setup doesn't produce knowledgeEntries | BASELINE PRE-EXISTING (confirmed via git stash) |
| `test_rejection_marks_rejected` | Same FakeDb issue | BASELINE PRE-EXISTING (confirmed via git stash) |

## Remaining Risks

1. **Beta verification pending** — Phases 5-14 (fresh project, authority, Rebuild/Refine/Reorganize, Playwright) require live Beta server
2. **`maintenance.py:wiki_health_report()`** reads unfiltered entries — stale rejected/superseded entries inflate health counts (non-mutating, but could confuse diagnostics)
3. **506 certification** — Live Playwright against a brand-new disposable project is the mandatory final gate (Co-Director Law 28)
4. **Timeline generators** have independent model discovery (separate from Production Control 504 fix)

## Verdict

**READY FOR PRIMARY REVIEW — IMPLEMENTATION PASSED, LIVE CERTIFICATION PENDING**

The implementation:
- 134 unit/regression tests pass
- 0 regressions introduced
- 3 authority boundary defects (G1-G3) identified by consumer audit and repaired
- 7 distinct fix layers across 9 files
- 2 pre-existing failures confirmed as unrelated baseline defects

**Final GO requires:**
1. Beta server verification (fresh project → Story empty, Characters empty)
2. Playwright certification against brand-new disposable project (24-step prescriptive flow)
3. Network cleanliness (0 unexpected 500/502/503/504)
4. All remaining phases pass with evidence

After those steps: **GO — CODIRECTOR WIKI USER-AUTHORITY LAW CERTIFIED**
