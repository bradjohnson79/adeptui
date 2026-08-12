# CO-DIRECTOR 2.0 — PHASE 3 ROUTER IMPLEMENTATION CONTRACT (FREEZE)

| Field | Value |
|---|---|
| Phase | 3 (implementation) |
| Date | 2026-08-08 |
| Status | **FROZEN** — governing contract for Phase 3 source edits. No Phase 3 source edit precedes this document. |
| Supersedes | Nothing. Phase 1 audit pack and Phase 2 contracts remain authoritative for their scope. |
| Governing law | Adept UI Build Memory Layer; Phase 1 audits; Phase 2 contracts; Taxonomy Authority Law (this document §1). |
| Phase 2 dependency | `GO — CO-DIRECTOR 2.0 PHASE 2 VERIFIED OPERATOR + PRODUCTION STATE CERTIFIED` complete. |

---

## 1. TAXONOMY AUTHORITY LAW (resolves "taxonomy #3" verifier ambiguity)

Co-Director has two distinct semantic layers with **different authoritative responsibilities**. This architecture is NOT three competing taxonomies because the two layers own different concerns.

| Layer | Owns | Does NOT Own |
|---|---|---|
| **Conversation IntentAnalysis** (`conversation/foundation/intent.py:90`) | conversational posture, question budget, user-goal summary, evidence spans, memory/tool advisories | execution routing, lane selection, target resolution |
| **Canonical RouteDecision** (NEW — Phase 3) | operational action classification, execution lane, target, destructive status, ambiguity, clarification | conversational composition, posture, question budget |

**Legacy Taxonomy B** (`intelligence/intent.py` `IntentKind`) is **deprecated**. It survives only behind an explicit compatibility adapter until its two consumers (`service.py:1729` boolean gate, `intelligence/service.py:139` dormant specialist path) are migrated. The adapter maps canonical RouteDecision values → legacy IntentKind where temporarily needed.

This is NOT intent taxonomy #3 because:
- IntentAnalysis and RouteDecision have non-overlapping responsibilities
- Legacy IntentKind is deprecated, not competing
- No new intent enum is created that duplicates either legacy taxonomy

---

## 2. EXISTING TAXONOMIES (verified against live source)

### 2A. Taxonomy A — `IntentType` (conversation/foundation/schemas.py:12-31)

**Source:** `conversation/foundation/intent.py:90` `analyze_intent(user_message) -> IntentAnalysis`
**19 members, LIVE — feeds DialoguePlan on every turn.**

| Member | Emitted by classifier? | Canonical RouteDecision mapping |
|---|---|---|
| `INFORM` | YES (explain questions 0.82, long text 0.7) | DISCUSS |
| `EXPLAIN_PROJECT` | YES (explain patterns 0.7-0.95) | DISCUSS |
| `BRAINSTORM` | No — dead enum member | DISCUSS |
| `REQUEST_FEEDBACK` | YES (be honest/critique 0.8) | DISCUSS |
| `REQUEST_BRIEF` | No — dead enum member | DISCUSS |
| `REQUEST_PLAN` | YES (next steps 0.85) | PROPOSE_CREATIVE_CHANGE |
| `REQUEST_ACTION` | YES (draft plan 0.8, imperative action 0.78) | PROPOSE_CREATIVE_CHANGE or EXECUTE_PRODUCTION (by target) |
| `REQUEST_GENERATION` | No — dead enum member | PROPOSE_CREATIVE_CHANGE |
| `REQUEST_EDIT` | No — dead enum member | PROPOSE_CREATIVE_CHANGE |
| `REQUEST_RESEARCH` | No — dead enum member | DISCUSS |
| `REQUEST_REVIEW` | No — dead enum member | READ_INSPECT |
| `CORRECT_ASSISTANT` | YES (correction: 0.9) | DISCUSS |
| `EXPRESS_DISSATISFACTION` | YES (that was wrong 0.85) | DISCUSS |
| `SEEK_REASSURANCE` | YES (sound good? 0.7-0.95 via explain chain) | DISCUSS |
| `SET_PREFERENCE` | YES (workflow hold chain) | DISCUSS |
| **`APPROVE`** | Declared — **never emitted** | APPROVE (router must wire) |
| **`REJECT`** | Declared — **never emitted** | REJECT (router must wire) |
| `PAUSE_ACTION` | YES (workflow hold 0.8) | DISCUSS |
| `CONTINUE_PREVIOUS_WORK` | No — dead enum member | DISCUSS |
| `UNKNOWN` | YES (0.4 fallback) | UNKNOWN / CLARIFY |

