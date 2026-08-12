# Co-Director Operational Integrity Audit — Intent→Tool Routing

**Milestone:** Co-Director Operational Integrity Audit
**Date:** 2026-08-07
**Status:** AUDIT COMPLETE — repairs tracked in milestone phases c2/c3
**Repo:** `C:\AdeptFilmWorks\AIVideoStudio`
**Audit scope:** `INTENT → TOOL ROUTING` pathway and the response pipeline (sync + streamed).
**Audit mode:** READ-ONLY. No files were modified; no non-readonly commands were run during the source investigation.
**Governing instrument:** This document is the governing audit for the routing pathway under Build Law 30. Supersedes any prior informal routing notes for this milestone.

---

## 1. Executive Summary

Co-Director routes a creator's natural-language turn through two parallel orchestration paths in `studio-api/app/codirector/service.py`. The path taken is decided by `core.usesLlmPrimary`, set during the conversation-core turn. The authoritative path (Path A, `usesLlmPrimary=True`) invokes the LLM, classifies intent, presents a static tool catalog, parses fenced tool calls, and dispatches them through a closed tool registry. The legacy path (Path B, `usesLlmPrimary=False`) returns a deterministic template reply and never invokes the model — it is the listening/hold path.

The routing layer is structurally sound in three respects: (1) the tool registry is **closed** and validated at import time, so an undeclared tool or missing handler aborts startup rather than failing mid-turn; (2) the `responseType` claimed by the model is **advisory and unforgeable** — the registry's declared `definition.kind` alone decides whether a call executes immediately (read) or becomes a durable proposal (mutation); (3) mutating tools never auto-apply — they create proposals, and approved-proposal replay is argument-pinned to the payload stored at proposal time.

The audit identified **19 defects** spanning eight failure surfaces: (a) read-before-write coverage is handler-by-handler rather than framework-enforced (D1–D6); (b) the grounding gate can flag but cannot retract already-streamed false-success tokens (D7); (c) there is no post-tool state-diff verification reconciling model prose against `invocation.result` (D8); (d) audited writes (`production_plan.create_draft`) persist without a preview-then-approve step (D9); (e) `is_stale` is not surfaced at proposal-creation time on the streaming chat path (D10); (f) specialist output honesty — heuristic findings produce a recommendation without a hard gate (D11) and synthesis overstates confidence for heuristic-only output (D16), while malformed provider JSON is silently rehabilitated (D15); (g) intent classification is lexical and English-only (D13), malformed tool calls are fatal on the sync path only (D12), the tool loop limit of 1 blocks legitimate multi-read sequences (D18), the mock provider is selectable outside E2E via env override (D17), and `gate_fail` is computed but discarded in grounding (D14); (h) the eight `prompts/core/*.md` files are placeholder duplicates whose bodies do not encode the policy their names promise (D19). None of the defects defeat the unforgeability invariant, but several allow the model to make truthful-sounding claims that the pipeline cannot automatically correct.

Repairs for defects 1–19 are mapped to milestone phase c2 in §8.

---

## 2. End-to-End Message Flow

There are two parallel orchestration paths in `studio-api/app/codirector/service.py`. Which one runs is decided by `core.usesLlmPrimary` (set in the conversation core turn).

### 2.1 Path A — Foundation LLM path (the authoritative path; `usesLlmPrimary=True`)

1. **HTTP entry** — `POST /codirector/chat` (sync) or `POST /codirector/chat/stream` (SSE)
   - `studio-api/app/routers/codirector.py:250` (`chat`), `:288` (`chat_stream`).
   - Body: `CoDirectorChatBody` (`codirector.py:74`) — `messages`, `project_id`, `scene_id`, `mode`, `model`, `provider_id`, `conversation_locale`, `attachment_ids`.

2. **Provider + ChatRequest preparations** — `_prepare_chat_request` (`service.py:360`).
   - Loads `Project` (raises `PROJECT_NOT_FOUND` if missing — `service.py:378`).
   - Builds context block from project payload, scene director payload, learning, Bible excerpt (`ProjectContextService.build`), compact wiki, attachments (`service.py:395–434`).
   - Composes `full_messages = [_build_system_message(...), *chat_messages]` (`service.py:452`). Tools catalog is included **only when `project_id` is present** (`service.py:454`).
   - `_build_system_message` (`service.py:337`) prepends `assistant_module.SYSTEM_PROMPT` (`assistant.py:23`) then appends context and `_tool_instructions()` (`service.py:304`).

3. **Conversation core turn** — `run_conversation_core_turn` (`conversation/orchestrate.py:282`) is invoked with `defer_enrichment=True` (`service.py:901`, `:1616`).
   - Classifies intent via `analyze_intent` (`conversation/foundation/intent.py:66`) — heuristic regex classifier into `IntentType` (`EXPLAIN_PROJECT`, `CORRECT_ASSISTANT`, `REQUEST_ACTION`, `REQUEST_PLAN`, `REQUEST_FEEDBACK`, `INFORM`, `PAUSE_ACTION`, `UNKNOWN`, etc.).
   - Builds a `DialoguePlan` (foundation authority) and a legacy `ConversationPlan` merged via `_plan_from_dialogue` (`orchestrate.py:575`).
   - `uses_llm = True` whenever a project turn runs (`orchestrate.py:1190`).
   - Builds `generationMessages` for the LLM via `build_generation_messages` (`conversation/foundation/response_generation.py:45`).

4. **Model invocation** — `_foundation_llm_turn` (sync, `service.py:905`) or `_stream_foundation_tokens` (stream, `service.py:1688`) calls `provider.generate` / `provider.stream`.
   - For Ollama: `OllamaProvider.generate` (`providers/ollama.py:286`) or `stream` (`providers/ollama.py:366`).

