# CO-DIRECTOR 2.0 — PHASE 10 TWO-TIER CERTIFICATION CONTRACT (FREEZE)

| Field | Value |
|---|---|
| Phase | 10 (certification) |
| Date | 2026-08-08 |
| Status | **FROZEN** |
| Dependency | Phase 9 certified (234/234) |
| Tier A | Deterministic/system correctness |
| Tier B | Real-model professional behavior |
| Provider | Ollama `qwen3.6:35b-a3b` (default configured model) |

## Tier A scope

Extends Phase 2–9 tests with:
- Cross-layer negative-side-effect matrix (11 route action classes × 4 side-effect types)
- Failure/recovery matrix (10 controlled failure types)
- Project isolation (5 proof tests)
- Mock/E2E isolation (2 tests)
- Randomized parameterized cases (deterministic seeds)

## Tier B scope

Real configured LLM (no mock/scripted). Sustained conversation scenarios:
- Schnick Coffee (10+ turns)
- Narrative (8 turns)
- Music video (5 turns)
- Adversarial (8 turns)

Scored against 15-dimension rubric (1–5 each). Critical failures auto-block.

## Repair policy

Architecture/integration defects: repair general and regress. Model-quality limitations: document unless they expose a prompting/context issue. No architecture churn for stylistic variance.

## Binary gate

Only green if: Tier A passes, Tier B score thresholds met, no critical failures, independent verifier passes.