**Consumers:** `conversation/orchestrate.py:355` (live), `prompt_intelligence/scoring_v2.py:31`, `prompt_intelligence/pipeline.py:149,251`. The `prompt_intelligence` package has its own separate `analyze_intent` — leave unchanged.

**Tests:** None found in `studio-api/tests/`.

### 2B. Taxonomy B — `IntentKind` (intelligence/schemas.py:22-47)

**Source:** `intelligence/intent.py:83` `classify_intent(user_message) -> IntentClassification`
**24 literals declared, ~14 reachable from regex. Much of it DORMANT behind `codirector_intelligence_v2` flag (OFF by default).**

| Member | Reachable? | Canonical RouteDecision mapping |
|---|---|---|
| `answer_question` | YES (question heuristic) | READ_INSPECT or DISCUSS |
| `develop_concept` | YES (concept/logline/premise) | PROPOSE_CREATIVE_CHANGE |
| `write_story` | YES (outline/story structure) | PROPOSE_CREATIVE_CHANGE |
| `revise_story` | **Unreachable** (no regex) | PROPOSE_CREATIVE_CHANGE |
| `create_character` | YES (character/build character) | PROPOSE_CREATIVE_CHANGE |
| `revise_character` | **Unreachable** | PROPOSE_CREATIVE_CHANGE |
| `design_location` | YES (design a location) | PROPOSE_CREATIVE_CHANGE |
| `plan_scene` | YES (plan/blocking/coverage/cinematic) | PROPOSE_CREATIVE_CHANGE |
| `write_scene` | YES (write/draft ... scene) | PROPOSE_CREATIVE_CHANGE |
| `revise_dialogue` | YES (revise/make dialogue) | PROPOSE_CREATIVE_CHANGE |
| `create_shot_list` | YES (shot list/create shots) | EXECUTE_PRODUCTION or PROPOSE_CREATIVE_CHANGE (stage-dependent) |
| `create_storyboard` | YES (storyboard/board shot) | PROPOSE_CREATIVE_CHANGE |
| `prepare_image_generation` | YES (prepare/generate image) | PROPOSE_CREATIVE_CHANGE |
| `prepare_video_generation` | YES (prepare/generate video) | PROPOSE_CREATIVE_CHANGE |
| `review_asset` | YES (review/check asset/render) | READ_INSPECT |
| `review_continuity` | **Unreachable** | READ_INSPECT |
| `assemble_sequence` | YES (assemble/sequence/edit) | EXECUTE_PRODUCTION |
| `plan_audio` | YES (sound design/sfx/music) | PROPOSE_CREATIVE_CHANGE |
| `plan_vfx` | **Unreachable** | PROPOSE_CREATIVE_CHANGE |
| `manage_production` | **Unreachable** | DISCUSS |
| `update_production_bible` | YES (change/update bible/canon) | MODIFY_KNOWLEDGE |
| `execute_project_action` | **Unreachable** | EXECUTE_PRODUCTION |
| `production_intelligence` | YES (production intelligence/orchestrate) | PROPOSE_CREATIVE_CHANGE |
| `unknown` | YES (fallback) | UNKNOWN / CLARIFY |

**Consumers:** `codirector/service.py:1729` (`_intelligence_enabled_for_turn` — reads only `isSimpleQuestion` + `primaryIntent`, uses as boolean gate), `intelligence/service.py:139` (specialist path behind feature flag, off-by-default), `evaluation/runner.py:54` (test harness).

**Route_stage consumer (stage_router.py:35-36):** single consumer `intelligence/service.py:140` — dormant. `route_stage` is a leaf function with zero production impact. **Retire, not replace.**

### 2C. Translation map — legacy → canonical (compatibility adapter only)

