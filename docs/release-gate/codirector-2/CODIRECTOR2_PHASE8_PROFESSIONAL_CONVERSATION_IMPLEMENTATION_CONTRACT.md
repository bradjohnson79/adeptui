# CO-DIRECTOR 2.0 — PHASE 8 PROFESSIONAL CONVERSATION REFINEMENT CONTRACT (FREEZE)

| Field | Value |
|---|---|
| Phase | 8 (implementation) |
| Date | 2026-08-08 |
| Status | **FROZEN** |
| Dependency | `GO — PHASE 7 SPECIALIST CREW REWIRE CERTIFIED` (166/166 regression) |

## 1. Architecture

Phase 8 ADAPTS the existing conversation subsystem. No `professional_conversation_v2.py`, no second response planner, no parallel conversation system.

## 2. Layers

| Layer | File | Change |
|---|---|---|
| Known-fact suppression | `inquiry.py` | Check Production State before generating questions. Suppress if creator-stated/creator-approved. |
| "No phantom knowledge" | `inquiry.py` | Don't ask known facts AND don't pretend to know unknowns. |
| Conversation goal | `orchestrate.py` | Ephemeral `current_goal` tracking. Goal persists across turns. Changes on explicit switch or task completion. |
| Next-step integration | `next_steps.py` + `planner.py` | Phase 6 Workflow Engine is single authority. Suppress recommendation on every reply. Offer only when: "what next?", task completes, blocker resolved, major-stage boundary. |
| Tone/response | `response_composer.py` | Suppress generic praise. Specific production insight. Professional disagreement. Verified operation language (pending→ack→success/failure). Response length task-appropriate. Correction without apology speeches. |
| Internal leakage | `response_composer.py` | Block: RouteDecision JSON, workflow assessment, tool fences, [mock], specialist IDs, raw synthesis internals. |
| Specialist synthesis | Consume Phase 7 | Phase 7 owns synthesis. Phase 8 ensures ONE creator-facing voice from the already-synthesized result. No redesign of synthesis.py. |

## 3. Schnick Coffee sustained scenario

11-turn conversation (not isolated tests). State carries across turns. Behavioral assertions, not exact prose. Verify: mentions complete draft, recognizes 20-sec context, doesn't repeat known runtime, doesn't expose internals, doesn't mutate unexpectedly.

## 4. No parallel conversation system

OpenCode must check against Phase 1 conversation audit. No new `conversation/` package files that duplicate existing machinery.

---

*Frozen. Phase 8 begins.*
