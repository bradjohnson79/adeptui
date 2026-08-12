# Co-Director 2.0 — Professional Creative Producer Intelligence (Phase 1 Audit Pack)

| Field | Value |
|---|---|
| Milestone | Co-Director 2.0 — Professional Creative Producer Intelligence (frozen architecture) |
| Phase | 1 (read-only architecture audits — no product code modified) |
| Date | 2026-08-08 |
| Governing law | Law 30 (single governing document per milestone — this README), Law 4 (projection-only Production State), Law 6 (evidence-derived stage), Law 8 (mock fail-closed), Law 28/31 (evidence before completion) |
| Foundation contracts | `docs/architecture/codirector/CODIRECTOR_FOUNDATION_CONTRACTS.md` |
| Status | All 8 audits complete, each `READY FOR PRIMARY REVIEW`. No binary GO/NO-GO claimed by a subagent. |

> Direction for 2.0 is **reuse, not rebuild**. The frozen-architecture target is a single
> creator-facing persona, scoped specialist context, limited tool exposure, a deterministic-first
> action layer, a projection-only Production State, and verified navigation. Every audit in this
> pack tested the current tree against that direction and returned a KEEP / ADAPT / REWIRE /
> CONSOLIDATE verdict — no greenfield rebuild is recommended anywhere.

---

## 1. Audit index

| # | Document | Domain | Verdict |
|---|---|---|---|
| 1 | [`CODIRECTOR2_INTENT_STAGE_ROUTER_AUDIT.md`](CODIRECTOR2_INTENT_STAGE_ROUTER_AUDIT.md) | Intent extraction + stage routing (intelligence/ + conversation/) | KEEP + HARDEN / REPLACE `route_stage` / UNIFY taxonomies |
| 2 | [`CODIRECTOR2_CONVERSATION_SUBSYSTEM_AUDIT.md`](CODIRECTOR2_CONVERSATION_SUBSYSTEM_AUDIT.md) | Conversation Core package map + Phase-8 fit | KEEP + EXTEND/ADAPT (no supersession) |
| 3 | [`CODIRECTOR2_REQUEST_LIFECYCLE_AUDIT.md`](CODIRECTOR2_REQUEST_LIFECYCLE_AUDIT.md) | End-to-end creator-message lifecycle, hop-by-hop | KEEP structure / EXTEND contract / UNIFY orchestrators |
| 4 | [`CODIRECTOR2_SPECIALIST_REUSE_AUDIT.md`](CODIRECTOR2_SPECIALIST_REUSE_AUDIT.md) | Specialist crew reuse (registry, runner, context) | KEEP + REWIRE / CONSOLIDATE foundation `creative/*` |
| 5 | [`CODIRECTOR2_STORY_INTELLIGENCE_AUDIT.md`](CODIRECTOR2_STORY_INTELLIGENCE_AUDIT.md) | Story compiler / Logline / Short / Long / correction | SUPERSEDE sync compiler / ADAPT editor to proposal flow |
| 6 | [`CODIRECTOR2_SCRIPTWRITER_WIKI_AUDIT.md`](CODIRECTOR2_SCRIPTWRITER_WIKI_AUDIT.md) | Script Writer backend/frontend + Wiki UI dropdowns | KEEP backend / EXTEND navigation / ADAPT Wiki UI |
| 7 | [`CODIRECTOR2_PRODUCTION_STATE_SOURCE_AUDIT.md`](CODIRECTOR2_PRODUCTION_STATE_SOURCE_AUDIT.md) | Authoritative stores feeding Production State projection | Projection-only (Law 4); fix parallel-copy risks |
| 8 | [`CODIRECTOR2_OPERATOR_MOCK_AUDIT.md`](CODIRECTOR2_OPERATOR_MOCK_AUDIT.md) | Operator/navigation tools + mock injection surfaces | SUPERSEDE/REMOVE inert "open" tools; E2E-gate mocks |

---

## 2. Cross-cutting findings (all 8 audits)

