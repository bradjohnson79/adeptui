# CO-DIRECTOR 2.0 — FROZEN ARCHITECTURE RECOMMENDATION

| Field | Value |
|---|---|
| Phase | 1 (parent synthesis; governing recommendation) |
| Date | 2026-08-08 |
| Status | Complete — `READY FOR CO-DIRECTOR 2.0 ARCHITECTURE REVIEW` |
| Reuse map | `CODIRECTOR2_REUSE_CLASSIFICATION.md` |
| Source audits | The eight `CODIRECTOR2_*_AUDIT.md` documents in this directory |

> This document is the architecture recommendation produced from the Phase 1 read-only audits.
> It fixes the request lifecycle, the reuse map, the insertion points, the migration boundaries,
> the no-duplication rules, the implementation phases, the risk register, and the regression
> dependencies. It changes nothing in code. Per the frozen plan, implementation waits for creator/
> architect review.

---

## 1. Request lifecycle (target, consolidated from Audit 1)

```
[1] Frontend composer (thin) → CoDirectorSession.send()          [ADAPT: single lifecycle entry]
[2] POST /conversations/{id}/events (creator event, idempotent)
[3] POST /chat/stream (SSE) → routers/codirector.py
[4] service.stream_for_project → run_conversation_core_turn (orchestrate.py)   [single spine]
[5] INTENT + STAGE ROUTER  → (intent, derivedStage, activeContext, productionState)
[6] DialoguePlan build (foundation/dialogue_policy.py) + grounding gates
[7] Action dispatch by class: DISCUSS / NAVIGATE / READ_INSPECT / MODIFY_KNOWLEDGE /
    PROPOSE_CREATIVE_CHANGE / EXECUTE_PRODUCTION / APPROVE / REJECT / CLARIFY / AMBIGUOUS
[8] NAVIGATE → VERIFIED OPERATOR request (requestId + originSessionId) → pending UX → ack
[9] LLM generation (truthful fallback) + creator_response_gate (strip leaked reasoning)
[10] structured reply → read_tool_call | mutation_proposal (ProposalService CURRENT→PROPOSED→ACCEPT/REJECT)
[11] Deferred enrichment: Story Intelligence + momentum + next-steps (post-first-token)
[12] STATE VERIFICATION: authoritative confirm before success claims; else honest failure
[13] append_assistant_completion (idempotent) → SSE → UI reconcile
```

Insertion points (from Audit 1, verified): Production State at `service.py:1846-1852/516/1070/1883`;
Router at `orchestrate.py:355/302`; Story Intelligence at `orchestrate.py:367-374`,
`intelligence/service.py:171-221`; Workflow at `service.py:1791/2480-2572`; Operator at
`bible/proposals.py:365/401`, `tools/execution.py:700/438`; State Verification at `proposals.py:97/401`,
`service.py:382/2254/2526`.

---

## 2. Reuse map (summary — full matrix in `CODIRECTOR2_REUSE_CLASSIFICATION.md`)

- **KEEP / KEEP+EXTEND (reuse, do not rebuild):** `conversation/foundation/*` (dialogue_policy,
  intent, grounding), `orchestrate.py`, `planner.py`, `inquiry.py`, `next_steps.py`, `momentum.py`,
  `snapshot.py`, `project_cache.py`, `knowledge.py`, `deferred_enrichment.py`, `wiki_verification.py`,
  `creator_response_gate.py`, `conversation_events.py`, `bible/proposals.py`, `scriptwriter/` backend,
  all authoritative stores, `intelligence/specialist_*`, `production_lifecycle/`, E2E gating, the
  audio/voice/focus navigation pattern.
- **ADAPT:** `codirector/service.py`, `structured_output.py`, Wiki frontend (`CoDirectorProjectContent.tsx`),
  `CoDirectorSession.tsx`, `wiki_intelligence/compiled/story_summary_editor` (route through proposals),
  `voice_performance`/`audio_studio`/`character_creator`/`focus_ui` open tools.
