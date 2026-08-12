# Co-Director 2.0 — Request Lifecycle Audit

**Status:** Source-derived audit of the current (v2) end-to-end creator-message lifecycle.
**Scope:** One creator message from composer submit through persistence and UI sync, hop-by-hop,
with classification and 2.0 insertion points. Written against current source as of this audit.
**Governing law reference:** Foundation Contracts (`docs/architecture/codirector/CODIRECTOR_FOUNDATION_CONTRACTS.md`)
and the Adept UI Build Memory Layer.

---

## 1. Lifecycle summary (one turn)

```
[1] Frontend  CoDirectorComposer.tsx → CoDirectorSession.send()
        └─ preflight health (codirectorHealth) + PLAN_UNAVAILABLE gate
[2] Frontend  appendUserTurn() → POST /conversations/{id}/events (creator event persisted first)
        └─ performSend() → api.codirectorChatStream() → POST /chat/stream (SSE)
[3] API       routers/codirector.py: chat_stream (292) → service.stream_for_project (1757)
[4] Service   _stream_for_project_inner (1791):
        RECEIVING → CLASSIFYING_INTENT → READ_PROJECT_CACHE → ASSEMBLING_PROMPT stages
[5] Core      run_conversation_core_turn (orchestrate.py:282):
        complexity → snapshot → analyze_intent → build_dialogue_plan → creative_state
        → generation messages + compose_reply fallback + evaluate_success
[6] Service   LLM primary: _stream_foundation_tokens → token events → fast grounding
        OR conversation-core reply (no LLM) OR legacy provider.stream loop
[7] Service   structured_output.parse_structured_reply on the final reply
        → message | read_tool_call | mutation_proposal (fence parse)
[8] Service   _interpret_reply → execute_read | execute_audited | propose_tool_call
        (events: tool_requested/started/completed/failed, proposal_created)
[9] Service   deferred enrichment post-first-token: wiki + momentum + confidence + next-steps
[10] Service   append_assistant_completion (idempotent asst-{request_id}) + tool events
[11] UI sync   conversation_state / what_changed / wiki_status / completed events →
        CoDirectorSession.onEvent → reconcileConversation() merge by id
[12] Approval  POST /proposals/{id}/approve → ProposalService.approve → receipt
        (creator-initiated, separate from the chat turn)
```

---

## 2. Hop-by-hop audit

### Hop 1 — Frontend chat composer + session

| Field | Value |
|---|---|
| Current Role | Composer captures draft + attachments; Enter infers `mode` (setup/prompt/chat) and calls `send()`. Session performs health preflight, single-flight guard, uploads pending attachments, appends the user message locally + persists it as an idempotent event, then streams. |
| Citations | `CoDirectorComposer.tsx:90-110` (textarea, Enter→mode→`send(undefined, mode)`); `CoDirectorSession.tsx:2177` (`send`), `1250-1251` (`performSend`), `1901` (`api.codirectorChatStream`), `2302` (`appendUserTurn`), `2187-2211` (health preflight + `PLAN_UNAVAILABLE` gate), `2023` (non-stream fallback `api.codirectorChat`), `804` (`appendUserTurn`), `847` (`reconcileConversation`) |
| Classification | **ADAPT** |
| Target Role (2.0) | Composer stays thin; `send()` must become the *only* lifecycle entry (remove mode-inference heuristics that duplicate `classify_intent`). Preflight should not hard-gate on `intelligenceEnabled` for plan words — the router decides. |
| Risk | Frontend mode-inference (`CoDirectorSession.tsx:2229-2232`) duplicates server intent classification → drift. Health preflight creates a second "capability" source. |

### Hop 2 — API routes

| Field | Value |
|---|---|
| Current Role | Thin HTTP layer: `POST /chat/stream`, `POST /chat`, `POST /cancel`; conversation CRUD + event append; proposals; tools; wiki; plans. Owns the stream session lifecycle. |
| Citations | `routers/codirector.py:250` (`chat`), `292` (`chat_stream`, owns `SessionLocal` for stream lifetime), `332` (`cancel`), `376` (`POST /conversations/{id}/events`), `517` (`events/stream` SSE revision broadcast), `1761` (approve), `1864` (tools/read), `1889` (tools/audited), `1913` (tools/proposals), `585` (intelligence/snapshot) |
| Classification | **KEEP** (structure) / **EXTEND** (contract) |
| Target Role (2.0) | Routes remain the boundary but must emit canonical `request_id`-scoped lifecycle; add state-machine transitions as first-class endpoints. |
| Risk | `events/stream` (517) is a polling loop, not push — a 2.0 workflow engine will want revision push. No validation that `/chat` and `/chat/stream` agree on the same handler. |