For the dormant specialist path that still keys on `IntentKind`:
```
answer_question → READ_INSPECT
develop_concept → PROPOSE_CREATIVE_CHANGE
write_story → PROPOSE_CREATIVE_CHANGE
create_character → PROPOSE_CREATIVE_CHANGE
design_location → PROPOSE_CREATIVE_CHANGE
plan_scene → PROPOSE_CREATIVE_CHANGE
write_scene → PROPOSE_CREATIVE_CHANGE
revise_dialogue → PROPOSE_CREATIVE_CHANGE
create_shot_list → EXECUTE_PRODUCTION or PROPOSE_CREATIVE_CHANGE
create_storyboard → PROPOSE_CREATIVE_CHANGE
prepare_image_generation → PROPOSE_CREATIVE_CHANGE
prepare_video_generation → PROPOSE_CREATIVE_CHANGE
review_asset → READ_INSPECT
assemble_sequence → EXECUTE_PRODUCTION
plan_audio → PROPOSE_CREATIVE_CHANGE
update_production_bible → MODIFY_KNOWLEDGE
production_intelligence → PROPOSE_CREATIVE_CHANGE
unknown → UNKNOWN
```

Reverse map (canonical → legacy, for adapter):
```
DISCUSS → "unknown" (the dormant specialist path gets the generic fallback trio)
NAVIGATE → "unknown"
READ_INSPECT → "review_asset" (closest match)
MODIFY_KNOWLEDGE → "update_production_bible"
PROPOSE_CREATIVE_CHANGE → "plan_scene" (generic creative change)
EXECUTE_PRODUCTION → "execute_project_action"
APPROVE → "unknown"
REJECT → "unknown"
CLARIFY → "unknown"
AMBIGUOUS → "unknown"
UNKNOWN → "unknown"
```

---

## 3. CANONICAL ROUTEDECISION (frozen)

```python
class RouteActionClass(str, Enum):
    DISCUSS = "DISCUSS"                 # conversation, feedback, brainstorming — zero writes
    NAVIGATE = "NAVIGATE"               # open/show/switch to workspace — Verified Operator lane
    READ_INSPECT = "READ_INSPECT"       # query data/list/inspect — zero writes
    MODIFY_KNOWLEDGE = "MODIFY_KNOWLEDGE"  # wiki/bible edit — proposal/approval
    PROPOSE_CREATIVE_CHANGE = "PROPOSE_CREATIVE_CHANGE"  # creative mutation — proposal/approval
    EXECUTE_PRODUCTION = "EXECUTE_PRODUCTION"    # destructive/execution — proposal/approval + safety
    APPROVE = "APPROVE"                 # accept proposal — ProposalService.approve
    REJECT = "REJECT"                   # reject proposal — ProposalService.reject
    CLARIFY = "CLARIFY"                 # specific ambiguity question — zero writes
    AMBIGUOUS = "AMBIGUOUS"             # cannot resolve — zero writes
    UNKNOWN = "UNKNOWN"                 # fallback — zero writes


class RouteDecision(BaseModel):
    actionClass: RouteActionClass
    target: Optional[str] = None        # specific workspace, tool family, entity
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    ambiguity: Optional[list[str]] = None  # ambiguous choices if actionClass=CLARIFY
    clarificationOptions: Optional[list[str]] = None
    executionLane: Optional[str] = None # "operator", "read", "proposal", "approve", "reject", "discuss", "unavailable"
    destructive: bool = False
    capabilityAvailable: bool = True    # False when understood but capability absent
    supportedAlternative: Optional[str] = None  # e.g. "SceneCraft is not installed. Try Script Writer?"
    evidence: list[str] = Field(default_factory=list)  # operational/context evidence only, no hidden reasoning
    classifierSource: Literal["deterministic", "semantic", "contextual"] = "deterministic"
    targetWorkspace: Optional[str] = None  # resolved workspace id for NAVIGATE
    targetToolIds: Optional[list[str]] = None  # narrowed tool family for READ_INSPECT
    writeAllowed: bool = False          # MUST be False for DISCUSS, READ, CLARIFY, AMBIGUOUS, UNKNOWN
```

---

## 4. CONFIDENCE ZONES + ROUTER CONTROL FLOW

Three confidence zones, not one threshold:

