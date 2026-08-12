# CO-DIRECTOR 2.0 — PHASE 7 SPECIALIST CREW REWIRE IMPLEMENTATION CONTRACT (FREEZE)

| Field | Value |
|---|---|
| Phase | 7 (implementation) |
| Date | 2026-08-08 |
| Status | **FROZEN** — governing contract for Phase 7 code. No Phase 7 source edit precedes this document. |
| Supersedes | Nothing. Sibling to the Phase 2–6 contract/certification pack; those documents remain current truth for their scope (Law 30). |
| Governing law | Adept UI Build Memory Layer; frozen architecture `CODIRECTOR2_FROZEN_ARCHITECTURE_RECOMMENDATION.md`; reuse map `CODIRECTOR2_REUSE_CLASSIFICATION.md`; specialist reuse audit `CODIRECTOR2_SPECIALIST_REUSE_AUDIT.md`. |
| Evidence base | `CODIRECTOR2_SPECIALIST_REUSE_AUDIT.md` + live runtime verification (below). |
| Certification target | `GO — CO-DIRECTOR 2.0 PHASE 7 SPECIALIST CREW REWIRE CERTIFIED` → `READY FOR CO-DIRECTOR 2.0 PHASE 8` |

> Source-of-truth order (unchanged): 1) actual repo behavior → 2) audit evidence → 3) frozen
> architecture recommendation → 4) this contract's conceptual descriptions. Where a citation in this
> contract disagrees with live source, the live source wins and this contract must be amended.

**Phase 7 scope.** Rewire the existing certified specialist infrastructure into a scoped internal
creative crew serving the Co-Director 2.0 executive stack. Selection becomes RouteDecision-aware;
minimum-crew delegation (default 1, hard max 3) is enforced; `allowed_context` domain allowlisting is
runtime-enforced; permission fields (`may_propose_tools`, `may_execute_tools`, `approval_required`,
`escalation_path`) genuinely constrain runtime; and a synthesis/conflict-reconciliation layer produces
a single creator-facing voice.

**Frozen exclusions (do NOT do in Phase 7).** Build a second specialist registry, second selector,
or second synthetic taxonomy. Rewrite `specialist_runner.py` internals beyond contract-designated
seams. Replace the existing `SynthesisEngine`; only extend it to be RouteDecision-aware and
conflict-classifying. Mutate `conversation/` composition (Phase 8). Change `routing/contracts.py`,
`production_state/contracts.py`, `operator/contracts.py`, or `workflow/definitions.py` contracts. No
new persisted specialist store. No specialist state authority — Production State remains a
read-through projection (Law 4).

---

## 1. Runtime-verified ground truth (2026-08-08)

Executed live against the working tree:

| Fact | Value |
|---|---|
| Enabled specialist count | **40** (runtime `SpecialistRegistry().ids()`) |
| Registry mechanism | Declarative via YAML front matter in `prompts/specialists/*.md`; `SpecialistRegistry._rebuild()` keeps only `enabled` |
| `may_execute_tools` | Forbidden for all specialists — enforced at `prompts/validator.py` AND `specialist_registry._from_prompt` (hard ValueError) |
| `may_propose_tools` | Front-matter flag; surfaced as `mayProposeTools`; only concrete coded proposal is `prompt-architect → propose_storyboard_generation` (heuristic path) |
| Wiki-write allowlist | `WIKI_WRITE_SPECIALIST_IDS` (30 ids) — gates Wiki-write *proposals*, consumed at `specialist_policies.build_contract` |
| Existing selector | `_INTENT_SPECIALISTS` intent→static tuple map, `MAX_SPECIALISTS = 8`, continuity auto-inject, required/optional split; **no route decision awareness, no confidence, no workflow/stage awareness** |
| Policy gate | `specialist_policies.select_specialists_for_turn` SKIPs all for complexity TINY/SMALL, heavy ids → BACKGROUND_ONLY |
| Execution | `SpecialistRunner`: compiles ONE `ContextPackage`, per-specialist `filter_for_specialist` scope; provider path (JSON-only, subordinate prompt) + heuristic path (`limited-analysis`, cached, TTL 600) |
| Approval boundary | `PlanBuilder` → every tool step `requiresApproval=True`; `PlanValidator` rejects non-mutating/unregistered tools; `PlanExecutorBridge.create_proposals` → `ToolExecutionService.propose` — no direct execution from findings |
| Single persona | `SynthesisEngine.synthesize` produces ONE `SynthesisResult.userMessage`; conversation main path treats consult as subordinate and falls through to foundation/provider LLM |
| Routing | `RouteDecision` frozen (11 action classes); `service.py` early-dispatches NAVIGATE and APPROVE/REJECT; `intelligence/service.py` still selects against legacy `IntentClassification` |

