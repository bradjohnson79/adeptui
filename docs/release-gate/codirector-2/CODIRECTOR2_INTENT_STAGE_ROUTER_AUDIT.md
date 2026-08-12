# Co-Director 2.0 — Intent + Stage Routing Audit (Phase 1, READ-ONLY)

**Audit scope:** `studio-api/app/codirector/intelligence/` — `intent.py`, `stage_router.py`, `contracts.py`, `schemas.py`, and the intent/stage/tool coupling paths in `service.py`, `context_compiler.py`, `synthesis.py`, plus consumers in `conversation/orchestrate.py` and `codirector/service.py`.

**Date:** 2026-08-08 · **Phase:** 1 (audit only — no implementation performed) · **Classification:** intent + stage routing

All citations are `file:line` relative to `studio-api/app/codirector/` unless prefixed otherwise.

---

## 1. Intent extraction — current behavior

### 1.1 Mechanism: pure regex heuristics, no model
- `intelligence/intent.py:10-14` — `_SIMPLE_QA_PATTERNS`: three regexes (question-word prefix `what|who|where|when|why|how|which|can you explain|tell me about`, auxiliary-prefix `is|are|do|does|did|will|would|should`, and trailing `?`).
- `intelligence/intent.py:16-67` — `_INTENT_RULES`: ~24 ordered `(regex, IntentKind, reason)` tuples. All are ASCII-English word-boundary regexes (`\b(...)\b`, `re.I`). First match wins (`break` at intent.py:99). Examples: `storyboard|board shot|next shot` → `create_storyboard` (intent.py:18), `make … dialogue … sarcastic|emotional|funny|sharper` → `revise_dialogue` (intent.py:20), `plan … conversation|scene|blocking|coverage|corridor` → `plan_scene` (intent.py:21-23), `change|update … eye color|locked|bible|canon|character` → `update_production_bible` (intent.py:34-35).
- `classify_intent()` (intent.py:83-170) is the sole entry point: `text = (user_message or "").strip()`, lowercased only for the question heuristic, then linear regex scan. **There is no model-based classification, no embeddings, no LLM call** — even when a provider is healthy, intent is never delegated to a model.
- `mode="setup"` hard-overrides the result to `plan_scene`/`plan-scene` (intent.py:144-149).

### 1.2 Confidence scoring behavior
- Confidence is **hard-coded, not computed**: `0.85 if primary != "unknown" else 0.45` (intent.py:168). Every matched rule — weak single-keyword hits included — receives the identical 0.85. The number does not reflect rule specificity, match strength, or ambiguity.
- The empty-message branch emits `confidence=0.2` + `needsClarification=True` (intent.py:151-158) — the only low-confidence path that asks.
- Downstream, synthesis maps the intent's binary flags to a response type (`synthesis.py:57-63`) and the confidence that is surfaced to creators is recomputed in `SynthesisEngine.synthesize` from specialist provenance (`synthesis.py:83-99`: 0.62 blockers / 0.55 all-heuristic / 0.88 validated), **not** from `IntentClassification.confidence`. Intent confidence is effectively dead data.

### 1.3 Ambiguity handling — silent, not clarifying
- `needsClarification` is set **only** for an empty message (intent.py:151-158). There is no `AMBIGUOUS` bucket.
- An unmatched message classifies as `unknown` with 0.45 confidence and **proceeds silently**. `unknown` is then routed to a real stage (`stage_router.py:31`) and to a real specialist trio `(director, producer, story-analyst)` (`specialist_selector.py:69`). Low confidence does not trigger CLARIFY — the system guesses with production-grade downstream effects (see §5).
- Question-shaped unknown messages are remapped to `answer_question` by `_looks_simple_question` (intent.py:101-103, 70-80) — a heuristic guess that a question is "simple".

### 1.4 Multilingual — English-only
- Every classifier regex is an English word/lemma pattern; only `re.I` is applied. No locale/language input exists on `classify_intent`. A Spanish/Chinese/French instruction matching zero patterns lands in `unknown` → silently routed to the generic specialist trio and stage `project_management`.
- A separate `language_intelligence/` package exists (e.g. `language_intelligence/api.py`, `language_intelligence/audio_phrases.py`) but is **not wired into** `classify_intent`. (The M3.0F `prompt_intelligence/language/` package is a prompt-enhancement language layer, unrelated to intent classification.)

