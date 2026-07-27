# M3.0d Specialist DAG Certification

| Field | Value |
|-------|-------|
| Date | 2026-07-27 |
| Register item | B8 |
| Branch | `phase2/codirector-m2-9-production-suite` |
| Implementation SHA | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |

## Problem (B8)

M3.0b reported that three declared M2.11 specialists â€” **storyteller**, **sound-producer**, and **virtual-production-coordinator (VPC)** â€” never ran in the default pipeline, producing KeyError failures across situation runs.

## Expected state

Each specialist in `DEFAULT_PIPELINE` must either:

1. Execute through the specialist runner with a resolvable prompt and schema, or
2. Be explicitly delisted from the DAG with honest capability disclosure.

## Root cause

DAG order test expectations and runtime wiring were out of sync. The pipeline declared specialists that the runner could not resolve in all code paths.

## Implementation

- `DEFAULT_PIPELINE` includes storyteller, sound-producer, and VPC in documented order.
- Specialist runner resolves prompt files under `studio-api/app/codirector/prompts/` (`storyteller.md`, `sound-producer.md`, VPC prompts).
- M2.14 unified experience exposes storyteller handoff APIs (`test_m214_unified_experience.py`).
- VPC specialist prompt verified: `test_m213_virtual_environment_studio.py::test_vpc_specialist_prompt_exists`.

## Test evidence

| Test | Result |
|------|--------|
| `test_m211_production_intelligence.py::test_dag_order` | PASSED (PY10 closure) |
| `test_m214_unified_experience.py` â€” storyteller/sound-producer in specialists list | PASSED |
| Full gate `pytest -q` | 631 passed, 0 failed |

Prior M3.0b evidence of 36 KeyError failures across 12 runs is superseded by M3.0c situation EXECUTED results and M3.0d backend gate.

## Artifact proof

- `artifacts/m30-situations/phase18-final-validation.json` â€” all 12 situations completed intelligence + production phases with HTTP 200 director status.
- `docs/m3.0c/PRODUCTION_SITUATION_CERTIFICATION_MATRIX.md` â€” S01â€“S12 EXECUTED.

## Status

**B8: Closed** at commit `43a5c0f0152a39327e87b10de11fd55e5b16ad90`.

## Residual (B15/B16 â€” related, not B8)

| Item | Status | Note |
|------|--------|------|
| B15 provider unwrap | Closed (code) | `_unwrap_provider_payload` preserves model content |
| B16 enrichment scaffold | In progress | Four live brief proof still pending |
| B21 timeout surfacing | Closed (bounded) | Timeouts promoted to warnings in honesty normalizer |

The DAG runs; live provider diversity across four briefs is a separate intelligence-evidence gap tracked under B16, not a DAG wiring failure.
