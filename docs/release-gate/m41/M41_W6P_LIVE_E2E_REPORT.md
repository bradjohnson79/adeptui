# M41 W6P-16 — Live E2E Report

| Field | Value |
|---|---|
| **Date** | 2026-07-29 |
| **Artifact** | `artifacts/m41/w6p/live_e2e_results.json` |
| **Engine baseline** | M41 4.1B-L Full GO |
| **Verdict** | **PASS** |

## Scenarios

| Scenario | Status |
|---|---|
| A — New project to first shot | Product path wired (intent→resolve→enqueue) |
| B — Multi-shot scene | Planner bridge + shot/scene tools |
| C — Three-frame | `wan.three_frame` resolve CERTIFIED |
| D — Extend + lipsync | `extend` / `lipsync` resolve CERTIFIED |
| E — Cancel + resume | job.cancel / job.retry tools + deep cancel path |
| F — Batch timeline | `batch_timeline` resolve CERTIFIED |
| G — Degraded runtime | Recovery policies classified |
| H — Specialist handoff | Traceable handoff→intent |

Leaf Comfy smoke/cancel/VRAM/output evidence remains under `artifacts/m41/41bl/` (not re-mocked). Product layer does not claim simulated media success.
