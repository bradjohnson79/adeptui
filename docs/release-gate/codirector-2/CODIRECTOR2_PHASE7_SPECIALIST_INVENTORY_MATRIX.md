# Co-Director 2.0 — Phase 7 Specialist Inventory Matrix (READ-ONLY)

| Field | Value |
|---|---|
| Deliverable | Agent A specialist inventory matrix for Phase 7 Specialist Crew Rewire |
| Kind | **Audit artifact only — no source code edited** |
| Date | 2026-08-08 |
| Contract | `CODIRECTOR2_PHASE7_SPECIALIST_CREW_IMPLEMENTATION_CONTRACT.md` (frozen) |
| Prior audit | `CODIRECTOR2_SPECIALIST_REUSE_AUDIT.md` (verified live; disagreements listed in §7) |
| Status | `READY FOR PRIMARY REVIEW` — subagent never claims GO |

Evidence base is **live runtime + source reading** (read-only Python against the real
`PromptLibrary` / `SpecialistRegistry` / contracts / policies), not the prior audit alone.

---

## 1. Runtime count verification

Executed from `C:\AdeptFilmWorks\AIVideoStudio\studio-api`:

```text
> python -c "from app.codirector.intelligence.specialist_registry import SpecialistRegistry; print(len(SpecialistRegistry().ids()))"
# => 40
```

| Fact | Value | Evidence |
|---|---|---|
| Enabled specialist count | **40** | `SpecialistRegistry().ids()` — exact, dynamic |
| Registry mechanism | Declarative via YAML front matter in `prompts/specialists/*.md`; `_rebuild()` keeps only `enabled` | `specialist_registry.py:60-65` |
| Prompt files scanned | 40 `.md`, all `type: specialist`, all `enabled: true` | `PromptLibrary.by_type("specialist")` |
| Covered by `CONTRACTS` | **33** | `intelligence/contracts.py` |
| Uncovered (no `SpecialistContract`) | **7** | see §2 legend |
| `may_execute_tools` | **False for all 40** (hard-blocked at `prompts/validator.py` AND `specialist_registry._from_prompt`) | runtime dump + `specialist_registry.py:69-70` |
| Policy-layer roster | `authoritative_roster()` builds 40 `CoDirectorSpecialistContract`s (synthesized for the 7 uncovered) | `specialist_policies.py:87-89` |
| Wiki-write allowlist | `WIKI_WRITE_SPECIALIST_IDS` = **30 ids**, all present in the 40 | `wiki_intelligence/contracts.py:114-147` |

The prior audit's count (40), contract split (33/7), and the exact 7 uncovered ids
(`costume-designer`, `marketing-pitch`, `project-bible-steward`, `props-master`,
`research-specialist`, `storyboard-artist`, `worldbuilding-specialist`) are **confirmed
identical** at runtime.

---

## 2. Per-specialist rows (all 40)

Legend: **MPT** = `may_propose_tools` (front matter); **MET** = `may_execute_tools`
(**False for every specialist — enforced at load and at registry build**); **AR** =
`approval_required` from `SpecialistContract` (blank = no contract → synthesized
`requiresCreatorApproval` from MPT only); **WW** = in `WIKI_WRITE_SPECIALIST_IDS`;
prompt file = `app/codirector/prompts/specialists/<id>.md`. Rows sorted by
`default_priority` desc then id (matches `all_enabled()`).