1. **Two intent taxonomies already diverge** (Audits 1, 2, 3): `conversation/foundation/intent.py` (`analyze_intent`, evidence spans, `should_ask_question`) vs `intelligence/intent.py` (`classify_intent`, English-only regex, fixed 0.85 confidence). 2.0 must unify on ONE taxonomy; the foundation one is the stronger base (`conversation/foundation/intent.py:90-284`).
2. **Stage is remembered, not derived** (Audits 1, 2, 7): conversation `creativeState` (keyword-inferred, persisted in snapshot), intelligence `ProductionStage` (derived-from-intent, write-only), and discovery `temperature.stage` are three divergent stage models. **Law 6 requires evidence-derived stage** — reconcile all three against authoritative artifacts. Production State Source audit ranks this the single **HIGH** parallel-copy risk: 7 parallel stage sources exist (`CODIRECTOR2_PRODUCTION_STATE_SOURCE_AUDIT.md:§4.1`); 2.0 picks `snapshot.productionLifecycle.currentStage` as the sole persisted authoritative stage.
3. **Silent guessing is the highest intent risk** (Audits 1, 3): low-confidence `unknown` intent proceeds to real specialists, a real stage, and a real plan with no CLARIFY/AMBIGUOUS path (`intent.py:168`, `service.py:139-140`, `specialist_selector.py:69`). 2.0 adds a deterministic-first action layer that emits CLARIFY/AMBIGUOUS instead of guessing.
4. **Two parallel specialist stacks** (Audit 4): `intelligence/` registry (40 specialists) vs `foundation/creative/*` roster (12 ids) — the single highest structural duplication risk to 2.0. Foundation `creative/*` must be CONSOLIDATED (merged or retired), never rebuilt. Three un-synchronized routing maps exist: `_INTENT_SPECIALISTS`, `_INTENT_MAP`/`_KEYWORD_MAP`, `DOMAIN_SPECIALIST_MAP`.
5. **"Open X" navigation is false-success shaped** (Audits 6, 8): no NAVIGATE intent, no deterministic "open" handler; `script.*` reads + dead `recommended_action="open_scriptwriter"` let the model truthfully claim "Script Writer is open" while nothing opened. Four inert navigation tools (`runtime.open_manager`, `references.open`, `continuity.open_workspace`, `posecraft.open_scene`) return success-shaped payloads the frontend never consumes. 2.0 needs a Verified Operator lane + `uiAction:"open_scriptwriter"` mirroring the audio/voice pattern.
6. **Story fields bypass the proposal/approval flow** (Audit 5): compiled Logline/Short/Long are written **directly** into `compiledWiki` (`editor.py:254-269`, `page_compiler.py:207`) with `approval_required=False` (`intelligence/contracts.py:366`). 2.0 reuses `ProposalService` (`bible/proposals.py:128-585`) for CURRENT→PROPOSED→ACCEPT/REJECT on story fields.
7. **Instruction contamination can enter story fields** (Audit 5): `extract_documentation` has no instruction/content split; correction paths store raw instruction text as confirmed high-authority records (`correction/apply.py:161-185`); `compile_story_summary` pastes `narrative[0]` verbatim as logline. Needs an input-side strip + a `NO_INSTRUCTION_CONTAMINATION_IN_SUMMARIES` law.
8. **Fire-and-forget success claims are corrected reactively, never retracted** (Audits 3, 8): wiki/tool premature-claim checks (`service.py:2230-2236`) emit correction events *after* tokens streamed. 2.0 blocks claims at generation (grounding gate) AND verifies.
9. **Mock surfaces must be E2E-gated** (Audits 3, 8): `mock.py:21` reads `ADEPT_CODIRECTOR_MOCK_SCENARIO` env with no app-level guard; scripted scenarios can emit unvalidated tool fences; `stream()` bypasses `creator_response_gate`. 2.0 fail-closed (Law 8).
10. **Production State must be projection-only** (Audit 7): it may compose authoritative info but must NOT become a second writable copy of any authoritative store (Law 4). All 14 domains have a single authoritative store identified; mutation→invalidation attach points are enumerated in the audit §3.

---

## 3. Priority remediation path (proposed Phase 2+ sequencing)

These are the 2.0 workstreams, sequenced to reuse existing infrastructure (frozen-architecture rule). Each is backed by the concrete `file:line` insertion points in the source audit; this README is the governing index, not a re-derivation.

1. **Unify the turn orchestrator** (Audit 3 §8): one engine replacing `chat_for_project` / `_stream_for_project_inner` / legacy provider loop; single entry for sync + stream.
2. **Merge Intent + Stage Router** (Audit 1): one taxonomy; deterministic-first action resolver producing 10 action classes (`DISCUSS, NAVIGATE, READ_INSPECT, MODIFY_KNOWLEDGE, PROPOSE_CREATIVE_CHANGE, EXECUTE_PRODUCTION, APPROVE, REJECT, CLARIFY, AMBIGUOUS`); replace `route_stage` with evidence-derived stage; populate dead fields (`secondaryIntents`, `targetShotId`).
3. **Production State projection** (Audit 7): build projection-only over the authoritative stores; single authoritative `currentStage` from lifecycle; wire mutation→invalidation through `project_cache.invalidate_cache_sections`.
4. **Consolidate specialist stacks** (Audit 4): fold `foundation/creative/*` into the single intelligence stack; unify the three routing maps; add per-specialist tool allowlists; scope context to task-relevant Production State.
5. **Story compiler to proposal flow** (Audit 5): route compiled Logline/Short/Long through `ProposalService`; add instruction strip + contamination law; consume `LivingProjectBrief`/`story_template` as canonical story-model inputs.
6. **Verified Operator lane** (Audits 6, 8): NAVIGATE intent + `uiAction:"open_scriptwriter"` + `workspaceUrl`; SUPERSEDE/REMOVE inert navigation tools; ack/pending/timeout UX; E2E-gate all mock surfaces.
7. **State Verification service** (Audit 3 §4.6): generalize `bible/proposals.py:97` staleness oracle + premature-claim checks into one verifier that also runs at approve-time.

---

## 4. Certification status

- All 8 Phase 1 audits are complete and return `READY FOR PRIMARY REVIEW`.
- Per the standing rules, a subagent never claims a binary GO/NO-GO. The binary certification for the Co-Director 2.0 milestone is the primary's call after primary review of this pack and the subsequent Phase 2+ implementation + Playwright certification (Law 28).
- No product code was modified by this Phase 1 pass; only the 8 audit documents + this README were written.