### 1.5 Intent object shape (`schemas.py`)
`IntentClassification` (schemas.py:106-119): `primaryIntent`, `secondaryIntents` (default `[]` — **never populated** anywhere in the codebase; dead field), `productionStage` (default `"production"`), `playbookId`, `targetSceneId` (only passed through from the request, intent.py:164), `targetShotId` (default `None` — **never set**; dead field), `complexity` (`simple|standard|complex`, set at intent.py:124-133), `requiresApproval` (set at intent.py:135-141), `needsClarification`, `clarificationQuestion`, `isSimpleQuestion`, `confidence`, `reasons` (keyword reasons from rule matches).
- `IntentKind` literal (schemas.py:22-47) contains 24 values; **only ~14 are ever emitted** by the classifier. `revise_story`, `revise_character`, `review_continuity`, `manage_production`, `plan_vfx`, `execute_project_action` are declared but unreachable from regex rules.
- `specialist_selector.py:166-233` keys on intent kinds the classifier never produces (`virtual_production`, `environment_studio`, `storyteller_discovery`, `sound_production`, `unified_experience`) — those roster entries are dead from the `classify_intent` path (they exist for m213/m214 idea-first flows which bypass `classify_intent`).
- `playbookId` mapping is ad-hoc and partly incoherent: `production_intelligence` and `plan_audio` both map to `plan-scene` (intent.py:119-122).

---

## 2. Stage routing — current behavior

### 2.1 What "stage" means today
Two unrelated stage models exist, plus a third lifecycle concept:

1. **Intelligence `ProductionStage`** (schemas.py:12-20: `development|writing|preproduction|production|postproduction|delivery|project_management`). Produced by `stage_router.route_stage()` (stage_router.py:35-36), which is a **pure static dict lookup** `_INTENT_STAGE` (stage_router.py:7-32) keyed by regex intent kind. E.g. `plan_scene → preproduction`, `review_asset → postproduction`, `answer_question → project_management`, `unknown → project_management`.
2. **Conversation `creativeStage`** (conversation/creative_state.py:5-17: `Project Creation|Vision|World Building|Characters|Episode Structure|Scenes|Dialogue|Production Planning|Generation|Editing|Final Delivery`). Heuristic keyword inference (`_infer_target`, creative_state.py:65-111), advanced by `update_creative_state` (creative_state.py:114-154), carried on `ConversationPlan.creativeStage` (conversation/schemas.py:53) and **persisted across turns** in `ProjectIntelligenceSnapshot.currentStage` (conversation/schemas.py:84-85; conversation/snapshot.py:149-151, 155-175) and `project_cache.developmentStage` (conversation/project_cache.py:158).
3. **Discovery `temperature.stage`** (EMERGENCE/EXPLORATION/… — orchestrate.py:372, 762-775) is a creative-temperature lifecycle, not a production stage; it never feeds either model above.

### 2.2 How stage is derived — from intent, never from project state
- Intelligence stage is derived **only** from the regex intent (input → `classify_intent` → `route_stage`). It is an **output**, never an input: nothing reads `intent.productionStage` for any decision. Grep across `app/` shows `productionStage` written at `intelligence/service.py:140` and `intelligence/intent.py:162` and defined at `schemas.py:109` — **zero reads**. `intent.py:162`'s hard-coded value is immediately overwritten by `route_stage()` at `intelligence/service.py:140`.
- The conversation `creativeStage` **is** remembered (persisted snapshot, loaded each turn at conversation/snapshot.py:140-152), but it is derived from message keywords and conversation history, **not** from project artifacts (timeline, scenes, bible, production plan).
- The foundation path is the one place conversation stage actually flows into intelligence: `intelligence/service.py:202-203` reads `conversation_plan["creativeStage"]`/`["creativeSubstate"]` and passes them into `run_foundation_creative_pass(...)` (foundation/pipeline.py:59-67 → `creativeStage`/`creativeSubstate` fields on `SpecialistRequest`).

### 2.3 Stage as input vs output
- Output only. `route_stage` is a leaf function (stage_router.py:35-36) invoked once at `intelligence/service.py:140`. It does not gate, influence, or constrain anything downstream (specialists, context, tools, plans).

### 2.4 Stage gates tool behavior?
- **No.** No code branches on `intent.productionStage`. Tool gating is done by workspace surface + intent keyword signals in `tools/exposure.py` (see §3.3), not by stage. The conversation `creativeStage` does influence prose (e.g. `response_composer.py:331` "Characters"/"Lead Character") and the foundation prompt context, but it never gates tool execution.

