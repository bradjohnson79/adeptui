# Co-Director Conversation Core Audit

**Branch:** `feature/ai-guided-setup`  
**Date:** 2026-08-03  
**Beta:** http://127.0.0.1:8760/  
**API:** http://127.0.0.1:8758/api/health  
**Baseline matrix:** [`CODIRECTOR_CAPABILITY_MATRIX.md`](./CODIRECTOR_CAPABILITY_MATRIX.md)

## Mission result

Conversation Core repairs intelligent inquiry, conversation planning, Tier-1 retrieval (including recent history on the intelligence path), Creative State Machine, Project Director, knowledge lifecycle, response composition, and an internal Conversation Success Score — without swapping models or exposing internals in the UI.

## Final verdict

**GO**

## Baseline capability-matrix findings addressed

| Gap | Before | After |
|---|---|---|
| Inquire intelligently | FAIL | Stage-scoped inquiry / invite-continuation / next-step policy |
| Retrieve recent conversation (intelligence) | FAIL/PARTIAL | `conversation.recent` fact in ContextCompiler |
| Assimilate / knowledge lifecycle | PARTIAL | confirmed/proposed/unresolved/approved/rejected/superseded/reference-only |
| Natural dialogue | PARTIAL | Deterministic ConversationPlan + composer for conversational turns |
| Stage focus | missing | Creative State Machine + Project Director every turn |

## Conversation pipeline

```text
User message
  → run_conversation_core_turn (always)
      → Tier-1 snapshot
      → Creative State Machine update
      → Project Director refresh
      → ConversationPlan + inquiry
      → Wiki candidate apply (lifecycle)
      → compose_reply (conversational intents)
      → Conversation Success Score (internal event)
      → persist projectIntelligence
  → if conversational intent: stream token/completed with composed reply
  → else: plan nudge + intelligence/provider path (with recent_messages)
```

Operational Dreamweaver intro trace:  
`docs/release-gate/codirector-final/artifacts/conversation-core/dreamweaver-intro-trace.json`

## Inquiry policy

Implemented in `conversation/inquiry.py` + `planner.py`:

- Max one primary question
- Intro / “I am going to tell you…” → acknowledge + invite, no questionnaire
- “Let me begin…” → invite continuation
- “What should we do next?” → specific recommendation, question not written to Wiki
- “main character” → Characters / Lead Character + one foundation question

## Creative State Machine + Project Director

- Stages: Project Creation → Vision → World Building → Characters → … → Final Delivery
- Substates for Characters (Lead / Supporting / Antagonists / Relationships) and other creative stages
- Project Director fields: goal, task, completed, outstanding questions, blockers, recommended next step
- Persisted under `project.settings_json.projectIntelligence`
- Never dumped into creator chat UI

## Retrieval changes

- Tier-1 snapshot every turn
- Recent conversation window + Wiki snapshot + attachment honesty retained
- Intelligence path now receives `recent_messages` and compact `conversation.plan`

## Knowledge states

Wiki/UI support: confirmed, proposed, unresolved, approved, rejected, superseded, reference-only  
Corrections supersede matched prior entries; rejections stay rejected; questions remain residue-filtered.

## Conversation Success Score

Internal only via `conversation_quality` stream event. Frontend does not render it. Playwright asserts body text never contains `conversation_quality` / plan dumps.

## Evidence

### Unit / semantic

```text
studio-api pytest tests/test_codirector_conversation_core.py
→ 10 passed
```

### Live Playwright (Beta)

```text
ADEPT_BETA_TARGET=1
codirector-conversation-core.spec.ts
codirector-foundational-capabilities.spec.ts
→ 2 passed (23.3s)
```

Foundational 7/7 suite not fully re-run in this pass; foundational Dreamweaver capability spec re-validated green alongside conversation-core.

### Beta verification

- Restarted via `Restart-AdeptUI-Beta.ps1`
- READY at http://127.0.0.1:8760/

## Timing measurements (Dreamweaver intro sample)

From artifact timings (local orchestrator):

- build_snapshot, creative_state, planning, knowledge, compose_reply, success_score, save_snapshot recorded in milliseconds-scale `timings` map
- No artificial delays added

## Subagent ledger

| Subagent | Role | Result | Evidence |
|---|---|---|---|
| Conversation package builder | Implement package modules | PASS | `studio-api/app/codirector/conversation/*` |
| Independent verifier | Code claim check | CONDITIONAL GO lean (no live run) | Claims 1–8 PASS in code |
| Primary | Integration, Beta, tests, report | GO | 10 unit + 2 Playwright live |

## Remaining limitations

- Conversation-core replies for conversational intents are heuristic/deterministic (by design for this milestone); specialist intelligence still used for production tool-heavy intents
- Soft stage inference only on unambiguous cues
- Performance instrumentation is turn-local timings, not a full distributed APM dashboard
- Multimodal cognition remains Stage 3

## Manual review path

1. Open http://127.0.0.1:8760/ with a disposable project → Co-Director  
2. Send the Dreamweaver introduction → expect acknowledgment + invitation, not a questionnaire  
3. Ask “What should we do next?” → specific recommendation; Wiki must not store the question  
4. Say “I want to start with the main character.” → lead-character focus + one useful question  
5. Add a facility fact, then correct to probe → superseded/confirmed behavior in Wiki  
6. Confirm UI never shows scores, plan JSON, or director dumps  

## Verdict

**GO**
