# Co-Director 2.0 — Story Intelligence / Wiki Refinement Audit (Phase 1, READ-ONLY)

**Audit scope:** the "Story Intelligence Compiler" domain — everything that today derives, stores, or refines Logline / Short Summary / Long Summary and the story-shaped Wiki content. Mapped: `wiki_intelligence/` (all modules + `compiled/` + `compiled/story_summary_editor/` + `correction/`), the summary/logline derivation path from raw conversation, instruction-contamination handling, creator-correction authority, proposal/approval reuse, the canonical story model, and Production-Bible/Wiki refinement writers.

**Date:** 2026-08-08 · **Phase:** 1 (audit only — no implementation performed) · **Classification:** story intelligence / wiki refinement

All citations are `file:line` relative to `studio-api/app/codirector/` unless prefixed otherwise. Doc path is **Law 30**-conformant (single governing doc per milestone; superseded `docs/release-gate/compiled-wiki/*AUDIT.md` reports cited but not treated as current truth).

---

## 1. Module map — `wiki_intelligence/`

### 1.1 `wiki_intelligence/orchestrator.py` (192 lines)
- `WikiIntelligenceOrchestrator` (orchestrator.py:29) routes regex/LLM-extracted seeds through specialists and applies validated decisions to knowledge entries.
- `process_seed_texts()` (orchestrator.py:36): seeds → `detect_domains_from_entries` → `assign_specialists_for_domains` → per-seed `heuristic_department_finding` or `adapt_specialist_finding` → `_reconcile` → `_apply_decisions`.
- `_reconcile()` (orchestrator.py:95): groups findings by source, rejects preference leaks (REJECT → `references`), classifies entity type, picks CREATE/MERGE/RECLASSIFY/REVIEW, sets canonState `INFERRED` normally, `PROPOSED` when confidence ≥ 0.8.
- `_apply_decisions()` (orchestrator.py:150): maps professional sections back to legacy keys via `_legacy_section_for_professional`, builds `WikiCandidate(state=proposed|confirmed)` — **`confirmed` only when canonState==CONFIRMED; LOCKED mutations are never written here** (orchestrator.py:159) — and persists through `apply_wiki_candidates` + `save_snapshot` (orchestrator.py:178-179).
- **Story fields:** story-shaped seeds (theme/premise/synopsis/logline/beat text) classify as `story` (classification.py:119-120) and land in the `story`/`creativeFoundation` bucket; text is truncated to 400 chars; nothing here invents prose.

### 1.2 `wiki_intelligence/classification.py` (210 lines)
- `is_user_preference_not_canon()` (classification.py:46) — working-preference quarantine regex (`agent gold`, `how i'd like us to work`, `call me`, `relationship mode`, …).
- `is_false_character_name()` (classification.py:50), `classify_entity_type()` (classification.py:64, creator-learned `entity_type_overrides` consulted first at :81-84), `target_section_for_entity()` (classification.py:134 — story→`story`, preference→`references`), `normalize_alias_key`/`names_are_aliases`/`extract_display_name` (:154/:161/:174), `detect_domains_from_entries()` (classification.py:180).
- **Story fields:** `classify_entity_type` returns `story` for `theme|premise|synopsis|logline|act structure|story beat` (classification.py:119-120) → section `story` (classification.py:143).

### 1.3 `wiki_intelligence/projection.py` (126 lines)
- `project_professional_toc()` (projection.py:53) builds the nested professional TOC; `_LEGACY_TO_PRO` (projection.py:25-35) maps legacy sections onto professional roots (`creativeFoundation→story`, `knownDetails→projectOverview`, `openQuestions→story`).
- `_canon_badge()` (projection.py:38) renders state as CONFIRMED/INFERRED/EXPLORATORY/DISPUTED/SUPERSEDED.
- `attach_professional_projection()` (projection.py:116) mutates the wiki payload (`professionalToc`, `toc`, `sourceOfTruth`, `projection="professional_v1"`).
- **Story fields:** reclassifies each entry by entity type into professional buckets; **read-only presentation layer**, no writes.

### 1.4 `wiki_intelligence/assignment.py` (64 lines)
- `assign_specialists_for_domains()` (assignment.py:11): problem-driven selection from `DOMAIN_SPECIALIST_MAP`, never every specialist; always adds script-supervisor/continuity-analyst when characters/timeline/wardrobe/props/canon present (assignment.py:42-50); returns `WikiSpecialistAssignment` with budget (`contextBudgetTokens=2500`, `latencyBudgetMs=8000`, assignment.py:62-63).

### 1.5 `wiki_intelligence/intelligence_roster.py` (36 lines)
- `available_specialist_ids()` (intelligence_roster.py:20) — cached union of `SpecialistRegistry` enabled ids + planned-but-unprompted roles (`costume-designer`, `props-master`, `storyboard-artist`, `worldbuilding-specialist`, `research-specialist`, `marketing-pitch`, `project-bible-steward`, intelligence_roster.py:8-16).
- `clear_roster_cache()` (intelligence_roster.py:35).