### Hop 3 — codirector/service.py

| Field | Value |
|---|---|
| Current Role | Orchestration hub: `_prepare_chat_request` builds provider + ChatRequest + project context; `chat_for_project` (sync) and `_stream_for_project_inner` (stream) run core + LLM + enrichment + persistence; `_intelligence_enabled_for_turn` gates intelligence; `_detect_premature_tool_success_claim` guards truthfulness. |
| Citations | `service.py:481` (`_prepare_chat_request`), `1034` (`chat_for_project`), `1757` (`stream_for_project`), `1791` (`_stream_for_project_inner`), `1440` (`_foundation_llm_turn`), `1385` (`_stream_foundation_tokens`), `1652` (`_intelligence_enabled_for_turn`), `382` (`_detect_premature_tool_success_claim`), `1253` (`_needs_foundation_intelligence`), `1262` (`_conversation_core_handles`), `1674` (`_emit_completion_with_fence_handling`), `2464-2475` (specialist consult subordinate), `2760` (`append_assistant_completion`), `2602` (`append_conversation_events`) |
| Classification | **ADAPT** |
| Target Role (2.0) | Becomes the *turn orchestrator only*: intent→router dispatch, then hand off to a 2.0 workflow engine for state transitions and tool phases. Today it interleaves core, LLM, enrichment, and persistence — that coupling is the main 2.0 refactor surface. |
| Risk | Three divergent reply paths (LLM primary / core handles / legacy provider loop at 2484) each with separate truthfulness checks — drift. Specialist consult at 2464 emits a progress event then silently falls through; no evidence is actually consulted. |

### Hop 4 — conversation/orchestrate.py (Conversation Core)

| Field | Value |
|---|---|
| Current Role | Per-turn deterministic core: complexity budget → snapshot → `analyze_intent` → `build_dialogue_plan` (authoritative) → creative-state update → generation messages + deterministic `compose_reply` + `evaluate_success`. Returns `ConversationCoreResult` with `usesLlmPrimary`, `reply`, `fallbackReply`, `wantsSpecialistConsult`, `timings`, `events`. |
| Citations | `orchestrate.py:282` (`run_conversation_core_turn`), `302-315` (complexity/budget), `350` (snapshot), `355` (`analyze_intent`), `355-401` (companion/relationship/discovery/partnership loads + state), `516/1386` (`wantsSpecialistConsult`), `1341` (module total) |
| Classification | **KEEP** (core authority) / **EXTEND** (stage awareness) |
| Target Role (2.0) | Keep as the *dialogue-authority engine* (Intent→DialoguePlan→state) but feed it the Intent+Stage Router's production stage and let a Workflow Engine own stage advance. The `ConversationPlan` output should carry a `productionStage` field for 2.0. |
| Risk | Core is called twice (sync `1070`, stream `1883`) with `defer_enrichment=True` hardcoded — no budget-aware deferral. Core knows nothing about production state (bible/timeline/jobs) beyond the wiki cache. |

### Hop 5 — structured_output.py

| Field | Value |
|---|---|
| Current Role | Classifies the provider reply by parsing markdown fences: ` ```proposal ` (Bible mutations) and ` ```tool ` (registry tool call with `responseType`). Returns `StructuredReply` (message / read_tool_call / mutation_proposal). |
| Citations | `structured_output.py:178` (`parse_structured_reply`), `120` (`extract_tool_block`), `72` (`extract_proposal_block`), `28` (ResponseType), `31-32` (fence regexes), `64-69` (`has_proposal_fence`/`has_tool_fence`), `203` (module total) |
| Classification | **SUPERSEDE** |
| Target Role (2.0) | Replace fence-parsing with a structured protocol: the provider should return typed `action` blocks (not markdown fences). The 2.0 router should never receive raw prose to regex-guess. Keep a backward-compat shim for the deterministic mock. |
| Risk | Fence regex is the single point where a model "hallucinating a tool" becomes a real mutation path — the parser trusts `definition.kind` over the claimed `responseType` (good) but the whole approach is fragile. Proposals and tool-calls can't coexist in one reply (fence priority). |