---

## 3. Tool coupling — intent/stage → specialist → tool

### 3.1 Intent → specialist selection (deterministic)
- Static roster map `_INTENT_SPECIALISTS` (specialist_selector.py:13-70, extended 73-94, 166-212, 215-232). `SpecialistSelector.select()` (specialist_selector.py:125-161) is deterministic: dict lookup → registry-existence filter → continuity add → cap at `MAX_SPECIALISTS = 8` (specialist_selector.py:11) → required/optional split. Default fallback for unmatched intents: `("director", "producer", "story-analyst")` (specialist_selector.py:69).
- Decision site: `intelligence/service.py:139-140` (classify + route_stage), `:230` (`self.selector.select(intent)`), `:249` (`self.runner.run_all(...)`).

### 3.2 Specialist → proposed tools
- Specialists emit `ProposedToolAction` (schemas.py:70-74) inside `SpecialistFinding` (schemas.py:93). Findings are merged in `SynthesisEngine.synthesize` (synthesis.py:38-46) with dedupe by `toolId`.
- `PlanBuilder.build` (planning.py:17-99) converts proposed actions into `PlanStep` with `toolId`, validates against the registry (`PlanValidator`, planning.py:114-140 — **only mutating-kind tools allowed**) and — for `create_storyboard` — auto-injects `propose_storyboard_generation` (planning.py:68-83).
- `PlanExecutorBridge.create_proposals` (planning.py:143-167) turns plan steps into approval proposals via `ToolExecutionService.propose` — mutations never auto-execute.

### 3.3 Main chat path tool coupling (model-dependent selection)
- `service.py:578-590` calls `tools/exposure.expose_ordered(surface, intent)` to deterministically **narrow ~485 tools** to a candidate set by workspace surface + intent-keyword signals (`tools/exposure.py:163-184` `_INTENT_DOMAIN_SIGNALS`, `:200-226` `_SURFACE_DOMAIN`, safe baseline `:134-155`; ambiguous intent **expands**, never restricts, `:18-19`).
- The LLM then selects the actual tool from that narrowed catalog and emits a ` ```tool ` JSON fence, which is **deterministically parsed** (`structured_output.py:120-203`); the registry's `kind` field decides `read_tool_call` vs `mutation_proposal` (`structured_output.py:169`), and execution/proposal handling lives in `service.py:_interpret_reply` (service.py:842+) and `_propose_tool_call` (service.py:768+). Tool aliases are resolved deterministically (`tools/aliases.py:93-94`).
- **Summary:** routing intent→roster is deterministic; **actual tool selection is model-dependent** within a deterministically-derived candidate set.

### 3.4 Conversation-core coupling (subordinate)
- `conversation/orchestrate.py:489-516` imports `select_specialists_for_turn` (specialist_policies.py:92-137), which gates specialists by complexity/budget and conversation `IntentType` (REQUEST_FEEDBACK/REQUEST_PLAN/REQUEST_ACTION — orchestrate.py:494-506). This is advisory only: `wantsSpecialistConsult` (orchestrate.py:1386) merely gates a "specialist_consult_subordinate" progress event in `service.py:2464-2475`; the conversation intent (`IntentType`) and the intelligence intent (`IntentKind`) are **two separate classifiers** with no shared taxonomy.

### 3.5 Note on live wiring
- `IntelligenceService.run_intelligence`/`stream_intelligence` (intelligence/service.py:70-413) are **not invoked** from any router or the live chat path (`grep` across `app/` and `app/routers/` finds no caller). The live path uses `classify_intent` only for the gate `_intelligence_enabled_for_turn` (service.py:1652-1671, gate at service.py:2464-2467) plus the foundation creative pass (`foundation/pipeline.py:59+`, selected via `should_run_foundation_creative` at foundation/pipeline.py:53-56 against `_CREATIVE_INTENTS` at foundation/pipeline.py:21-40). The M2.4 `stream_intelligence` flow is effectively dormant/legacy behind `feature_flags.codirector_intelligence_v2` (default `False`, feature_flags.py:63).

---

## 4. Fallback behavior — what happens when nothing matches

- **Intent fallback:** `unknown` (0.45 confidence) → routed to stage `project_management` (stage_router.py:31) and specialists `(director, producer, story-analyst)` (specialist_selector.py:69). No error, no CLARIFY.
- **Specialist fallback:** if no specialists resolve, `IntelligenceService.stream_intelligence` yields `CONTEXT_INCOMPLETE` error (intelligence/service.py:232-240) or (foundation path) `:213-221`. In the live chat path, Conversation Core simply handles the turn without specialists.
- **Synthesis fallback:** if no recommendation, blockers, and no tool actions, synthesis emits a generic "I'm with you — share the next detail…" (synthesis.py:63-71).
- **Provider fallback:** `resolve_provider_for_specialists` (specialist_runner.py:116-154) silently downgrades to `LIMITED_ANALYSIS_MODE` heuristic findings when no healthy provider; confidence is capped at 0.55 (synthesis.py:91-97) and a `Limited-analysis` assumption is appended (intelligence/service.py:326-332). This fallback is honest but **not a creator-visible warning**.
- **Tool fallback:** unregistered tool ids in plan steps become blockers (planning.py:50-53) or `PLAN_INVALID` errors (planning.py:128-140); an unknown ` ```tool ` fence yields a structured error, never a silent drop (structured_output.py:9-10, 167-168).

