# CO-DIRECTOR 2.0 — REUSE CLASSIFICATION (MASTER SYNTHESIS)

| Field | Value |
|---|---|
| Phase | 1 (parent synthesis over the eight read-only audits) |
| Date | 2026-08-08 |
| Source docs | The eight `CODIRECTOR2_*_AUDIT.md` documents in this directory |
| Status | Complete — `READY FOR CO-DIRECTOR 2.0 ARCHITECTURE REVIEW` |

> Governing rule (frozen architecture): **extend before rewriting**. A component may be
> superseded only where the audit proves it cannot satisfy the target contract. This matrix is
> the consolidated verdict of all eight audits. Classification values: KEEP, EXTEND, ADAPT,
> SUPERSEDE, REMOVE, CONSOLIDATE.

---

## 1. Master matrix

| Component | Current Role | Source of Truth | Classification | Target Role (2.0) | Risk |
|---|---|---|---|---|---|
| `conversation/foundation/intent.py` (`analyze_intent`) | Intent analysis with evidence spans + `should_ask_question` + `user_goal_summary` | conversation turn | **KEEP + EXTEND** | Base taxonomy for the unified 2.0 Router (extend to the 10 action classes) | Second taxonomy already diverges |
| `intelligence/intent.py` (`classify_intent`) | English-only regex intent, fixed confidence, first-match-wins | conversation turn | **SUPERSEDE / CONSOLIDATE** | Merge into unified router (foundation taxonomy wins) | Two intent taxonomies |
| `intelligence/stage_router.py` (`route_stage`, `_INTENT_STAGE`) | Static intent→stage map; **write-only**, gates nothing | static map | **REPLACE** | Evidence-derived stage (Law 6) from authoritative lifecycle | Stage remembered-not-derived |
| `conversation/creative_state.py` | Keyword-inferred stage/substate, persisted in snapshot | conversation snapshot | **ADAPT → SUPERSEDE by derivation** | Keep as conversational heuristic input only; never source of truth | 7 parallel stage sources (§4.1 Production State audit) |
| `conversation/foundation/dialogue_policy.py` (`build_dialogue_plan`) | Sole authority for creator-facing behavior | DialoguePlan | **KEEP + EXTEND** | Add professional next-step + already-answered suppression + goal awareness | Bypass via other reply paths |
| `conversation/foundation/grounding.py` | LLM-output quality gates (question budget, generic-praise ban, questionnaire ban) | generated reply | **KEEP** | Direct Phase 8 asset (useful-before-flattery, no generic clarification) | Under-application if paths skip grounding |
| `conversation/orchestrate.py` (`run_conversation_core_turn`) | Top-level turn orchestration; Intent→DialoguePlan authoritative | conversation turn | **KEEP + EXTEND** | Single orchestration spine; attach Router + Production State + Story + Workflow hooks | Drift if a second orchestration path is added |
| `conversation/planner.py` | Heuristic conversation planner | turn | **KEEP + EXTEND** | Stage-aware planner | — |
| `conversation/inquiry.py` (`decide_inquiry`) | Question gating | turn | **KEEP + EXTEND** | Already-answered suppression via provenance-aware Production State | Repeats known questions |
| `conversation/next_steps.py` (`build_next_step_options`) | Contextual next-step options ("soft invitations") | turn + state | **KEEP + EXTEND** | Stage/evidence-aware professional next steps | Generic options |
| `conversation/momentum.py` | Cross-session continuity | project settings | **KEEP** | Continuity asset | — |
| `conversation/snapshot.py` | Persists conversation snapshot (incl. creative stage + lifecycle) | project settings (`projectIntelligence`) | **KEEP + EXTEND** | Persist `conversationFocus` separately from derived stage | Persisting stage as truth |
| `conversation/project_cache.py` | Revisioned Project Intelligence Cache; section invalidation | cache | **KEEP** | Feed Production State projection; propagate invalidation | Stale projections |
| `conversation/knowledge.py` (`apply_wiki_candidates`) | Wiki write application rules | conversation | **KEEP** | Creator-authored verbatim path (Law 7) | AI-rewriting creator content |
| `conversation/deferred_enrichment.py` | Background enrichment after stream | post-TTFT | **KEEP + EXTEND** | Story compiler + operator ack correlation run here | Late success claims |
| `conversation/wiki_verification.py` | Wiki write verification (never blocks TTFT) | store | **KEEP** | Authoritative verification source for knowledge writes | — |
| `conversation/creator_response_gate.py` (root `codirector/`) | Strips leaked reasoning before creator-facing output | response | **KEEP** | Mandatory gate for ALL creator-facing streams | Bypass |
| `conversation_events.py` (root) | Append-only conversation store, idempotent, revisioned | DB | **KEEP** | Authoritative conversation log; operator ack correlation | — |
| `codirector/service.py` (`stream_for_project` / `_stream_for_project_inner`) | Stream orchestration entry; RECEIVING→…→ASSEMBLING stages; `_interpret_reply` dispatch | turn | **ADAPT** | Single entry; insert Router/Production State/Operator hooks at identified points; retire legacy loop | Three reply paths drift |
| `codirector/structured_output.py` (`parse_structured_reply`) | Structured reply parsing | reply | **ADAPT** | Keep; align fence parse with unified action classes | Multiple parsers |
| `providers/` + mock provider | Model provider abstraction + simulated responses | config/env | **KEEP + REMOVE (mock gating)** | Keep abstraction; harden mock fail-closed (Law 8) | Mock leak (currently double-guarded) |
| `intelligence/service.py` | Specialist consult / proposal orchestration | — | **ADAPT** | Hook Router + Workflow; remove dead streaming path | Dormant legacy path |
| `intelligence/specialist_registry.py` | 40-specialist registry, front-matter-driven | prompts/specialists + contracts | **KEEP + REWIRE** | Scoped context, per-specialist tool allowlists | Two stacks |
| `intelligence/specialist_selector.py` | Intent→static id map (cap 8) + continuity | registry | **KEEP + REWIRE** | Router-driven selection; unified routing map | 3 unsynchronized routing maps |
| `intelligence/specialist_runner.py` | Per-specialist scoped context + subordinate execution | contracts | **KEEP + REWIRE** | Limited tools, approval boundary, guaranteed return to Co-Director | Heuristic silent fallback |
| `intelligence/specialist_policies.py` | Subordination invariants, complexity gate, BACKGROUND_ONLY | contracts | **KEEP + REWIRE** | Enforce allowlists + single-face | — |
| `foundation/creative/*` roster (12 ids) | Second specialist stack, declared "the sole specialist stack" | foundation/creative/roster.py | **CONSOLIDATE** (merge or retire into the intelligence stack) | ONE specialist framework | Highest structural duplication risk |
| `bible/proposals.py` (`ProposalService`) | CURRENT→PROPOSED→ACCEPT/REJECT approval engine | proposals store | **KEEP + EXTEND** | Reuse for story fields + operator acks + staleness oracle | Bypass |
| `wiki_intelligence/` (classification, projection, orchestrator, editor) | Wiki/story intelligence + compiled story summary | compiledWiki | **KEEP + ADAPT** | Story Intelligence Compiler base; route Logline/Short/Long through ProposalService | Direct LLM-to-field writes bypass approval |
| `wiki_intelligence/compiled/story_summary_editor` | Compiled Logline/Short/Long editor | compiledWiki | **ADAPT** | Proposal-flow edition (CURRENT→PROPOSED→ACCEPT) | `approval_required=False` today |
| `wiki_intelligence/correction/*` | Creator-correction application | correction store | **KEEP + ADAPT** | Verbatim creator authority (Law 7); strip instruction contamination | Raw instruction text stored as high-authority |
| `scriptwriter/` backend (store, service, api, fountain, pdf_export, transactions, continuity, bible_detect) | Full script backend (28 routes, revisions, Fountain, PDF, continuity, transactions) | scriptwriter DB | **KEEP** | Reuse as-is; add verbatim paste + authorship attribution | No per-element author today |
| `scriptwriter_tools.py` (Co-Director) | 9 read + 7 mutating script tools, proposal-gated | scriptwriter | **KEEP + EXTEND** | Add `uiAction:"open_scriptwriter"` + `workspaceUrl` (Verified Operator) | Dead `recommended_action="open_scriptwriter"` |
| Wiki frontend `CoDirectorProjectContent.tsx` (nav/tabs) | Wiki tabs, Story/Production dropdowns | frontend state | **ADAPT** | Repair dropdown defects; keyboard contract; open reliably | 5 concrete defects found |
| `CoDirectorSession.tsx` (frontend) | Chat session, SSE events, mode inference, uiAction handling | frontend | **ADAPT** | Single lifecycle entry; Verified Operator ack UI; add open_scriptwriter branch | Mode inference duplicates intent |
| Navigation "open" tools: `posecraft.open_scene`, `runtime.open_manager`, `references.open`, `continuity.open_workspace` | Fire-and-forget success-shaped returns; frontend never consumes | — | **SUPERSEDE / REMOVE** | Replace with Verified Operator lane | False success |
| Navigation tools: `voice_performance.open_workspace`, `audio.open_studio`, `character_creator.open_voice_creator`, `timeline.focus_ui` | Workspace open with `uiAction` consumed by frontend | — | **KEEP + ADAPT** | Extend the same pattern to scriptwriter | Partial channels |
| `production_lifecycle/` (ProjectProductionLifecycle) | Gated lifecycle `currentStage` STORY→COMPLETE; persisted in snapshot | snapshot.productionLifecycle | **KEEP** | **Sole authoritative persisted stage** | Parallel stage copies |
| Authoritative stores (project, characters, scenes, Bible, canon, decisions, Timeline, MAGI, Image Planning, Multi-Shot, workspace) | Canonical per-domain data | respective stores | **KEEP (read sources)** | Production State composes these; never a second writable copy | Projection becoming a store |
| E2E/mock infrastructure (mock provider, routers/e2e, fixtures) | Test injection surfaces | env-gated | **KEEP + EXTEND** | Complete `STUDIO_E2E` gating; `m213 e2e/guided` mount-gating | Handler-only gate on m213 |

