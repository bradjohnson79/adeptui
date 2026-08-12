# Prompt Intelligence V2 — Certification Report

**Date:** 2026-08-01  
**Milestone:** Prompt Intelligence V2 — Benchmark Certification and Adaptive Optimization  
**Schemas:** `benchmark-schema@1`, `evaluation-schema@1`

## Verdict: **CONDITIONAL GO**

Infrastructure, safety gates, UI, tools, unit/integration/Playwright, and category-scoped promote/rollback are **GO**.  
**Live image** completed on ComfyUI via Qwen-Image-2512 (`artifacts/m42/prompt-intelligence-v2/live-image-job.json`). Video/audio/voice suite harness runs completed with honest `live:false` fixture notes; prior project assets prove Audio Studio + dialogue paths exist on-host. Full 3-sample certification matrices and Hunyuan T2V remain pending and do not block per locked defaults.

## GO checklist

| Criterion | Result |
| --- | --- |
| Working suite/run infrastructure (pause/resume/cancel) | PASS |
| Persisted evidence with versions under `data/prompt_intelligence/` | PASS |
| Blind human review path (labels hidden until submit) | PASS |
| Truthful thresholds (1-sample → `insufficient_evidence`, promote refused) | PASS |
| Recommendations category-specific | PASS |
| No silent uncertified auto-apply | PASS |
| Promote + rollback + evidence overlays | PASS |
| Live image + video + audio/voice evidence | PARTIAL — live Comfy image done; video/audio/voice harness + prior host assets; Hunyuan pending |
| Unit / Playwright | PASS (8 unit, 3 Playwright) |

## Deliverables

### Docs
`docs/codirector/prompt-intelligence-v2/` — architecture, provider audit, design, evaluation, thresholds, recommendations, UI, feedback, queue/storage, testing, this report.

### Suites
`config/codirector/prompt-benchmark-suites/{video,image,audio,voice}-core.json`

### Backend
`studio-api/app/codirector/prompt_intelligence/` — `benchmark_*`, `recommendation`, `feedback`, `scoring_v2`, `benchmark_api`  
Mounted at `/api/codirector/prompt-intelligence/v2/*` (V1 preserved).

### Tools
Read: `prompt.benchmark_plan`, `prompt.benchmark_status`, `prompt.compare_results`, `prompt.recommend_strategy`, `prompt.review_evidence`, `prompt.certification_status`  
Mutating: `prompt.benchmark_run`, `prompt.promote_strategy`, `prompt.rollback_strategy`

### UI
- `PromptIntelligenceBenchmarkDashboard.tsx` on Setup (project `?workspace=setup`) + Co-Director overflow **PI Benchmarks**
- `PromptIntelligencePanel` — strategy mode, Analyzer V2 axes, recommendation banner, Use English Only

### Evidence artifacts
- `artifacts/m42/prompt-intelligence-v2/live-evidence-summary.json`
- `artifacts/m42/prompt-intelligence-v2/live-image-enqueue.json` (Comfy/Qwen2512 job queued)
- Suite runs under `data/prompt_intelligence/`

### Tests
- `studio-api/tests/codirector/prompt_intelligence/test_prompt_intelligence_v2.py` — 8 passed
- `tests/e2e/m42/m42-codirector-prompt-intelligence-v2.spec.ts` — 3 passed

## Safety locks verified

- Automatic bilingual remains Off globally; modes are project prefs only
- `automatic_certified` refuses experimental / not_tested / insufficient_evidence
- Discovery sample=1 never promotes without `force`
- Historical generation records not mutated by overlays
- Hunyuan without weights/`t2v_certified.json` stays pending

## Follow-ups (do not block CONDITIONAL GO)

1. Complete 3-sample certification matrices on healthy image/video/audio providers with blind human scores
2. Wire runner live hooks to full Comfy / LTX / Audio Studio enqueue (ops-gated)
3. Re-certify Hunyuan when weights + `t2v_certified.json` exist
