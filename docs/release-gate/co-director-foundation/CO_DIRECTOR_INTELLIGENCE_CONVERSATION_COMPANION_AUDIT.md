# Co-Director Intelligence, Conversation & Companion Audit

**Date:** 2026-08-05  
**Branch:** `feature/ai-guided-setup`  
**Scope:** Conversation Core / foundational AI, production intelligence, memory surfaces, UI observability, and Creative Companion / Story Guardian readiness  
**Related GO:** Part A — `GO — CO-DIRECTOR FOUNDATIONAL AI ARCHITECTURE VERIFIED`  
  (`docs/release-gate/co-director-foundation/CO_DIRECTOR_FOUNDATIONAL_AI_AUDIT.md`)  
**Dreamweaver cert project (live Beta):** `The Dreamweaver` / `97437f25-1d97-4e2a-8cf4-30449dcddbd4`  
**Selected model at Part A cert:** `qwen3.6:35b-a3b` (Ollama; selected == actual; `fallback_used=false`)

---

## Executive summary

Part A closed the collaboration **control plane**: Intent → DialoguePlan → selected LLM → grounding, with listening certified on Dreamweaver.

Co-Director is no longer a bare model-connected chat shell for discovery turns. It is a verified **attentive collaborator** for explain-before-production workflows.

It is **not yet** a verified **creative companion / story guardian / honest advisor**. That layer (Part B) is largely absent as typed, tested infrastructure — present only as light prompt constraints (e.g. “no empty praise”).

**Audit conclusion:** There is substantially more to add. The highest-value next work is Creative Companion & Advisory Intelligence on top of the Part A path — not another listening patch, and not a parallel chat stack.

---

## Audit question

> With the intelligence layer, conversation layer, and companion aspect in view — is there more we should add to improve Co-Director?

**Answer: Yes.**  
Prioritize story-loyal companion intelligence, strength memory, fair advisory resistance, and creator-authority escalation — additive to Conversation Core, not a rewrite of Part A.

---

## Architecture under review

```text
Creator UI (CoDirectorSession)
  → POST /api/codirector/chat/stream
  → service.stream_for_project
      → run_conversation_core_turn
           → foundation.intent.analyze_intent (+ evidence_spans)
           → foundation.dialogue_policy.build_dialogue_plan  ★ creator-facing authority
           → legacy planner / inquiry / director (subordinate signals)
           → persist mode / activeGoal / prefs on snapshot
      → if usesLlmPrimary:
           → LLM from DialoguePlan (selected provider)
           → grounding → one repair → traced deterministic fallback
           → SSE: tokens (content), inference_trace, conversation_state
      → else (flagged production analysis):
           → IntelligenceService specialists (feature-gated)
```

Primary code roots:

| Area | Path |
| --- | --- |
| Conversation foundation | `studio-api/app/codirector/conversation/foundation/` |
| Orchestration | `studio-api/app/codirector/conversation/orchestrate.py` |
| Gateway | `studio-api/app/codirector/service.py` |
| Legacy conversation helpers | `planner.py`, `inquiry.py`, `project_director.py`, `response_composer.py` |
| Production intelligence | `studio-api/app/codirector/intelligence/` |
| Foundation domains / ops | `studio-api/app/codirector/foundation/` |
| UI | `studio-web/src/components/CoDirector/` |
| Frozen contracts | `docs/architecture/codirector/CODIRECTOR_FOUNDATION_CONTRACTS.md` |

---

## Layer maturity matrix