### Hop 6 — Providers (incl. mock fallback leak points)

| Field | Value |
|---|---|
| Current Role | Abstract model backend. `OllamaProvider` applies `creator_response_gate` on every turn (split content vs thinking, strip jargon). `MockCoDirectorProvider` is deterministic for E2E with scripted scenarios and tool fences. |
| Citations | `providers/base.py` (`CoDirectorProvider`, `ChatRequest`, `ChatResult`); `providers/ollama.py:92` (class), `286` (`generate`), `366` (`stream`), `428` (`gate_creator_facing`), `301-327` (turn gating); `providers/mock.py:283` (`generate`), `509` (`stream`), `103` (`_scripted_reply`), `421` (`_tool_scenario_reply`), `21` (`_scenario`), `174` (`_is_follow_up_turn`), `141-163` (`_TOOL_SCENARIOS`) |
| Classification | **KEEP** (abstraction) / **REMOVE** (mock leak patterns) |
| Target Role (2.0) | Provider interface stays; mock must be strictly test-only (already flagged `test_only`, `honesty:"mocked"`). 2.0 should forbid mock in the chat hot path outside E2E. |
| Risk / mock-leak points | (a) `mock.py:347-355` — default reply fabricates a generic "I can help with..." without grounding; a creator in a mock-misconfigured env gets fake competence. (b) `_is_follow_up_turn` (174) matches on substring `"Tool result for"` in user content — a real model reply containing that phrase in a chat can be misread. (c) scripted steps (103-136) can emit a tool fence for *any* tool — no registry check at emit time. (d) `scenario=="slow"` sleeps 0.35s and is not gated to E2E in `stream` (521). (e) mock `stream` re-emits the whole reply as tokens but the `completed` event content is un-gated (no `creator_response_gate`). |

### Hop 7 — intelligence/intent.py + stage_router.py

| Field | Value |
|---|---|
| Current Role | `classify_intent` (heuristic regex intent classifier) → `IntentClassification`; `route_stage` maps intent → `ProductionStage`. Used by `_intelligence_enabled_for_turn` and by `IntelligenceService`. |
| Citations | `intelligence/intent.py:83` (`classify_intent`), `10-14` (`_SIMPLE_QA_PATTERNS`), `16-67` (`_INTENT_RULES`), `70-80` (`_looks_simple_question`), `160-170` (return `IntentClassification`); `intelligence/stage_router.py:7-32` (`_INTENT_STAGE`), `35` (`route_stage`) |
| Classification | **EXTEND** → **SUPERSEDE** (in 2.0 the router is the authority) |
| Target Role (2.0) | 2.0 Intent+Stage Router must merge these two files: classify intent AND resolve stage/playbook in one authoritative pass, with confidence + fallback, feeding the DialoguePlan and the Workflow Engine. Current `stage_router` is a naive static dict with hardcoded `production`/`preproduction` overrides in `classify_intent` (162) that can contradict `route_stage`. |
| Risk | `classify_intent` sets `productionStage` (162) and `route_stage` (35) can disagree; `unknown` intents default to `project_management` silently; `create_storyboard` hardcodes `requiresApproval=True` at the classifier level (135-141), bypassing the DialoguePlan authority. |

### Hop 8 — Specialist dispatch