### 1.6 `wiki_intelligence/maintenance.py` (129 lines)
- `wiki_health_report()` (maintenance.py:16) — duplicates, conflicts, incomplete profiles, invalid character fragments, recommendation.
- `tool_wiki_context()` (maintenance.py:55) — **approved, project-scoped Wiki context** for image/video/script/audio tools; skips rejected/superseded, false characters, preferences; emits `[et/state] text` lines.
- `run_wiki_maintenance()` (maintenance.py:88), `compact_tool_wiki_lines()` (maintenance.py:120).
- **Story fields:** `tool_wiki_context` includes `creativeFoundation` (story) and `worldAndSetting` by default (maintenance.py:59); this is the read side used by compilers.

### 1.7 `wiki_intelligence/reorganize.py` (650 lines)
- `_legacy_section_for_professional()` (reorganize.py:62), `_detect_problems()` (reorganize.py:81 — false characters, misplaced location/org, preference leak, alias/duplicate clusters, clipped fragments).
- `start_wiki_reorganization()` (reorganize.py:244) → `_run_reorganization()` (reorganize.py:291): alias-cluster merge (canonical = longest display name, :407-439), locked/creator-explicit protection (`preserve_locked_canon`, `USER_EXPLICIT_WIKI_WRITE` provenance, reorganize.py:448-455), false-character reject, preference leak → `references`/`reference-only` quarantine (reorganize.py:481-500), reclassify by entity type (:502-525), dedupe, revision + undo snapshot (`WikiReorganizationRevision`, reorganize.py:562-579).
- `undo_wiki_reorganization()` (reorganize.py:210) restores the pre-reorg snapshot.
- **Story fields:** final stage compiles pages via `compile_wiki_bundle` (reorganize.py:585-587) and reports `compiledStorySummary.unresolvedQuestions` (reorganize.py:617). Readability gate `repeated_theme` / `character_pollution` can fail-soft to PARTIAL (reorganize.py:604, 622-624).

### 1.8 `wiki_intelligence/finding_adapter.py` (135 lines)
- `adapt_specialist_finding()` (finding_adapter.py:16): converts a `SpecialistFinding`/dict into `WikiSpecialistFinding` with `StructuredFact(statement, field, canonState, confidence, sourceIds)`, `WikiConflict`, recommendedAction, canonRecommendation (INFERRED→PROPOSED when conf ≥ 0.85).
- `heuristic_department_finding()` (finding_adapter.py:99): deterministic structured finding used when a live LLM specialist is skipped (reorganize/orchestrator paths) — text wrapped in `"{specialist_id} reviewed: …"` (finding_adapter.py:124).
- **Story fields:** fact statements are verbatim seed text (not synthesized prose); provenance is carried in `sourceIds`.

### 1.9 `wiki_intelligence/contracts.py` (373 lines) — the frozen contracts
- `CanonState` (contracts.py:9), `WikiAction` (contracts.py:19), `SpecialistRecommendedAction` (contracts.py:20), `ExecutionMode` (contracts.py:30), `ReorgStatus` (contracts.py:31).
- `PROFESSIONAL_TOC_ROOTS` (contracts.py:43), `REORGANIZE_DOMAINS` (contracts.py:59), `DOMAIN_SPECIALIST_MAP` (contracts.py:74), **`WIKI_WRITE_SPECIALIST_IDS` allowlist (contracts.py:114-147)**, `FALSE_CHARACTER_TOKENS` (contracts.py:149).
- `StructuredFact` (contracts.py:174) — has `evidence` + `sourceIds` fields (currently underused; only `statement`/`field`/`canonState`/`confidence`/`sourceIds` populated).
- `WikiIntelligenceDecision` (contracts.py:226), `WikiReorganizationJob`/`Revision` (contracts.py:259/286).
- `ProductionCharacterProfile` (contracts.py:299) — **structured character model**: motivations, goals, fears, contradictions, relationships, arcSummary, unresolvedQuestions, sourceMessageIds/sourceAssetIds. `ProductionLocationProfile` (contracts.py:334), `ProductionTimelineEvent` (contracts.py:358).

### 1.10 `wiki_intelligence/compiled/` — the page compiler subpackage
- `page_compiler.py`:
  - `_entry_texts()` (page_compiler.py:23) — confirmed-ish knowledge only.
  - `get_compiled_wiki()` (page_compiler.py:41) — returns cached `compiled_bible_v1` or force-compiles.
  - `compile_wiki_bundle()` (page_compiler.py:49) — **deterministic** path: builds [Project Overview, Story, *Character, *Episode, World] pages, runs `compile_story_summary` (page_compiler.py:106-111), persists `compiledWiki` into the snapshot (page_compiler.py:207-208). This is the only compile path used by background `deferred_enrichment` (deferred_enrichment.py:166).
  - `compile_wiki_bundle_async()` (page_compiler.py:212) — **LLM-backed** path: runs `edit_story_summary` (page_compiler.py:228) with `conservative_fallback` (page_compiler.py:235), reuses sync bundle for pages/TOC, overwrites `storySummary` (page_compiler.py:239-246). Wired into user-triggered routes only (routers/codirector.py:889, 1040, 1048, 1201, 1473).