| Range | Behavior | Notes |
|---|---|---|
| ≥ 0.85 | Deterministic → route directly | "Open Script Writer" → NAVIGATE, "What scenes do we have?" → READ_INSPECT |
| 0.70–0.85 | Deterministic match. If action is **consequential** (EXECUTE_PRODUCTION, destructive NAVIGATE, MODIFY_KNOWLEDGE) → run semantic validation. If action is **non-consequential** (DISCUSS, benign READ) → route directly. | "Let's work on the script" may be DISCUSS or NAVIGATE — 0.70–0.85 needs semantic to disambiguate. "How does batch generation work?" → DISCUSS at any confidence. |
| < 0.70 | Run semantic classifier. If classifier confidence ≥ 0.70 for non-consequential, route. If ≥ 0.85 for consequential, route. Else → CLARIFY with specific options. | "Get rid of that" with no explicit target → CLARIFY even if classifier guesses high — consequential action requires explicit target. |
| Malformed/error | → CLARIFY with `actionClass=AMBIGUOUS` or `UNKNOWN`, `writeAllowed=False` | Never execute from malformed output. |

**Consequential actions require higher confidence:** `EXECUTE_PRODUCTION` requires minimum 0.85 confidence. `NAVIGATE` to destructive requires 0.85. `DISCUSS` can route at 0.70. The router must be permissive with discussion (false-positive is just a response) but conservative with mutations (false-positive mutates creator project).

**Flow:**
```
message + context → deterministic classifier
    ↓
deterministic produces RouteDecision with confidence
    ↓
confidence ≥ 0.85? → route directly
confidence 0.70–0.85 + consequential? → semantic validation
confidence 0.70–0.85 + non-consequential? → route directly
confidence < 0.70? → semantic classifier
classifier still < threshold for action? → CLARIFY
malformed/error? → CLARIFY/UNKNOWN safe
```

---

## 5. ROUTER INPUTS (frozen)

| Input | Source | Required? |
|---|---|---|
| `message` | User message text | YES |
| `derivedStage` | Phase 2 `get_authoritative_stage(project_id)` | YES |
| `stageEvidence` | Phase 2 `collect_stage_evidence(project_id)` | For stage-sensitive routing |
| `conversationFocus` | Phase 1 `IntentAnalysis.user_goal_summary` + `active_goal` | YES (from orchestrate.py) |
| `activeWorkspace` | Phase 2 `session_context.build_session_context(...).activeWorkspace` | YES |
| `recentVerifiedOperatorState` | Phase 2 `operator.service.get_operator_record(...)` | For NAVIGATE disambiguation / recent-context |
| `availableCapabilities` | From `tools/exposure` or capabilities registry | YES — must not route to unavailable capabilities |
| `targetWorkspaces` | Frozen list of valid workspace targets (from `core/workspaces.ts`) | For NAVIGATE validation |
| `activeProposalIds` | From current pending proposals | For APPROVE/REJECT routing |

---

## 6. EXECUTION LANE CONTRACTS

### 6.1 NAVIGATE → Verified Operator
RouteDecision with `actionClass=NAVIGATE` → Verified Operator lane (Phase 2):
- RouteDecision is consumed BEFORE `_run_read_tool` or alongside it
- Operator block injected into the result (reuse `service.py:792-801`)
- Pending UX → ack → success/failure response
- NO direct frontend navigation bypass
- Target validated against available workspace list

### 6.2 READ_INSPECT → Existing audit read path
RouteDecision with `actionClass=READ_INSPECT`:
- Router narrows `targetToolIds` (candidate tool set, e.g. `{scene.get, scene.list, scene.list_characters}`)
- Passes through EXISTING capability-scoped tool selection (`tools/exposure.py`)
- Passes through EXISTING audited read execution (`_run_read_tool` at `service.py:722`)
- NO new router-specific direct read executor
- Result: authoritative read result, same as today

### 6.3 MODIFY_KNOWLEDGE / PROPOSE_CREATIVE_CHANGE / EXECUTE_PRODUCTION → Proposal/Approval
RouteDecision → existing proposal/approval infrastructure:
- Router identifies the action class and target
- MAY pre-populate tool family or target registry tool ids
- Existing `ProposalService.propose` → approve → execute chain (proposals.py)
- ALL mutations remain approval-gated as today
- `destructive=true` routes through existing destructive safety gates