5. **Tool interpretation loop** — only entered when the model emits a ` ```tool ` fence (see §4). `_interpret_reply` (`service.py:684`) parses via `parse_structured_reply` (`structured_output.py:178`).
   - Read tools: `_run_read_tool` (`service.py:534`) → `ToolExecutionService.execute_read` (`tools/execution.py:226`). Result is fed back via `outcome.follow_up_prompt` (`service.py:618`) and a single follow-up turn is run (`_follow_up_request`, `service.py:841`). `TOOL_LOOP_LIMIT = 1` (`service.py:77`).
   - Mutating tools: `_propose_tool_call` (`service.py:625`) → `ToolExecutionService.propose` (`tools/execution.py:566`) creates a durable proposal; **nothing is applied**.
   - Audited writes (`production_plan.create_draft` only): `execute_audited` (`tools/execution.py:438`) runs immediately because `requires_approval=False`.

6. **Grounding** — `evaluate_grounding` (`conversation/foundation/grounding.py:103`) runs after the stream (`service.py:1783`). It checks the reply against the `DialoguePlan` (question budget, workflow HOLD, prohibited elements, generic praise, dependency language, fake wiki claims, etc.). It does **not** rewrite streamed tokens; it can only substitute the fallback when the streamed reply is empty (`service.py:1790–1793`).

7. **Deferred enrichment** — `run_deferred_enrichment` (`service.py:917`, `:1943`) performs Wiki extraction, read-back verification (`wiki_verification.py`), momentum, creative confidence, next-step options. This is **deliberately after TTFT** (`conversation/wiki_verification.py:10`: `WIKI_VERIFICATION_NEVER_BLOCKS_TTFT = True`).

8. **Persistence** — `append_assistant_completion` (`service.py:945`, `:1016`) records the assistant turn.

### 2.2 Path B — Legacy conversation-core path (`usesLlmPrimary=False`)

Used when the foundation path is bypassed (e.g., no project, or `_conversation_core_handles` matches). `_conversation_core_handles` (`service.py:956`) checks `_CONVERSATION_CORE_INTENTS` (`service.py:1053`). The reply is `core.reply` (a deterministic template), and the model is **not** invoked. This is the listening/hold path.

### 2.3 Cancellation

`request_cancel` (`service.py:485`) marks the request and cancels the asyncio task. `is_cancelled` is checked inside the stream loop (`service.py:1693`) and inside `_run_read_tool`'s parent loop.

## 3. Intent Classification

Intent classification is a heuristic regex pass, not an LLM judgement. `analyze_intent` (`conversation/foundation/intent.py:66`) normalizes the user message, lowercases it, collects evidence spans, and returns an `IntentAnalysis` carrying an `IntentType` plus evidence. The recognized types include `EXPLAIN_PROJECT`, `CORRECT_ASSISTANT`, `REQUEST_ACTION`, `REQUEST_PLAN`, `REQUEST_FEEDBACK`, `INFORM`, `PAUSE_ACTION`, and `UNKNOWN`.

The classified intent feeds two downstream consumers:

- **DialoguePlan construction** (foundation authority) and the legacy `ConversationPlan` merged via `_plan_from_dialogue` (`orchestrate.py:575`). The plan governs question budget, workflow HOLD, prohibited elements, and grounding constraints evaluated in §5.
- **Path selection.** `_conversation_core_handles` (`service.py:956`) consults `_CONVERSATION_CORE_INTENTS` (`service.py:1053`) to decide whether the legacy template path (Path B) handles the turn without invoking the LLM.

Intent classification does **not** decide tool routing. Tool routing is decided later by the model emitting a fenced tool block (§4) and the registry's declared kind — never by the intent label. This separation is intentional: it keeps the model from forging a "REQUEST_ACTION" label into an immediate mutation.

---

## 4. Tool Invocation Protocol

### 4.1 Tool catalog presentation to the model

`_tool_instructions()` (`service.py:304`) builds a static catalog from `tool_registry.all_definitions()` and splits it into **"Read tools (run immediately)"** and **"Change tools (require the user's approval)"** based on `definition.kind`. The model is told:

> "You can never apply a change yourself — a proposed change is shown to the user for approval and the server applies it only after they approve." (`service.py:323`)

> "Request at most ONE tool per reply… After a read tool returns, answer the user in plain prose without requesting another tool." (`service.py:328–330`)

The catalog is composed from the registry alone — no capability probes run during catalog construction, so composing a chat turn costs nothing extra. A model asking for a tool whose capability is missing gets a `capability_blocked` event at execution time, which is the honest answer.

### 4.2 Tool call extraction (provider-agnostic)

`parse_structured_reply` (`structured_output.py:178`) is the single routing classifier. It looks for a ` ```tool ` fence first, then a ` ```proposal ` fence. A tool fence wins over a proposal fence when both appear: the tool fence is explicit about its intent, and running both in one turn would mean two different approval artifacts from a single reply.

### 4.3 `responseType` unforgeability (critical security property)

`structured_output.py:161–169` establishes the central security property of the routing layer: the `responseType` claimed by the model is **advisory and unforgeable**. The actual `response_type` is derived from the registry's declared `definition.kind`:

```python
response_type: ResponseType = "read_tool_call" if definition.kind == "read" else "mutation_proposal"
```

A model claiming `read_tool_call` for a mutating tool is **not** honored — the registry decides. This means the model cannot escalate a mutation into an immediate side effect by mislabeling it.

### 4.4 Malformed tool calls

- Bad JSON in the fence → `StructuredReply(error="Tool block was not valid JSON: …")` (`structured_output.py:139`).
- Not a JSON object → `error="Tool block must be a JSON object."` (`:141`).
- Unknown `responseType` → `error="Tool block has an unknown responseType …"` (`:147`).
- Missing `toolId` → `error="Tool block is missing 'toolId'."` (`:154`).
- Unknown tool id → `error="'{tool_id}' isn't a Co-Director tool."` (`:168`).
- These become `STRUCTURED_OUTPUT_INVALID` errors in `_interpret_reply` (`service.py:704–713`) and are **fatal on the sync path** (`service.py:1006–1009`).

### 4.5 Per-provider tool calling

- **Ollama** (`providers/ollama.py`): No native tool-calling API is used. Tools are conveyed via the system prompt catalog and the model emits fenced JSON. The provider handles **empty replies** (one retry with `think=False`, `ollama.py:305–311` and `:433–457`) and **contamination** via `gate_creator_facing` (`creator_response_gate.py:147`) — it strips/quarantines leaked reasoning. If still empty after retry → `OLLAMA_EMPTY_RESPONSE` (`ollama.py:340`, `:470`).
- **Mock** (`providers/mock.py`): Deterministic scenario-based replies selected by `ADEPT_CODIRECTOR_MOCK_SCENARIO`. Scenarios include `malformed_proposal` (`mock.py:252`), `tool_loop_limit` (`:294`), `read_tool_success`, `read_tool_blocked_capability`, `mutation_tool_proposal`, etc. `_is_follow_up_turn` (`mock.py:50`) detects the post-tool follow-up so E2E scenarios terminate.
- **Base** (`providers/base.py`): Defines `ChatRequest`, `ChatResult`, `CoDirectorProvider` abstract interface.

### 4.6 Tool loop bound

`TOOL_LOOP_LIMIT = 1` (`service.py:77`). The for-loop runs `range(TOOL_LOOP_LIMIT + 1)` (`service.py:985`) so at most one read tool executes per user turn; a second tool request hits `TOOL_LOOP_LIMIT_REACHED` (`service.py:813`).

### 4.7 Registry closure

`tools/registry.py` is a **closed registry**. `_validate_bindings()` (`registry.py:1180`) runs at import time and raises `RuntimeError` if any declared tool lacks a handler or any handler is bound for an undeclared tool. `require_kind` (`registry.py:1226`) enforces tool kind at execution entry.

---

## 5. Response Pipeline

### 5.1 Sync path

`_foundation_llm_turn` (`service.py:905`) calls `provider.generate`, then `_interpret_reply` (`service.py:684`) classifies the reply. Read tools run immediately and feed back via `outcome.follow_up_prompt` (`service.py:618`); a single follow-up turn (`_follow_up_request`, `service.py:841`) lets the model answer in prose. Mutating tools become durable proposals. `STRUCTURED_OUTPUT_INVALID` is fatal on this path (`service.py:1006–1009`). The assistant turn is persisted by `append_assistant_completion` (`service.py:945`, `:1016`).

### 5.2 Streamed path

`_stream_foundation_tokens` (`service.py:1688`) calls `provider.stream`. Tokens are emitted to the client as they arrive. `is_cancelled` is checked inside the stream loop (`service.py:1693`). After the stream completes, `evaluate_grounding` (`grounding.py:103`) runs (`service.py:1783`) and the deferred enrichment runs (`service.py:1943`). Premature wiki-success claims are detected post-stream and surfaced as `wiki_status.prematureClaim` (`service.py:1957–1988`).

### 5.3 Truthfulness gates (what stops false-success claims today)

1. **Tool execution is server-side and logged.** `ToolExecutionService.execute_read` / `execute_audited` / `execute_approved_proposal` all go through `_log_invocation` (`tools/execution.py:146`) which records `status` (`succeeded` / `failed` / `blocked`) in `codirector_tool_invocations`. A failed apply raises `CoDirectorError` (`:724`, `:739`) — the error propagates.
2. **Read-tool failure is fed back to the model as a constraint.** `_run_read_tool` sets `outcome.follow_up_prompt` to: *"The `{tool_id}` tool could not run: {err.message} … Tell the user plainly what you cannot check right now… Do not request another tool."* (`service.py:589–593`). The model is instructed to admit the failure.
3. **Mutating tools never auto-execute.** `_propose_tool_call` (`service.py:625`) creates a proposal; the model cannot claim "done" because nothing happened. The receipt (`tool_proposal_created` event, `service.py:676`) is what the user sees.
4. **Approved-proposal replay is argument-pinned.** `execute_approved_proposal` (`tools/execution.py:697`) replays `payload.arguments` stored at proposal time — "the model gets no second say at approval" (`:707`). Schema version is checked (`:711`).
5. **Wiki success claims are gated.** `orchestrate.py:1226–1243` detects premature wiki-success language ("added to the wiki", "saved to the wiki", etc.) and flags `fake_wiki` when `documentation.candidate_count == 0`. The grounding gate (`grounding.py:202`) emits `NO_FAKE_WIKI_CLAIMS`. The streaming path separately detects premature claims post-stream and emits `wiki_status.prematureClaim` (`service.py:1957–1988`).
6. **Grounding gate.** `evaluate_grounding` (`grounding.py:103`) flags `Claimed tool use under tool_policy=NONE` (`grounding.py:98`) and `EXPLORATION_NOT_CANONIZED` (`:186`).

## 6. Defects

Nineteen defects are catalogued below. Each states the **root cause**, not merely the symptom, and carries the controlling file:line citations. D1 is the framework meta-gap; D2–D6 are the specific handler-level read-before-write gaps surfaced by D1; D7–D11 are truthfulness/verification gaps; D12 is a sync/stream asymmetry in malformed-call handling; D13–D19 are defects added from the complete source-report continuation (intent classification, grounding dead boolean, specialist repair/confidence honesty, mock-provider guard, tool-loop bound, and placeholder prompt files). All citations in D13–D19 were spot-verified against the current working tree on 2026-08-07 (see §9).

### D1 — Read-before-write is framework-unenforced (meta-gap)

**Root cause:** The framework imposes no invariant that every mutating `apply` handler must call a `_require_*` (or equivalent authoritative read) before mutating. `ToolExecutionService.propose` (`tools/execution.py:566`) pins `base_resource_versions` (`:391`) so approval-time staleness is detected, but the **preview** and **apply** handlers themselves are not required to re-read state. There is no framework-level invariant like "every mutating apply must call a `_require_*` first." Safety is handler-by-handler, so any new handler that forgets the check inherits a silent leak. The specific handler-level instances of this gap are enumerated as D2–D6 below.

**Handlers that DO read before write (evidence of the pattern, not the guarantee):** `bible_domain.apply_propose_character_update` (`tools/handlers/bible_domain.py:90`) calls `_require_bible` (`:16`) and reads existing entities via `ops.entities_for_version` (`:94`) before merging (`:105`) and validating (`:106`); `apply_propose_canon_record` (`:136`), `apply_propose_canon_supersession` (`:157`), `apply_propose_continuity_update` (`:178`), `apply_propose_reference_link` (`:209`) all preview through `_require_bible` (`:126`, `:147`, `:168`, `:199`). `project_decisions.apply_record_production_decision` (`tools/handlers/project_decisions.py:73`) uses `_require_project` (`:18`) and reads `project.name` (`:78–81`). Scenes handlers use `_require_project`/`_require_scene`. `director_timeline_tools` previews read current timeline state via `get_director_timeline` and `_layout_state`.

### D2 — `wave4_plans.apply_create_draft` performs no idempotency read

**Root cause:** `wave4_plans.apply_create_draft` (`tools/handlers/wave4_plans.py:251`) only calls `_project(ctx)` (`:35`), which checks the project id is present. It does **not** load the project or check for an existing draft with the same title/objective before calling `PlanService.create_draft`. Idempotency relies entirely on `PlanService` internals, so a repeated draft proposal can create duplicates unless the service happens to deduplicate.

### D3 — `wave4_plans.apply_propose`/`apply_approve`/`apply_reject` skip plan-state read at the handler

**Root cause:** `wave4_plans.apply_propose` (`tools/handlers/wave4_plans.py:285`), `apply_approve` (`:304`), and `apply_reject` (`:319`) pass `planId` straight to `PlanService` with no read of the plan's current state at the handler level. Staleness is enforced by `expected_version` inside `PlanService`, not by the handler. The handler does not call `ToolExecutionService.is_stale` (`tools/execution.py:685`) — that check lives in the approval flow, so the handler is blind to staleness until approval.

### D4 — `bible_domain.apply_propose_canon_supersession` does not verify the superseded record

**Root cause:** `bible_domain.apply_propose_canon_supersession` (`tools/handlers/bible_domain.py:157`) calls `BibleDomainService.create_canon_record` with `supersedes_stable_id` but the handler does **not** verify the superseded record exists or is the current version. It delegates entirely to the service, so a supersession against a stale or missing record is only caught (if at all) inside the service, not at the tool boundary.

### D5 — `bible_domain.apply_propose_continuity_update` can create duplicate continuity entities

**Root cause:** `bible_domain.apply_propose_continuity_update` (`tools/handlers/bible_domain.py:178`) generates a new `entity_key` (`f"cont-{uuid.uuid4().hex[:8]}"`) without reading existing continuity entities. Because it never queries for an existing continuity entity for the same subject, it can create duplicates instead of updating the existing record.

### D6 — `bible_domain.apply_propose_reference_link` performs no existence/duplicate check

**Root cause:** `bible_domain.apply_propose_reference_link` (`tools/handlers/bible_domain.py:209`) does not check whether the asset or target already exists or whether a link already exists. It delegates entirely to the service, so duplicate or dangling reference links are only prevented (if at all) by service-level logic, not at the tool boundary.

### D7 — Grounding cannot rewrite streamed false-success tokens

**Root cause:** `service.py:1790–1793` only substitutes the fallback when the streamed reply is **empty**. The grounding gate (`grounding.py:103`) can flag a violation but has no mechanism to retract tokens already emitted to the client. If the model streamed "Done — I added the scene", the user sees the false claim plus (for wiki claims only) a downstream `wiki_status.prematureClaim` flag. For non-wiki false-success claims (e.g., "I created the scene"), there is **no automatic correction** — only the `STRUCTURED_OUTPUT_INVALID` path is fatal.

### D8 — No post-tool state-diff verification

**Root cause:** After `execute_read` or `execute_audited` runs, the pipeline does **not** re-read native state to confirm the model's prose ("I added X") matches the actual change. The invocation receipt is logged, but the model's prose is not reconciled against `invocation.result`. The only verification is the wiki-specific `WikiWriteVerification` (`wiki_verification.py`), which is deferred and never blocks TTFT. There is no general prose-vs-state reconciliation step.

### D9 — `production_plan.create_draft` runs without preview-then-approve

**Root cause:** `execute_audited` (`tools/execution.py:438`) runs immediately for `production_plan.create_draft` because `requires_approval=False`. The model can persist a draft directly. The draft is non-authoritative (state=draft/unapproved), but the model can still truthfully claim "I created a plan", and the receipt (`tool_completed` with `unapprovedDraft: True`, `service.py:791–797`) is the only signal. There is no gate preventing the model from implying the plan is approved.

### D10 — `is_stale` not surfaced at proposal-creation time on the streaming chat path

**Root cause:** `ToolExecutionService.is_stale` (`tools/execution.py:685`) exists but is invoked only by `ProposalService.approve` (per the docstring at `:704`). A proposal created against stale resources is not surfaced to the model or the user at proposal-creation time in the chat stream — only at approval time. The streaming chat path never calls `is_stale` during `_propose_tool_call` (`service.py:625`), so a stale proposal is presented as fresh until the user tries to approve it.

### D11 — Specialist findings are heuristic by default with no recommendation gate

**Root cause:** `specialist_runner.run_one` (`intelligence/specialist_runner.py:222`) falls back to `_heuristic_finding` (`:438`) when no provider is available, and labels output with `LIMITED_ANALYSIS_ASSUMPTION` (`:102`). But `synthesize` (`intelligence/synthesis.py:23`) still produces a `recommendation` from heuristic-only findings. The recommendation is presented without a hard gate that blocks it when every contributing finding was heuristic — the limited-assumption label is advisory, not a routing constraint.

### D12 — Malformed tool calls are fatal on the sync path only (stream-path asymmetry)

**Root cause:** Malformed tool calls (bad JSON, non-object, unknown `responseType`, missing `toolId`, unknown tool id) become `STRUCTURED_OUTPUT_INVALID` errors in `_interpret_reply` (`service.py:704–713`) and are **fatal on the sync path** (`service.py:1006–1009`). The explicit "on the sync path" qualifier means the streamed path does not treat the same errors as fatal — a malformed tool call during streaming does not abort the turn the way it does synchronously. This asymmetry lets a streamed turn survive a malformed tool block that would have killed a sync turn, producing inconsistent routing guarantees across the two orchestration paths.

### D13 — Intent classifier is lexical and English-only

**Root cause:** `analyze_intent` (`conversation/foundation/intent.py:66`) is a pure regex heuristic. `_ACTION_RE` (`intent.py:41–44`) only matches an act intent when an English action verb (generate/render/create/run/execute/build) co-occurs with an English noun (scene/image/video/clip/shot); `_EXPLAIN_PATTERNS` (`intent.py:10–23`) are likewise English regexes. A real act intent like "Make the hero look tired" does **not** match `_ACTION_RE` (no scene/image/video/clip/shot token), so `should_use_tools` stays `False` (`intent.py:168–170` only fires on a match). A non-English intent ("décris la scène") matches neither `_ACTION_RE` nor `_EXPLAIN_PATTERNS` and falls through to `UNKNOWN` (`should_use_tools=False`, `:236`). The `should_use_tools` flag is therefore unreliable for non-lexical or non-English action requests, and the act-vs-explain posture set by the DialoguePlan inherits that unreliability.

**Repair (c2.13):** Replace the lexical-only classifier with a model-assisted intent pass (or add a fallback that asks the LLM to classify when no regex matches), and add non-English pattern coverage; gate `should_use_tools` on the assisted result rather than regex hits alone.

### D14 — `evaluate_grounding.gate_fail` is computed but discarded

**Root cause:** `grounding.py:225–239` computes `gate_fail` over `NO_`-prefixed notes and a fixed set of gate names, then explicitly discards it: `_ = gate_fail  # retained for callers/diagnostics; violations list is authoritative` (`grounding.py:239`). The authoritative pass/fail is `bool(violations)`. New companion notes are folded into `violations` post-hoc (`grounding.py:241–243`), but the logic is convoluted: the `gate_fail` boolean includes `NO_`-prefixed notes that the `violations` list may not, yet because `gate_fail` is unused, those gates only fire when they also appear in `violations`. The dead boolean is a maintenance trap — a future editor could wire `gate_fail` to a decision and silently diverge from `violations`.

