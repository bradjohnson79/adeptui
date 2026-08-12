# Co-Director 2.0 — Specialist Crew Reuse Audit

**Audit domain:** Specialist infrastructure in `studio-api/app/codirector/intelligence/` and the specialist prompt packs under `studio-api/app/codirector/prompts/specialists/` (plus `core/` and `playbooks/` persona claims).

**Audit phase:** Phase 1 (READ-ONLY). No implementation was performed. This document is the only artifact written.

**Status:** `READY FOR PRIMARY REVIEW` (audit findings only; no binary GO/NO-GO is claimed by a subagent).

**Orientation used:**
- `docs/ADEPT_UI_BUILD_MEMORY_LAYER.md` (canonical laws)
- `docs/architecture/codirector/CODIRECTOR_FOUNDATION_CONTRACTS.md`
- `docs/release-gate/final-systems/ADEPT_UI_FINAL_SYSTEMS_AND_RESILIENCE_CERTIFICATION_PROMPT.md`
- Frozen-architecture direction for 2.0 (single creator-facing persona, scoped specialist context, limited tool exposure, specialists return to Co-Director).

---

## 1. DYNAMIC COUNT — actual specialist registry

### 1.1 How specialists are registered (mechanism)

Registration is **declarative, via YAML front matter in Markdown prompt files** — not decorators, not import scanning, not a static Python list.

1. `Prompts/loader.PromptLibrary` scans `core/`, `specialists/`, `playbooks/`, `standards/` for `*.md` files and buckets them by front-matter `type` (`_DEFAULT_SEARCH_DIRS`, `loader.py:15`; `_iter_prompt_files`, `loader.py:89-94`; `reload`, `loader.py:50-87`).
2. `prompts/parser.py:29-54` parses the minimal YAML front matter.
3. `prompts/validator.py:113-180` validates every file; it hard-rejects `may_execute_tools: true` for specialists (`validator.py:141-149`) and requires a known `output_schema` and known context keys (`validator.py:13-49`).
4. `intelligence/specialist_registry.py` builds `SpecialistDefinition` records by iterating `library.by_type("specialist")` (`_rebuild`, `specialist_registry.py:60-65`) and keeps only `enabled` entries (`specialist_registry.py:64-65`). `_from_prompt` (`specialist_registry.py:67-83`) re-rejects `may_execute_tools=true` (`specialist_registry.py:69-70`).

Each specialist is therefore "registered" at its prompt file's front matter. The single hard-coded list that exists is in the **foundation** stack (see §7) — not in the intelligence registry.

### 1.2 Verification run (runtime/repo state)

Executed read-only Python against the real `PromptLibrary` + `SpecialistRegistry`:

- Specialist prompt files scanned: **40**
- Diagnostics: loaded **76**, skipped **0** (no validation failures, all front matter valid)
- Registered enabled specialists: **40**

### 1.3 The 40 registered specialists