| Layer | Classification | Evidence / notes |
| --- | --- | --- |
| Model runtime | **PRESENT** | Live Ollama path; inference trace; no silent model substitute on Part A cert |
| Conversational state | **PRESENT / PARTIAL** | `cognitiveMode`, `activeGoal`, `workflowHold`, prefs on snapshot; commitments thin |
| Intent understanding | **PRESENT** | Foundation intent + `evidence_spans`; covers live failure + paraphrases |
| Dialogue policy | **PRESENT** | `DialoguePlan` sole authority for listening/HOLD; title/premise quarantined |
| LLM response generation | **PRESENT** | Primary speaker when provider available; template/fallback last resort |
| Grounding gates | **PRESENT / PARTIAL** | Listening/HOLD gates strong; companion/advisory gates absent |
| Personality | **PARTIAL** | Typed default profile + prompt guidance; not project-learned |
| Working / episodic memory | **PRESENT** | Conversation events + snapshot recent messages + mode/goal |
| Semantic / wiki memory | **PRESENT / PARTIAL** | Wiki candidates + learning copy; provenance hooks incomplete for principles |
| Preference memory | **PARTIAL** | Snapshot prefs for explain-before-production; foundation collaboration prefs are process-local in-memory |
| Context assembly | **PARTIAL** | Goal-ranked listening assembler; no advisory/strength-ranked assembler |
| Tool routing | **PRESENT** | Proposal/tool loop; subordinate to `tool_policy` on listening turns |
| Production intelligence (specialists) | **PRESENT (GATED)** | M2.4 stack exists; `codirector_intelligence_v2` defaults off |
| Creative companion / support | **ABSENT** | No `CreatorCompanionState` / `CreativeSupportAssessment` |
| Writer’s-block intelligence | **ABSENT** | No block taxonomy / intervention policy |
| Story strength / principles | **ABSENT** | No gradual profile with provenance |
| Deviation / advisory authority | **ABSENT** | No `StoryDeviationAssessment` / `CreativeAdvisoryPlan` escalation |
| Anti-sycophancy enforcement | **PARTIAL** | Prompt prohibitions only; no hard gates |
| UI observability | **PRESENT / PARTIAL** | Activity mode/goal/tools/memory; Wiki learning; Not Checked clarified; no advisory Change Review |
| Companion live certification | **ABSENT** | Part B cert not run; foundation GO does not imply companion GO |

---

## What is strong (keep)

### 1. Single authoritative conversation path
IntentAnalysis → DialoguePlan → ResponseGeneration (LLM) → Grounding is the creator-facing authority. Legacy modules are subordinate signals, not competing controllers.

### 2. Listening failure class closed
The Dreamweaver phrase (“I will tell you… before we move into production”) and paraphrase set resolve to LISTENING / HOLD without title/premise intake. Certified with the real selected model.

### 3. Honest generation policy
Deterministic templates are last resort only (generation fail, grounding fail after one repair, provider unavailable). Trace records `fallback_used` and reason.

### 4. Inspectability started
Activity surfaces mode/goal; SSE emits `inference_trace` and `conversation_state`; Wiki empty state speaks “learning,” not false canon; “Not Checked” means Production Assurance not run.

### 5. Adjacent production machinery is rich
Specialists, bible/proposals, plans, tools, prompt intelligence, and adaptive learning exist nearby. The gap is fusion into companion cognition — not a blank slate.

---

## Gaps and risks

### G1 — Companion intelligence is prompt-thin
Feedback policy asks for honest critique and forbids empty praise, but there is no structured post-intent assessment of:
- encourage vs critique vs ideation vs execution help
- frustration / stuckness vs foundational reconsider
- technical/production problems misread as story problems

**Risk:** Supportive tone without project-specific judgment.

### G2 — No story-strength memory
Co-Director retains facts and holds mode, but does not maintain emotional core, theme promises, tone laws, non-negotiables, or confirmed-vs-emerging principles with provenance.

**Risk:** Long-term loyalty is to the transcript, not to what makes the story work.

### G3 — No fair resistance / creator-authority protocol
Missing escalation:
1. Honest advice  
2. Consequence confirmation for major/foundational insistence  
3. Committed collaboration after confirm (no re-litigation, clean supersede)

**Risk:** Either limp agreement or unmanaged argumentativeness.

### G4 — Dual intent / dual brains
Foundation conversation intent and Intelligence v2 intent remain separate. When production intelligence is enabled, DialoguePlan authority can be bypassed by a parallel specialist path.

**Risk:** Inconsistent creator experience across “chat” vs “analyze” turns.

### G5 — Memory classes uneven
| Class | State |
| --- | --- |
| Episodic conversation | Strong |
| Working goal / mode | Present |
| Wiki / bible artifacts | Strong infrastructure, weak principle semantics |
| Durable creative preferences | Partial / split stores |
| Strength records / exploratory variants | Absent |

### G6 — Context assembly is listening-shaped
`assemble_listening_context` ranks title, goal, hold, facts, recent turns. Advisory turns also need latest proposal, relevant principles, affected canon, gains/losses, and production constraints — without full-bible dumps.

### G7 — Personality is static
Default numeric profile constrains expression. It does not adapt by project, mode, or creator preference, and must not drift into theatrical “companion” performance.

---