| Field | Value |
|---|---|
| Current Role | `IntelligenceService.run_intelligence`/`stream_intelligence` = full M2.4 pipeline (classify → selector/runner or foundation pass → synthesize → plan → proposals). `_intelligence_enabled_for_turn` gates whether the chat path consults at all. |
| Citations | `intelligence/service.py:45` (class), `65` (`should_use_intelligence`), `70` (`run_intelligence`), `106` (`stream_intelligence`), `139-140` (classify + route), `171-221` (foundation pass), `230-262` (legacy selector+runner), `285-315` (synthesize), `349-395` (plan + proposals); `intelligence/specialist_policies.py:35` (`creatorFacingAllowed=False`), `92` (`select_specialists_for_turn`); `intelligence/specialist_runner.py:116` (`resolve_provider_for_specialists`), `168` (`run_all`), `222` (`run_one`), `317` (`_provider_structured`), `21` (`DEFAULT_TIMEOUT_SEC=25.0`), `100` (`LIMITED_ANALYSIS_MODE`) |
| Classification | **ADAPT** |
| Target Role (2.0) | Specialists stay subordinate (never creator-facing) but must be dispatched *inside* the Workflow Engine's execution phase, not as an un-invoked library. Today `stream_intelligence` is library-only (no route/chat caller) and the chat path's "consult" at `service.py:2464-2475` is a no-op progress event. |
| Risk | Dead code (the whole M2.4 pipeline is uncalled from chat). `LIMITED_ANALYSIS_MODE` (heuristic fallback, runner:100) means "limited-analysis" assumptions can be silently added to synthesis (service.py:326-332) — a truthfulness risk if ever wired into chat. 25s timeout per specialist. |

### Hop 9 — Proposal / approval

| Field | Value |
|---|---|
| Current Role | `ProposalService` is the single write path for Bible mutations (`BibleMutationSet`) and tool calls (`ToolCallPayload`). `approve` branches once on flavour, guards staleness, idempotency, records decision + receipt. |
| Citations | `bible/proposals.py:52` (terminal statuses), `128` (class), `130` (`create_proposal`), `164` (`create_tool_proposal`), `211` (`_get_row` scope check), `310` (`reject`), `328` (`request_revision`), `346` (`cancel`), `365` (`approve`), `490` (`_approve_tool_proposal`), `566` (`get_receipt`); `plans/commands.py:44` (`PlanCommandService`), `122` (`create_draft`), `322` (`propose`), `336` (`approve`), `390` (`reject`); `routers/codirector.py:1761-1811` (approve/reject/request-revision/cancel/receipt) |
| Classification | **KEEP** (core) / **EXTEND** |
| Target Role (2.0) | Keep the propose→approve→execute→receipt invariant. 2.0 needs a unified `StateVerification` layer between approve and execute (verify resources unchanged) and plan-level approval to reuse the same receipt semantics. |
| Risk | `approve` sets status `executing` (437) before applying; if apply raises, rollback records `failed` (467-488) — but the `approved` decision row is already committed (436), so a failed approval leaves an `approved` decision + `failed` status (acceptable but worth documenting). Tool proposal staleness checked at approve only (401); `create_tool_proposal` computes it at creation (207). |

### Hop 10 — Tool handlers execution

| Field | Value |
|---|---|
| Current Role | Registry (`tools/registry.py`) defines tools + schema versions; `ToolExecutionService` runs read (immediately), audited mutating (immediately, no approval), or propose-only (approval required). Each handler is a typed function. |
| Citations | `tools/execution.py:188` (class), `226` (`execute_read`), `438` (`execute_audited`), `569` (`propose`), `700` (`execute_approved_proposal`), `667` (`parse_payload`), `688` (`is_stale`), `800` (`list_invocations`); `tools/registry.py:67` (`MutationHandler`), `1244` (`find`), `1283` (`read_handler`), `1288` (`mutation_handler`); `tools/definitions.py:71` (`ToolDefinition`), `135` (`ToolInvocationOut`); `tools/sanitize.py:174` (`sanitize_arguments`), `256` (`sanitize_result`); `service.py:677` (`_run_read_tool`), `768` (`_propose_tool_call`), `905-973` (audited branch) |
| Classification | **KEEP** (registry discipline) / **EXTEND** |
| Target Role (2.0) | Handlers become capability-verified steps executed by the Workflow Engine; `execute_approved_proposal` should run under `VerifiedOperator` (verify-then-execute) semantics. Keep `requires_approval` in the registry as the single authority (never hardcoded tool-id lists — already the case at `service.py:905-918`). |
| Risk | Read-tool loop bound `TOOL_LOOP_LIMIT` enforced at `service.py:988` and mock `tool_loop_limit` scenario relies on gateway, not handler. No per-tool idempotency for audited writes beyond invocation ledger. |

### Hop 11 — Persistence / stores

