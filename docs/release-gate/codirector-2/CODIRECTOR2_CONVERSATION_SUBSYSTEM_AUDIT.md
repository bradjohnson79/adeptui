# CO-DIRECTOR 2.0 — CONVERSATION SUBSYSTEM AUDIT

| Field | Value |
|---|---|
| Phase | 1 (read-only architecture audit) |
| Date | 2026-08-08 |
| Status | Complete |
| Scope | `studio-api/app/codirector/conversation/` + related root Co-Director files |

> Compiled by the parent session directly from source reads. An initial subagent run for this
> audit was abandoned because it reported subpackages that do not exist in this tree
> (`core/`, `fundamentals/`, `context_engine/`, `decision_engine/`, `guidance/`) — that output
> was discarded and is not cited here.

---

## 1. Package map (verified against tree)

Root modules:

| Module | Role (from source docstrings/reads) |
|---|---|
| `orchestrate.py` | Top-level Conversation Core orchestration. **Intent → DialoguePlan is authoritative.** Entry `run_conversation_core_turn` (~line 282). |
| `planner.py` | Heuristic conversation planner for creator chat (DialoguePlan production). |
| `foundation/dialogue_policy.py` | `build_dialogue_plan` — the **sole authority** for creator-facing behavior. |
| `foundation/intent.py` | `analyze_intent` — intent analysis with **evidence spans**, not labels alone; returns `user_goal_summary` + `should_ask_question`. |
| `foundation/grounding.py` | Response grounding / quality gates against DialoguePlan (+ companion gates). Enforces `question_budget`, detects generic praise (`_GENERIC_PRAISE_RE`), questionnaires (`_QUESTIONNAIRE_RE`). |
| `foundation/personality.py` | Default personality profile — expression constraints, not facts. |
| `foundation/context_assembler.py` | Goal-ranked context assembly for listening / discovery turns. |
| `foundation/response_generation.py` | Builds LLM generation inputs from DialoguePlan; deterministic fallback last resort. |
| `foundation/policy_version.py`, `foundation/schemas.py` | Version markers + typed contracts (Part A). |
| `inquiry.py` | `decide_inquiry` — whether/how to ask the creator (question gating). |
| `next_steps.py` | `build_next_step_options` — contextual next-step options, "soft invitations, not menus". |
| `momentum.py` | Conversation Momentum Engine — continuity across sessions; `update_momentum_from_turn`, `resume_greeting`. |
| `circuit_breakers.py` | Optional-source circuit breakers — skip flaky retrieval without blocking chat. |
| `knowledge.py` | `apply_wiki_candidates` — knowledge application rules for project conversation memory. |
| `creative_state.py` | Creative state machine heuristics — **keyword-inferred stage/substate**, remembered and persisted (see §4). |
| `creative_confidence.py` | Lean Creative Confidence — longitudinal project patterns (Phase 1). |
| `success_score.py` | Internal quality scoring for a deterministic conversation turn. |
| `complexity.py` | Request complexity classification + context budgets. |
| `snapshot.py` | Snapshot load/save/bootstrap for conversation intelligence (persists creative stage). |
| `project_cache.py` | Compact revisioned Project Intelligence Cache — warm on open, section invalidation. |
| `project_director.py` | Deterministic project director state refresh. |
| `deferred_enrichment.py` | Background Wiki / Living Brief enrichment after response streaming begins. |
| `request_timing.py` | Per-request stage timing ledger (sanitized for SSE/diagnostics). |
| `reasoning_remediation.py` | Project-safe remediation of persisted assistant messages that leaked internal reasoning. |
| `response_composer.py` | Natural-language reply composition for the conversation core. |
| `wiki_rebuild.py` | Generic "Rebuild Wiki from conversation" — any projectId, format-aware. |
| `wiki_verification.py` | Wiki write verification — persistence vs presentation; never blocks TTFT. |
| `schemas.py` | Shared schemas for the conversation core. |

Subpackages:

| Subpackage | Modules | Role |
|---|---|---|
| `foundation/` | context_assembler, dialogue_policy, grounding, intent, personality, response_generation, policy_version, schemas | Foundational AI intelligence layer (Part A) — intent authority + dialogue policy + grounding gates. |
| `companion/` | advisory, block, context, deviation, lens, persistence, principles, problem_source, return_points, strengths, support, schemas | Creative Companion & Advisory Intelligence (additive). Evidence-based (strengths "no vague flattery"), story-deviation assessment, creative lens. |
| `discovery/` | brief, composition, curiosity, documentation, form, intrigue, persistence, research, response_evidence, schemas, temperature | Personality discovery + living brief + adaptive questions + emergence protection (`temperature.stage`). |
| `partnership/` | composition, deliverables, destination, journey, marketing, ownership, persistence, pitch, questions, readiness, rehearsal, schemas, story_template, vision | Hands-on partnership: ownership, artifacts, journey, vision, pitch, marketing. Preview-first, never silently approved. |
| `relationship/` | onboarding, persistence, roles, schemas | Relationship onboarding + creator creative profile + role emphasis. |

Related root Co-Director files (`studio-api/app/codirector/`):

| File | Role |
|---|---|
| `conversation_events.py` | Append-only event store: server-assigned sequences, idempotency on `(project_id, client_request_id)` and `(project_id, message_id)`, optimistic concurrency via `codirector_conversations.revision` header; `fold_events` reconstructs legacy shape. |
| `conversation_compaction.py` | Compaction summary events (`compact_conversation`, `revision_after_compact`). |
| `conversation_audit.py` | `audit_conversation` — sequence monotonicity, message_id uniqueness, revision presence, fold count. |
| `creator_response_gate.py` | Response isolation gate — strips/blocks leaked reasoning before streaming/persisting creator-facing replies. |
| `conversation_memory.py`, `structured_output.py`, `inference_activity.py` | Related conversation persistence / output / activity plumbing. |

---

## 2. Classification matrix

| Layer | Current Role | File/Function citations | Classification | Target Role in 2.0 | Risk |
|---|---|---|---|---|---|
| `orchestrate.py` | Top-level turn orchestration; Intent→DialoguePlan authoritative | `orchestrate.py:282` (`run_conversation_core_turn`) | KEEP + EXTEND | Keep as the single orchestration spine; add Production State read + Router hook + stage derivation into DialoguePlan assembly | Drift if a second orchestration path is added |
| `foundation/dialogue_policy.py` | Sole authority for creator-facing behavior | `foundation/dialogue_policy.py:24` (`build_dialogue_plan`) | KEEP + EXTEND | Add professional next-step + already-answered suppression + goal-awareness into the plan | Bypassing it via other reply paths |
| `foundation/intent.py` | Intent analysis with evidence spans + `should_ask_question` + `user_goal_summary` | `foundation/intent.py:90` (`analyze_intent`) | KEEP + EXTEND | This is the natural foundation for the 2.0 Router intent classes (DISCUSS/NAVIGATE/etc.) — extend to the 10 action classes | Parallel `intelligence/intent.py` taxonomy already diverges (see §4) |
| `foundation/grounding.py` | LLM-output quality gates: question budget, generic-praise ban, questionnaire ban | `foundation/grounding.py:76,92-94,156` | KEEP | Strong existing anti-affirmation + anti-unnecessary-question enforcement — direct Phase 8 asset | Under-applied if other paths skip grounding |
| `foundation/context_assembler.py` | Goal-ranked context assembly | `foundation/context_assembler.py` | KEEP + EXTEND | Add `derivedStage` + `productionState` scoped projection to context | Context bloat |
| `planner.py` | Heuristic conversation planner | `planner.py` | KEEP + EXTEND | Stage-aware planner; professional next-step options | — |
| `inquiry.py` | Question gating (`decide_inquiry`) | `inquiry.py:43` | KEEP + EXTEND | Add already-answered suppression via provenance-aware Production State | Repeats known questions today |
| `next_steps.py` | Contextual next-step options ("soft invitations") | `next_steps.py:225` (`build_next_step_options`) | KEEP + EXTEND | Make options stage/evidence-aware (professional next-step reasoning) | Generic options |
| `momentum.py` | Cross-session continuity, energy, resume greeting | `momentum.py:82` | KEEP | Continuity asset for Phase 8 | — |
| `creative_state.py` | Keyword-inferred, **remembered** stage/substate | `creative_state.py:65-154` (`_infer_target`, `update_creative_state`) | ADAPT → SUPERSEDE by derivation | Replace with evidence-derived stage (Law 6). Keep as conversational heuristic input only, never source of truth | Stage remembered-not-derived |
| `snapshot.py` | Persists conversation snapshot incl. creative stage | `snapshot.py:149-175` | KEEP (persist) + EXTEND | Persist conversation focus separately from derived stage | Persisting stage as truth |
| `project_cache.py` | Revisioned Project Intelligence Cache; warm on open, section invalidation | `project_cache.py` | KEEP | Feed Production State Projection from cache; propagate invalidation on native mutations | Stale projections |
| `knowledge.py` | Wiki write application rules | `knowledge.py:52` (`apply_wiki_candidates`) | KEEP | Creator-authored content verbatim path (Law 7) | AI-rewriting creator content |
| `deferred_enrichment.py` | Background enrichment after stream | `deferred_enrichment.py` | KEEP + EXTEND | Story Intelligence compiler runs here; operator ack correlation | Late success claims (see Audit 1 risk) |
| `wiki_verification.py` | Wiki write verification, never blocks TTFT | `wiki_verification.py` | KEEP | Authoritative verification source for knowledge writes | — |
| `circuit_breakers.py` | Optional-source circuit breakers | `circuit_breakers.py` | KEEP | Truthful fallback on provider/retrieval flakiness | Silent fallback |
| `success_score.py` | Internal turn quality score | `success_score.py` | KEEP | Diagnostic metric; expose sanitized | — |
| `complexity.py` | Complexity classification + context budgets | `complexity.py` | KEEP | Inform specialist scoping (Phase 7) | — |
| `reasoning_remediation.py` | Remediation of leaked reasoning in persisted messages | `reasoning_remediation.py` | KEEP | Defensive layer under Creator Response Gate | — |
| `response_composer.py` | NL reply composition | `response_composer.py` | KEEP + ADAPT | Single professional persona composition | — |
| `request_timing.py` | Stage timing ledger (sanitized) | `request_timing.py` | KEEP | Observability (§18) | — |
| `wiki_rebuild.py` | Rebuild Wiki from conversation | `wiki_rebuild.py` | KEEP | Story Intelligence ingestion trigger | — |
| `companion/*` | Advisory/lens/deviation/strengths (evidence-based) | `companion/` | KEEP | Professional creative-judgment asset; strengths "no vague flattery" aligns with Phase 8 | Overlap with discovery |
| `discovery/*` | Personality discovery, living brief, adaptive questions, emergence protection | `discovery/` | KEEP | Question generation source — must be provenance-aware | Giant questionnaire risk (already mitigated) |
| `partnership/*` | Ownership/journey/artifacts/vision/pitch preview-first | `partnership/` | KEEP | Workflow Engine asset (commercial/narrative journey) | — |
| `relationship/*` | Onboarding, roles, creator profile | `relationship/` | KEEP | Creator profile persistence | — |
| `conversation_events.py` | Append-only conversation store (idempotent, revisioned) | `conversation_events.py` | KEEP | Authoritative conversation log; operator ack can correlate here | — |
| `creator_response_gate.py` | Strips leaked reasoning before creator-facing output | `creator_response_gate.py` | KEEP | Mandatory gate for ALL creator-facing streams | Bypass |
| `conversation_audit.py`, `conversation_compaction.py` | Integrity audit + compaction | `conversation_audit.py`, `conversation_compaction.py` | KEEP | Deterministic certification + regression (Tier A) | — |