| # | id | persona file | priority |
|---|----|--------------|----------|
| 1 | `director` | `prompts/specialists/director.md` | 90 |
| 2 | `project-bible-steward` | `prompts/specialists/project-bible-steward.md` | 90 |
| 3 | `story-analyst` | `prompts/specialists/story-analyst.md` | 88 |
| 4 | `bible-manager` | `prompts/specialists/bible-manager.md` | 86 |
| 5 | `producer` | `prompts/specialists/producer.md` | 85 |
| 6 | `pipeline-manager` | `prompts/specialists/pipeline-manager.md` | 84 |
| 7 | `code-director` | `prompts/specialists/code-director.md` | 83 |
| 8 | `technical-director` | `prompts/specialists/technical-director.md` | 82 |
| 9 | `screenwriter` | `prompts/specialists/screenwriter.md` | 80 |
| 10 | `story-summary-editor` | `prompts/specialists/story-summary-editor.md` | 80 |
| 11 | `continuity-analyst` | `prompts/specialists/continuity-analyst.md` | 78 |
| 12 | `prompt-architect` | `prompts/specialists/prompt-architect.md` | 76 |
| 13 | `story-editor` | `prompts/specialists/story-editor.md` | 75 |
| 14 | `script-supervisor` | `prompts/specialists/script-supervisor.md` | 74 |
| 15 | `art-director` | `prompts/specialists/art-director.md` | 72 |
| 16 | `cinematographer` | `prompts/specialists/cinematographer.md` | 70 |
| 17 | `production-designer` | `prompts/specialists/production-designer.md` | 68 |
| 18 | `worldbuilding-specialist` | `prompts/specialists/worldbuilding-specialist.md` | 67 |
| 19 | `performance-director` | `prompts/specialists/performance-director.md` | 66 |
| 20 | `choreographer` | `prompts/specialists/choreographer.md` | 65 |
| 21 | `editor` | `prompts/specialists/editor.md` | 64 |
| 22 | `qa-reviewer` | `prompts/specialists/qa-reviewer.md` | 63 |
| 23 | `vision-reviewer` | `prompts/specialists/vision-reviewer.md` | 62 |
| 24 | `asset-manager` | `prompts/specialists/asset-manager.md` | 61 |
| 25 | `casting-director` | `prompts/specialists/casting-director.md` | 60 |
| 26 | `lighting-supervisor` | `prompts/specialists/lighting-supervisor.md` | 59 |
| 27 | `vfx-supervisor` | `prompts/specialists/vfx-supervisor.md` | 58 |
| 28 | `animation-supervisor` | `prompts/specialists/animation-supervisor.md` | 57 |
| 29 | `compositing-supervisor` | `prompts/specialists/compositing-supervisor.md` | 56 |
| 30 | `character-creator` | `prompts/specialists/character-creator.md` | 55 |
| 31 | `sound-designer` | `prompts/specialists/sound-designer.md` | 55 |
| 32 | `costume-designer` | `prompts/specialists/costume-designer.md` | 54 |
| 33 | `props-master` | `prompts/specialists/props-master.md` | 53 |
| 34 | `virtual-production-coordinator` | `prompts/specialists/virtual-production-coordinator.md` | 52 |
| 35 | `storyboard-artist` | `prompts/specialists/storyboard-artist.md` | 51 |
| 36 | `music-supervisor` | `prompts/specialists/music-supervisor.md` | 50 |
| 37 | `research-specialist` | `prompts/specialists/research-specialist.md` | 49 |
| 38 | `sound-producer` | `prompts/specialists/sound-producer.md` | 48 |
| 39 | `marketing-pitch` | `prompts/specialists/marketing-pitch.md` | 47 |
| 40 | `storyteller` | `prompts/specialists/storyteller.md` | 40 |

Priority is set by front matter `default_priority` (`specialist_registry.py:81`); `all_enabled()` sorts by `(-default_priority, id)` (`specialist_registry.py:97-100`).

> Note: `project-bible-steward` and `story-summary-editor` ship `default_priority` 90/80 but their persona text explicitly says "Never speak to the creator" — the priority column does not imply a speaking role (see §5).

### 1.4 Contract coverage

`intelligence/contracts.py` defines `CONTRACTS` (`contracts.py:41-370`) — **33 of the 40** specialists have a `SpecialistContract`. The **7 without** a contract entry:

`costume-designer`, `marketing-pitch`, `project-bible-steward`, `props-master`, `research-specialist`, `storyboard-artist`, `worldbuilding-specialist`

These 7 still get a runtime `CoDirectorSpecialistContract` synthesized by `specialist_policies.build_contract` (`specialist_policies.py:62-84`).

---

## 2. Per-specialist contract fields

Source: registry front matter (derived above), `CONTRACTS` (`contracts.py:41-370`), `PRODUCT_ROLE_MAP` (`contracts.py:374-395`), `WIKI_WRITE_SPECIALIST_IDS` (`wiki_intelligence/contracts.py:114-147`), `_DOMAIN_HARD_RULES` (`specialist_policies.py:141-158`).

Legend: `MPT` = `may_propose_tools`; `MET` = `may_execute_tools` (always False, enforced); `AR` = `approval_required` from contract; `ESCL` = escalation path; `WW` = member of Wiki-write allowlist.