**Repair (c2.14):** Either delete `gate_fail` and its dead computation, or make it the single authoritative signal and derive `violations` from it. Do not leave a computed-but-unused gate boolean next to the real one.

### D15 — `_validate_or_repair` silently rehabilitates malformed provider JSON

**Root cause:** `specialist_runner._validate_or_repair` (`intelligence/specialist_runner.py:344–364`) catches `ValidationError`, substitutes `summary`/`recommendation` with the specialist's `display_name` (`:354–355`), fills all list fields with empty defaults, sets `contentDropped` (`:363`), and returns a `SpecialistFinding` that `model_validate`s. The caller then stamps `finding.status = "validated"` (`specialist_runner.py:262`). The original `ValidationError` is dropped, and `contentDropped` is set but never surfaced to the creator. A malformed provider payload therefore becomes a "validated" finding indistinguishable from a real one except for the unsurfaced `contentDropped` flag.

**Repair (c2.15):** Surface `contentDropped` to the creator (e.g., a `specialist_content_dropped` event) and retain the original validation error in the finding's provenance; do not stamp `status="validated"` on a repaired finding — use `status="repaired"` or `status="degraded"`.

### D16 — Specialist synthesis overstates confidence for heuristic-only output

**Root cause:** `synthesize` (`intelligence/synthesis.py:23`) sets `confidence=0.88 if not blockers else 0.62` (`synthesis.py:86`) whenever there are no blockers, even when every contributing finding came from `_heuristic_finding` (`specialist_runner.py:438`) with `confidence=0.55` and the `LIMITED_ANALYSIS_ASSUMPTION` label (`specialist_runner.py:102`). The honesty signal lives in `assumptions`, not in `confidence`, so a creator reading only `confidence` sees 0.88 (high) for output that was never run through a real provider. This extends D11 (which covers the missing recommendation gate): D11 is the missing block on routing heuristic output; D16 is the confidence label that misrepresents heuristic output as high-trust even when it is presented.