| Field | Value |
|---|---|
| Current Role | Append-only `codirector_conversation_events` is source of truth; server owns both creator and assistant/tool events. `messages_json` retained only for backfill. Proposals/invocations/receipts/intelligence findings in their own tables. |
| Citations | `conversation_events.py:279` (`append_events`), `147` (`fold_events`), `349` (`append_single`), `386` (`current_revision`); `service.py:2760` (`append_assistant_completion`), `2792` (`_safe_append_tool_event`), `2823` (`append_tool_event`); `service.py:2575-2584` (persistence comment — server owns both sides); `intelligence/store.py:19` (`save_finding`), `49` (`save_synthesis`), `77` (`save_plan`), `159` (`list_findings`); `routers/codirector.py:376` (event append), `361` (conversation get), `517` (revision stream) |
| Classification | **KEEP** |
| Target Role (2.0) | Keep append-only + revision as the single source of truth; add state-machine transition events (production stage changes) to the same log so the Workflow Engine is fully replayable. |
| Risk | Optimistic concurrency on revision (409 CONFLICT) — no retry/rebuild path exposed to frontend except manual. `fold_events` reconstructs legacy shape; 2.0 should not rely on it. |

### Hop 12 — UI sync / response

| Field | Value |
|---|---|
| Current Role | SSE `onEvent` applies ~30 event types to React state; `conversation_state` carries a large flattened state dict; on terminal the client calls `reconcileConversation()` (GET conversation) to merge by id. |
| Citations | `CoDirectorSession.tsx:1321` (`onEvent`), `1349-1378` (`conversation_state` flattening), `1379` (`processing_stage`), `1399` (`wiki_status`), `1815` (`finalizeCompleted`), `1923` (`finalizeCompleted` call), `847` (`reconcileConversation`), `858-867` (merge by id), `2516` (`approveProposal`), `2586` (`rejectProposal`); `api.ts:1899` (`codirectorChatStream`), `2011` (`codirectorGetConversation`), `2020` (`codirectorAppendConversationEvents`), `5079` (`approveProposal`), `5084` (`rejectProposal`) |
| Classification | **ADAPT** |
| Target Role (2.0) | Replace the flat `conversation_state` blob with a typed state-machine snapshot (mode + stage + transition). Client should render state transitions rather than 30 ad-hoc events. |
| Risk | `conversation_state` (2169-2204) hand-builds 40+ fields from 8 different core payloads — every new core field needs a UI-side mapping. The client persists via `appendUserTurn` and reconciles via full GET — race if two tabs stream the same project. |

---

## 3. Classification matrix (summary)

| Hop | Component | Class | 2.0 Target |
|---|---|---|---|
| 1 | Frontend composer/session | ADAPT | Thin lifecycle entry; remove mode-inference |
| 2 | API routes | KEEP/EXTEND | Canonical lifecycle contract; push revision |
| 3 | `service.py` | ADAPT | Turn orchestrator; Workflow Engine owner |
| 4 | `orchestrate.py` | KEEP/EXTEND | Dialogue authority; stage-aware plan |
| 5 | `structured_output.py` | SUPERSEDE | Typed action protocol |
| 6 | Providers | KEEP/REMOVE | Interface stays; mock gated to E2E |
| 7 | `intent.py` + `stage_router.py` | EXTEND→SUPERSEDE | Unified Intent+Stage Router |
| 8 | Specialist dispatch | ADAPT | Subordinate consult inside Workflow Engine |
| 9 | Proposal/approval | KEEP/EXTEND | Unified approval + StateVerification |
| 10 | Tool handlers | KEEP/EXTEND | VerifiedOperator execution |
| 11 | Persistence/stores | KEEP | Append-only + transition events |
| 12 | UI sync | ADAPT | Typed state-machine snapshot |

---

## 4. Insertion points (concrete file:line)

### 4.1 Production State
- **`service.py:1846-1852`** — project-cache read (`load_project_cache`/`warm_project_cache`): 2.0 production-state loader inserts here; cache must carry production stage + lifecycle state, not just wiki/momentum.
- **`service.py:516`** (`_build_project_payload`) — currently assembles project context; extend to include production stage + bible version + timeline readiness for the router.
- **`service.py:1070-1077` / `1883-1890`** — both core call sites should pass the resolved production stage into `run_conversation_core_turn`.
- **`routers/codirector.py:585`** (`GET /intelligence/snapshot`) — existing snapshot read is the natural read surface for a 2.0 production-state snapshot DTO.

