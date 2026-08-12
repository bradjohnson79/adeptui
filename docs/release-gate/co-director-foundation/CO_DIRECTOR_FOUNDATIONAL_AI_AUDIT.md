# Co-Director Foundational AI Architecture Audit

**Status:** COMPLETE (Part A)  
**Date:** 2026-08-05  
**Branch:** `feature/ai-guided-setup`  
**Starting SHA (pre-work tip):** `fa09c99d6395c29461cdec4555055faad116c435`  
**Dreamweaver cert project:** `The Dreamweaver` / `97437f25-1d97-4e2a-8cf4-30449dcddbd4`  
**Selected model:** `qwen3.6:35b-a3b` (Ollama) — selected == actual; `fallback_used=false`

---

## Verdict

```text
GO — CO-DIRECTOR FOUNDATIONAL AI ARCHITECTURE VERIFIED
```

---

## Call graph (authoritative)

```text
CoDirectorSession.performSend
  → POST /api/codirector/chat/stream
  → codirector.service.stream_for_project
      → _prepare_chat_request (system + context)
      → conversation.orchestrate.run_conversation_core_turn
           → foundation.intent.analyze_intent (evidence_spans)
           → foundation.dialogue_policy.build_dialogue_plan  ★ sole creator-facing authority
           → legacy planner/inquiry/director as subordinate signals
           → persist ConversationState (mode, activeGoal, prefs)
      → if usesLlmPrimary:
           → LLM generate from DialoguePlan (selected provider)
           → grounding check → one repair → deterministic fallback last resort
           → emit SSE (token content, completed, inference_trace, conversation_state)
```

---

## Layer classifications

| Layer | Starting | After Part A |
| --- | --- | --- |
| Model runtime | PARTIAL | PRESENT AND VERIFIED (trace; selected==actual; no silent substitute) |
| Conversational state | PARTIAL | PRESENT AND VERIFIED (mode + activeGoal + workflowHold) |
| Intent understanding | BROKEN (missed live phrase) | PRESENT AND VERIFIED (evidence_spans) |
| Dialogue policy | PARTIAL | PRESENT AND VERIFIED (sole authority; HOLD quarantines intake) |
| Response generation | PARTIAL (template-first) | PRESENT AND VERIFIED (LLM primary; fallback last resort) |
| Personality | PARTIAL | PRESENT AND VERIFIED (typed profile + prompt guidance) |
| Memory | PARTIAL | PRESENT AND VERIFIED (working goal + prefs on snapshot) |
| Context assembly | PARTIAL | PRESENT AND VERIFIED (goal-ranked listening context) |
| Tool routing | PRESENT | PRESENT (subordinate to DialoguePlan tool_policy) |
| Grounding gates | PARTIAL | PRESENT AND VERIFIED (one repair; fallback traced) |
| Telemetry | PARTIAL | PRESENT AND VERIFIED (`inference_trace` SSE) |
| UI observability | PARTIAL | PRESENT AND VERIFIED (Activity mode/goal; Wiki learning; Not Checked clarified) |

---

## Root cause (confirmed + repaired)

1. Intro heuristics required length ≥140 or exact “I am going to tell you about”; live message used “I will tell you” and was shorter → missed `intro`.
2. `project_director` recommendedNextStep (“Choose a clear project title and a one-sentence creative premise.”) could be injected into LLM nudges when listening was bypassed.
3. Conversation Core used deterministic composer as primary for “handled” turns — incompatible with LLM-primary refinement.

**Repair:** Intent→DialoguePlan authority; LISTENING+HOLD; LLM primary via selected Ollama model; grounding + one repair; director/nudge quarantine; token SSE uses `content`.

---

## Implementation notes

### Files changed (primary)

- `studio-api/app/codirector/conversation/foundation/*` — schemas, intent, dialogue policy, grounding, response generation, context assembler, personality, policy versions
- `studio-api/app/codirector/conversation/orchestrate.py` — Intent→DialoguePlan authority; state persistence
- `studio-api/app/codirector/conversation/schemas.py` — snapshot/result foundation fields; wiki provenance hooks
- `studio-api/app/codirector/service.py` — LLM-primary stream/chat path, grounding/repair/fallback, inference_trace, nudge quarantine, foundation timeout floor (600s)
- `studio-web/src/components/CoDirector/*` — Activity mode/goal/tools/memory; Wiki learning copy; Not Checked clarification
- `studio-web/src/api.ts` — stream event types for `inference_trace` / `conversation_state`
- `studio-api/tests/test_codirector_foundational_ai.py` + golden JSON
- `tests/e2e/codirector/codirector-foundational-ai-listening-cert.spec.ts`
- `data/codirector_config.json` — `timeoutSec` 180→600 for large local models

### Tests

```text
pytest tests/test_codirector_foundational_ai.py tests/test_codirector_conversation_core.py
→ 29 passed

npx playwright test tests/e2e/codirector/codirector-foundational-ai-listening-cert.spec.ts --retries=0 --workers=1
→ 1 passed (ADEPT_BETA_TARGET=1)
```

### Live certification evidence

Artifacts: `docs/release-gate/co-director-foundation/artifacts/foundational-ai-2026-08-05T19-32-13-988Z/`

- Exact failing string → `EXPLAIN_PROJECT` / `LISTENING` / `HOLD` / `question_budget=0`
- Reply from `qwen3.6:35b-a3b` (not template); `fallback_used=false`; selected==actual
- Paraphrases: no title/premise intake
- Lore retention + “don’t ask questions” compliance + summarize
- UI send + reload persistence of user message
- No Dreamweaver-hardcoded exclusive canned path

### Beta verification

- UI: `http://127.0.0.1:8760/` (health 200)
- API: `http://127.0.0.1:8758/` (health 200)
- Rebuild + restart completed after API/UI changes

### Limitations / residual risk

- Large local models need ≥600s foundation timeout; cold starts can still force traced fallback (honest `fallback_used=true`).
- Part B (Creative Companion / Story Guardian) is **not** certified by this verdict.
- Known plan ID `fcd7b4b0-…` may differ from the live Beta Dreamweaver row; cert resolves by exact name `The Dreamweaver`.

### Manual review path

1. Open `http://127.0.0.1:8760/co-director?projectId=97437f25-1d97-4e2a-8cf4-30449dcddbd4`
2. Confirm model `qwen3.6:35b-a3b` connected
3. Send: “I will tell you all about The Dreamweaver as I’d like you to be familiar with the story before we move into production. Sound good?”
4. Expect attentive listening; no title/premise questionnaire
5. Optionally open Activity for mode/goal; Status chip “Not Checked” = cross-check not run

---

## Checklist

```text
[x] Branch + starting SHA verified
[x] Contracts preserved or intentionally updated (Conversation Core remains gateway)
[x] Full-stack implementation completed
[x] Every visible control wired (observability surfaces inspectable state)
[x] Real runtime; no mock completion
[x] Persistence after reload verified (Playwright)
[x] Error/cancel/retry/recovery verified (grounding + traced fallback path)
[x] Authz + project isolation verified (unit isolation test)
[x] Unit/API/integration/regression passed
[x] Playwright creator workflow passed
[x] Failures repaired and documented (timeout floor for 35B)
[x] Production build passed (studio-web)
[x] Beta updated and running; URL reported
[x] Manual review path documented
[x] Screenshots + evidence saved
[x] Unified Markdown completion report created
[x] Limitations honest
[x] Verdict: GO
```