- `story_compiler.py` — **the current deterministic Logline/Short/Long derivation**:
  - `compile_story_summary()` (story_compiler.py:21): `narrative = [t for t in story_texts if len(t)>=40]` (story_compiler.py:29); **logline = narrative[0]** truncated to 220 (story_compiler.py:40-43); **short = first 2 narrative texts** joined (≤480) (story_compiler.py:44); **long = first 6 narrative texts** + first episode summary (≤1400) (story_compiler.py:45-47); themes mined from theme-ish strings (story_compiler.py:30-37); conflicts via keyword scan (story_compiler.py:49-54).
  - `compile_story_page()` (story_compiler.py:68) — renders Logline/Short/Long/Theme/Conflict/Episode/Open-Question sections; warm sparse nudge when Long omitted (story_compiler.py:80-108).
  - **Risk:** the deterministic path is pure concatenation — it will paste any story-section record verbatim, including instruction-shaped records.
- `overview_compiler.py` — `compile_project_overview()` (overview_compiler.py:12): natural-language Project Overview from project.name/type + facts; hardcodes `16:9` and `MiniMax H3` (overview_compiler.py:30-31).
- `character_compiler.py` — `resolve_characters()` (character_compiler.py:90): character pages; `_is_junk_name` (character_compiler.py:25), `_display_name` (character_compiler.py:62); honors `alias_map` + `entity_type_overrides`; casts questions like "What does X want most deeply right now?" (character_compiler.py:160-164).
- `episode_compiler.py` — `compile_episode_pages()` (episode_compiler.py:8): episode pages from persisted installments (summary/scene bullets/characters).
- `readability.py` — `assert_wiki_readability()` (readability.py:17): flags generic/raw titles, `repeated_theme_toc`, `character_pollution` (readability.py:34-47).
- `promotion.py` — `detect_explicit_wiki_write()` (promotion.py:22) regex (`add this to the wiki|put this in…|make this canon|belongs in the wiki`) and `promote_explicit_wiki_text()` (promotion.py:26) → `promote_note_to_wiki(…, authority="USER_EXPLICIT_WIKI_WRITE")`.
- `contracts.py` — `CompiledStorySummary` (compiled/contracts.py:37) with `logline/shortSummary/longSummary`, per-section `Coverage`, `requiresCreatorReview`, `editorMode` (`llm|deterministic`).

### 1.11 `compiled/story_summary_editor/` — the editorial story compiler
- `contracts.py`: `StorySummarySource` (story_summary_editor/contracts.py:19) — **curated evidence only**: confirmedFacts, approvedScriptSummaries, creatorStatedInterpretations, specialistInterpretations, confirmedCharacterRoles, confirmedTimelineEvents, confirmedWorldRules, inferredThemes, unresolvedQuestions, sourceIds, previousApprovedSummary. `CompiledStorySummary` (contracts.py:37).
- `editor.py`: `edit_story_summary()` (editor.py:138) — LLM-backed primary with **conservative deterministic fallback** (no silent degradation; `editorMode` records the path); `_SPECIALIST_ID="story-summary-editor"` (editor.py:32); provider resolved via `resolve_provider_for_specialists` with 45s timeout (editor.py:203, 272-282); law violations blank fields or fall back (editor.py:214-235); **result persisted directly into `compiledWiki` cache** — `_persist` (editor.py:254-269) — *not* through any proposal/approval flow.
- `evidence.py`: `build_story_summary_source()` (evidence.py:77) — classifies every knowledge entry as fact vs creator-interpretation vs specialist-interpretation by `provenance` (evidence.py:26-62; **creator-explicit = highest authority**, evidence.py:26-27, 50-62); pulls approved script summaries from creative-operating + lifecycle (evidence.py:116-132); character roles from compiled pages or `keyCharacters` (evidence.py:134-146); normalizes themes (evidence.py:148); injects learned-correction rules as highest-authority facts and drops conflicting specialist interpretations (evidence.py:150-172); `evidence_hash()` (evidence.py:210) for no-op recompile detection.
- `laws.py`: **the ten hard laws** (laws.py:62-73) — `SUMMARY_DEPTH_MUST_NOT_EXCEED_PROJECT_KNOWLEDGE`, `NO_TECHNICAL_LANGUAGE…`, `NO_SUMMARY_PLACEHOLDER_PROSE`, `NO_GENERIC_STORY_FLUFF`, `SUMMARY_REVISION_SHOULD_BE_MINIMAL…`, `SUMMARY_STYLE_MUST_BE_EDITORIAL_NOT_PROMOTIONAL`, `SUMMARY_FACTS_AND_INTERPRETATIONS_MUST_REMAIN_DISTINCT`, `DETERMINISTIC_FALLBACK_MUST_PREFER_OMISSION…`, `LOG_LINE_SHORT_AND_LONG_SUMMARY_HAVE_INDEPENDENT_READINESS`, `PREVIOUS_APPROVED_SUMMARY_SHOULD_BE_REVISED_NOT_BLINDLY_REGENERATED`. `validate()` (laws.py:241); grounding check `check_grounding` (laws.py:119-142, alias/token-tolerant, rejects invented proper nouns); fact-vs-interpretation hedge check (laws.py:145-176); stability diff (laws.py:179-205).
- `readiness.py`: independent per-section coverage — `logline_readiness` (readiness.py:24), `short_summary_readiness` (readiness.py:39), `long_summary_readiness` (readiness.py:51), `should_render` (readiness.py:68, renders ≥ PARTIAL).
- `fallback.py`: `conservative_fallback()` (fallback.py:30) — factual synopsis from confirmed facts or **omission**; long summary only when SUBSTANTIAL/MATURE (fallback.py:50).
- `theme_normalizer.py`: `normalize_theme()` (theme_normalizer.py:33) — strips `Theme: X: Thematic thread…` pollution into clean tokens.
- `triggers.py`: `should_recompile_summary()` (triggers.py:14), `is_minor_evidence_change()` (triggers.py:38) — hash + structural signals.

