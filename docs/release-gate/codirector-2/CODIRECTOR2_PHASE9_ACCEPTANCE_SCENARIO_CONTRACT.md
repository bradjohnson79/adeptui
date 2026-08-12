# CO-DIRECTOR 2.0 — PHASE 9 ACCEPTANCE SCENARIO CONTRACT (FREEZE)

| Field | Value |
|---|---|
| Phase | 9 (acceptance) |
| Date | 2026-08-08 |
| Status | **FROZEN** |
| Dependency | Phase 8 certified (180/180) |
| Method | Python pytest sustained-conversation harness. No new architecture. |

## Approach

`ScenarioSession` holds persistent mock project state across 4–14 turns per scenario. Each turn calls the full Phase 2–8 backend pipeline (`classify_deterministic` → `route_turn` → `plan_conversation` → `response_composer`) with the accumulated state. Assertions are behavioral (not exact prose) and include negative side effects.

## Scenarios

| Scenario | Turns | File |
|---|---|---|
| Schnick Coffee | 14 | `test_p9_schnick_coffee.py` |
| Narrative scene | 8 | `test_p9_narrative.py` |
| Music video | 5 | `test_p9_music_video.py` |
| Resilience (manual work, switching, correction) | 19 | `test_p9_resilience.py` |
| Failure/recovery + known/unknown + specialist restraint | 17 | `test_p9_edge_cases.py` |

## No new architecture

Phase 9 only adds tests and repairs defects. No new intelligence systems.

## Repair law

If a defect is exposed in an earlier phase's subsystem, repair the general contract and rerun that phase's regression.