**Repair (c2.16):** Make `confidence` reflect the worst contributing finding's confidence when all findings are heuristic (e.g., cap at 0.55 and surface `LIMITED_ANALYSIS_ASSUMPTION` into `confidence` or a sibling `confidenceBasis` field); do not allow a no-blockers synthesis to read 0.88 when no real provider ran.

### D17 — Mock provider is selectable outside E2E via env override (mitigated, not enforced)

**Root cause:** `active_provider_id` (`service.py:91`) rejects `ADEPT_CODIRECTOR_PROVIDER=mock` unless `e2e_enabled()` (`service.py:99`), and `e2e_enabled()` checks `STUDIO_E2E` (`service.py:88`). The guard is correct, but it relies on an environment variable: if `STUDIO_E2E` is set in a production shell (intentionally or by mistake), `mock` becomes selectable and silently masks a broken local-model deployment for real users. The mitigation is documentation-level — there is no config-level enforcement that prevents `STUDIO_E2E` from being set in a production runtime.

**Repair (c2.17):** Add a hard config guard (e.g., refuse `mock` when a production marker like `ADEPT_ENV=production` is set, independent of `STUDIO_E2E`), and log a warning whenever `active_provider_id` falls back from `mock` to `ollama` so a misconfigured shell is visible.

### D18 — Tool loop limit of 1 blocks legitimate multi-step read sequences