| id | persona file | allowed_context | MPT | AR | WW | ESCL / hard-rule |
|----|--------------|-----------------|-----|----|----|------------------|
| director | director.md | scene, characters, locations, continuity, visual_language | Y | — | Y | Canon→Bible Manager; QA→QA Reviewer |
| project-bible-steward | project-bible-steward.md | project_overview, canon, characters, locations, story, continuity | N | — | Y | Organize Project Bible; never mutate locked canon; no creator-facing |
| story-analyst | story-analyst.md | project_overview, story, scene, characters, canon | Y | — | Y | Research-like analysis permission-aware; no web unless allowed |
| bible-manager | bible-manager.md | project_overview, canon, characters, locations, story, continuity | Y | **Y** | Y | Never mutate canon w/o creator approval; propose only |
| producer | producer.md | project_overview, scene, capabilities, production_decisions | Y | **Y** | Y | Destination-aware planning; budget blockers→User Review |
| pipeline-manager | pipeline-manager.md | capabilities, scene, shot, project_overview | Y | — | Y | Technical workflow only; never invent marketing pressure |
| code-director | code-director.md | capabilities, project_overview | Y | — | — | Schema breaks→Pipeline Manager; never fake CONNECTED |
| technical-director | technical-director.md | capabilities, shot, scene | Y | — | — | Missing caps→Pipeline Manager |
| screenwriter | screenwriter.md | project_overview, scene, characters, story, canon | Y | — | Y | Respect ownership/locked scripts; draft only when authorized |
| story-summary-editor | story-summary-editor.md | project_overview, story, characters, canon, continuity | N | — | — | Presentation not invention; canon conflicts→Bible Manager |
| continuity-analyst | continuity-analyst.md | continuity, characters, wardrobe, scene, previous_shot, next_shot | Y | **Y** | Y | Never mutate canon; report conflicts only |
| prompt-architect | prompt-architect.md | shot, characters, locations, references, visual_language, capabilities | Y | — | — | Missing refs→Asset Manager |
| story-editor | story-editor.md | project_overview, story, scene, characters, canon | Y | — | Y | Respect ownership; do not overwrite locked script sections |
| script-supervisor | script-supervisor.md | scene, characters, continuity, story | Y | — | Y | Continuity→Continuity Supervisor |
| art-director | art-director.md | visual_language, characters, locations, references, wardrobe | Y | — | Y | Lighting→Lighting Supervisor |
| cinematographer | cinematographer.md | scene, shot, visual_language, locations, previous_shot, next_shot, continuity | Y | — | Y | Visual/shot guidance only; subordinate synthesis by Co-Director |
| production-designer | production-designer.md | locations, objects, scene, visual_language | Y | — | Y | Asset gaps→Asset Manager |
| worldbuilding-specialist | worldbuilding-specialist.md | story, locations, continuity, canon, characters | N | — | Y | Never overwrite locked canon; structured findings only |
| performance-director | performance-director.md | scene, characters, story | Y | — | Y | Performance notes only; never speak as Co-Director |
| choreographer | choreographer.md | scene, characters, shot, continuity | Y | — | — | Animation→Animation Supervisor |
| editor | editor.md | scene, shot, previous_shot, next_shot | Y | — | Y | Continuity cuts→Continuity Supervisor; timeline mutations→approval |
| qa-reviewer | qa-reviewer.md | scene, shot, continuity, references, visual_language, capabilities | Y | **Y** | — | Unresolved blockers→User Review |
| vision-reviewer | vision-reviewer.md | shot, references, continuity, visual_language | Y | **Y** | — | Unresolved defects→QA Reviewer / User Review |
| asset-manager | asset-manager.md | characters, locations, references, scene, capabilities | Y | **Y** | Y | Missing locked refs→User Review |
| casting-director | casting-director.md | characters, references, wardrobe | Y | — | Y | Character casting notes only; no creator-facing voice |
| lighting-supervisor | lighting-supervisor.md | scene, shot, locations, visual_language, continuity | Y | — | Y | Camera exposure→Cinematographer |
| vfx-supervisor | vfx-supervisor.md | scene, shot, vfx, capabilities | Y | — | Y | Comp→Compositing Supervisor |
| animation-supervisor | animation-supervisor.md | scene, shot, characters, continuity, capabilities | Y | — | — | Capability gaps→Pipeline Manager |
| compositing-supervisor | compositing-supervisor.md | scene, shot, vfx, capabilities, visual_language | Y | — | — | Render gaps→Pipeline Manager |
| character-creator | character-creator.md | characters, references, wardrobe, story, continuity | Y | **Y** | Y | Canon conflicts→Bible Manager; missing refs→Casting Director |
| sound-designer | sound-designer.md | scene, locations, audio | Y | — | Y | Audio design only; no forced commercialization |
| costume-designer | costume-designer.md | characters, wardrobe, continuity, story, references | N | — | Y | Propose Wiki updates via orchestrator only |
| props-master | props-master.md | characters, story, continuity, references | N | — | Y | Never invent props; structured findings only |
| virtual-production-coordinator | virtual-production-coordinator.md | scene, shot, locations, visual_language, continuity, production_plan | Y | **Y** | — | Escalate to continuity-analyst |
| storyboard-artist | storyboard-artist.md | story, visual_language, characters, references, shot, scene | N | — | Y | Never invent frames; structured findings only |
| music-supervisor | music-supervisor.md | project_overview, scene, story | Y | — | Y | Audio guidance only; destination-aware |
| research-specialist | research-specialist.md | story, references, canon, locations | N | — | Y | Permission-aware; no web unless allowed |
| sound-producer | sound-producer.md | scene, audio, music, dialogue, continuity | Y | — | Y | Sonic direction; no new providers |
| marketing-pitch | marketing-pitch.md | story, production_plan, production_decisions, references | N | — | Y | Never force commercialization |
| storyteller | storyteller.md | scene, characters, story, tone, continuity | Y | — | Y | Idea-first discovery; approval-aware handoff |

