# Co-Director Foundation Capability Matrix — Phases 1.5–6

| Capability | Phase | Unit | Semantic | Live | Failure | Isolation | Status |
|---|---|---:|---:|---:|---:|---:|---|
| KnowledgePack catalog + query API | 1.5 | PASS | PASS | PASS | n/a | PASS | PASS |
| Shared-source doctrine (no private duplicates) | 1.5 | PASS | PASS | PASS | n/a | PASS | PASS |
| Story / Character / World specialists | 2 | PASS | PASS | PASS | n/a | PASS | PASS |
| Cinematic craft specialists | 2 | PASS | PASS | PASS | n/a | PASS | PASS |
| Continuity supervisor | 2 | PASS | PASS | PASS | n/a | PASS | PASS |
| Creative Director pre-synthesis | 2 | PASS | PASS | PASS | n/a | PASS | PASS |
| Production readiness / dependencies | 3 | PASS | PASS | PASS | n/a | PASS | PASS |
| Estimates (non-guarantee) | 3 | PASS | PASS | soft | n/a | PASS | PASS |
| Collaboration modes | 4 | PASS | PASS | PASS | n/a | PASS | PASS |
| Preference memory (editable/forgettable) | 4 | PASS | PASS | soft | n/a | PASS | PASS |
| Safe autonomous audits | 5 | PASS | PASS | PASS | SKIP-ENV | PASS | PASS |
| Bounded retry / no duplication | 5 | PASS | PASS | SKIP-ENV | SKIP-ENV | PASS | PASS |
| Domain profiles + combined profiles | 6 | PASS | PASS | soft | n/a | PASS | PASS |
| Domain-adapted guidance | 6 | PASS | PASS | soft | n/a | PASS | PASS |
| Single orchestration pipeline | integ | PASS | PASS | PASS | n/a | PASS | PASS |
| Disposable-project Playwright cert | cert | PASS | PASS | PASS | SKIP-ENV | PASS | PASS |

Statuses: PENDING | PASS | FAIL | SKIP-ENV | soft (covered by unit/API; light live touch)

Evidence:
- Unit: 51 passed (`test_codirector_foundation_*` + conversation core)
- Live: `codirector-foundation-2-6-autonomous-cert.spec.ts` — 1 passed (~1.3m)
- Artifacts: `docs/release-gate/codirector-final/artifacts/autonomous-cert/CODIRECTOR-AUTONOMOUS-CERT-2026-08-03T18-23-04-439Z/`
