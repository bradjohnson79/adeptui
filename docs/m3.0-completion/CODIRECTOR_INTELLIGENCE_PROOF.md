# Co-Director Intelligence Proof (M3.0 Completion Phase 8)

| Field | Value |
|-------|-------|
| Date | 2026-07-27 |
| Scope | Specialist provider path + limited-analysis honesty |
| Code | `studio-api/app/codirector/intelligence/specialist_runner.py`, `m211/orchestrator.py`, `intelligence/service.py`, chat `stream_for_project` |
| Tests | `studio-api/tests/test_m30_intelligence_provider.py` |

---

## 1. What changed

| Call site | Before | After |
|-----------|--------|-------|
| `ProductionIntelligenceOrchestrator.run` | Hardcoded `use_provider=False` (LLM branch unreachable) | Resolves provider via `resolve_provider_for_specialists()`; `use_provider=True` when healthy and not `STUDIO_E2E` |
| Chat intelligence (`stream_for_project` -> `IntelligenceService`) | Omitted `use_provider` (defaulted false) | Passes `use_provider=None` so the same resolver enables the provider path when available |
| Heuristic / unavailable path | Assumptions said E2E/mock path even outside E2E | Clearly labeled **limited-analysis / heuristic** - not deep story or emotional intelligence |

Resolver rules (`resolve_provider_for_specialists`):

1. `STUDIO_E2E` set -> limited-analysis (no provider calls).
2. No provider / health not reachable or no model -> limited-analysis.
3. Otherwise -> `use_provider=True`, `analysisMode=provider`.

Orchestration responses now include `analysisMode`, `honesty` (`provider` | `limited`),
`honestyNotes`, and `useProvider`.

---

## 2. Pytest proof

Focused suite: `tests/test_m30_intelligence_provider.py`

| Test | Assertion |
|------|-----------|
| `test_two_briefs_non_identical_digests_with_provider` | Two different briefs + mock provider returning brief-specific JSON produce **non-identical** specialist digests |
| `test_use_provider_false_honesty_labels_limited` | With `use_provider=False`, assumptions/summary carry **limited** / **heuristic** honesty labels |
| `test_resolve_provider_e2e_forces_limited` | `STUDIO_E2E=1` forces limited-analysis even if a ready provider is supplied |
| `test_resolve_provider_ready_enables_use` | Ready provider outside E2E enables `use_provider=True` |

Run:

```
cd studio-api
python -m pytest tests/test_m30_intelligence_provider.py tests/test_m211_production_intelligence.py -q
```

---

## 3. Honesty contract

When the provider path is not used, specialist findings and orchestration enrichment must
not be presented as deep reasoning:

- Specialist assumption: limited-analysis / heuristic (see `LIMITED_ANALYSIS_ASSUMPTION`).
- Summary includes `(limited-analysis)` on the heuristic path.
- Enrichment `source` is `limited-analysis-heuristic` with an explicit note.
- Confidence on heuristic findings is reduced (0.55) versus provider-validated findings.

No fake deep emotional intelligence is claimed on the limited path.

---

## 4. Live Ollama note

When Ollama (or another configured Co-Director provider) is reachable with a model and
`STUDIO_E2E` is unset, orchestration and chat intelligence use the provider path. Two
distinct production briefs should then yield non-identical specialist digests from the
model. The automated proof above uses a brief-aware mock provider so CI does not require
a live Ollama host; the wiring under test is the same `use_provider=True` branch.