### 4.2 Intent + Stage Router
- **`orchestrate.py:355`** — `analyze_intent` call: replace/augment with the unified `IntentClassification` + `route_stage` (the 2.0 router).
- **`orchestrate.py:354`** (`processing_stages`), **`orchestrate.py:302`** (complexity) — router must produce stage + playbook + complexity in one pass.
- **`service.py:1652-1671`** (`_intelligence_enabled_for_turn`) — currently re-classifies intent on every turn; 2.0 router result should be passed in, not recomputed.
- **`intelligence/intent.py:83` + `intelligence/stage_router.py:35`** — merge into one router module; resolve the `productionStage` conflict between `intent.py:162` and `stage_router._INTENT_STAGE`.

### 4.3 Story Intelligence
- **`orchestrate.py:367-374`** — creative temperature / intrigue assessment (`assess_creative_temperature`, `assess_intrigue`): 2.0 story-intelligence signals insert here, feeding the DialoguePlan.
- **`orchestrate.py:400`** — `active_goal`/`workflow_hold` resolution: story-intelligence "what's really being asked" should inform goal extraction.
- **`service.py:2110-2115`** (`discovery_questions`) and **`service.py:2000-2005`** (`intrigue` event) — UI emission points for story-intelligence outputs.
- **`intelligence/service.py:171-221`** (foundation creative pass) — the `run_foundation_creative_pass` is the 2.0 story-intelligence engine; wire it via the router, not as uncalled library code.

### 4.4 Workflow Engine
- **`service.py:1791`** (`_stream_for_project_inner`) — the entire stream body becomes a thin dispatch into the 2.0 Workflow Engine (stage machines per intent).
- **`service.py:2480-2572`** (legacy provider loop) — delete/replace: the follow-up loop (`_follow_up_request`, `service.py:1016`) is the 2.0 engine's tool-phase primitive; keep the phase concept, generalize it.
- **`service.py:1070`** (sync path) and **`service.py:1883`** (stream path) — single engine entry must replace the two divergent implementations.
- **`routers/codirector.py:909`** (`creative-operating/decision`) — the decision loop is a *separate* workflow entry; 2.0 should route it through the same engine (it currently calls `run_creative_decision_loop` directly, `decision_loop.py:54`).

### 4.5 Verified Operator
- **`bible/proposals.py:365`** (`approve`) — insert verification between staleness gate (401) and apply (436/448): re-check base resource versions right before execution.
- **`tools/execution.py:700`** (`execute_approved_proposal`) — the operator boundary: verify payload's pinned `base_resource_versions` still current, then execute.
- **`tools/execution.py:438`** (`execute_audited`) — audited writes should also verify preconditions (draft targets unchanged).
- **`service.py:905-973`** (audited branch in `_interpret_reply`) — the chat-side dispatch must route through VerifiedOperator, not call `execute_audited` directly.

### 4.6 State Verification
- **`bible/proposals.py:97`** (`_stale_for_row`) / **`bible/proposals.py:401`** — the staleness oracle; 2.0 generalizes it into a `StateVerification` service covering bible + tools + production lifecycle + timeline.
- **`service.py:382`** (`_detect_premature_tool_success_claim`) and **`service.py:2254-2274`** / **`2526-2549`** (premature-claim correction events) — these are the runtime verification checks; 2.0 centralizes them into one verifier that also runs at approve-time.
- **`tools/execution.py:688`** (`is_stale`) — tool-resource staleness; extend to production state (stage/lifecycle) not just resource versions.

---

## 5. Fire-and-forget success-claim risks