| # | id | display name | prompt file | allowed_context | MPT | AR | WW | ESCL path / hard rule | prio | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | director | Director | director.md | scene, characters, locations, continuity, visual_language | Y | – | Y | Canon→Bible Manager; QA→QA Reviewer | 90 | **KEEP** |
| 2 | project-bible-steward | Project Bible Steward | project-bible-steward.md | project_overview, canon, characters, locations, story, continuity | N | – | Y | HR: organize Project Bible; never mutate locked canon; never creator-facing | 90 | **MERGE → bible-manager** |
| 3 | story-analyst | Story Analyst | story-analyst.md | project_overview, story, scene, characters, canon | Y | – | Y | Canon conflicts→Bible Manager; feasibility→Pipeline Manager | 88 | **KEEP** |
| 4 | bible-manager | Production Bible Manager | bible-manager.md | project_overview, canon, characters, locations, story, continuity | Y | **Y** | Y | Locked conflicts→User Review; continuity→Continuity Supervisor; HR: propose only, never silent mutate | 86 | **KEEP+TIGHTEN** (absorb steward) |
| 5 | producer | Producer | producer.md | project_overview, scene, capabilities, production_decisions | Y | **Y** | Y | Budget/capability blockers→User Review; HR: destination-aware, no forced commercialization | 85 | **KEEP+TIGHTEN** (heavy, BACKGROUND_ONLY) |
| 6 | pipeline-manager | Pipeline Manager | pipeline-manager.md | capabilities, scene, shot, project_overview | Y | – | Y | Missing capabilities→User; mutations→proposal paths; HR: technical workflow only | 84 | **KEEP** (heavy) |
| 7 | code-director | Code Director | code-director.md | capabilities, project_overview | Y | – | N | Schema breaks→Pipeline Manager; never fake CONNECTED | 83 | **DEFER** (dev-facing, not creator crew) |
| 8 | technical-director | Technical Director | technical-director.md | capabilities, shot, scene | Y | – | N | Missing capabilities→Pipeline Manager | 82 | **KEEP+TIGHTEN** |
| 9 | screenwriter | Screenwriter | screenwriter.md | project_overview, scene, characters, story, canon | Y | – | Y | Canon→Bible Manager; HR: respect ownership/locked scripts; draft only when authorized | 80 | **KEEP** (heavy, drafts) |
| 10 | story-summary-editor | Story Summary Editor | story-summary-editor.md | project_overview, story, characters, canon, continuity | N | – | N | Canon conflicts→Bible Manager; insufficient evidence→omit section; presentation, not invention | 80 | **KEEP+TIGHTEN** |
| 11 | continuity-analyst | Continuity Analyst | continuity-analyst.md | continuity, characters, wardrobe, scene, previous_shot, next_shot | Y | **Y** | Y | Unresolved→Bible Manager + User Review; HR text claims mayProposeWikiWrites=false but WW=True at runtime (**inconsistency, §7**) | 78 | **KEEP** (heavy) |
| 12 | prompt-architect | Prompt Architect | prompt-architect.md | shot, characters, locations, references, visual_language, capabilities | Y | – | N | Missing refs→Asset Manager | 76 | **KEEP+TIGHTEN** (sole concrete tool proposal `propose_storyboard_generation`) |
| 13 | story-editor | Story Editor | story-editor.md | project_overview, story, scene, characters, canon | Y | – | Y | Story Analyst for beat conflicts; HR: don't overwrite locked script sections | 75 | **KEEP** (drafts) |
| 14 | script-supervisor | Script Supervisor | script-supervisor.md | scene, characters, continuity, story | Y | – | Y | Continuity→Continuity Supervisor | 74 | **KEEP+TIGHTEN** (scope to script continuity only) |
| 15 | art-director | Art Director | art-director.md | visual_language, characters, locations, references, wardrobe | Y | – | Y | Lighting→Lighting Supervisor | 72 | **KEEP** |
| 16 | cinematographer | Cinematographer | cinematographer.md | scene, shot, visual_language, locations, previous_shot, next_shot, continuity | Y | – | Y | Lighting→Lighting Supervisor; caps→Pipeline Manager; HR: visual/shot guidance only | 70 | **KEEP** (heavy) |
| 17 | production-designer | Production Designer | production-designer.md | locations, objects, scene, visual_language | Y | – | Y | Asset gaps→Asset Manager | 68 | **KEEP** |
| 18 | worldbuilding-specialist | Worldbuilding Specialist | worldbuilding-specialist.md | story, locations, continuity, canon, characters | N | – | Y | (no contract — synthesized policy rule only) | 67 | **DEFER** |
| 19 | performance-director | Performance Director | performance-director.md | scene, characters, story | Y | – | Y | Story conflicts→Story Analyst; HR: never speak as Co-Director | 66 | **KEEP** |
| 20 | choreographer | Choreographer | choreographer.md | scene, characters, shot, continuity | Y | – | N | Animation→Animation Supervisor | 65 | **MERGE → director / animation-supervisor** |
| 21 | editor | Editor | editor.md | scene, shot, previous_shot, next_shot | Y | – | Y | Continuity cuts→Continuity Supervisor; timeline mutations→approval | 64 | **KEEP** |
| 22 | qa-reviewer | QA Reviewer | qa-reviewer.md | scene, shot, continuity, references, visual_language, capabilities | Y | **Y** | N | Unresolved blockers→User Review | 63 | **KEEP** |
| 23 | vision-reviewer | Vision Reviewer | vision-reviewer.md | shot, references, continuity, visual_language | Y | **Y** | N | Unresolved defects→QA Reviewer / User Review | 62 | **KEEP** |
| 24 | asset-manager | Asset Manager | asset-manager.md | characters, locations, references, scene, capabilities | Y | **Y** | Y | Missing locked refs→User Review | 61 | **KEEP** |
| 25 | casting-director | Casting Director | casting-director.md | characters, references, wardrobe | Y | – | Y | Missing identity refs→Asset Manager; HR: no creator-facing voice | 60 | **KEEP** |
| 26 | lighting-supervisor | Lighting Supervisor | lighting-supervisor.md | scene, shot, locations, visual_language, continuity | Y | – | Y | Camera exposure→Cinematographer | 59 | **KEEP** |
| 27 | vfx-supervisor | VFX Supervisor | vfx-supervisor.md | scene, shot, vfx, capabilities | Y | – | Y | Comp→Compositing Supervisor | 58 | **KEEP** (heavy) |
| 28 | animation-supervisor | Animation Supervisor | animation-supervisor.md | scene, shot, characters, continuity, capabilities | Y | – | N | Capability gaps→Pipeline Manager | 57 | **KEEP** (heavy) |
| 29 | compositing-supervisor | Compositing Supervisor | compositing-supervisor.md | scene, shot, vfx, capabilities, visual_language | Y | – | N | Render gaps→Pipeline Manager | 56 | **MERGE → vfx-supervisor** |
| 30 | character-creator | Character Creator | character-creator.md | characters, references, wardrobe, story, continuity | Y | **Y** | Y | Canon→Bible Manager; refs→Casting Director (alias `character_creator`) | 55 | **KEEP** |
| 31 | sound-designer | Sound Designer | sound-designer.md | scene, locations, audio | Y | – | Y | Music clashes→Music Supervisor; caps→Pipeline Manager; HR: audio design only | 55 | **KEEP+TIGHTEN** (heavy) |
| 32 | costume-designer | Costume Designer | costume-designer.md | characters, wardrobe, continuity, story, references | N | – | Y | (no contract — synthesized policy rule only) | 54 | **DEFER** |
| 33 | props-master | Props Master | props-master.md | characters, story, continuity, references | N | – | Y | (no contract — synthesized policy rule only) | 53 | **DEFER** |
| 34 | virtual-production-coordinator | Virtual Production Coordinator | virtual-production-coordinator.md | scene, shot, locations, visual_language, continuity, production_plan | Y | **Y** | N | Escalate→continuity-analyst (alias `vpc`) | 52 | **KEEP** |
| 35 | storyboard-artist | Storyboard Artist | storyboard-artist.md | story, visual_language, characters, references, shot, scene | N | – | Y | (no contract — synthesized policy rule only) | 51 | **DEFER** |
| 36 | music-supervisor | Music Supervisor | music-supervisor.md | project_overview, scene, story | Y | – | Y | SFX conflicts→Sound Designer; caps→Pipeline Manager; HR: destination-aware | 50 | **DEFER** (heavy; folded into sound-producer crew) |
| 37 | research-specialist | Research Specialist | research-specialist.md | story, references, canon, locations | N | – | Y | (no contract — synthesized policy rule only) | 49 | **DEFER** |
| 38 | sound-producer | Sound Producer | sound-producer.md | scene, audio, music, dialogue, continuity | Y | – | Y | (none in contract; SonicConcept lead, explicit "coordinates" designer+supervisor) | 48 | **KEEP** (heavy; audio crew lead) |
| 39 | marketing-pitch | Pitch and Marketing Producer | marketing-pitch.md | story, production_plan, production_decisions, references | N | – | Y | (no contract — synthesized policy rule only); pitch/marketing is not a crew consult lane | 47 | **RETIRE** (from consult crew) |
| 40 | storyteller | Storyteller | storyteller.md | scene, characters, story, tone, continuity | Y | – | Y | (none in contract; approval-aware StorytellerProductionHandoff) | 40 | **KEEP** (drafts) |