- **CONSOLIDATE:** `foundation/creative/*` specialist roster → intelligence stack; the 3 specialist
  routing maps → 1; two intent taxonomies → 1.
- **REPLACE / SUPERSEDE:** `intelligence/stage_router.py` (evidence-derived stage);
  `intelligence/intent.py` (merge into foundation taxonomy); inert nav tools
  (`posecraft.open_scene`, `runtime.open_manager`, `references.open`, `continuity.open_workspace`);
  `creative_state.py` stage as source of truth.
- **REMOVE:** dead streaming path (`stream_intelligence`), dead schema fields, frontend mode-inference
  duplication.

---

## 3. Insertion points (file:line, from audits)

| 2.0 subsystem | Insertion points |
|---|---|
| Production State Projection | `service.py:1846-1852, 516, 1070, 1883`; `project_cache.invalidate_cache_sections`; read `snapshot.productionLifecycle` + authoritative stores |
| Intent + Stage Router | `orchestrate.py:355, 302`; `intelligence/service.py:139`; `codirector/service.py:1665`; base taxonomy `conversation/foundation/intent.py:90` |
| Story Intelligence Compiler | `orchestrate.py:367-374`; `service.py:2110`; `intelligence/service.py:171-221`; `deferred_enrichment.py`; proposals at `bible/proposals.py:128-585` |
| Workflow Engine | `service.py:1791, 2480-2572, 1016`; `routers/codirector.py:909`; `production_lifecycle/service.py` stage evidence |
| Verified Operator | `scriptwriter_tools.py` → `uiAction:"open_scriptwriter"` + `workspaceUrl` (mirror `audio_studio_tools.py:284-285`); `CoDirectorSession.tsx:1710-1762` (add branch ~`:1735`); ack correlation in `conversation_events.py` |
| State Verification | `bible/proposals.py:97, 401`; `service.py:382, 2254, 2526`; `tools/execution.py:688`; `wiki_verification.py` |
| Specialist scoping (Phase 7) | `context_compiler.py:160-194, 438-478`; `specialist_registry.py:67-83`; `specialist_policies.py:62-84`; `specialist_runner.py:330-336`; `planning.py:49-66` |
| Wiki dropdown repair | `CoDirectorProjectContent.tsx:226-296` (openGroup `:255`, `normalizeContentTab` `CoDirectorShell.tsx:31-48`), `codirector-cinematic.css:509, 517-523` |

---

## 4. Migration boundaries

1. **Test-only (Phase 1).** No product code. (This recommendation.)
2. **Operator + Production State (Phase 2).** Additive infrastructure; existing conversation path
   unchanged until ack channel lands; Production State is read-only composition.
3. **Router + Story Intelligence (Phase 3).** Router becomes the dispatch authority; legacy paths
   retained behind the flag until deterministic-first coverage proves out; story fields route through
   ProposalService.
4. **Script Writer/Wiki + Workflow (Phase 4).** UI repairs + `open_scriptwriter` navigation; workflow
   derives stage from authoritative evidence only.
5. **Specialist consolidation + conversation refinement (Phase 5).** `foundation/creative/*` folds into
   the intelligence stack; already-answered suppression + professional next steps.
6. **Certification.** Two-tier (deterministic + real model), full regression, independent verifier.

Boundary rule: **no phase may begin until the previous phase's regression is green.** Each phase is
reviewable and reversible independently.

---

## 5. No-duplication rules (enforced at review)

1. One intent taxonomy. 2. One orchestration spine. 3. One specialist framework. 4. One persisted
   stage (`snapshot.productionLifecycle.currentStage`). 5. One timeline truth path (W46↔MAGI handoff).
6. Projection-only Production State. 7. One proposal engine. 8. One conversation stack.
9. One Script Writer backend. 10. Creator content verbatim (Law 7).

---

## 6. Implementation phases (mapped from the frozen plan to audit evidence)