---

## 5. Silent guessing — places the system guesses without creator confirmation

1. **Low-confidence intent → silent production guess.** `unknown` (0.45) proceeds to real specialists and a real stage with no CLARIFY (`intent.py:168` + `service.py:139-140` + `specialist_selector.py:69`). The system never asks "what do you want to do?" except on an empty message (intent.py:151-158).
2. **Question heuristic.** A message that "looks like a simple question" is silently classified `answer_question` (intent.py:101-103) and the intelligence path is skipped (`should_use_intelligence` → `False`, intelligence/service.py:65-68).
3. **Conversation creative-stage auto-advance.** `update_creative_state` changes the persisted `creativeStage`/`creativeSubstate` from keywords (creative_state.py:114-154), which is silently persisted to the snapshot and feeds future turns and foundation prompts (conversation/snapshot.py:155-175; service.py:202-203). A wrong guess changes project state across turns.
4. **`mode="setup"` override.** Any setup-mode message is forced to `plan_scene` (intent.py:144-149).
5. **Known-intent specialist roster.** `unknown` → `(director, producer, story-analyst)` runs three specialist consults on a guess (specialist_selector.py:69).
6. **Tool exposure expansion.** Ambiguous intent deliberately expands the exposed tool set (`tools/exposure.py:18-19`) — benign (no execution) but a guess that widens the model's blast radius.
7. **LIMITED_ANALYSIS downgrade** (specialist_runner.py:100-154) silently substitutes heuristic findings for model reasoning in E2E/unhealthy-provider cases (mitigated only by confidence caps and an assumption string, not by asking the creator).

---

## 6. Existing action classes vs the 2.0 required classes

### Existing intent/action categories
| Source | Enum / keys | Examples |
|---|---|---|
| Intelligence `IntentKind` (schemas.py:22-47) | 24 literals | `answer_question`, `plan_scene`, `create_storyboard`, `prepare_video_generation`, `update_production_bible`, `execute_project_action`, `unknown` |
| Conversation `IntentType` (conversation/foundation/schemas.py:12-31) | 19 | `INFORM`, `EXPLAIN_PROJECT`, `REQUEST_FEEDBACK`, `REQUEST_PLAN`, `REQUEST_ACTION`, `REQUEST_GENERATION`, `REQUEST_EDIT`, `REQUEST_REVIEW`, `CORRECT_ASSISTANT`, **`APPROVE`**, **`REJECT`**, `PAUSE_ACTION`, `SET_PREFERENCE`, `UNKNOWN` |
| Legacy `PrimaryIntent` (conversation/schemas.py:19-28) | 8 | `receive_information`, `answer_question`, `request_clarification`, `recommend_next_step`, `execute_action`, `confirm_correction`, `invite_continuation`, `summarize` |