---

## 2. Touched files & ownership boundaries (subagent mapping)

| Area | File(s) | Owner | Disposition |
|---|---|---|---|
| Contract freeze | `docs/release-gate/codirector-2/CODIRECTOR2_PHASE7_SPECIALIST_CREW_IMPLEMENTATION_CONTRACT.md` | parent (this doc) | NEW (this file) |
| Inventory | — (prompt front matter + `contracts.py` + `specialist_policies.py` + `wiki_intelligence/contracts.py`) | Agent A (read-only) | audit artifact only |
| Scoped context | `studio-api/app/codirector/intelligence/context_compiler.py` | Agent B | ADAPT — enforce `allowed_context` runtime allowlisting w/ forbidden-domain filter; no new store |
| Selection | `studio-api/app/codirector/intelligence/specialist_selector.py` | Agent C | REWRITE — RouteDecision-aware; NAVIGATE/READ → 0; DISCUSS → 1; cross-disciplinary max 2–3; structured confidence + targetDomain |
| Permissions | `studio-api/app/codirector/intelligence/specialist_policies.py` (+ enforcement points) | Agent D | HARDEN — runtime enforcement of `may_propose_tools`/`may_execute_tools`/`approval_required`/`escalation_path` (not decorative) |
| Synthesis | `studio-api/app/codirector/intelligence/synthesis.py` | Agent E | EXTEND — RouteDecision-aware, conflict classification, no raw JSON/system-prompt leakage to creator |
| Service gating | `studio-api/app/codirector/service.py` and `studio-api/app/codirector/intelligence/service.py` | parent + Agent F (bounded diff only) | GATE — selection behind `route_decision`; zero-specialist NAVIGATE/READ guard; single-persona enforcement |
| Tests | `studio-api/tests/test_phase7_specialist_crew.py` (new) + existing suites | Agent G | scaffold only new fixture/mocks per this contract |
| E2E | Playwright `tests/e2e/**` or existing mock-scripted harness | Agent H | reuse `STUDIO_E2E` + `ADEPT_CODIRECTOR_MOCK_SCENARIO=scripted`; no expensive generation |
| Regression | prior-phase suites + existing Co-Director suite | parent | no broad regression |
| Verifier | fresh read-only subagent | Agent V | VERIFIED or BLOCKED |

**Ownership hard rules (all waves):**
- No subagent edits `routing/contracts.py`, `production_state/*`, `operator/*`, `workflow/definitions.py`, `conversation/` (all READ-ONLY this phase).
- No subagent creates a second specialist registry, second selector, or second synthetic taxonomy.
- `service.py` is shared: subagents propose bounded diffs; parent merges and resolves conflicts.
- Each subagent returns `READY FOR PRIMARY REVIEW` (never final GO). Parent owns final integration, Beta refresh, certification verdict.

---

## 3. Minimum-crew selection contract (frozen)

| RouteActionClass | Specialists | Rationale |
|---|---|---|
| `NAVIGATE` | **0** (hard guard) | Operator lane only |
| `READ_INSPECT` | **0** unless justified (simple read) | Read via native reads; a compelling analytic request may justify 1 |
| `APPROVE` / `REJECT` | **0** | proposal/anti-proposal lane |
| `CLARIFY` / `AMBIGUOUS` / `UNKNOWN` | **1** at most (best-guess Domain Expert) | clarify, no deep crew |
| `DISCUSS` (creative / needs-sharpening) | **1** by default | focused single-expert view |
| `MODIFY_KNOWLEDGE` | **1** (knowledge steward) | single-domain steward |
| `PROPOSE_CREATIVE_CHANGE` | **1–2** | primary + optional cross-domain contributor |
| `EXECUTE_PRODUCTION` | **max 3** (2–3) | production crew; bounded |

Hard bounds: **default 1, hard max 3** (`MAX_SPECIALISTS = 3` replaces old 8). `selectionConfidence`
(0..1) + `targetDomain` structured output required. Workflow/stage awareness: selector MAY consume
`workflow stage + activeTask` when production carriers provide it. Creator-goal priority preserved:
explicit dialogue/script intent → Script discipline specialists (screenwriter/story-editor), NOT DOP.