| Phase | Workstream | Evidence base | Exit gate |
|---|---|---|---|
| 2A | Verified Operator channel (request/ack/pending/timeout, multi-tab correlation, fail-closed mocks) | Audit 8 (operator), Audit 1 (lifecycle) | Operator ack deterministic test |
| 2B | Production State Projection (per-field provenance, freshness invalidation) | Audit 5 (stores), Audit 1 (insertion points) | Projection provenance test |
| 3 | Intent + Stage Router (deterministic-first, 10 action classes, evidence-derived stage, AMBIGUOUS/CLARIFY) | Audit 3 (router), Audit 1 (lifecycle) | "Create shots" zero-writes during script dev |
| 4 | Story Intelligence Compiler (canonical model, Logline/Short/Long, contamination strip, proposal flow) | Audit 6 (story) | Compiler tests + contamination adversarial |
| 5 | Script Writer/Wiki (dropdown repair, `open_scriptwriter`, verified nav) | Audit 7 (scriptwriter/wiki) | Verified open test |
| 6 | Workflow Engine (commercial + narrative, evidence-derived stages) | Audit 5 (lifecycle) | Workflow stage reconciliation tests |
| 7 | Specialist crew rewire (scoped context, allowlists, single face) | Audit 4 (specialists) | Scoping tests |
| 8 | Professional conversation refinement (already-answered suppression, next steps, conversationFocus) | Audit 2 (conversation) | Suppression tests |
| 9 | Schnick Coffee deterministic scenario | All audits | Scenario PASS |
| 10 | Two-tier certification (deterministic + real model) | All audits | GO |
| 11 | Independent verifier + final report | Evidence set | VERIFIED / GO |

---

## 7. Risk register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | "Open X" false-success persists | High | High | Verified Operator lane + ack; no ack = no success claim |
| 2 | Second specialist stack accidentally built | Med | High | CONSOLIDATE `foundation/creative/*`; registry is single source |
| 3 | Stage written in a new place (Law 4 breach) | Med | High | Only `snapshot.productionLifecycle.currentStage` writable; projection read-only |
| 4 | Two intent taxonomies continue to drift | High | Med | Unify in Phase 3; dead schema fields removed |
| 5 | Story fields bypass proposals again | Med | High | ProposalService enforced; `approval_required` default true for AI-derived |
| 6 | Instruction contamination recurs | Med | Med | Input-side strip + `NO_INSTRUCTION_CONTAMINATION` validation + adversarial tests |
| 7 | Mock/E2E surface leaks (Law 8) | Low | High | Complete `STUDIO_E2E` gating incl. m213 mount gate; fail-closed |
| 8 | Regression spike across operational suites | Med | High | Per-phase regression gates; no phase starts on red |
| 9 | Conversation stack duplicated in Phase 8 | Med | Med | Audit 2 evidence; only adapt existing modules |
| 10 | Wiki dropdown defects regress | Med | Low | UI repair + Playwright coverage |

---

## 8. Regression dependencies

- Existing Co-Director operational suite must remain green throughout (frozen §17): tool registry,
  exposure, ownership, proposal/approval, error truthfulness, project isolation, Bible, Character,
  Voice, Image Pipeline, Multi-Shot, Timeline, MAGI, Script Writer, conversation subsystem.
- Each new subsystem ships its own deterministic tests before integration.
- The Final Systems & Resilience gate and Product Law gate remain the locked overall gates per AGENTS.md.
- No implementation workstream may begin until this recommendation is reviewed and the Phase 2
  contracts are frozen by the creator/architect.

---

## 9. Recommendation statement

**Phase 1 is complete and returns `READY FOR CO-DIRECTOR 2.0 ARCHITECTURE REVIEW`.**

The audit pack proves the frozen-architecture direction is achievable **by reuse**: the certified
foundation already contains 90% of the required machinery. The work is consolidation, scoping,
verification, and one new deterministic-first action layer — not a rebuild. The single most urgent
defect to fix first is the false-success "Open X" navigation (Verified Operator lane), followed by
the two-stack specialist consolidation and evidence-derived stage.

**STOP.** No implementation until the creator/architect reviews this recommendation and the reuse
map, and freezes the Phase 2 contracts.
