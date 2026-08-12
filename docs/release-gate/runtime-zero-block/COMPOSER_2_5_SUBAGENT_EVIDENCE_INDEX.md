# Composer 2.5 Subagent Evidence Index

**RUN_ID:** `runtime-zero-block-2026-08-05T18-16-27Z`  
**Coordinator:** Composer 2.5 (primary)

| Workstream | Agent | Files Changed | Tests | Live Artifact | Evidence Path | Verdict |
| ---------- | ----- | ------------- | ----- | ------------- | ------------- | ------- |
| Wave 0 Baseline | Primary | docs/release-gate/runtime-zero-block/* | n/a | route_probes, status_check | artifacts/.../baseline/ | GO |
| A/C Cross-check + API | Primary | status/runner.py, probe_context.py, registry.py, types.py, weighting.py, comfy_health.py | test_codirector_status_cross_check.py (9) | PA project-bound 0 blocked | artifacts/.../baseline/status_check_with_project.json | GO — CORE PA STABLE |
| B Co-Director | Primary | inference_activity.py, service.py stream wrap | busy≠timeout unit | provider slow/healthy | same | GO — NON-DEGRADED PATH WIRED |
| D Registries | Primary | SCENECRAFT_RELEASE_EXCLUSION, manifest builder | scenecraft exclusion test | CURRENT_RELEASE_CAPABILITY_MANIFEST.json | docs/.../CURRENT_RELEASE_CAPABILITY_MANIFEST.json | GO — RECONCILED + FROZEN |
| E/F Comfy + Hunyuan + Models | Primary + shell | hunyuan15/13b_builder.py, workflows/registry.py, readiness.py, hunyuan_providers.py | readiness HyVideo ready | models junctions | artifacts/.../models/ | GO — NODES/MODELS READY |
| G Library | Primary | library.preflight write probe | PA library.preflight | writeProbePassed | status_check_with_project.json | GO — PERSISTENCE PROBE |
| H–I Workflows | Primary + Task | matrix writer, image smoke | readiness 12/13 ready | image job done; matrix 3/13 GO | artifacts/.../workflows/ | BLOCKED — LIVE CATALOG INCOMPLETE |
| Q UI Truthfulness | Primary | CoDirectorStatusPanel.tsx, status types | Playwright stages 1–6 | screenshots pending Stage 8 | artifacts/.../playwright/ | PARTIAL |
| R Playwright | Primary | adept-ui-runtime-workflow-zero-block-cert.spec.ts | e2e partial | stage1–6 ok | artifacts/.../playwright/ | PARTIAL |
| S Independent Verifier | Primary | audit §26 | read-only | n/a | ADEPT_UI_RUNTIME_AND_WORKFLOW_ZERO_BLOCK_AUDIT.md | BLOCKED |
| Soak | pending | post_cert_soak.ps1 | pending | pending | artifacts/.../soak/ | pending |