---

## 2. No-duplication rules (derived from the audits)

1. **ONE intent taxonomy** — `conversation/foundation/intent.py` wins; `intelligence/intent.py` and the frontend mode-inference collapse into it.
2. **ONE orchestration spine** — `orchestrate.py` `run_conversation_core_turn`; retire the legacy provider loop and the dead `stream_intelligence` path.
3. **ONE specialist framework** — the `intelligence/` stack (registry/runner/policies); CONSOLIDATE `foundation/creative/*`.
4. **ONE persisted stage** — `snapshot.productionLifecycle.currentStage`; all other stage sources become candidate evidence only. No new persisted `stage` field.
5. **ONE timeline truth path** — reconcile W46↔MAGI via the handoff contract; never a third timeline store.
6. **Projection-only Production State** — no field may be written back to a store it projects; per-field provenance mandatory.
7. **ONE proposal engine** — story fields, operator ops, and mutations all flow through `bible/proposals.py`.
8. **ONE conversation stack** — no second conversation system in Phase 8.
9. **No second Script Writer backend** — reuse `scriptwriter/` as-is.
10. **Creator content verbatim** — creator-pasted/edited content persists without AI normalization; only AI-derived fields require proposal/approval.

---

## 3. Highest-risk items for review

| Rank | Risk | Audits |
|---|---|---|
| 1 | "Open X" false-success navigation (Script Writer) — no NAVIGATE intent, no verified ack | 6, 8 |
| 2 | Two parallel specialist stacks + 3 unsynchronized routing maps | 4 |
| 3 | 7 parallel stage sources; stage remembered-not-derived | 5, 2, 3 |
| 4 | Two divergent intent taxonomies | 1, 2, 3 |
| 5 | Story fields bypassing proposal/approval (direct LLM-to-field writes) | 6 |
| 6 | Instruction contamination entering story fields | 6 |
| 7 | Fire-and-forget success claims corrected reactively, never blocked | 1, 8 |
| 8 | Mock surfaces must remain fail-closed (m213 handler-only gate) | 8 |
| 9 | Three reply paths causing silent drift | 1 |
| 10 | Wiki Story/Production dropdown defects (5 concrete bugs) | 7 |