**Tool exposure:** there is **no per-specialist tool allowlist** in the registry. Tool exposure is binary: the `may_propose_tools` front-matter flag (`specialist_registry.py:79`, surfaced as `mayProposeTools` at `specialist_registry.py:38`). The only concrete, coded tool proposal is `prompt-architect → propose_storyboard_generation` in the heuristic path (`specialist_runner.py:538-546`). The one allowlist that exists is `WIKI_WRITE_SPECIALIST_IDS` (`wiki_intelligence/contracts.py:114-147`, 30 ids) which gates *Wiki-write proposals* (not tool execution); it is consumed at `specialist_policies.py:79`. `MET` is always False — enforced at both load time (`validator.py:141-149`) and registry build (`specialist_registry.py:69-70`).

---

## 3. Selection — `specialist_selector.py`

- Mechanism: **intent → static tuple mapping, no scoring/embedding**. `_INTENT_SPECIALISTS` (`specialist_selector.py:13-70`, extended at `:73-94`, `:166-184`, `:186-212`, `:215-232`) maps `intent.primaryIntent` to a hard-coded list of specialist ids.
- Candidate filtering: each candidate is kept only if present in the registry (`specialist_selector.py:136-143`), capped at `MAX_SPECIALISTS = 8` (`specialist_selector.py:11`, `:140-143`).
- Continuity: intents in `_CONTINUITY_INTENTS` (`specialist_selector.py:96-105`, `:213`, `:233`) auto-inject `continuity-analyst` (`specialist_selector.py:145-152`).
- Partitioning: `required` = top `min(3, len)` for non-simple, `min(1, len)` for simple; the rest are `optional` (`specialist_selector.py:158-161`). Overflow past the cap is moved to `skipped` (`specialist_selector.py:154-156`).
- **Confidence:** the selector itself computes none. Confidence is attached downstream: intent classifier returns 0.85 (known intent) / 0.45 (unknown) (`intent.py:168`); the heuristic runner fixes specialist confidence at 0.55 (`specialist_runner.py:561`); synthesis sets 0.88 (validated), 0.62 (blockers), 0.55 (all-heuristic) (`synthesis.py:92-99`).
- Secondary gate: `specialist_policies.select_specialists_for_turn` (`specialist_policies.py:92-137`) SKIPs **all** specialists for complexity `TINY`/`SMALL`, and marks heavy domains `BACKGROUND_ONLY` (`specialist_policies.py:48-59`, `:73`).
- Third mechanism (foundation stack): `foundation/creative/routing.py:76-120` uses intent + keyword + domain-profile maps with its own ordering logic — a **separate, un-synchronized** selector (see §7).

---

## 4. Execution — `specialist_runner.py`