### 1.12 `wiki_intelligence/correction/` — creator-correction system
- `contracts.py`: `CorrectionType` (correction/contracts.py:10), `CorrectionPreview` (contracts.py:64), `CreatorWikiCorrection` (contracts.py:83), `CoDirectorLearnedCorrection` (contracts.py:100).
- `classify.py`: `classify_correction()` (classify.py:376) — LLM classifies intent + targets, heuristic fallback, ambiguity gate (`CORRECTION_MUST_NOT_GUESS_MAJOR_CANON`, classify.py:30-31, 199-206); `SUMMARY_CORRECTION` detected on `summary|logline` keyword (classify.py:182-186).
- `apply.py`: `apply_correction()` (apply.py:81) — **DETERMINISTIC_CODE_APPLIES**: supersedes (never erases) old records, writes confirmed records with `provenance="explicit_wiki_write:USER_EXPLICIT_WIKI_WRITE"` (apply.py:120-127, 141-145), **writes the instruction itself as a confirmed record** (apply.py:161-185), persists learned correction (apply.py:190-207), reversible revision (apply.py:209-229).
- `memory.py`: project-scoped correction memory (`settings_json["correctionMemory"]`, memory.py:1-6) — `active_aliases` (memory.py:77), `active_rules` (memory.py:87), `entity_type_overrides` (memory.py:92).
- `undo.py`: `undo_correction()` (undo.py:22) — snapshot restore + deactivate learned correction.

---

## 2. How Logline / Short / Long are produced today

**Two competing paths, only one of which runs in the default flow.**

### 2.1 Path A — deterministic (default, background)
```
user message → extract_documentation (discovery/documentation.py:39, regex-only)
→ DiscoveryWikiCandidate → WikiCandidate(provenance=c.status) (orchestrate.py:723-732,
   deferred_enrichment.py:96-110) → apply_wiki_candidates (conversation/knowledge.py:52)
→ snapshot.knowledgeEntries
→ compile_wiki_bundle (page_compiler.py:49) → compile_story_summary (story_compiler.py:21)
   → logline=narrative[0], short=first 2 texts, long=first 6 texts + first episode summary
→ persisted to snapshot.compiledWiki (page_compiler.py:207-208)
```
This is what runs on ordinary turns via `run_deferred_enrichment` (deferred_enrichment.py:166 calls the **sync** `compile_wiki_bundle`). The result is **concatenated record text**, not editorial prose.

### 2.2 Path B — LLM editorial editor (user-triggered routes only)
```
compile_wiki_bundle_async (page_compiler.py:212) → edit_story_summary (editor.py:138)
→ build_story_summary_source (evidence.py:77) → provider (45s timeout) → 10 laws (laws.py:241)
→ conservative_fallback if no provider → _persist into compiledWiki cache (editor.py:254-269)
```
Wired only at `routers/codirector.py:889` (script-analyze), `:1040` (wiki/promote), `:1048` (wiki/compile), `:1201` (correction/apply), `:1473` (wiki/reorganize), plus `/wiki/story-summary/refine` (codirector.py:1056-1066) and `/wiki/story-summary/correct` (codirector.py:1069-1105). **`compile_wiki_bundle_async` is never called from background enrichment**, so most conversation turns render Path A output.

### 2.3 Direct-to-field vs proposal
- **Direct-to-field, no proposal flow.** Both paths write `storySummary` straight into `snapshot.compiledWiki` (page_compiler.py:207; editor.py:263-265). `approval_required=False` for `story-summary-editor` (intelligence/contracts.py:366).
- LLM specialists never mutate knowledge entries directly; `WIKI_WRITE_SPECIALIST_IDS` (contracts.py:114) gates who may *propose*, and the orchestrator applies writes as `proposed` candidates (orchestrator.py:160-164). But that gating **does not apply to the compiled Story page fields**, which are written without proposal.
- The `ProposalService` CURRENT→PROPOSED→ACCEPT/REJECT flow (`bible/proposals.py:128-585`) exists for Bible mutations and tool calls but is **not used** for story-field generation (see §5).

---

## 3. Instruction contamination

### 3.1 Existing guards (what is enforced)
- **Chat-reply contamination** is separate from story fields: `creator_response_gate.py` (`find_contamination` :92, `gate_creator_facing` :147) strips thinking/prompt/policy leakage from creator replies. It does **not** inspect wiki/story writes.
- **Story-summary editor laws** (laws.py:62-73) reject technical language, placeholder filler ("Short summary would go here"), promotional voice, and theme-record pollution in *output*. `check_grounding` (laws.py:119-142) rejects invented proper nouns (unsupported entities) in output.
- **Input cleaning** happens in two places:
  - `extract_documentation` gates substantive messages (`is_substantive_project_message`, discovery/documentation.py:30) and filters stop-words in name extraction (documentation.py:72-76).
  - `knowledge._is_residue` / `_is_question` (conversation/knowledge.py:20-38) skip questions, greetings, and short commands; `wiki.py:_is_conversation_residue` (wiki.py:151-163) does the same for UI sections.