Zero-specialist guard is **enforced at selection AND at the service layer** (defense in depth).

---

## 4. Scoped-context contract (frozen)

- `ContextCompiler.compile` must enforce the union of `allowed_context` across **selected** specialists
  as a runtime **allowlist**: any fact category not in the union is excluded from the compiled package.
- Forbidden-domain filter: a fixed forbidden set (e.g. `full_tool_registry`, `full_marketing_plan`,
  full conversation dump) is always excluded even if a specialist lists it.
- `filter_for_specialist` already narrows to the individual specialist's categories — this is the
  per-specialist allowlist and must remain. No new store; facts remain read-through from authoritative
  sources (Law 4/Law 5).
- User message parity: `user.message` fact is always included (delimited, redacted) regardless of category.

---

## 5. Permission-enforcement contract (frozen)

| Field | Semantic | Enforcement point |
|---|---|---|
| `may_propose_tools` | May emit `ProposedToolAction`s | Runtime: selector may only plan tool actions for specialists with this flag; `PlanBuilder` keeps `requiresApproval=True` boundary |
| `may_execute_tools` | MUST be False for specialists | Already hard-blocked at validator + registry; Phase 7 adds a runtime assert at runner entry |
| `approval_required` (contract) | Specialist's outputs require creator approval before effect | Propagated to synthesis → plan steps (`requiresApproval=True`); no silent effect |
| `escalation_path` | Where the specialist routes hard/edge cases | Surfaced in synthesis only as creator-facing actionable paths if genuinely actionable; never as a JSON dump |

No specialist may bypass approved proposal/execution lanes or the Verified Operator channel.

---

## 6. Synthesis/conflict contract (frozen)

`SynthesisEngine.synthesize` extended (RouteDecision-aware):
- Inputs: creator message + `RouteDecision` + Production State slice + specialist findings.
- Classify disagreement: stylistic / technical / continuity / feasibility / priority.
- Combine compatible recommendations; present genuine tradeoffs otherwise.
- Never expose raw specialist JSON, system prompts, or proposal scaffolding to the creator.
- Handle timeout/failure gracefully — no fabricated results (a failed/timed-out specialist must not
  produce a confidence above the heuristic band; no invented recommendation).

`synthesis.conflictsResolved` stays the single conflict ledger; `userMessage` remains the single
creator-facing voice.

---

## 7. Service-gating contract (frozen)

- `intelligence/service.py` selection is gated by the Phase 3 `RouteDecision` (already computed in
  `service.py`); the legacy `IntentClassification`-driven selection is superseded for the crew path.
- `service.py` NAVIGATE/READ early dispatch already returns before specialists; add a **zero-specialist
  guard** in the consult path (`wantsSpecialistConsult`) so non-production action classes can never
  allocate specialists.
- Specialists are subordinate consultants only: single creator-facing persona remains Co-Director /
  DialoguePlan authority. `specialist_policy="OPTIONAL_SUBORDINATE"` semantics preserved.

---

## 8. Tests (frozen scope)

Unit (`tests/test_phase7_specialist_crew.py`):
- registry loads with dynamic exact count (40) — replaces `>= 28` assertion in `test_m211_production_intelligence.py`
- context allowlists enforced; forbidden context excluded
- RouteDecision-sensitive selection; workflow-sensitive selection; active-goal-sensitive selection
- zero specialists for NAVIGATE and simple READ
- one-specialist normal case; bounded multi-specialist (max 2–3); no unbounded recursion
- `may_propose_tools` / `may_execute_tools` / `approval_required` / `escalation_path` enforced
- result structure validated; malformed result rejected; timeout fallback
- conflict classification; synthesis
- project isolation; provenance preserved
- N1–N15 negative assertions

E2E: reuse mock-scripted provider; P7-E2E-1..11; no expensive generation; `[mock]` never appears in
creator mode.

Regression: prior-phase (Phases 2–6, 137/137) + existing Co-Director suite must stay green.

---

## 9. STOP conditions

1. If specialist infrastructure cannot enforce context isolation → STOP.
2. If scoped context requires copying project truth into another store → STOP.
3. If specialists require bypassing Phase 3 / proposal-approval / Verified Operator → STOP.
4. If multiple specialists must speak directly to creator → STOP.
5. If registry incompatible with frozen architecture → STOP.