- Orchestration: `run_all` (`specialist_runner.py:168-220`) resolves definitions, then compiles **one** context package for the whole specialist set (`context_compiler.compile`, `context_compiler.py:160-194`) and per-specialist **scopes** it via `filter_for_specialist` (`specialist_runner.py:206`, `context_compiler.py:540-552`).
- **Context scope:** specialists do **not** receive the full project. `compile` unions only the `allowed_context` categories across selected specialists (`context_compiler.py:184-192`), applies a 12,000-char budget by category priority (`context_compiler.py:38`, `:482-536`), and `filter_for_specialist` keeps only facts whose category is in the individual specialist's `allowed_context` (plus the user message) (`context_compiler.py:548-550`). Conversation history and plan are only compiled when `project_overview` is allowed (`context_compiler.py:362-402`) and are still category-filtered per specialist.
- Two execution modes (`specialist_runner.py:108-154`):
  - **Provider path** (live model): `run_one` → `_provider_structured` (`specialist_runner.py:317-347`); system prompt hard-codes subordination (`specialist_runner.py:330-336`): *"You are the {name} specialist — a subordinate department. You never speak as Co-Director and never address the creator directly. Return ONLY JSON matching specialist-finding-v1 inside a ```json fence. Never execute tools."*
  - **Heuristic path** (`limited-analysis`): used when `STUDIO_E2E` is set, no healthy provider, or provider explicitly disabled (`specialist_runner.py:108-154`); results are cached (`specialist_runner.py:288-314`) and flagged `LIMITED_ANALYSIS_ASSUMPTION` (`specialist_runner.py:102-105`).
- **Creator contact:** specialists **cannot** speak to the creator. Provider output must be a JSON finding (`specialist_runner.py:345-347`); heuristic output is a structured `SpecialistFinding` (`schemas.py:83-103`). Findings are folded by `SynthesisEngine.synthesize` (`synthesis.py:22-112`) into a single `SynthesisResult.userMessage` — one creator-facing voice. In the conversation path the consult is explicitly "subordinate" and falls through to the foundation/provider LLM (`codirector/service.py:2461-2475`).
- **Approval:** yes — proposals must pass approval. Specialist `ProposedToolAction`s (`schemas.py:70-74`, default `requiresApproval=True`) flow through `SynthesisResult` → `PlanBuilder.build` where every tool step is created `requiresApproval=True` (`planning.py:54-66`, `:93`) and only mutating tools are allowed (`planning.py:134-140`), then `PlanExecutorBridge.create_proposals` → `ToolExecutionService.propose(...)` (`planning.py:143-167`). No tool is executed from a specialist finding directly.

---

## 5. Policies — `specialist_policies.py`

- `CoDirectorSpecialistContract` (Pydantic) enforces invariants (`specialist_policies.py:14-35`): `mayExecuteTools=False` (`:33`), `creatorFacingAllowed=False` — explicitly "always false — Core Law" (`:35`), default `maximumContextTokens=4000` (`:27`), forbidden context sources include `full_marketing_plan`, `full_tool_registry` (`:26`).
- `build_contract` (`:62-84`): derives domain from id (`:69`), forbids `onboarding_ack`/`tiny_rename` (`:72`), maps `executionMode` — heavy ids `BACKGROUND_ONLY` (`:73`), `mayProposeWikiWrites` via `WIKI_WRITE_SPECIALIST_IDS` (`:79`), `mayCreateDrafts` only for screenwriter/story-editor/storyteller (`:80`), `requiresCreatorApproval` from `may_propose_tools` (`:82`).
- `select_specialists_for_turn` (`:92-137`): complexity gate (TINY/SMALL → all SKIP, `:102`), selection only among `selected_ids`, mode BACKGROUND for heavy domains (`:116-126`).
- Domain hard rules `_DOMAIN_HARD_RULES` (`:141-158`) + `UNSUPPORTED_SPECIALIST_DOMAINS` (`:161-166`) keep unshipped personas honest (no fake-GO).
- `roster_artifact` (`:173-185`) exposes a versioned roster with `creatorFacingAllowed: False` (`:178`).

---

## 6. Caching — `specialist_cache.py`

- In-memory process dict (`specialist_cache.py:10`).
- Key = SHA-256 of `{projectId, specialistId, task, source_revisions (contextHash), requestHash (sha of user message)}` (`specialist_cache.py:13-29`).
- TTL 600s default (`specialist_cache.py:43-44`); get evicts expired entries (`:32-40`); invalidation by project/specialist scans values (`:47-63`).
- **Only the heuristic (limited-analysis) path uses this cache** (`specialist_runner.py:288-314`). Provider-path results are not cached here.