---

## 3. Mapping answers (with citations)

1. **Where are questions to the creator GENERATED?**
   `inquiry.py:43` (`decide_inquiry`) gates questioning; `foundation/dialogue_policy.py:24` sets `question_budget` on the DialoguePlan; `discovery/form.py` builds adaptive discovery questions "never a giant generic questionnaire"; `partnership/questions.py` is an "intuitive key-question engine — scores hidden; flow-safe deferral"; `companion/context.py` assembles mode-specific context. Grounding (`foundation/grounding.py:76,156`) then rejects any reply that exceeds `question_budget`.

2. **Where does CLARIFICATION originate and how specific is it?**
   Clarification is currently delegated to the LLM during DialoguePlan generation (`foundation/response_generation.py`), constrained only by `question_budget`. There is no dedicated, *specific-alternatives* clarification builder in this tree. This is a **Phase 8 gap**: the 2.0 AMBIGUOUS/CLARIFY contract ("Did you want me to open Script Writer, or stay here…?") has no deterministic home yet.

3. **Where does praise/affirmation originate?**
   No dedicated affirmation module. Instead, `foundation/grounding.py:94` actively **rejects generic praise** in generated replies (`_GENERIC_PRAISE_RE`), and `companion/strengths.py` is explicitly "evidence-based … no vague flattery". Good existing anti-flattery posture — the 2.0 "useful before flattery" rule is largely already enforced.