### 6.4 APPROVE / REJECT → Existing ProposalService entry points
RouteDecision with `actionClass=APPROVE` or `REJECT`:
- Router identifies the intent from message ("accept this", "keep mine")
- Routes through existing CERTIFIED entry points: `ProposalService.approve` / `ProposalService.reject`
- Does NOT call lower-level `bible/operations.py` or `tools/execution.py` directly
- Requires an active pending proposal (if none → CLARIFY)

### 6.5 DISCUSS / CLARIFY / AMBIGUOUS / UNKNOWN → Conversation reply
RouteDecision with these action classes:
- `writeAllowed=False` (asserted in tests)
- No tool execution, no operator request, no proposal
- Conversation core (`orchestrate.py`) handles the response as today
- CLARIFY carries `ambiguity` / `clarificationOptions` for specific disambiguation

---

## 7. STAGE-SENSITIVE ROUTING RULES (frozen)

### 7.1 Same message, different stage → different RouteDecision

**Case: "Create shots"**

| derivedStage | Expected RouteDecision | Notes |
|---|---|---|
| SCRIPT | PROPOSE_CREATIVE_CHANGE, target=shot_planning, writeAllowed=false | Propose transition, discuss shot planning. Zero shot creation. |
| IMAGE_PLANNING | EXECUTE_PRODUCTION, target=create_shots, writeAllowed=true | Route to existing shot-planning execution/proposal lane. |
| TIMELINE_ASSEMBLY | CLARIFY/AMBIGUOUS | Ambiguous — clarify whether user wants more shots or to edit existing timeline. |

### 7.2 conversationFocus overrides stage default for target

Section 3C frame:

> derivedStage = image-planning, conversationFocus = script dialogue revision
> "Let's change the final line."
> → DISCUSS or MODIFY_KNOWLEDGE against script/dialogue context, NOT image-planning operation

`derivedStage` remains authoritative for stage. `conversationFocus` wins for routing target. The stage is not silently rewritten — just the action target changes.

### 7.3 Capability-unavailable rule

Understood request + unavailable capability:
- actionClass = correctly identified (NAVIGATE, READ_INSPECT, etc.)
- capabilityAvailable = false
- executionLane = "unavailable"
- supportedAlternative = human-readable suggestion
- DO NOT overload UNKNOWN

---

## 8. DETERMINISTIC ROUTER RULES (frozen)

### 8.1 NAVIGATE patterns (new — currently absent as intent)
- `(?:open|show|switch to|take me to|go to|bring up|launch|load)\b.*\b(workspace|editor|studio|panel|view|mode)` → NAVIGATE
- Specific workspace targets from resolved list: `script writer`, `timeline`, `audio studio`, `voice studio`, `mag editor`, `continuity`, `bible`, `posecraft`, `runtime manager`, `references`, `characters`, `casting`, etc.
- MUST validate target against available workspaces list
- Negation detection: `(?:don't|do not|won't|not) .*(?:open|show|switch|go)` → NOT NAVIGATE (route to DISCUSS)

### 8.2 READ_INSPECT patterns (refactored from existing)
- `(?:what|show me|inspect|list|get|find|search|what's in|how many)\b.*\b(scene|asset|character|batch|plan|clip|track|shot|version|draft)` → READ_INSPECT
- Question-word starts without action imperative → READ_INSPECT (if not explanation-seeking)

### 8.3 DISCUSS patterns (refactored from taxonomy A)
- `(?:what do you think|how do you feel|let's talk about|let's discuss|let's work on|help me think through|can you help me)\b` → DISCUSS
- `(?:be honest|critique|does this work|what's your take)\b` → DISCUSS
- `(?:correction:|actually|instead|no, that's wrong)\b` → DISCUSS (CORRECT_ASSISTANT posture)
- `(?:I want to tell you|let me explain|before we start|walk you through)\b` → DISCUSS (EXPLAIN posture)
- Question structure + `(?:about|think|feel|opinion|suggestion|recommend)` → DISCUSS

