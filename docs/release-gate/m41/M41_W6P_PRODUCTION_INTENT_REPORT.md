# M41 W6P-2 — Production Intent Report

| Field | Value |
|---|---|
| **Date** | 2026-07-29 |
| **Module** | `studio-api/app/codirector/production_intent/` |
| **Artifact** | `artifacts/m41/w6p/production_intent_results.json` |
| **Verdict** | **PASS** |

## Contract

`ProductionIntent` is the single structured intent used by Co-Director, Director, Generate Studio, Timeline, planner, and specialists. It expresses product goals without selecting Comfy graphs.

Supported operations include image/video/audio/subtitle/editorial/job lifecycle ops listed in the Wave 6P mission.

## Bridge

- `to_resolver_request(intent)` → public WorkflowResolver params
- `to_studio_job_params(intent, contract)` → QueueWorker enqueue payload with `videoRuntime` + provenance

## Persistence

Intents stored under `data/production_intents/{projectId}/{intentId}.json`.