---

## 7. Duplication

The dominant duplication is **two full, parallel specialist stacks**:

1. **Intelligence registry** — 40 prompt-driven specialists (`intelligence/specialist_registry.py`).
2. **Foundation creative roster** — 12 hard-coded ids in `foundation/creative/roster.py:5-18`: `creative_director`, `story_architect`, `character_architect`, `world_builder`, `cinematic_psychology`, `cinematography_director`, `lighting_director`, `production_designer`, `editor`, `sound_director`, `performance_director`, `continuity_supervisor`.

`foundation/pipeline.py:3-4` states the foundation path is "the sole specialist stack (legacy M2.4 runner is skipped)", yet both stacks remain live and neither derives from the other.

**Direct persona duplicates (foundation ↔ intelligence):**

| Foundation id | Duplicates intelligence id(s) |
|---------------|------------------------------|
| `story_architect` | story-analyst, story-editor, screenwriter, storyteller |
| `character_architect` | character-creator, casting-director, performance-director |
| `world_builder` | worldbuilding-specialist, production-designer |
| `cinematic_psychology` | story-analyst, performance-director, vision-reviewer |
| `cinematography_director` | cinematographer |
| `lighting_director` | lighting-supervisor |
| `production_designer` | production-designer |
| `editor` | editor |
| `sound_director` | sound-designer, sound-producer, music-supervisor |
| `performance_director` | performance-director |
| `continuity_supervisor` | continuity-analyst (contracts already alias `continuity-supervisor`, `contracts.py:78`) |
| `creative_director` | **top-level Co-Director persona** (`prompts/core/codirector.md`) — its review pass (`foundation/creative/creative_director.py:81-153`) re-implements the single-face synthesis/trim role |

**Within the intelligence registry (intra-stack overlap):**
- `project-bible-steward` vs `bible-manager` — near-identical canon/Bible stewardship duties (`project-bible-steward.md`, `bible-manager.md`).
- `story-summary-editor` vs `story-editor` vs `screenwriter` — overlapping story/presentation duties (`story-summary-editor.md`, `story-editor.md`, `screenwriter.md`).
- `sound-designer` vs `sound-producer` vs `music-supervisor` — overlapping sonic duties (`sound-designer.md`, `sound-producer.md`, `music-supervisor.md`); `sound-producer.md` explicitly "coordinates" the other two.

**Third routing surface:** `DOMAIN_SPECIALIST_MAP` (`wiki_intelligence/contracts.py:74-111`) is another specialist→domain routing table that must stay consistent with the two selectors above.

**Duplication vs top-level Co-Director:** the foundation `creative_director` review (`creative_director.py:81-153`) and the intelligence `SynthesisEngine` (`synthesis.py:22-112`) both implement "fold specialist advice into one creator-facing recommendation" — i.e., the persona role already owned by `codirector.md` (`codirector.md:19,22`).

---

## 8. Fragmentation — how specialists relate to the conversation

- **Conversation context:** only indirectly and always scoped. Recent messages and the conversation plan are compiled into the context package only when `project_overview` is in `allowed_context` (`context_compiler.py:362-402`), then `filter_for_specialist` drops any fact not in the specialist's categories (`context_compiler.py:548-550`). Most specialists do not carry `project_overview`, so most receive essentially no conversation history — only the delimited user message.
- **Persona bypass:** prevented by construction. The provider system prompt forbids direct address (`specialist_runner.py:330-336`); the main conversation path gates consult behind `wantsSpecialistConsult` + `_intelligence_enabled_for_turn` (`codirector/service.py:2464-2467`, `:1652-1671`) and explicitly falls through to the foundation/provider LLM — "specialist synthesis is not the final speaker" (`codirector/service.py:2461-2475`).
- **Where specialist output re-enters the conversation:**
  1. `SynthesisEngine.synthesize` produces the single `SynthesisResult.userMessage` (`synthesis.py:48-112`).
  2. Foundation path overrides can set `synthesis.userMessage`/`recommendation` from `CreativeDirectorReview.prioritizedRecommendations[0]` (`intelligence/service.py:298-310`) — still one internal voice, but note it can bypass `SynthesisEngine` prose.
  3. Companion context injects findings as `"Specialist findings (subordinate evidence)"` (`conversation/companion/context.py:100-103`).
  4. `conversation/orchestrate.py:487-514` marks `specialist_policy="OPTIONAL_SUBORDINATE"` and gates by budget/need.
  - The creator-facing rule is re-stated in `prompts/core/codirector.md:19` ("single creator-facing production partner… they never become an independent creator-facing speaker and never bypass the DialoguePlan") and `:22` ("Never expose internal agent chatter, specialist ids, routing").

