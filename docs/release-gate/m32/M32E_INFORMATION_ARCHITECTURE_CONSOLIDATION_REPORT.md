# M3.2e — Information Architecture Consolidation Report

## Summary

Shared status vocabulary, adapters, and UI primitives land on Aurora tokens. Tier‑1 surfaces migrate onto StatusBadge / ReadinessMeter / EmptyState / SectionHeader / DataTable patterns with `.ds-surface` containment.

## Status layer

- `studio-web/src/status/` — kinds, tones, mapCapability, mapHealth, mapGenerationTool, mapJob
- Unit tests: `studio-web/src/status/status.test.ts` (node:test)
- Shared health poll: `studio-web/src/hooks/useStudioHealth.ts`

## Primitives

StatusBadge, StatusDot, StatusPanel, ReadinessMeter, InlineNotice, EmptyState, ErrorState, SectionHeader, ListToolbar, SearchField, DataTable, ImageReadyCard under `studio-web/src/components/ui/`.

## Tier‑1 migrations

| Surface | Notes |
|---|---|
| SystemStatusStrip | StatusBadge + useStudioHealth; testids preserved |
| CapabilityReadinessPanel | SectionHeader, ReadinessMeter, StatusBadge, ds-surface |
| GenerationToolsHub | mapGenerationToolStatus + StatusBadge; BLOCKED unchanged |
| JobPanel | EmptyState, StatusBadge, traceback disclosure, Button |
| Home | SectionHeader + EmptyState light touch |
| SourceManager | ds-surface + StatusBadge; Offline ≠ Blocked |

## Honesty rules

- Install Required ≠ Failed
- Offline ≠ Blocked
- Partial ≠ Ready
- Unknown ≠ healthy
- No derived readiness from health for capability panel

## Evidence

- Playwright: `tests/e2e/m32e/information-architecture.spec.ts` (M32E-IA-01..25) — **passed**
- Unit: `node --experimental-strip-types --test studio-web/src/status/status.test.ts` — **3 passed**
- Screenshots: `artifacts/m32/information-architecture/`
- Audit: `artifacts/m32e/ui-pattern-audit.json`
- Matrix: `docs/release-gate/m32/M32E_UI_MIGRATION_MATRIX.md`
