# Production Dock — Subagent Ownership Matrix (SA1–SA16)

**Primary agent:** sole integrator / certifier. Subagents report only `READY FOR PRIMARY REVIEW`. Never final GO.

| SA | Role | Allowed paths |
| --- | --- | --- |
| SA1 | Dock shell/layout | `studio-web/src/components/production-dock/**`, `studio-web/src/styles/production-dock/**` |
| SA2 | Runtime source + provider UX | `studio-web/src/components/production-dock/provider/**` |
| SA3 | Secrets / hosted providers | `studio-api/app/provider_settings/**`, `studio-api/app/secrets*`, `studio-api/app/hosted_providers/**`, tests |
| SA4 | Model registry + contracts | `studio-api/app/model_registry/**`, `studio-web/src/modelRegistry/**`, contracts doc |
| SA5 | LLM routing | `studio-web/src/components/production-dock/llm/**`, `studio-api/app/codirector/model_routing/**` |
| SA6 | Video prefs | `studio-web/src/components/production-dock/video/**`, `studio-api/app/model_preferences/video/**` |
| SA7 | Image prefs | `studio-web/src/components/production-dock/image/**`, `studio-api/app/model_preferences/image/**` |
| SA8 | Audio diagnostics | `studio-web/src/components/production-dock/audio/**`, `studio-api/app/runtime_diagnostics/audio/**` |
| SA9 | Co-Director dock launch | `studio-web/src/components/production-dock/codirector/**`, CoDirector host FAB removal |
| SA10 | Aurora Night/Day | `studio-web/src/theme/**`, `studio-web/src/styles/tokens/**`, dock settings |
| SA11 | Health + queue | `studio-web/src/components/production-dock/diagnostics/**`, `studio-api/app/system_diagnostics/**` / production_control |
| SA12 | A11y review | read-only unless reassigned |
| SA13 | Security review | read-only unless reassigned |
| SA14 | Tests / Playwright | `studio-api/tests/test_production_dock*.py`, `tests/e2e/m42/m42-production-dock*.spec.ts` |
| SA15 | Architecture review | read-only |
| SA16 | Migration + resolver verify | `studio-api/app/production_control/migration.py`, preference store, migration report |

**Shared package owned by primary + SA16:** `studio-api/app/production_control/**` (prefs, resolve, gate, status, router).