---

## Classification matrix

| Component | Current Role | File/Function citations | Classification | Target Role in 2.0 | Risk |
|-----------|--------------|-------------------------|----------------|---------------------|------|
| `specialist_registry.py` + `PromptFrontMatter` | Declarative, prompt-driven registry (40), validates `may_execute_tools=false` | `specialist_registry.py:60-83`; `validator.py:141-149` | **KEEP + REWIRE** | Single source of truth for specialist roster; add per-specialist tool allowlist; keep enabled/front-matter model | Medium — registry is reused by legacy and foundation paths inconsistently |
| `prompts/specialists/*.md` (40 personas) | Persona + allowed_context + tool flags | front matter of each file | **KEEP** | Reuse personas; do not author a parallel set for 2.0 | Low if pruned for overlap |
| `specialist_selector.py` | Intent→static id map, cap 8, continuity injection; no confidence | `specialist_selector.py:13-161` | **KEEP + REWIRE** | Selection driven by task/Production-State relevance; unify with `DOMAIN_SPECIALIST_MAP` | Medium — hard-coded maps drift; foundation selector is separate |
| `specialist_runner.py` | Per-specialist scoped context; provider + heuristic paths; subordinate JSON-only output | `specialist_runner.py:168-347` | **KEEP + REWIRE** | Scoped context to task-relevant Production State; limited tool exposure; guaranteed return to Co-Director | High — provider path is the main live-reasoning surface |
| `specialist_policies.py` | Subordination invariants, complexity gate, heavy=BACKGROUND, wiki-write allowlist | `specialist_policies.py:14-137` | **KEEP** | Keep as the enforcement layer for 2.0 | Low |
| `specialist_cache.py` | In-memory heuristic-result cache (TTL 600s) | `specialist_cache.py:13-63` | **KEEP** | Keep; key on context hash already supports Production State scoping | Low |
| `contracts.py` / `schemas.py` | `SpecialistContract` (33), `SpecialistFinding`, `ProposedToolAction`, `ContextPackage` | `contracts.py:9-36,41-370`; `schemas.py:70-132` | **KEEP** | Reuse envelopes; fill missing contracts for the 7 uncovered specialists | Low |
| `context_compiler.py` | Budgeted, category-scoped context compilation + per-specialist filter | `context_compiler.py:160-194,482-552` | **KEEP + REWIRE** | Scope to task-relevant Production State (already category-scoped — extend to state slices) | Medium |
| `synthesis.py` | Conflict-resolution + single-face compression | `synthesis.py:22-112` | **KEEP** | Single creator-facing voice in 2.0 | Low |
| `planning.py` (PlanBuilder + Bridge) | Proposal creation with `requiresApproval=True`; mutating-tools-only | `planning.py:49-167` | **KEEP** | Keep as the approval boundary for 2.0 tool exposure | Low |
| `foundation/creative/*` (12-id roster, routing, runners, creative_director) | Second parallel heuristic specialist stack + pre-synthesis review | `roster.py:5-18`; `routing.py:76-120`; `runners.py:24-102,389-404`; `creative_director.py:81-153` | **CONSOLIDATE** | Fold into the single intelligence stack or explicitly deprecate; never rebuild both | **High — primary fragmentation risk** |

**Expected-direction verdict (frozen architecture = KEEP + REWIRE: scoped context, limited tools, single creator-facing persona):**
**CONFIRMED.** The evidence shows the architecture is already most of the way there — subordination is enforced in 4 places (`specialist_runner.py:330-336`, `specialist_policies.py:35`, `codirector/service.py:2461-2475`, `codirector.md:19-22`), tool execution is uniformly forbidden (`validator.py:141-149`, `specialist_registry.py:69-70`), approvals are mandatory before mutation (`planning.py:54-66,143-167`), and context is already scoped per specialist (`context_compiler.py:540-552`). The main corrective work is **consolidation**, not greenfield: the intelligence specialist stack (registry + runner + policies + cache + contracts) **must NOT be rebuilt** — it must be reused and rewired. The foundation `creative/*` stack is the portion that must be merged or retired, not duplicated further.