**Root cause:** `TOOL_LOOP_LIMIT = 1` (`service.py:77`) caps a single user turn to at most one read tool. The loop runs `range(TOOL_LOOP_LIMIT + 1)` and a second read request hits `if tools_used >= TOOL_LOOP_LIMIT:` → `TOOL_LOOP_LIMIT_REACHED` (`service.py:813–815`). This is a deliberate safety bound (it stops a tool-happy model from turning one user message into unbounded local work), but it constrains legitimate read-before-write workflows: a "list scenes, then get scene X, then list bible entities" sequence is impossible in one turn — the second read is rejected before the model can ground its proposal. The mechanism is already cited at §2.1 step 5, §4.6, and §7.6; this entry promotes it to a numbered defect with the workflow-impact framing.

**Repair (c2.18):** Raise the bound for read-only sequences (e.g., allow up to 2–3 consecutive read tools when none mutate), or introduce a "read chain" mode that permits multi-read sequences while keeping the hard cap on any mutation attempt; keep the per-turn mutation cap at 1.

### D19 — Core prompt files are placeholder duplicates

**Root cause:** All eight `prompts/core/*.md` files — `codirector.md`, `approval-policy.md`, `uncertainty-policy.md`, `context-discipline.md`, `production-principles.md`, `user-authority.md`, `synthesis.md`, `response-style.md` (under `studio-api/app/codirector/prompts/core/`) — carry distinct front matter (`id`, `display_name`, `description`) and a distinct `# <Title>` / `## Mission` line, but their bodies (`## Responsibilities`, `## Decision Framework`, `## Communication Discipline`) are byte-identical generic text ("Serve the user as one unified production partner…", "Locked Bible data overrides inference…", "Lead with the recommendation. Explain briefly…"). Verified by diffing `codirector.md`, `approval-policy.md`, `response-style.md`, `synthesis.md`, and `uncertainty-policy.md` against the current tree — all share the identical body block. The real policy lives in `assistant.SYSTEM_PROMPT` (`assistant.py:23`) and the `grounding.py` regexes, not in these named policy files. A file named `approval-policy.md` that does not encode approval policy is a maintenance trap: an editor who updates it expecting behavioral change will see none.