### Gap vs 2.0 required classes (`DISCUSS, NAVIGATE, READ_INSPECT, MODIFY_KNOWLEDGE, PROPOSE_CREATIVE_CHANGE, EXECUTE_PRODUCTION, APPROVE, REJECT, CLARIFY, AMBIGUOUS`)
- `DISCUSS` → partial. Covered only loosely by `INFORM`/`REQUEST_FEEDBACK`/`BRAINSTORM` (conversation) and `answer_question`/`plan_scene` (intelligence). No dedicated discussion action.
- `NAVIGATE` → **absent** as an intent. Navigation is implicit (workspace surface in `tools/exposure.py:200-226`), never classified as an action. No "open X" intent.
- `READ_INSPECT` → partial. Model-dependent `read_tool_call` via fence (structured_output.py:169) with no intent-class linkage; `review_asset` is the closest producer intent but is rarely reached (no regex rule except `review|check … asset|render|result|image|video`, intent.py:28).
- `MODIFY_KNOWLEDGE` → **absent** as an action class. Wiki writes are governed by a separate detection (`conversation/deferred_enrichment.py`, `wiki_intelligence/correction/classify.py`) with `requiresConfirmation`/`clarificationQuestion` (correction/classify.py:220-224), not by an intent class.
- `PROPOSE_CREATIVE_CHANGE` → implicit via `ProposedToolAction`/`ProposedToolAction.requiresApproval` (schemas.py:70-74) and the ` ```tool `/` ```proposal ` fences; not an intent class.
- `EXECUTE_PRODUCTION` → partial. `execute_project_action` exists as a Literal (schemas.py:44) but is unreachable from regex; `execute_action`/`REQUEST_ACTION` exist in conversation layers.
- `APPROVE` / `REJECT` → present **only** as conversation `IntentType` members (schemas.py:27-28) but **never emitted** by `analyze_intent` (grep shows no assignment); proposal approval is handled by plan/tool services (`production_plan.approve`/`production_plan.reject` in tools/aliases.py:74-75), not by intent routing.
- `CLARIFY` → effectively absent. Only empty-message clarification (intent.py:151-158); the `CLARIFY` posture exists (conversation/foundation/schemas.py:43) but the ambiguity path never triggers it.
- `AMBIGUOUS` → **absent**. No ambiguity detection anywhere in intent paths.

---

## 7. Deterministic-first — obvious-command patterns

### Already deterministic (non-LLM)
- **Intent regex** (intent.py:16-67) and **conversation intent regex** (conversation/foundation/intent.py:90-284, incl. `_ACTION_IMPERATIVE_RE` at :51-55 matching add/change/update/remove/delete… over concrete objects) — deterministic phrase matching.
- **Conversation stage inference** (creative_state.py:65-111) — keyword → stage/substate.
- **Tool catalog narrowing** (tools/exposure.py, wired at service.py:578-590) — deterministic surface+intent filtering with safe baseline.
- **Fence parsing & read/mutation decision** (structured_output.py:120-203) — deterministic `kind`-based classification.
- **Plan validation** (planning.py:114-140) — deterministic, mutating-only.
- **Specialist roster selection** (specialist_selector.py:125-161) — deterministic.

### Gaps — obvious commands NOT handled deterministically
- "Open X" (`runtime.open_manager`, `scene.get`, `workspace.get_active_context`, …): no deterministic "open" handler; opening is left to the model's ` ```tool ` choice.
- "Delete Y" (`script.propose_delete`, `asset` soft-delete handlers, `scene_references_w6p.py:144` soft-delete): deletion intent is regex-capturable (conversation/foundation/intent.py:51-55) but execution still requires the model to emit a tool fence; no first-class "delete" action path.
- `APPROVE`/`REJECT` of a proposal: explicit approve/reject phrases are not classified deterministically; they surface as `UNKNOWN`/`INFORM` (conversation) and rely on tool-specific APIs.
- "Create/draft a plan" (`_PLAN_RE`, conversation/foundation/intent.py:69) is classified but only sets `should_use_tools=True`; the actual tool emission remains model-dependent.
- No deterministic-first executor exists between intent classification and model fallback for these obvious commands.

---

## Classification matrix