---

## PHASE 7 REWIRE POINTS (concrete insertion points)

### (a) Scope specialist context to task-relevant Production State
- `context_compiler.py:160-194` — `compile()` currently unions all `allowed_context` and appends `user.message`/recent-messages/plan only under `project_overview`. Extend the `allowed` union to compute a **task-relevant Production State slice** (scene/shot/canon/continuity selected by intent + active scope) instead of the union of all selected specialists' categories.
- `context_compiler.py:438-478` — after `_apply_budget`, attach the `activeScope`/state slice (`activeScope` already exists at `:444`, `:462`) so downstream `filter_for_specialist` (`:540-552`) narrows to state-relevant facts.
- `specialist_runner.py:206` — pass the scoped package through; optionally tighten `specialist_runner.py:337-341` (`_provider_structured` user prompt) to inject only the task-relevant state (facts already truncated to 6000 chars) rather than a broad dump.

### (b) Enforce limited tool exposure
- `specialist_registry.py:67-83` (`_from_prompt`) — add a `tools: tuple[...]` field derived from front matter and surface it in `to_dict` (`:29-51`) so each specialist carries an explicit tool allowlist.
- `specialist_policies.py:62-84` (`build_contract`) — set the allowlist on `CoDirectorSpecialistContract` (model at `:14-35`); keep `mayExecuteTools=False` (`:33`) and gate `requiresCreatorApproval` off the allowlist (`:82`).
- `specialist_runner.py:334` — extend the "Never execute tools" instruction with the specialist's allowlist, and validate any emitted `ProposedToolAction.toolId` against it before `planning.py:49-66` builds steps.
- `planning.py:49-66` + `PlanExecutorBridge.create_proposals` (`:143-167`) — keep `requiresApproval=True` (already `:61`) as the hard boundary; reject tool proposals not on the specialist allowlist.

### (c) Guarantee specialists return to Co-Director (single face), never hijack
- `specialist_runner.py:330-336` — keep/strengthen the subordinate system prompt ("never speak as Co-Director and never address the creator directly; return ONLY JSON").
- `codirector/service.py:2461-2475` — keep the "subordinate consultants only… not the final speaker" fall-through to the foundation/provider LLM; move the consult decision fully behind `_intelligence_enabled_for_turn` (`:1652-1671`).
- `intelligence/service.py:293-315` — ensure synthesis is the single exit (`SynthesisResult.userMessage`, `:410-413`); guard the foundation override at `:298-310` so only `CreativeDirectorReview` (an internal review) can set prose, never a raw specialist finding.
- `conversation/companion/context.py:100-103` — keep findings labeled "subordinate evidence" and capped (6) so specialist text can never read as the Co-Director persona.

---

## Top risks

1. **Two parallel specialist stacks** (`intelligence/` registry vs `foundation/creative/` roster) continue to diverge — duplication is the single highest structural risk to 2.0.
2. **Hard-coded routing maps drift** — `_INTENT_SPECIALISTS` (`specialist_selector.py`), `_INTENT_MAP`/`_KEYWORD_MAP` (`foundation/creative/routing.py`), and `DOMAIN_SPECIALIST_MAP` (`wiki_intelligence/contracts.py:74-111`) are three un-synchronized sources of "which specialists run for which intent."
3. **`creative_director` + `SynthesisEngine` both own "single face"** — a future change that lets either speak directly to the creator breaks the one-persona law (`codirector.md:19`).
4. **Heuristic path is silent fallback risk** — `limited-analysis` is gated by provider health/E2E (`specialist_runner.py:116-154`) but is the default under E2E; any 2.0 claim must not present heuristic output as deep reasoning (mitigated by `synthesis.py:91-99` confidence caps, but only in the legacy path).
5. **7 specialists have no `SpecialistContract`** — they rely on synthesized contracts (`specialist_policies.py:62-84`); escalate only by default strings.
6. **Overlap within the 40** (bible-manager/project-bible-steward; story editors; sonic trio) will multiply the tool/context surface in 2.0 unless pruned.
