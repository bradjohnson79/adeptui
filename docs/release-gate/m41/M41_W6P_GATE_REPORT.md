# M41 W6P-20 — Gate Report

| Field | Value |
|---|---|
| **Date** | 2026-07-29 |
| **Endpoint** | `GET /api/video-runtime/wave6p-gate` |
| **Artifact** | `artifacts/m41/w6p/wave6p_gate_results.json` |
| **Evaluator** | `studio-api/app/video_runtime/wave6p_gate.py` |

## Inclusion rule

`wave6pGo` is true only when every required boolean is true (not a numeric test count):

- prerequisiteEngineGo
- consumerContractPassed
- toolRegistryPassed
- productionIntentPassed
- plannerPassed
- codirectorUxPassed
- directorIntegrationPassed
- timelineIntegrationPassed
- assetProvenancePassed
- cancellationRecoveryPassed
- persistencePassed
- liveE2ePassed
- playwrightPassed
- subagentBetaPassed
- manualBetaReady
- Final certification stamp **GO**

Cloud fal failures do not block local GO while cloud remains disabled and unadvertised.