## Improvement backlog (prioritized)

### Must-have — Part B spine (companion GO path)

1. **CreativeSupportAssessment** after IntentAnalysis — evidence spans + support strategy; distinguish encourage / critique / ideation / execution / frustration / foundational reconsider / technical-misread-as-story.
2. **StoryStrengthProfile / StoryPrinciple** — gradual build with provenance; confirmed vs emerging; user approve / reject / reclassify.
3. **CreativeAdvisoryPlan** extending DialoguePlan — advise strength, acknowledge logic, gains/losses, alternatives, confirmation, exploratory preserve, accept-after-confirm.
4. **Extended grounding gates** — e.g. no generic praise, no automatic agreement, creator authority respected, exploration not silently canonized, no repeated argument after confirmation.
5. **Live companion cert** on Dreamweaver with real selected model — stages covering critique, block, deviation, insistence, celebration, isolation, resume.

### High-value — harden Part A while building Part B

6. Formally subordinate Intelligence v2 routing to DialoguePlan (or merge intent into one analyzer with evidence).
7. Persist creator preferences through the same project snapshot/settings path used by Conversation Core.
8. Mode-specific context assemblers: listening / critique / planning / execution / advisory.
9. Stronger multi-turn “confirmed vs uncertain” summarization with wiki provenance on writes.
10. Light personality adaptation by mode (directness/challenge up for critique; warmth up for listening) without theatricality.

### Nice-to-have — after companion GO

11. Compact Change Review UI only for major exploratory / foundational changes.
12. Writer’s-block intervention map (one useful next step; no idea dumps).
13. Strength recall when unblocking (“this already works because…” + source ids).
14. Deeper specialist fusion into companion turns without turning chat into an ops console.

---

## Explicit non-goals (for this improvement track)

- Replacing Conversation Core with a parallel companion chat stack
- Hardcoding The Dreamweaver lore or Dreamweaver-only advisory shortcuts
- Therapeutic / clinical / dependency-building companion language
- Enabling Intelligence v2 by default without DialoguePlan subordination
- Claiming All-GO Final Systems closed from companion work alone
- Passing companion cert with template-primary replies when the model is available

---

## Relationship to Part A / Part B gates

| Gate | Status | Meaning |
| --- | --- | --- |
| Part A — Foundational AI | **GO** | Listening, intent evidence, LLM primary, grounding, reload retention verified |
| Part B — Creative Companion & Advisory | **Not started / NO-GO until certified** | Story guardian + companion intelligence not yet typed, wired, or live-certified |

Part A GO must not be read as companion completeness. Until Part B earns its own live GO, Co-Director remains incomplete as Adept UI’s creative companion/advisor — even though foundational collaboration infrastructure is verified.

Target companion verdict (when earned):

```text
GO — CO-DIRECTOR CREATIVE COMPANION AND ADVISORY INTELLIGENCE VERIFIED
```

Until then the honest posture is:

```text
NO-GO — CO-DIRECTOR LACKS VERIFIED CREATIVE COMPANION AND ADVISORY INTELLIGENCE
```

---

## Recommended sequencing

1. Keep Part A path frozen as the only conversation authority.
2. Implement Part B additively under Conversation Core (`conversation/companion/` or equivalent schemas).
3. Wire support → (block/deviation as needed) → DialoguePlan + CreativeAdvisoryPlan → LLM → extended grounding.
4. Persist strengths/principles with provenance; never silent canon promotion.
5. Certify live on Dreamweaver with the real selected model.
6. Only then claim companion readiness for human Beta creative collaboration.

---

## Manual review snapshot (current Beta)

- UI: `http://127.0.0.1:8760/`
- API: `http://127.0.0.1:8758/`
- Open Co-Director on **The Dreamweaver**
- Listening path should remain attentive (Part A)
- Ask for honest critique / “I’m stuck” / major story change — expect **generic-capable model help**, not yet **verified companion/guardian behavior**

---

## Verdict of this audit

**Finding:** More should be added — specifically the Creative Companion, Story Guardian, and Advisory Intelligence layer.

**Co-Director today:** Verified foundational collaborator for listening/discovery.  
**Co-Director still missing:** Project-specific strength loyalty, structured support assessment, fair advisory resistance, exploratory-vs-confirmed canon discipline, and companion live certification.

**Next decisive move:** Implement and certify Part B on the existing Intent → DialoguePlan → LLM → Grounding path.