4. **Where do next-step suggestions originate?**
   `next_steps.py:225` (`build_next_step_options`) — "soft invitations, not menus"; `discovery/curiosity.py` (deferred follow-through); `planner.py` (heuristic planner). These are not yet stage/evidence-aware — Phase 8 target.

5. **Where is the current conversation GOAL tracked (separate from production stage)?**
   Partially. `foundation/intent.py` returns `user_goal_summary` per turn and `DialoguePlan` carries the goal; `momentum.py` and `snapshot.py` persist cross-turn state; `creative_state.py` tracks a *creative* stage/substate. There is no explicit, persisted `conversationFocus` field distinct from derived stage — **Phase 8 addition**, to be layered on the existing intent `user_goal_summary` (do not build a second tracker).

6. **Where are prior established facts considered vs ignored?**
   `snapshot.py` (persisted snapshot), `project_cache.py` (warm Project Intelligence Cache), `creative_state.py` (stage/substate), `momentum.py` (cross-session), `companion/lens.py` (gradual creative interpretation). These are the inputs a provenance-aware Production State projection would read. There is **no per-field provenance / no already-answered ledger** today — Phase 2B/8 addition.

7. **Where are already-answered questions suppressed or repeated?**
   Only indirectly: `grounding.py` bans question-budget overflow, and `knowledge.py`/`apply_wiki_candidates` absorb established facts into Wiki. There is **no deterministic "don't re-ask" mechanism** — the Phase 8 §14 "already-answered question suppression" must read provenance-aware Production State before inquiry.

8. **Circuit breakers / overuse guards:**
   `circuit_breakers.py` (skip flaky retrieval without blocking chat); `foundation/grounding.py` question-budget + empty-praise + questionnaire bans; `momentum.py` energy continuity. Good foundation; keep.

9. **Creator-response gate:**
   `creator_response_gate.py` strips leaked reasoning before streaming/persisting; `structured_output.py` parses replies; `reasoning_remediation.py` repairs already-persisted leaks. Keep as mandatory surface for all creator-facing output.

---

## 4. Cross-cutting findings (cross-reference Audit 3)

- **Two intent taxonomies already diverge:** `conversation/foundation/intent.py` (`analyze_intent`, evidence spans, `should_ask_question`) vs `intelligence/intent.py` (`classify_intent`, English-only regex, fixed confidence) — see `CODIRECTOR2_INTENT_STAGE_ROUTER_AUDIT.md`. The 2.0 Router must unify on ONE taxonomy; the foundation one is the stronger base.
- **Stage is remembered, not derived:** `creative_state.py` infers stage from keywords and persists it in the snapshot; `discovery/temperature.py` has a third `stage`. Law 6 requires evidence-derived stage. None of the three reconcile with authoritative artifacts (script existence, shot planning, Timeline batches).
- **Quality gates already exist and should be preserved:** `foundation/grounding.py` question-budget/praise/questionnaire enforcement is exactly the Phase 8 "no generic clarification / no flattery" posture — extend, don't replace.

---

## 5. Phase 8 feedback — adaptable vs missing

| Phase 8 goal | Adaptable existing module | Missing work |
|---|---|---|
| Already-known-fact retention | `snapshot.py`, `project_cache.py`, `knowledge.py`, `momentum.py` | Per-field provenance (2B) feeding the projection |
| Already-answered suppression | `inquiry.py` + `grounding.py` question budget | Deterministic "don't re-ask" read of Production State |
| Professional next-step reasoning | `next_steps.py` + `planner.py` | Stage/evidence-aware option building |
| Conversation goal separate from derived stage | `foundation/intent.py` `user_goal_summary` + `snapshot.py` | Explicit persisted `conversationFocus` |
| Specific (non-generic) clarification | — | New AMBIGUOUS/CLARIFY builder (small, deterministic) |
| Useful-before-flattery | `grounding.py` + `companion/strengths.py` | Already largely satisfied |

---

## 6. Top risks

1. A second conversation stack being built in Phase 8 — **forbidden**. Everything needed to adapt exists here.
2. `creative_state.py` stage being treated as truth when it is keyword-inferred and remembered.
3. Multiple reply paths bypassing `foundation/dialogue_policy.py` / `creator_response_gate.py` (see Audit 1: three reply paths).
4. Generic clarification because there is no deterministic AMBIGUOUS/CLARIFY builder.
5. Question-budget grounding gate being skipped by any new surface.

**Verdict:** Conversation subsystem is a **KEEP + EXTEND/ADAPT** foundation. No supersession required. The 2.0 Router, Production State, and Story Intelligence should attach to the existing Conversation Core spine, not replace it.