| Component | Current Role | File/Function citations | Classification | Target Role in 2.0 | Risk |
|---|---|---|---|---|---|
| `intelligence/intent.py` `classify_intent` | Regex intent classifier (English-only, first-match-wins) | `intent.py:83-170`, rules `:16-67`, confidence `:168` | **KEEP + HARDEN** | Deterministic-first intent layer producing 2.0 action classes; add CLARIFY/AMBIGUOUS + multilingual; populate `secondaryIntents` | Low-confidence silent guesses; English-only; fixed 0.85 confidence |
| `intelligence/schemas.py` `IntentClassification` | Intent object (dead fields: `secondaryIntents`, `targetShotId`, `productionStage` mostly unused) | `schemas.py:106-119` | **REWORK** | 2.0 action-decision schema: `(intent, derivedStage, activeContext, productionState)` | Schema churn across consumers |
| `intelligence/stage_router.py` `route_stage` | Static intent→stage map; **write-only** (no reader) | `stage_router.py:7-36`; sole caller `service.py:140` | **REPLACE** | `derivedStage` from project state + conversation (not intent) | Stage never gates anything today; deriving it is additive |
| `conversation/creative_state.py` | Keyword stage/substate state machine; **remembered** in snapshot | `creative_state.py:5-154`; persistence `conversation/snapshot.py:149-175`, `project_cache.py:158` | **KEEP as signal** | Feed `derivedStage`/creative substate into action decision; keep remembered but reconcile with project artifacts | Stage remembered-not-derived → stale stage drives foundation prompts |
| `intelligence/service.py` | Orchestrates classify→route→select→run→synthesize→plan→propose; foundation fork at `:161-211` | `service.py:70-413` (`:139-140`, `:202-203`, `:230`) | **RECONCILE** | Single action-decision entrypoint using `(intent, derivedStage, activeContext, productionState)`; drop dead streaming path or rewire | Dormant/legacy path (`codirector_intelligence_v2` off by default, feature_flags.py:63) |
| `intelligence/specialist_selector.py` | Deterministic intent→roster map | `specialist_selector.py:13-233` (`:125-161`) | **REMAP** | Map 2.0 action classes → specialist/skill bundles | Roster keys (`virtual_production` etc.) unreachable from classifier (dead entries) |
| `intelligence/context_compiler.py` | Builds `ContextPackage` (facts, budget, provenance); conversation_plan injected | `context_compiler.py:160-478` (`:385-402`) | **EXTEND** | Carry `derivedStage`, `activeContext`, `productionState` as first-class fields | Already the natural place for `activeContext` |
| `intelligence/synthesis.py` | Aggregates findings; recomputes confidence; picks responseType | `synthesis.py:22-112` (`:83-99`) | **EXTEND** | Map to action decision; distinguish CLARIFY/AMBIGUOUS responses | Confidence derived from specialist provenance, not intent |
| `intelligence/planning.py` | Plan/step/tool proposal bridge (mutating-only, approval-gated) | `planning.py:17-167` | **KEEP** | `EXECUTE_PRODUCTION` / `PROPOSE_CREATIVE_CHANGE` executor behind approval | Fine as-is; needs intent-class linkage |
| `intelligence/contracts.py` | Specialist contracts + role map (advise-only) | `contracts.py:9-417` | **KEEP** | Specialist/skill contracts behind action classes | Large surface; aliases fine |
| `tools/exposure.py` + `service.py:578-590` | Deterministic tool-catalog narrowing by surface+intent | `tools/exposure.py:163-340` | **KEEP + EXTEND** | Backbone of deterministic-first tool coupling; add obvious-command execution | Ambiguity expands blast radius (benign today) |
| `structured_output.py` fence parse | Deterministic read/mutation classification | `structured_output.py:120-203` (`:169`) | **KEEP** | Model-fallback tool boundary under action decision | Tool selection itself is model-dependent |
| `conversation/foundation/intent.py` `analyze_intent` | Second, richer regex intent (postures, evidence spans); includes APPROVE/REJECT enum members but never emits them | `conversation/foundation/intent.py:90-284`; enum `conversation/foundation/schemas.py:12-31` | **UNIFY** | Single taxonomy with 2.0 action classes; wire APPROVE/REJECT emission | Two parallel intent systems drift (intent taxonomies don't share classes) |
| `conversation/orchestrate.py` | Subordinate specialist gating; `wantsSpecialistConsult` | `orchestrate.py:489-516`, `:1386` | **KEEP subordinate** | Action decision stays authoritative; specialists remain subordinate | Bypass risk if specialists become independent speakers |
| `codirector/service.py` | Chat gate (`_intelligence_enabled_for_turn`), tool exposure, fence interpretation, stage nudge into system prompt | `service.py:1652-1671`, `:578-590`, `:842+`, `:1288-1318` | **INJECTION POINT** | Host deterministic-first action layer before model fallback | Gate uses only `classify_intent` today |

---

## MIGRATION PATH

**Feasibility: CONFIRMED.** Moving from `intent → stage` (static, write-only) to `(intent, derivedStage, activeContext, productionState) → action decision` is feasible with low structural risk, because:
- `derivedStage` needs no new infrastructure — the conversation `creativeStage` is already persisted and already injected into the foundation path (`intelligence/service.py:202-203`); `route_stage` is a leaf with zero readers, so it can be re-derived or retired without breakage.
- `activeContext` already exists as `ContextPackage` (`context_compiler.py:160-478`) with provenance-tagged facts — extend it with `derivedStage`/`productionState` fields rather than inventing a new container.
- `productionState` has existing sources: `production_plan.*` tools (tools/aliases.py:65-81), `production_lifecycle/` package, `workspace.get_active_context`.

### Concrete insertion points (file:line)
1. **Deterministic-first action resolver (new layer) — insert BEFORE model fallback:**
   - `intelligence/service.py:139` (before/around `classify_intent`) and `codirector/service.py:1665` (gate) — a deterministic "obvious command" matcher (open/delete/approve/reject/draft-plan/create) that short-circuits to an action decision instead of the generic regex classifier.
   - `structured_output.py:120-203` (`extract_tool_block` / `parse_structured_reply`) — intercept obvious tool commands deterministically before the model-generated fence is the only path.
   - `codirector/service.py:842+` (`_interpret_reply`) and `tools/exposure.py:163-340` — execute the deterministic layer; keep the deterministic `kind`-based read/mutation decision (structured_output.py:169).
2. **Stage derivation — replace `route_stage`:** rewrite `stage_router.py:35-36` / `_INTENT_STAGE` (`:7-32`) to derive stage from `(project state, conversation creativeStage, production plan)` instead of intent; wire conversation stage in at `intelligence/service.py:202-203` (already reads `conversation_plan`).
3. **Context enrichment:** extend `ContextPackage` (schemas.py:122-132) and populate in `context_compiler.py:385-402` (already ingests `conversation_plan`) with `derivedStage`, `activeContext`, `productionState`.
4. **Action decision schema:** evolve `IntentClassification` (schemas.py:106-119) → action-decision record carrying the four inputs and one 2.0 action class; remap `specialist_selector._INTENT_SPECIALISTS` (specialist_selector.py:13-233) and `specialist_policies.select_specialists_for_turn` (specialist_policies.py:92-137) to the action classes.
5. **Unify taxonomies:** map conversation `IntentType` (conversation/foundation/schemas.py:12-31) and intelligence `IntentKind` (schemas.py:22-47) onto the 2.0 classes; wire APPROVE/REJECT emission (currently dead enum members) at `conversation/foundation/intent.py:90-284`.
6. **Reconcile the legacy streaming path:** either wire `IntelligenceService.stream_intelligence` (`intelligence/service.py:106-413`) into the live path or retire it; today it is dead behind `feature_flags.codirector_intelligence_v2` (feature_flags.py:63).

### Recommended target flow (2.0)
`user_message + conversation_plan + project artifacts` → **deterministic-first action resolver** → `(intent, derivedStage, activeContext, productionState)` → **action decision** (one of the 10 classes) → specialist/skill bundles (subordinate) → proposal/approval gate → execution. Model only consulted when the deterministic layer cannot reach a decision; CLARIFY/AMBIGUOUS emitted explicitly instead of silent guessing.

---

## Top risks

1. **Silent guessing (highest):** low-confidence `unknown` intent proceeds to real specialists, a real stage, and a real plan with no CLARIFY/AMBIGUOUS (`intent.py:168`, `service.py:139-140`, `specialist_selector.py:69`).
2. **English-only intent:** all classifier regexes are English (`intent.py:16-67`); non-English input falls to `unknown` → silent generic routing; `language_intelligence` is not wired in.
3. **Stage remembered-not-derived:** conversation `creativeStage` is persisted keyword-guessed state (`creative_state.py:65-154`, `conversation/snapshot.py:149-175`) that never reconciles with project artifacts, while the intelligence `ProductionStage` is derived-from-intent and **write-only** (zero readers) — two divergent stage models that can drift.
4. **Two intent taxonomies:** intelligence `IntentKind` and conversation `IntentType` never interoperate; roster keys exist that the classifier cannot produce (dead specialist mappings).
5. **Dormant legacy path:** `IntelligenceService.stream_intelligence` and `productionStage` are effectively unused in the live path; migration must decide keep-vs-retire or risk maintaining a second, dead routing stack.
6. **Model-dependent tool execution** within an only-narrowed catalog remains the mutation path; deterministic-first coverage for open/delete/approve/reject is needed to shrink the blast radius.