- **Preference quarantine:** `is_user_preference_not_canon` (classification.py:46) rejects "working preference" phrasing and reorganize moves it to `references`/`reference-only` (reorganize.py:481-500).

### 3.2 Gaps — instruction text can enter story fields
1. **No instruction/content split at capture.** A message like "Place this into the short summary: Barnes arrives at the facility." is substantive (≥60 chars, documentation.py:30-36) and the `_SUBSTANTIVE` regex (documentation.py:16-20) does **not** include instruction verbs (`place`, `put`, `summarize`, `logline`). The *instruction* is not separated from the *content* before candidate extraction, so instruction fragments can be captured as EVENT/PROJECT/overview candidates (documentation.py:131-145, 362-379).
2. **Deterministic compiler pastes verbatim.** `compile_story_summary` uses `narrative[0]` as the logline (story_compiler.py:40-43); if that record is instruction text, the logline is instruction text. `conservative_fallback` is safer (confirmed-fact sentences only) but is only reached via the async path.
3. **Explicit write paths store the instruction verbatim.**
   - `promotion.detect_explicit_wiki_write` matches "put this in…" (promotion.py:12-19) and `promote_explicit_wiki_text` writes the *message* verbatim with `USER_EXPLICIT_WIKI_WRITE` (promotion.py:26-40).
   - `correction/apply.py:161-185` — "The creator's instruction itself becomes a confirmed high-authority record" (the raw instruction text is stored as a confirmed knowledge entry).
   - `routers/codirector.py:1088-1098` (`/wiki/story-summary/correct`) appends the raw correction instruction as a `confirmed` entry with `provenance="USER_EXPLICIT_WIKI_WRITE"`.
   These are *then* read back as evidence by `build_story_summary_source` (evidence.py:100-106 treats any confirmed/USER_EXPLICIT entry as a fact), so the instruction text becomes summary evidence on the next compile.
4. **No contamination law in `laws.py`.** The ten laws check *output style* but there is no check that instruction phrases ("put this in the short summary", "change the summary to", "rewrite the logline") are absent from output, and no instruction-token blocklist at input.
5. **Prior documented bugs:** none of the existing audit reports (`docs/release-gate/compiled-wiki/STORY_SUMMARY_EDITOR_AUDIT.md`, `WIKI_CREATOR_CORRECTION_AUDIT.md`) record an explicit instruction-contamination incident. Their limitations sections note the grounding validator is alias/token heuristic and "very creative paraphrases… could in principle slip through" (STORY_SUMMARY_EDITOR_AUDIT.md:135-136). The creator-authority laws (`CREATOR_CORRECTION_PRIORITY`, `CREATOR_CORRECTION_SURVIVES_RECOMPILE`) are the documented precedent for authority precedence, not for contamination.

---

## 4. Creator corrections — authority

- **Authoritative immediately (Law 7), deterministic apply, never AI-rewritten:**
  - `correction/apply.apply_correction` (apply.py:81) writes `state="confirmed"` records with `USER_EXPLICIT_WIKI_WRITE` provenance, supersedes (never erases) old inferences, persists a project-scoped `CoDirectorLearnedCorrection` (apply.py:190-207), and is fully reversible (`undo.py:22`).
  - Authority precedence is enforced in evidence classification (evidence.py:26-62: creator-explicit > fact > specialist-interpretation), in reorganize protection (reorganize.py:448-455: LOCKED / CANON_LOCKED / USER_EXPLICIT_WIKI_WRITE are kept untouched), and in `classify_entity_type` overrides (classification.py:81-84).
  - The LLM is only allowed to *interpret* a correction (`LLM_INTERPRETS`, classify.py:1-6, :376-395); **apply is always deterministic** (`DETERMINISTIC_CODE_APPLIES`, apply.py:1-7).
- **Story-summary correction path** (`routers/codirector.py:1069-1105`): the correction is appended as a confirmed knowledge record, then `edit_story_summary` recompiles. The *record* is authoritative; the *compiled prose* is re-presented by the LLM editor from that evidence (presentation, not rewrite of the record).

---

## 5. Proposal / approval reuse — does story-field generation use CURRENT→PROPOSED→ACCEPT/REJECT?

**No. It bypasses it.**

