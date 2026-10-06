# 09 — Tests (Gate L)

**Surface:** CURRENT DEVELOPMENT  
**Date:** 2026-08-30

Measured in `studio-api` venv unless noted. `pytest` from repo root fails (`ModuleNotFoundError: app`).

## Backend

| Suite | Result |
|---|---|
| `test_project_lock_media.py` | included in 78-pass bundle |
| `test_generator_authority.py` | included |
| `test_runtime_supervisor_lifecycle.py` | included |
| `test_timeline_auto_approve_gate.py` | included |
| `test_spatial_document_authority.py` | included |
| `test_timeline_knowledge_compile.py` | included |
| `test_minimax_duration_truth.py` | included |
| `test_ltx_leaf_graph_lora_kwargs.py` | included |
| `test_generator_knowledge.py` | included |
| Combined A–G + LoRA kwargs | **78 passed**, 0 failed (8.34s) |
| `test_timeline_generation_adapters.py` + `test_production_dock.py` | **41 passed**, 0 failed (28.41s) |

## Frontend

`node --test src/timelineMaster/draftCapabilities.test.ts` — **4 passed**.

`generatorDuration.test.ts` via `node --test` still fails collection (needs vitest / `.js` import). Pre-existing. Not weakened.

## Not run as Gate L

Full Vitest suite. Full backend pytest tree. Collection-broken WIP files (`test_comfy_transport_error.py`, `test_ltx_i2v_lora_failures.py`) left untouched.