Derived runtime facts (policy layer, `specialist_policies.build_contract`):
- `executionMode = BACKGROUND_ONLY` for **10 heavy ids**: producer, pipeline-manager,
  screenwriter, continuity-analyst, cinematographer, music-supervisor, sound-designer,
  sound-producer, vfx-supervisor, animation-supervisor (`_HEAVY_IDS`).
- `mayCreateDrafts = True` only for **`screenwriter`, `story-editor`, `storyteller`**.
- `requiresCreatorApproval` (policy) = `may_propose_tools` for every specialist — a
  **separate** approval field from contract `approval_required` (8 contracts: bible-manager,
  producer, continuity-analyst, qa-reviewer, vision-reviewer, asset-manager,
  character-creator, virtual-production-coordinator). Both retained; contract field wins in §3.

---

## 3. Overlap analysis — KEEP / KEEP+TIGHTEN / MERGE / DEFER / RETIRE

**Tallies: KEEP = 22 · KEEP+TIGHTEN = 7 · MERGE = 3 · DEFER = 7 · RETIRE = 1 (Σ 40)**

| Verdict | Count | ids |
|---|---|---|
| KEEP | 22 | director, story-analyst, pipeline-manager, screenwriter, continuity-analyst, story-editor, art-director, cinematographer, production-designer, performance-director, editor, qa-reviewer, vision-reviewer, asset-manager, casting-director, lighting-supervisor, vfx-supervisor, animation-supervisor, character-creator, virtual-production-coordinator, sound-producer, storyteller |
| KEEP+TIGHTEN | 7 | bible-manager (core, absorbs steward — canon gate, AR=True), producer, technical-director, story-summary-editor, prompt-architect, script-supervisor, sound-designer |
| MERGE | 3 | project-bible-steward→**bible-manager**; choreographer→**director**/**animation-supervisor**; compositing-supervisor→**vfx-supervisor** |
| DEFER | 7 | code-director, worldbuilding-specialist, costume-designer, props-master, storyboard-artist, music-supervisor, research-specialist |
| RETIRE | 1 | marketing-pitch (out of consult crew — no creator consult lane; keep persona for a future pitch module, never a per-turn crew member) |

Each specialist is in exactly one bucket; **Σ = 22 + 7 + 3 + 7 + 1 = 40**.

### Explicitly flagged trios

**a) `project-bible-steward` vs `bible-manager` — MERGE**
Near-identical allowed_context (only difference: steward adds nothing bible-manager lacks —
both `project_overview, canon, characters, locations, story, continuity`), same MPT on
bible-manager only, both WW. Steward has **no contract**, tasks background organization /
periodic stewardship; bible-manager owns canon proposals with AR=True. **Recommendation:
fold `project-bible-steward` into `bible-manager` (one canon/Bible steward; stewardship mode
becomes a `bible-manager` mode).** Keep the persona text as a mode/adjunct, do not run both
in any crew.

**b) `story-summary-editor` vs `story-editor` vs `screenwriter` — KEEP ALL with scope walls**
These read overlapping but split cleanly by output contract and route class:
- `screenwriter` (dialog/script **production**; heavy, drafts, scale/ownership) →
  `PROPOSE_CREATIVE_CHANGE` / `EXECUTE_PRODUCTION` dialogues.
- `story-editor` (arc **coherence**; drafts; WW) → `MODIFY_KNOWLEDGE` story / arc advisory.
- `story-summary-editor` (creator-facing **presentation**; dedicated `story-summary-v1`
  schema; `confidence_required=False`, `reasoning_required=False`; MPT=False) →
  `MODIFY_KNOWLEDGE` summary writes, never a per-turn creative adjudicator.
**Recommendation: KEEP+TIGHTEN each (allowed_context/responsibility walls), do NOT merge** —
distinct output schemas and distinct route fit. This disagrees mildly with the prior audit,
which lumps them as one "overlapping story/presentation duties" prune target.

**c) `sound-designer` vs `sound-producer` vs `music-supervisor` — one lead, one subordinate, one deferred**
- `sound-producer` (SonicConcept / score / ambience / cues / mix intent; explicitly
  "coordinates Music Supervisor and Sound Designer") = **single audio crew lead** → KEEP.
- `sound-designer` (SFX/ambience/dialogue minutes; heavy) = optional **cross-domain
  subordinate** → KEEP+TIGHTEN.
- `music-supervisor` (cues/tempo/stingers) = **DEFER** from default crew (covered by
  sound-producer's score brief; keep persona for destination-aware music-only turns).
Current `plan_audio` spawns `sound-designer, music-supervisor, editor, director` (4) — under
the frozen max-3 rule this must become `sound-producer` (+`sound-designer` optional) = 1–2.

### Secondary overlap notes
- `choreographer ↔ director(blocking) ↔ animation-supervisor(motion)` → MERGE choreographer
  into animation-supervisor (motion) with director owning blocking.
- `compositing-supervisor ↔ vfx-supervisor` → nearly identical allowed_context
  (`scene, shot, vfx, capabilities` [+visual_language]) → MERGE into vfx-supervisor.
- `worldbuilding-specialist ↔ bible-manager(canon) ↔ production-designer(locations)` and
  `costume-designer / props-master / storyboard-artist ↔ character-creator / production-designer`
  are contract-free niche personas → DEFER (need contracts + scope before reuse;
  contiguous coverage already exists in the KEEP set).
- `_DOMAIN_SPECIALIST_MAP` (`wiki_intelligence/contracts.py:74-111`) references DEFER'd ids
  (`costume-designer`, `props-master`, `storyboard-artist`, `worldbuilding-specialist`,
  `research-specialist`, `project-bible-steward`) — map must be updated in lockstep with the
  crew rewire to avoid routing to retired/deferred specialists (contract §1: list stays one
  source of truth).

---

## 4. Spins (as-shipped, pre-rewire)

Computed from `specialist_selector.py` + `intelligence/service.py`:

| Item | Value |
|---|---|
| `MAX_SPECIALISTS` | **8** (`specialist_selector.py:11`) — Phase 7 replaces with **default 1, hard max 3** |
| `plan_scene` spawns | **8** — story-analyst, director, screenwriter, producer, cinematographer, script-supervisor, sound-designer, music-supervisor (`:15-24`) |
| `revise_dialogue` spawns | **4** — screenwriter, story-editor, performance-director, sound-designer (`:14`) |
| Other spawns | create_storyboard 8, prepare_video_generation 8, production_intelligence 8, unified_experience 7, review_asset 6, design_location 5, prepare_image_generation 6, assemble_sequence 5, virtual_production 6, environment_studio 5, storyteller_discovery 5, sound_production 5, create_character 5, revise_character 5, plan_audio 4, answer_question 2, unknown 3 |
| Continuity auto-inject | adds continuity-analyst for `_CONTINUITY_INTENTS` (incl. create/revise_character, plan_scene, revise_dialogue, unified_experience, storyteller_discovery, sound_production) — **adds nothing when crew already at 8** (e.g. plan_scene) |
| Runtime selection | `intelligence/service.py:230` `self.selector.select(intent)` against legacy `IntentClassification`; foundation tank (`run_foundation_creative_pass`) is a **separate parallel stack** selected by `foundation/creative/routing.py` (12 ids) — the two stacks are NOT synchronized |
| Partitions | required = min(3, len) for standard, min(1, len) for simple; rest optional; overflow→skipped (`:158-161`) |
| No confidence / no route decision / no workflow-stage awareness | selector static; confidence assigned downstream (intent 0.85/0.45, heuristic 0.55, synthesis 0.88/0.62/0.55) |

Phase 7 target (frozen contract §3): `MAX_SPECIALISTS = 3`; RouteDecision-aware; NAVIGATE/READ
→ 0; DISCUSS → 1; cross-disciplinary max 2–3; structured `selectionConfidence`(0..1) +
`targetDomain`; zero-specialist guard enforced at selection **and** service layer.

---

## 5. Suggested minimal crew mapping per RouteActionClass

Basis: frozen contract §3 minimum-crew table + the KEEP set in §3 (post-merge crew = 24 core ids).

| RouteActionClass | Crew | Recommended specialist ids (default → optional) | Rationale |
|---|---|---|---|
| NAVIGATE | **0** (hard guard) | — | Operator lane only; needs zero specialists |
| READ_INSPECT | **0** | (compelling analytic request may justify 1: story-analyst) | Native reads, not crew work |
| APPROVE / REJECT | **0** | — | Proposal / anti-proposal lane |
| CLARIFY / AMBIGUOUS / UNKNOWN | **1** (best-guess Domain Expert) | director → (story-analyst) | One guess, no deep crew |
| DISCUSS | **1** | director / storyteller / sound-producer (topic-selected) | Focused single-expert view; pick by targetDomain |
| MODIFY_KNOWLEDGE | **1** | bible-manager (canon) / story-editor (story arc) / story-summary-editor (summary writes) | Single-domain steward; AR=True where canon/entity mutation is proposed |
| PROPOSE_CREATIVE_CHANGE | **1–2** | primary (screenwriter / character-creator / director) + optional cross-domain (story-editor, sound-producer, casting-director) | Primary + one cross-domain contributor |
| EXECUTE_PRODUCTION | **2–3** (max 3) | director or virtual-production-coordinator (lead) + cinematographer / sound-producer / editor / vision-reviewer as needed | Bounded production crew |

### Per legacy intent (what the old `_INTENT_SPECIALISTS` should become)

| Legacy intent | Recommended ids | Crew size |
|---|---|---|
| create_character | **character-creator** (+ casting-director, bible-manager) | 1–2 |
| revise_character | **character-creator** (+ casting-director) | 1–2 |
| revise_dialogue | **screenwriter** (+ story-editor or performance-director) | 1–2 |
| plan_scene | **director** (+ cinematographer or producer) | 1–2 |
| plan_audio | **sound-producer** (+ sound-designer) | 1–2 |
| create_storyboard | **director** + prompt-architect | 1–2 |
| prepare_video_generation | **director** + cinematographer + vision-reviewer | 2–3 |
| prepare_image_generation | **art-director** + prompt-architect | 1–2 |
| design_location | **production-designer** + art-director | 1–2 |
| assemble_sequence | **editor** + director | 1–2 |
| review_asset | **qa-reviewer** + vision-reviewer | 1–2 |
| answer_question | story-analyst (0–1; READ-ish → prefer 0) | 0–1 |
| production_intelligence | **story-analyst** + bible-manager (+ continuity-analyst) | 1–2 |
| virtual_production | **virtual-production-coordinator** + director | 1–2 |
| environment_studio | **virtual-production-coordinator** + production-designer | 1–2 |
| storyteller_discovery | **storyteller** | 1 |
| sound_production | **sound-producer** + sound-designer | 1–2 |
| unified_experience | **storyteller** + sound-producer + director | 2–3 |
| update_production_bible (MODIFY_KNOWLEDGE) | **bible-manager** | 1 |
| execute_project_action (EXECUTE_PRODUCTION) | **director**/virtual-production-coordinator + cinematographer + producer | 2–3 |