- `ProposalService` (`bible/proposals.py:128`) implements the full flow for Bible mutations and tool calls: `create_proposal` (proposals.py:130) → `preview` (proposals.py:247) → `approve` (proposals.py:365, with staleness gate :399-416, idempotency :421-434) / `reject` (:311) / `request_revision` (:329) / `cancel` (:347) → execution receipt (:566). The docstring states this is "the only write path the model can reach on behalf of a user" (proposals.py:1-17).
- Story summary fields are written **directly** into the compiledWiki cache (`editor._persist` editor.py:254-269; `page_compiler` page_compiler.py:207) — no `CoDirectorProposal` row, no approval, no receipt.
- Wiki knowledge candidates use the *word* "proposed" as an entry state (orchestrator.py:160-164) but that is not the ProposalService flow — there is no durable proposal, preview diff, or ACCEPT/REJECT decision record for story fields.
- `story-summary-editor` is declared `approval_required=False` (intelligence/contracts.py:366).
- **Reuse target:** the ProposalService machinery (staleness, preview diff, idempotent execution, decision record, receipt) is directly adaptable to AI-derived Logline/Short/Long proposals — the payload would be a structured story-field mutation rather than a `BibleMutationSet`/`ToolCallPayload`.

---

## 6. Canonical story model — what exists

There is **no single authoritative structured story model** (premise/protagonist/objective/conflict/stakes/setting/tone/genre/characters/relationships/beats/ending/themes) consumed by the compiler. Partial models exist in five places:

1. **`conversation/discovery/brief.py` — `LivingProjectBrief.fields`** (brief.py:42-58): `project_identity, format, genre, tone, premise, audience_experience, main_characters, central_conflict, timeline, world_rules, visual_direction, themes, open_questions, confirmed_decisions, setting` — the closest living story-brief, grown gently from conversation (brief.py:25-40). **Not consumed by `build_story_summary_source`.**
2. **`conversation/partnership/story_template.py` — `build_story_template`** (story_template.py:18): working_title, format, genre, tone, audience promise, core premise, protagonist, protagonist goal, central conflict, inciting event, key relationships, world/setting, story stakes, themes, visual identity, open questions, destination — a `CreativeDeliverable` with field marks (Confirmed/Emerging/Needs decision). **Not consumed by the compiler.**
3. **`bible/domain/schemas.py` + `bible/schemas.py`:** `ProjectOverviewData` (domain/schemas.py:19 — name, description, genre, tone, logline), `CharacterData` (domain/schemas.py:31 — goals, fears, arcSummary, affiliations, aliases), `RelationshipData` (domain/schemas.py:172), `TimelineEntryData` (domain/schemas.py:218); entity types `story_arc`, `story_beat`, `narrative_thread` declared in `EntityType` (bible/schemas.py:9-33).
4. **`wiki_intelligence/contracts.py`:** `ProductionCharacterProfile` (contracts.py:299 — motivations, goals, fears, contradictions, relationships, arcSummary), `ProductionLocationProfile` (contracts.py:334), `ProductionTimelineEvent` (contracts.py:358).
5. **`conversation/companion/lens.py`:** `ProjectCreativeLens` (lens.py:10-30 — emotional tones, dominant genres, artistic priorities, pacing). **Not consumed by the compiler.**

The compiler's actual evidence today (`StorySummarySource`, story_summary_editor/contracts.py:19) is **knowledge entries + script summaries + character roles + timeline/world rules + themes** — a flat list, **not** the structured brief/template fields. Notably absent from compiler evidence: **premise, protagonist objective, story stakes, beats, ending/destination, relationships, audience promise.**

---

## 7. Wiki refinement / Production Bible refinement writers

- **`wiki.py` — `build_project_wiki`** (wiki.py:327): authoritative UI wiki. `SECTION_KEYS` (wiki.py:27-37); `normalize_wiki_section` (wiki.py:75) and `_section_key_for_message` (wiki.py:186) map arbitrary category text to UI sections; `_sanitize_text` strips UUIDs/whitespace and caps 320 chars (wiki.py:86-89); `_is_conversation_residue` (wiki.py:151-163) rejects questions/greetings/commands; merges discovery candidates (wiki.py:239-267) and asset references (wiki.py:270-324); attaches `USER_EXPLICIT_WIKI_WRITE`/`proposed` states from snapshot (wiki.py:358-392); **strips preferences and false-character fragments from creator surfaces** (wiki.py:503-529); attaches professional projection (wiki.py:544-549) and compiled Bible (wiki.py:550-568, overview prose preferred at :564-567).
- **`wiki_export.py`:** `build_export_model` (wiki_export.py:235), `export_pdf_bytes` (wiki_export.py:292), `export_offline_html_zip` (wiki_export.py:413); strips internal keys/UUIDs (wiki_export.py:46-61, 96-108).
- **`conversation/wiki_rebuild.py`:** `rebuild_wiki_from_conversation` (wiki_rebuild.py:54) — fold events → extract → dedupe → persist → read-back verify → cache refresh.
- **`conversation/wiki_verification.py`:** `build_verification` (wiki_verification.py:43) — PERSISTED/VERIFIED/VISIBLE states; `WIKI_VERIFICATION_NEVER_BLOCKS_TTFT` (wiki_verification.py:10).
- **Wiki-write allowlisted specialists:** `WIKI_WRITE_SPECIALIST_IDS` (contracts.py:114-147) gates `mayProposeWikiWrites` in `build_contract` (intelligence/specialist_policies.py:62-84); the orchestrator applies writes, specialists only propose structured findings (specialist_policies.py:78). **This allowlist governs knowledge-entry proposals — it does not cover compiled Logline/Short/Long writes.**
- **Production Bible refinement** (proposal path): `bible/proposals.py` + `bible/operations.apply_mutation_set` (proposals.py:448-450) + `bible/domain/schemas.validate_entity_data` (domain/schemas.py:254). Separate from the wiki_intelligence story-field path.