1. **Wiki claim before verification** — `service.py:2230-2236`: reply regex `"added to the wiki|updated the wiki|saved to the wiki"` only *corrects* after the fact (emits `prematureClaim` + `premature_tool_success`); the streamed tokens are never retracted. Creator can read the false success before the correction event. Guard: block the phrase at generation (grounding gate) AND verify.
2. **Foundation stream never executes mutating tools but can claim them** — `service.py:2254-2274` detects "no editing tool ran" only *after* the claim was streamed; the correction is reactive.
3. **Legacy stream path** (`service.py:2526-2549`) — `_mutating_executed` is computed from `outcome.invocations`; a proposal alone doesn't count (correct), but the check runs only after `_interpret_reply` yields — a tool *failure* mid-loop can still leave a stale "completed" claim un-corrected if `follow_up_prompt` was set.
4. **`_propose_tool_call` succeeds silently if proposal is stale** — it emits `proposal_stale` (829-839) but the reply prose that says "I'll do X when you approve" has already streamed; no re-words.
5. **Mock provider fabricates competence** — `mock.py:347-350` generic "I can help with..." and `mock.py:351-355` script-writing claims are emitted without any actual capability check; in a misconfigured env (mock not E2E-gated) this is a false-competence success claim.

## 6. Mock-leak points (must be E2E-only in 2.0)

- `mock.py:21` `_scenario()` reads `ADEPT_CODIRECTOR_MOCK_SCENARIO` env with no app-level guard — any env var set leaks the mock into a non-E2E run.
- `mock.py:328-339` scripted scenario can emit arbitrary tool fences with no registry validation at emit time (validated only at *install* time, `_validate_scripted_step`).
- `mock.py:509-528` `stream()` bypasses `creator_response_gate` — raw reply text streamed as tokens.
- `mock.py:174-186` `_is_follow_up_turn` substring heuristic on `"Tool result for"` — fragile, can mis-trigger.
- `mock.py:520-521` `slow` scenario sleep is scenario-gated but not env-gated.

## 7. Duplicate lifecycle implementations

| Duplication | Sites | Impact |
|---|---|---|
| Two reply orchestrators | `service.py:1034` (sync `chat_for_project`) vs `service.py:1757/1791` (stream) — same core call, same enrichment, separate logic | Drift in fallback/truthfulness handling; sync path ignores tool lifecycle events (`1182` drains generator into `pass`) |
| Three provider-reply paths in stream | LLM-primary (`1930-2421`), core-handles (`2423-2452`), legacy loop (`2480-2572`) | Each has its own fence interpretation + premature-claim check |
| Intent classification twice | `intelligence/intent.py:83` (router) + `_intelligence_enabled_for_turn` (`service.py:1665`) + `classify_request_complexity` (`orchestrate.py:302`) | Three different "what is this request" answers |
| Production-stage resolution | `intent.py:162` (hardcoded) + `stage_router.py:35` (dict) + `orchestrate.py` DialoguePlan | Can disagree silently |
| Proposal write paths | `ProposalService.create_proposal` (`bible/proposals.py:130`) + `create_tool_proposal` (164) + `PlanExecutorBridge.create_proposals` (`intelligence/service.py:383`) + manual POST `/proposals` (`routers/codirector.py:1727`) | Four creators, one approval system (approve is unified — good) |
| Decision/workflow entry | `service.py:2464` (specialist consult no-op) + `routers/codirector.py:909` (`run_creative_decision_loop`) | Two "workflow" entry points, neither is a workflow engine |
| Persistence write paths | `append_events` (`conversation_events.py:279`) via `appendUserTurn`, `append_assistant_completion` (`service.py:2760`), `_safe_append_tool_event` (2792), `save_conversation` (2623, legacy) | Converged on append-only; `save_conversation` legacy path remains |

---

## 8. Priority recommendation (2.0)

1. **Unify the turn orchestrator** — one engine replacing `chat_for_project` / `_stream_for_project_inner` / legacy loop (§7 row 1-2).
2. **Merge Intent+Stage Router** — one pass for intent/stage/playbook/complexity feeding DialoguePlan + engine (§4.2).
3. **Typed action protocol** — supersede fence regex with structured output (§Hop 5), keep mock shim E2E-gated (§6).
4. **Workflow Engine + Production State + State Verification** — stage-aware execution with approve-time verification (§4.4-4.6), reusing the unified ProposalService.
5. **Wire the M2.4 specialist pipeline for real or delete it** — `stream_intelligence` is dead code in chat today (§Hop 8); 2.0 either folds findings into the engine or removes the dead path to avoid drift.
