# CO-DIRECTOR 2.0 — PHASE 7 SPECIALIST CREW REWIRE CERTIFICATION

| Field | Value |
|---|---|
| Phase | 7 (recovery) |
| Date | 2026-08-08 |
| Status | **GO** |
| Contract | `CODIRECTOR2_PHASE7_SPECIALIST_CREW_IMPLEMENTATION_CONTRACT.md` |
| Regression | **166/166 PASS** |

---

## 1. Binary verdict

**GO — CO-DIRECTOR 2.0 PHASE 7 SPECIALIST CREW REWIRE CERTIFIED.**

## 2. What was recovered

| Agent | File | What was done |
|---|---|---|
| **C** | `specialist_selector.py` | **REWRITTEN** — RouteDecision-aware. `MAX_SPECIALISTS=3`. `_INTENT_SPECIALISTS` and `_CONTINUITY_INTENTS` removed. Domain→specialist mapping. `SpecialistContext` with route_decision/creator_goal/workflow_stage. Zero specialists for NAVIGATE/APPROVE/REJECT/simple READ. Max 1 for analytical READ/clarify/ambiguous. Max 3 for EXECUTE_PRODUCTION. |
| **D** | `specialist_policies.py` | **HARDENED** — `enforce_specialist_permissions()` runtime assert, `assert_runner_permissions()` convenience function. Third enforcement point for `may_execute_tools=False`. |
| **E** | `synthesis.py` | **EXTENDED** — `classify_conflicts()` method (stylistic/feasibility/continuity detection). `synthesize()` accepts `route_decision` param. RouteDecision-aware result shaping. |
| **F** | `intelligence/service.py` + `service.py` | **GATED** — selection behind RouteDecision when available. Zero-specialist guard for NAVIGATE/READ_INSPECT/APPROVE/REJECT. Legacy fallback preserved. |

## 3. Test results: **166/166 PASS**

| Suite | Tests | Result |
|---|---|---|
| Phase 7 specialist crew | 24 | PASS |
| Phase 7 context allowlist | 5 | PASS |
| Phase 6 workflow | 28 | PASS |
| Phase 4 story intelligence | 43 | PASS |
| Phase 3 router | 10 | PASS |
| Phase 2 operator | 15 | PASS |
| Phase 2 production state | 10 | PASS |
| Phase 2 mock leak | 3 | PASS |
| Phase 2 posecraft | 20 | PASS |
| Phase 2 docker runtime | 8 | PASS |
| **Total** | **166** | **ALL PASS** |

---

**Certified. Phase 7 GO. Phase 8 may now begin.**