---

## 8. Classification matrix

| Component | Current Role | File/Function citations | Classification | Target Role in 2.0 | Risk |
| --- | --- | --- | --- | --- | --- |
| `compiled/story_compiler.py` `compile_story_summary` | Deterministic Logline/Short/Long = concatenated story texts | story_compiler.py:21, 40-47 | **SUPERSEDE** (by editor fallback) | Remove from default path; keep only as a debugging/legacy reader | Can paste instruction-laden or un-edited records as logline |
| `compiled/story_summary_editor/editor.py` `edit_story_summary` | LLM editorial compile, direct cache write | editor.py:138, 254-269 | **ADAPT** | 2.0 compiler primary: produce a *proposed* story-field result | Must stop direct write; add proposal emit |
| `compiled/story_summary_editor/evidence.py` `build_story_summary_source` | Curated evidence w/ provenance classification (fact/creator/specialist) | evidence.py:77, 26-62, 150-172 | **KEEP + ADAPT** | Authoritative source builder for the compiler; add brief/template fields | None major; add structured story inputs |
| `compiled/story_summary_editor/laws.py` `validate` | Ten post-condition laws; grounding heuristic | laws.py:62-73, 241, 119-142 | **KEEP + ADAPT** | Core validation gate; add instruction-contamination law + per-source citation check | Grounding is token/alias heuristic (documented gap) |
| `compiled/story_summary_editor/readiness.py` | Per-section coverage MINIMAL→MATURE | readiness.py:24, 39, 51, 68 | **KEEP** | Gates for when a story-field *proposal* is warranted | Low |
| `compiled/story_summary_editor/fallback.py` `conservative_fallback` | Factual synopsis or omission | fallback.py:30 | **KEEP** | Guaranteed-safe deterministic result for proposal preview / no-provider mode | Low |
| `compiled/story_summary_editor/triggers.py` | Recompile/minor-change classification | triggers.py:14, 38 | **KEEP** | Decides when a story-field proposal is needed | Low |
| `compiled/page_compiler.py` `compile_wiki_bundle(_async)` | Sync deterministic compile; async LLM compile (routes only) | page_compiler.py:49, 212-246 | **ADAPT** | Wire async/LLM path into background enrichment; route writes through proposal | Async path currently unused on ordinary turns |
| `wiki_intelligence/orchestrator.py` | Routes seeds → specialists → proposed wiki candidates | orchestrator.py:36, 95, 150-180 | **KEEP + ADAPT** | Reuse decision/applied model for story-field proposals | Never promotes to CONFIRMED w/o creator action; extend to story fields |
| `wiki_intelligence/classification.py` | Entity routing, preference/false-char filters | classification.py:46, 64, 134 | **KEEP + ADAPT** | Add instruction-token rejection at classification; story→`story` routing stays | Instruction verbs not in preference regex |
| `wiki_intelligence/projection.py` | Professional TOC read-only projection | projection.py:53, 116 | **KEEP** | Unchanged | Low |
| `wiki_intelligence/assignment.py` + `intelligence_roster.py` | Problem-driven specialist assignment | assignment.py:11; intelligence_roster.py:20 | **KEEP** | Unchanged | Low |
| `wiki_intelligence/finding_adapter.py` | Specialist finding → structured fact | finding_adapter.py:16, 99 | **KEEP** | Unchanged; structured facts carry `evidence`/`sourceIds` | `evidence` field underused |
| `wiki_intelligence/contracts.py` | Frozen contracts; `WIKI_WRITE_SPECIALIST_IDS` allowlist | contracts.py:114, 174, 226, 299 | **KEEP + ADAPT** | Add story-field proposal/decision contracts; allowlist covers compiled fields | None |
| `wiki_intelligence/reorganize.py` | Canon cleanup, merge/reclassify/quarantine, locked-canon protection | reorganize.py:81, 291, 448-500 | **KEEP** | Unchanged | Low |
| `wiki_intelligence/maintenance.py` | Health report + approved tool context | maintenance.py:16, 55 | **KEEP** | Unchanged | Low |
| `wiki_intelligence/correction/` | Creator correction: classify (LLM) → deterministic apply → learned memory → undo | classify.py:376; apply.py:81, 161-185; memory.py:77-102; undo.py:22 | **KEEP** | Creator-authoritative override for compiled story fields too | Instruction verbatim write (apply.py:161-185) feeds summary evidence |
| `bible/proposals.py` `ProposalService` | The one durable propose→approve→execute flow | proposals.py:128-585 | **ADAPT (reuse)** | Back the CURRENT→PROPOSED→ACCEPT/REJECT flow for AI-derived story fields | Currently unused for story fields |
| `conversation/discovery/documentation.py` `extract_documentation` | Regex capture from user message | documentation.py:39, 30-36 | **KEEP + ADAPT** | Add instruction/content split + contamination token filter | Captures instruction fragments |
| `conversation/discovery/brief.py` + `partnership/story_template.py` | LivingProjectBrief fields; story template deliverable | brief.py:14-67; story_template.py:18-109 | **ADAPT** | Canonical story model inputs to the compiler (premise/protagonist/conflict/stakes/beats/ending) | Not consumed by compiler today |
| `wiki.py` / `wiki_export.py` / `conversation/wiki_rebuild.py` / `conversation/wiki_verification.py` | UI wiki build, export, rebuild, verification | wiki.py:327, 503-529; wiki_export.py:235; wiki_rebuild.py:54; wiki_verification.py:43 | **KEEP** | Unchanged; compiler output surfaces through these | Low |
| `conversation/knowledge.py` `apply_wiki_candidates` | Supersede/reject lifecycle for knowledge entries | knowledge.py:52-93 | **KEEP + ADAPT** | Reuse supersede semantics for story-field revisions | Residue filter weak for instruction text |