### 8.4 APPROVE/REJECT patterns (new — currently dead enum members)
- `(?:approve|accept|use this|looks good|confirmed|that works|go ahead)\b` with pending proposal → APPROVE
- `(?:reject|decline|don't use|keep mine|keep what I|revert|undo proposal|discard)\b` with pending proposal → REJECT
- Require active proposal context (list of pending proposal IDs). If no pending proposal → CLARIFY.

### 8.5 MODIFY_KNOWLEDGE patterns (refactored from taxonomy B)
- `(?:add|update|change|put).*\b(wiki|summary|bible|canon|knowledge|entry|logline|synopsis|description)` → MODIFY_KNOWLEDGE
- `(?:remove|delete).*\b(wiki|entry|knowledge|fact|canon)` → MODIFY_KNOWLEDGE

### 8.6 EXECUTE_PRODUCTION patterns (refactored from existing)
- `(?:delete|remove|destroy|erase|clear|trash)\b.*\b(batch|scene|clip|sequence|shot|track|asset|version)` → EXECUTE_PRODUCTION, destructive=true
- `(?:generate|render|build|execute|run|queue)\b.*\b(scene|shot|clip|batch|plan|sequence)` → EXECUTE_PRODUCTION (stage-dependent)
- `(?:create shots|shot list|film|record)\b` → stage-dependent (see §7)

### 8.7 Negation detection (new — mandatory)
- `(?:don't|do not|won't|not|never|no|not yet)\b.*\b(?:open|show|switch|launch|navigate|make|create|delete|remove)` → strip the negated pattern, do NOT route to the negated action class
- "I don't want to open Timeline yet" → MUST NOT trigger NAVIGATE
- Negated patterns return to the general classifier (typically DISCUSS or UNKNOWN)

### 8.8 False-positive guard (new)
- Question structure + `(?:use|using|about).*(workspace|editor|tool|feature)` → DISCUSS, not the action implied by the tool name
- "What do you think about using Script Writer for this?" → MUST NOT trigger NAVIGATE
- "Can you open Script Writer?" (question structure asking for action) → CAN trigger NAVIGATE (the question is a request, not discussion)

---

## 9. SEMANTIC / MODEL FALLBACK CONTRACT

**Input:**
```json
{
  "message": "user text",
  "derivedStage": "SCRIPT",
  "conversationFocus": "script dialogue revision",
  "activeWorkspace": "scriptwriter",
  "recentActions": ["script.inspect", "audio.open_studio"],
  "availableActionClasses": ["DISCUSS", "NAVIGATE", "READ_INSPECT", ...],
  "availableTargets": ["script_writer", "timeline", "audio_studio", ...],
  "currentStageAuthoritative": "SCRIPT",
  "stageEvidence": [...]
}
```

**Expected output (structured, validated):**
```json
{
  "actionClass": "DISCUSS",
  "target": "script",
  "confidence": 0.88,
  "ambiguity": null,
  "clarificationOptions": null,
  "destructive": false,
  "writeAllowed": false
}
```

**Validation:**
- actionClass ∈ RouteActionClass enum
- confidence ∈ [0.0, 1.0]
- If destructive=true, must have confident target
- If actionClass=APPROVE/REJECT, must have target proposal id
- If actionClass=NAVIGATE, target must be in available workspaces (or capabilityAvailable=false)
- Malformed JSON → safe CLARIFY with `actionClass=AMBIGUOUS, writeAllowed=False`

**Failure behavior:**
- Provider timeout → CLARIFY/UNKNOWN safe fallback
- Malformed output → CLARIFY/UNKNOWN safe fallback
- Valid but confidence < threshold for action → CLARIFY with specific options
- NO execution from fallback path

---

## 10. ZERO-WRITE RULES (tested explicitly)

| Action Class | writeAllowed | Assertions |
|---|---|---|
| DISCUSS | FALSE | No write tools, no proposals, no operator requests, no snapshot mutations |
| NAVIGATE | FALSE | No project mutations; operator lane registers request but does not mutate project state |
| READ_INSPECT | FALSE | No write tools, no proposals, no project mutations |
| CLARIFY | FALSE | No write tools, no proposals |
| AMBIGUOUS | FALSE | No write tools, no proposals |
| UNKNOWN | FALSE | No write tools, no proposals |
| APPROVE | TRUE | Only ProposalService.approve; limited to that |
| REJECT | TRUE | Only ProposalService.reject; limited to that |
| MODIFY_KNOWLEDGE | TRUE | Only via proposal/approval lane |
| PROPOSE_CREATIVE_CHANGE | TRUE | Only via proposal/approval lane |
| EXECUTE_PRODUCTION | TRUE | Only via proposal/approval lane + destructive safety |

