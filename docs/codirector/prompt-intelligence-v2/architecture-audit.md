# Prompt Intelligence V2 — Architecture Audit

**Date:** 2026-08-01  
**V1 engine:** `prompt-intelligence@1`  
**V2 schemas:** `benchmark-schema@1`, `evaluation-schema@1`

## V1 foundation (preserved)

| Asset | Path |
| --- | --- |
| Pipeline | `studio-api/app/codirector/prompt_intelligence/pipeline.py` |
| Profiles | `config/codirector/prompt-profiles/` |
| Offline matrix | `prompt_intelligence/benchmark.py` + `scripts/codirector/prompt_intelligence_benchmark.py` |
| HTTP | `/api/codirector/prompt-intelligence/{enhance,analyze,profiles,validate}` |
| UI | `PromptIntelligencePanel.tsx` |
| Cert | `docs/codirector/prompt-enhancement/certification-report.md` (V1 GO) |

V1 does **not** perform live generation comparisons. All `bilingualCertified` flags remain `false`.

## V2 extension surface

- Suites/cases in `config/codirector/prompt-benchmark-suites/`
- Run store under `data/prompt_intelligence/`
- Evidence overlays in `config/codirector/prompt-profiles/evidence/`
- New modules: `benchmark_*`, `recommendation`, `feedback`, `scoring_v2`, `benchmark_api`
- Queue: reuse `queue_worker` heavy_local + cancel_and_halt
- UI pattern: clone `VideoModelLibrary` benchmark row actions

## Non-regressions

- Four-layer prompt contract unchanged
- Manual override / Reset preserved
- Chinese never silently enabled
- Historical generation metadata immutable