---

## 9. COMPILER GAP — what is missing for the 2.0 Logline / Short / Long compilers

### 9.1 Missing (must be built)
1. **Proposal/approval for AI-derived story fields.** Story summaries are written directly into `compiledWiki` (editor.py:254-269; page_compiler.py:207) with `approval_required=False` (intelligence/contracts.py:366). 2.0 requires CURRENT→PROPOSED→ACCEPT/REJECT via `ProposalService`-style flow (staleness, preview diff, decision record, receipt) for compiled Logline/Short/Long — a structured `story-field mutation` payload analogous to `BibleMutationSet` (bible/schemas.py:212).
2. **Clean evidence structure with source provenance.** Today `StructuredFact` has `evidence`+`sourceIds` (contracts.py:174) but `CompiledStorySummary` carries only a flat `sourceRecordIds` (contracts.py:47) and a lossy `evidence_hash` (evidence.py:210). There is **no sentence/field-level grounding map** (which evidence supports the logline vs short vs long).
3. **Instruction/content split at capture.** `extract_documentation` has no separator for instruction text ("Place this into the short summary") vs story content; instruction verbs (`place|put|summarize|logline|short summary`) are absent from `_SUBSTANTIVE` (documentation.py:16-20) and from `is_user_preference_not_canon` (classification.py:10-13). Need an input-cleaning/instruction-strip step before candidate extraction.
4. **Contamination validation law.** `laws.py` has no law rejecting instruction phrases in output, and no instruction-token blocklist in evidence. Add a law e.g. `NO_INSTRUCTION_CONTAMINATION_IN_SUMMARIES` checked as a post-condition over all three fields, plus an input-side filter.
5. **Deterministic path safety.** `compile_story_summary` (story_compiler.py:40-47) can paste instruction-bearing records as logline/short/long. The default background path must either use the safe fallback (`conservative_fallback`, fallback.py:30) or route through the editor; `compile_wiki_bundle_async` must be invoked from `deferred_enrichment` (deferred_enrichment.py:166) instead of the sync compiler.
6. **Structured story model consumption.** `StorySummarySource` ignores `LivingProjectBrief.fields` (brief.py:42-58) and `story_template` fields (story_template.py:10-87) — premise, protagonist objective, stakes, beats, ending, relationships, audience promise are missing from compiler evidence.
7. **Grounding upgrade.** `check_grounding` (laws.py:119-142) is proper-noun alias/token matching, not semantic; per the documented limitation (STORY_SUMMARY_EDITOR_AUDIT.md:135-136), creative paraphrases can slip. 2.0 needs authoritative citation per summary sentence.
8. **Summary-field supersede/versioning.** Repeated compiles overwrite `compiledWiki["storySummary"]` (editor.py:263) with no revision diff of logline/short/long beyond the `revisionDelta` string; reuse `apply_wiki_candidates` supersede semantics (conversation/knowledge.py:74-91) for story fields.

### 9.2 Adaptable from existing modules (do not rebuild)
- Provenance classification (fact/creator/specialist) — `evidence.py:26-62`.
- Creator-authority override + learned corrections — `correction/memory.py:77-102`, `apply.py:190-207`.
- Ten-law post-condition gate — `laws.py:241` (extend, don't replace).
- Per-section readiness — `readiness.py:24-68`.
- Safe deterministic fallback — `fallback.py:30`.
- Recompile triggers / minor-change detection — `triggers.py:14-51`.
- Proposal machinery (staleness, preview, idempotent approve, receipt) — `bible/proposals.py:128-585`.
- Supersede/reject lifecycle — `conversation/knowledge.py:52-93`.
- Locked-canon protection — `reorganize.py:448-455`.
- Explicit-write promotion — `compiled/promotion.py:22-40`.
- Tool-context read path — `maintenance.py:55-85`.

---

## 10. Summary verdict

The 2.0 "Story Intelligence Compiler" is **partially pre-built and heavily reusable**: the editorial editor (`story_summary_editor/`), the evidence classifier, the ten laws, readiness, triggers, fallback, and the creator-correction system already implement most compiler mechanics. What is missing is (a) routing story-field writes through the existing proposal/approval flow, (b) a per-field provenance/grounding map, (c) instruction/content separation and an instruction-contamination law, (d) consuming the structured brief/template story model, and (e) making the safe async editor the default path instead of the concatenation-based `story_compiler`. No implementation was performed in this audit.