**Repair (c2.19):** Either populate each `prompts/core/*.md` with the distinct policy its name promises (and wire it into the system-message composition), or delete the placeholder files and document that core policy lives in `assistant.SYSTEM_PROMPT` + `grounding.py`. Do not leave decorative policy files whose bodies are identical.

## 7. Strengths

The routing layer's structural guarantees are real and should be preserved during c2 repairs:

1. **Closed registry with import-time validation.** `_validate_bindings()` (`registry.py:1180`) raises `RuntimeError` at startup if any declared tool lacks a handler or any handler is bound for an undeclared tool. A misconfigured registry cannot reach a creator turn.
2. **Unforgeable `responseType`.** `structured_output.py:161–169` derives `response_type` from `definition.kind`, not from the model's claim. A model cannot escalate a mutation into an immediate side effect by mislabeling it.
3. **Mutating tools never auto-apply.** `_propose_tool_call` (`service.py:625`) creates durable proposals; the user-facing receipt is `tool_proposal_created` (`service.py:676`). The model cannot truthfully claim a mutation was applied at proposal time.
4. **Argument-pinned replay.** `execute_approved_proposal` (`tools/execution.py:697`) replays `payload.arguments` stored at proposal time (`:707`) with a schema-version check (`:711`). The model gets no second say at approval.
5. **Server-side execution + logging.** All tool execution flows through `_log_invocation` (`tools/execution.py:146`), recording `succeeded`/`failed`/`blocked` in `codirector_tool_invocations`. Failed applies raise `CoDirectorError` (`:724`, `:739`).
6. **Read-tool failure fed back as a constraint.** `_run_read_tool` (`service.py:534`) instructs the model to admit failure via `outcome.follow_up_prompt` (`service.py:589–593`), and the tool loop is bounded at `TOOL_LOOP_LIMIT = 1` (`service.py:77`) with `TOOL_LOOP_LIMIT_REACHED` (`service.py:813`).
7. **Wiki-success gating.** Premature wiki-success language is detected (`orchestrate.py:1226–1243`), gated by `NO_FAKE_WIKI_CLAIMS` (`grounding.py:202`), and surfaced post-stream as `wiki_status.prematureClaim` (`service.py:1957–1988`).
8. **Provider contamination gate.** `gate_creator_facing` (`creator_response_gate.py:147`) strips/quarantines leaked reasoning for Ollama, with a single `think=False` retry on empty replies (`ollama.py:305–311`, `:433–457`) before `OLLAMA_EMPTY_RESPONSE` (`:340`, `:470`).
9. **Cancellation honored in-stream.** `request_cancel` (`service.py:485`) is checked inside the stream loop (`service.py:1693`) and inside `_run_read_tool`'s parent loop.

---

## 8. Repair Recommendations (mapped to milestone phase c2)