Creator-goal priority preserved (contract §3): explicit dialogue/script intent must select
Script discipline (screenwriter/story-editor), never DOP.

---

## 6. Summary

- **Exact enabled count:** **40** (runtime `SpecialistRegistry().ids()`).
- **Covered by `SpecialistContract`:** **33** — **uncovered:** **7** (`costume-designer`,
  `marketing-pitch`, `project-bible-steward`, `props-master`, `research-specialist`,
  `storyboard-artist`, `worldbuilding-specialist`; all still get synthesized
  `CoDirectorSpecialistContract`s, and none may execute tools).
- **Verdict tallies:** **KEEP 22 · KEEP+TIGHTEN 7 · MERGE 3 · DEFER 7 · RETIRE 1 = 40.**
- **Spins confirmed:** `MAX_SPECIALISTS = 8`; `plan_scene` → 8, `revise_dialogue` → 4;
  Phase 7 replaces with default 1 / hard max 3, RouteDecision-aware, 0 for NAVIGATE/READ.

## 7. Disagreements with `CODIRECTOR2_SPECIALIST_REUSE_AUDIT.md` (verify, don't blind-copy)

All factual claims in the prior audit that I re-ran (count, contract split, per-row context,
WW membership, MPT, AR) **checked out exactly**. Deliberate interpretative differences:

1. **Remedy for the overlap trios.** Audit recommends generic "prune overlap within the 40."
   This matrix is more surgical: **3 concrete merges** (project-bible-steward→bible-manager,
   choreographer→director/animation-supervisor, compositing-supervisor→vfx-supervisor) but
   **keeps** the story trio (screenwriter/story-editor/story-summary-editor) and the sonic
   trio (sound-producer/sound-designer + deferred music-supervisor) because each remaining
   member has a distinct output schema/contract and distinct route-class fit. Deleting them
   wholesale would break `story-summary-v1` writer and SonicConcept lead.
2. **`continuity-analyst` wiki-write inconsistency (new finding).** `_DOMAIN_HARD_RULES`
   says "mayProposeWikiWrites=false" (`specialist_policies.py:142`) but
   `WIKI_WRITE_SPECIALIST_IDS` includes `continuity-analyst`
   (`wiki_intelligence/contracts.py:125`); runtime sets `mayProposeWikiWrites=True` for it.
   The audit recorded both sides without reconciling. Resolve one way in Phase 7 (amend prose
   or drop from allowlist) — a continuity reporter proposing wiki writes contradicts its own
   "report conflicts only" rule.
3. **`marketing-pitch` disposition.** Audit treats it as an ordinary enabled specialist.
   This matrix **RETIREs it from the consult crew**: contract-free, MPT=false, marketing/pitch
   is not a creator crew consult lane in the frozen architecture, and its
   `_DOMAIN_HARD_RULES` stance is "never force commercialization." Park the persona behind a
   future pitch module; never let selection route to it.
4. **Two approval fields are distinct (not one).** Audit's §5/§7 treats "approval" as one
   concept. Live source has two: contract `approval_required` (8 specialists, authoritative)
   and policy `requiresCreatorApproval = may_propose_tools` (all 40 with MPT). Phase 7 must
   keep both semantics explicitly (contract §5) rather than conflate.
5. **`_DOMAIN_SPECIALIST_MAP` references deferred/retired ids.** Audit said the map "must stay
   consistent," but lists `costume-designer`, `props-master`, `storyboard-artist`,
   `worldbuilding-specialist`, `research-specialist`, `project-bible-steward` as routable.
   Under the crew rewire these routes must be redirected to the KEEP-set owners
   (character-creator / production-designer / bible-manager / continuity-analyst) or the
   entries dropped — otherwise the wiki-intelligence path routes to crew members that Phase 7
   retires from per-turn selection.
6. **Foundation/creative stack** remains the audit's top duplication risk, and that is
   **out of Phase 7 scope** (not in the frozen touched-files list). No disagreement on the
   risk — only on sequencing: it is a Phase 8+ consolidation item, not a Phase 7 change.

Agent A completes the read-only inventory. Only this matrix was written; no source touched.