---

## 11. OBSERVABILITY CONTRACT

Per route decision, emit a diagnostic event (can be appended as an event or logged):

```json
{
  "type": "route_decision",
  "requestId": "...",
  "projectId": "...",
  "actionClass": "NAVIGATE",
  "target": "script_writer",
  "confidence": 0.92,
  "classifierSource": "deterministic",
  "derivedStage": "SCRIPT",
  "activeWorkspace": "chat",
  "ambiguity": false,
  "executionLane": "operator",
  "writeAllowed": false,
  "capabilityAvailable": true,
  "evidence": ["matched pattern: open <workspace>"]
}
```

Do NOT log hidden model reasoning, raw LLM output, or creator message content beyond evidence spans.

---

## 12. LEGACY MIGRATION

- Taxonomy B's `classify_intent` is adapted/replaced by the new router for `_intelligence_enabled_for_turn` boolean gate (service.py:1729). The gate checks: is route decision DISCUSS/UNKNOWN/CLARIFY? → skip intensive intelligence.
- Taxonomy B's `route_stage` (stage_router.py:35-36) is retired — Phase 2's `derivedStage` replaces it.
- Taxonomy B's `IntentKind` → compatibility adapter map (§2C reverse map) for the dormant `stream_intelligence` path (behind feature flag, off by default). The adapter is removed when the specialist stack is rewired (Phase 7).
- Taxonomy A's `analyze_intent` is KEPT as the conversation-intent layer. The new router runs ALONGSIDE it, before or at the same insertion point in `orchestrate.py:355`.

**Authority direction:** Canonical RouteDecision → legacy adapter. NOT the reverse.

---

## 13. ROUTER CORPUS (minimum cases)

`tests/fixtures/codirector2_route_cases.json` — machine-readable. Each case:

```json
{
  "id": "case-1",
  "message": "Open Script Writer.",
  "stage": "SCRIPT",
  "workspace": "chat",
  "focus": "script development",
  "expectedActionClass": "NAVIGATE",
  "expectedTarget": "script_writer",
  "expectedWriteAllowed": false,
  "expectedOperatorRequested": true,
  "negation": false
}
```

Minimum 16 cases: Cases 1–12 from the Phase 3 prompt + Case 13 (false-positive "using X does not NAVIGATE"), Case 14 (negation), Case 15 (unavailable capability), Case 16 (conversationFocus overrides stage default). Each includes negative assertions.

---

## 14. COMMITTED DEVIATIONS FROM PHASE 2 CONTRACT

| # | Phase 2 clause | Why kept/deviated |
|---|---|---|
| 1 | `_voice_handoff` workspaceUrl strips — deferred | Unchanged in Phase 3 — Phase 5 consolidation |
| 2 | Audio `_start_async_generate` uiAction kept as post-mutation handoff | Unchanged — router notes this as an execution-lane for EXECUTE_PRODUCTION handoffs |
| 3 | timeline.focus_ui ack target field | Unchanged — router may normalize it in future |

No new deviations introduced. Phase 2 contracts remain authoritative.

---

## 15. SUBAGENT SEQUENCE

1. **Agent A** (this contract + taxonomy mapping) — FREEZE RouteDecision schema, map all taxonomy values
2. **Agents B + C + D** (parallel) — deterministic router, semantic fallback, context integration — share frozen RouteDecision
3. **Parent integrates** B/C/D output — resolve interface mismatches
4. **Agent E** — lane integration (only after router contracts are stable)
5. **Agent F** — corpus + adversarial + negative tests
6. **Agent G** — full regression
7. **Agent H** — independent verifier + certification report

---

*This contract is frozen as of 2026-08-08. No Phase 3 source edit precedes this document. Any deviation required by live source must amend this contract before the edit (Law 30).*