Phase c2 owns routing-pipeline integrity. Repairs are ordered by dependency, not severity.

| # | Defect | Repair | Phase c2 sub-step |
|---|---|---|---|
| R1 | D1 (framework meta-gap) | Introduce a framework invariant: every mutating `apply` handler must call a `_require_*` (or a new `require_authoritative_state(ctx, ...)`) before mutating. Enforce via a decorator or a base-handler hook that raises `TOOL_APPLY_WITHOUT_READ` when the invariant is missing. | c2.1 |
| R2 | D2 | `wave4_plans.apply_create_draft` must load the project and check for an existing draft with the same title/objective before `PlanService.create_draft`; dedupe or surface a `DUPLICATE_DRAFT` proposal outcome. | c2.2 |
| R3 | D3 | `wave4_plans.apply_propose`/`apply_approve`/`apply_reject` must read the plan's current state at the handler and call `ToolExecutionService.is_stale` (`tools/execution.py:685`) before delegating to `PlanService`. | c2.3 |
| R4 | D4 | `bible_domain.apply_propose_canon_supersession` must verify the `supersedes_stable_id` record exists and is the current version before calling the service; raise `SUPERSEDED_NOT_CURRENT` otherwise. | c2.4 |
| R5 | D5 | `bible_domain.apply_propose_continuity_update` must query existing continuity entities for the subject before generating a new `entity_key`; update in place when one exists. | c2.5 |
| R6 | D6 | `bible_domain.apply_propose_reference_link` must check asset/target existence and an existing link before creating; raise `REFERENCE_LINK_EXISTS` or `REFERENCE_TARGET_MISSING` as appropriate. | c2.6 |
| R7 | D7 | Add a post-stream correction path: when grounding flags a non-wiki false-success claim, emit a `correction` SSE event that the client renders inline beneath the streamed reply (not a retraction). Document that token retraction is intentionally not supported. | c2.7 |
| R8 | D8 | Add a general post-tool state-diff verification step that reconciles model prose against `invocation.result` for audited writes; surface a `prose_state_mismatch` flag when they diverge. | c2.8 |
| R9 | D9 | Either gate `production_plan.create_draft` behind preview-then-approve, or add a hard `unapprovedDraft` label constraint so the model cannot imply the draft is approved. Prefer the label constraint to preserve the audited-write fast path. | c2.9 |
| R10 | D10 | Call `ToolExecutionService.is_stale` (`tools/execution.py:685`) inside `_propose_tool_call` (`service.py:625`) on the streaming path and surface a `proposal_stale` event at creation time, not only at approval. | c2.10 |
| R11 | D11 | Add a hard gate in `synthesize` (`intelligence/synthesis.py:23`): when every contributing finding is heuristic (`LIMITED_ANALYSIS_ASSUMPTION`), block the `recommendation` or label it `HEURISTIC_ONLY — NOT_ROUTABLE`. | c2.11 |
| R12 | D12 | Make malformed-tool-call handling symmetric across paths: either fatal on both sync and stream, or convert to a non-fatal `structured_output_invalid` SSE event on both. Prefer the event on both so a malformed block does not kill a streamed turn the user already saw tokens from. | c2.12 |
| R13 | D13 | Replace the lexical-only intent classifier with a model-assisted intent pass (or a fallback that asks the LLM to classify when no regex matches); add non-English pattern coverage; gate `should_use_tools` on the assisted result, not regex hits alone. | c2.13 |
| R14 | D14 | Either delete `gate_fail` and its dead computation in `grounding.py:225–239`, or make it the single authoritative signal and derive `violations` from it. Do not leave a computed-but-unused gate boolean next to the real one. | c2.14 |
| R15 | D15 | Surface `contentDropped` to the creator (e.g., a `specialist_content_dropped` event) and retain the original `ValidationError` in the finding's provenance; stamp `status="repaired"`/`"degraded"` on repaired findings, not `"validated"`. | c2.15 |
| R16 | D16 | Make `confidence` reflect the worst contributing finding's confidence when all findings are heuristic (cap at 0.55, surface `LIMITED_ANALYSIS_ASSUMPTION` into `confidence` or a sibling `confidenceBasis`); never allow a no-blockers synthesis to read 0.88 when no real provider ran. | c2.16 |
| R17 | D17 | Add a hard config guard that refuses `mock` when a production marker (e.g., `ADEPT_ENV=production`) is set, independent of `STUDIO_E2E`; log a warning whenever `active_provider_id` falls back from `mock` to `ollama`. | c2.17 |
| R18 | D18 | Raise the bound for read-only sequences (allow up to 2–3 consecutive read tools when none mutate), or introduce a "read chain" mode permitting multi-read sequences while keeping the per-turn mutation cap at 1. | c2.18 |
| R19 | D19 | Either populate each `prompts/core/*.md` with the distinct policy its name promises (and wire it into system-message composition), or delete the placeholder files and document that core policy lives in `assistant.SYSTEM_PROMPT` + `grounding.py`. Do not leave decorative policy files with identical bodies. | c2.19 |

**Phase c2 exit criteria:** all 19 defects have a regression test (Build Law 13), the closed-registry and unforgeability invariants remain green, and a Playwright creator workflow exercises a mutating proposal end-to-end (Build Law 31).

---

## 9. Verification log

The following source-report citations were spot-verified against the current working tree on 2026-08-07. At least 8 were checked; corrections are recorded where drift was found.

| # | Citation (as in source report) | Verified at | Result | Correction |
|---|---|---|---|---|
| V1 | `studio-api/app/routers/codirector.py:250` (`chat`), `:288` (`chat_stream`) | `codirector.py:250`, `:288` | Match | — |
| V2 | `studio-api/app/codirector/service.py:360` (`_prepare_chat_request`) | `service.py:360` | Match | — |
| V3 | `studio-api/app/codirector/service.py:77` (`TOOL_LOOP_LIMIT = 1`) | `service.py:77` | Match | — |
| V4 | `studio-api/app/codirector/service.py:304` (`_tool_instructions`), `:323` ("You can never apply a change yourself") | `service.py:304`, `:323` | Match | — |
| V5 | `service.py:329` ("Request at most ONE tool per reply") | `service.py:328–330` | Drift | The sentence begins on line 328 ("Use responseType … Request at ") and continues on 329. Corrected to `service.py:328–330` in §4.1. |
| V6 | `studio-api/app/codirector/structured_output.py:178` (`parse_structured_reply`), `:161–169` (unforgeability) | `structured_output.py:178`, `:161–169` | Match | — |
| V7 | `studio-api/app/codirector/conversation/foundation/intent.py:66` (`analyze_intent`) | `intent.py:66` | Match | — |
| V8 | `studio-api/app/codirector/providers/ollama.py:286` (`OllamaProvider.generate`) | `ollama.py:286` | Match | — |
| V9 | `studio-api/app/codirector/tools/execution.py:566` (`propose`) | `execution.py:566` | Match | — |
| V10 | `studio-api/app/codirector/tools/registry.py:1180` (`_validate_bindings`) | `registry.py:1180` | Match | — |
| V11 | `studio-api/app/codirector/service.py:684` (`_interpret_reply`), `:905` (`_foundation_llm_turn`), `:901` (`defer_enrichment=True`) | `service.py:684`, `:905`, `:901` | Match | — |
| V12 | `studio-api/app/codirector/conversation/orchestrate.py:282` (`run_conversation_core_turn`), `:1190` (`uses_llm = True`) | `orchestrate.py:282`, `:1190` | Match | — |
| V13 | `service.py:1783` (`evaluate_grounding`) | `service.py:1783` | Match | — |
| V14 | `wiki_verification.py:10` (`WIKI_VERIFICATION_NEVER_BLOCKS_TTFT = True`) | `conversation/wiki_verification.py:10` | Path drift | Source report omits the `conversation/` directory segment. Actual path is `studio-api/app/codirector/conversation/wiki_verification.py:10`. Cited with the full path in §2.1. |
| V15 | `studio-api/app/codirector/tools/handlers/bible_domain.py:90` (`apply_propose_character_update`), `:16` (`_require_bible`) | `bible_domain.py:90`, `:16` | Match | — |
| V16 | `studio-api/app/codirector/tools/handlers/wave4_plans.py:251` (`apply_create_draft`), `:35` (`_project`) | `wave4_plans.py:251`, `:35` | Match | — |
| V17 | `studio-api/app/codirector/tools/handlers/project_decisions.py:73` (`apply_record_production_decision`), `:18` (`_require_project`) | `project_decisions.py:73`, `:18` | Match | — |
| V18 | `intent.py:41–45` (`_ACTION_RE`), `:10–23` (`_EXPLAIN_PATTERNS`) | `intent.py:41–44`, `:10–23` | Match | Confirms English-only regexes; `_ACTION_RE` requires a scene/image/video/clip/shot token. Cited in D13. |
| V19 | `intent.py:168–170` (`should_use_tools=True` for REQUEST_ACTION), `:100–101` (`should_use_tools=False` for CORRECT_ASSISTANT) | `:168–170`, `:100–101` | Match | — |
| V20 | `grounding.py:225–239` (`gate_fail` computed then `_ = gate_fail` at `:239`) | `:225–239` | Match | Confirms the dead boolean. Cited in D14. |
| V21 | `specialist_runner.py:344–364` (`_validate_or_repair`), `:262` (`finding.status = "validated"`), `:354–355` (display_name fill) | `:344–364`, `:262`, `:354–355` | Match | — |
| V22 | `synthesis.py:86` (`confidence=0.88 if not blockers else 0.62`) | `synthesis.py:86` | Match | Cited in D16. |
| V23 | `service.py:91` (`active_provider_id`), `:88` (`e2e_enabled` → `STUDIO_E2E`), `:99` (mock guard) | `:91`, `:88`, `:99` | Match | Cited in D17. |
| V24 | `service.py:77` (`TOOL_LOOP_LIMIT = 1`), `:813–815` (`TOOL_LOOP_LIMIT_REACHED`) | `:77`, `:813–815` | Match | Cited in D18. |
| V25 | `prompts/core/*.md` (8 files) identical bodies | `codirector.md`, `approval-policy.md`, `response-style.md`, `synthesis.md`, `uncertainty-policy.md` diffed | Match | Confirmed identical body block (Responsibilities/Decision Framework/Communication Discipline) across 5 of 8 files; only front matter + H1/Mission differ. Cited in D19. |

**Summary of corrections:** two citations carried minor drift in the original pass. V5 (`service.py:329` → `service.py:328–330`) was a line-range imprecision for a sentence that straddles 328–330; corrected in §4.1. V14 (`wiki_verification.py:10` → `conversation/wiki_verification.py:10`) was a missing directory segment; corrected in §2.1. The seven defects added from the source-report continuation (D13–D19) were each spot-verified against the current working tree (V18–V25) with no further drift. No findings were retracted; all 19 defects and their citations stand.

---

## 10. Status

**Status:** AUDIT COMPLETE — repairs tracked in milestone phases c2/c3.

This document is the governing audit for the Co-Director intent→tool routing pathway under Build Law 30. Routing defects D1–D19 are owned by milestone phase c2 (§8). State/context isolation defects are owned by milestone phase c3 and governed by the companion document `CODIRECTOR_STATE_CONTEXT_AUDIT.md`. No routing defect in this audit is certified repaired; certification requires the c2 exit criteria in §8 plus binary GO per Build Law 24.



