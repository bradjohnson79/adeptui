# M42 Wave 4C — Timeline Product Rename Report

| Field | Value |
|---|---|
| **Phase** | M42 Wave 4C — Director → Timeline Product Rename |
| **Branch** | `phase2/m42-timeline-product-rename` |
| **Baseline tip** | `f758744` (from `phase2/m42-magi-editor-foundation`) |
| **Verdict** | **GO** |
| **wave4cGo** | `true` |
| **Canonical product** | Timeline |
| **Expanded label** | Timeline Generator |
| **Deprecated standalone label** | Director |
| **AI assistant (unchanged)** | Co-Director |
| **Stamped** | 2026-07-30 |

## Purpose

Remove product-name ambiguity between the timeline-generation workspace (formerly **Director**) and **Co-Director** (AI production assistant). Wave 4C is a language, routing, persistence, compatibility, documentation, and certification milestone — not a Timeline runtime redesign.

## Locked outcomes

| Decision | Result |
|---|---|
| Canonical workspace id | `timeline` |
| Legacy alias | `director` → `timeline` via `resolveWorkspace()` |
| Route shape | `/project/:id?workspace=timeline` |
| Legacy query | `/project/:id?workspace=director` canonicalizes to `timeline` (preserves other query params) |
| Hero asset | `studio-web/public/images/hero/Timeline_Anadriya_4-3.png` |
| Scene `/director` API | LEFT_STABLE (shot-direction domain) |
| `DirectorTracks` / selection modules | LEFT_STABLE filenames (display rename only) |
| Analytics | Option A — stable event IDs; product called Timeline in docs |

## What changed (user-facing)

- Home launch card: **Timeline Generator** / Open Timeline (new 4:3 Anadriya hero)
- Workspace registry: `WORKSPACES.timeline` (menus, command palette, badges)
- Project Home / explore tiles default to Timeline
- Library / Co-Director / MAGI cross-links: Open Timeline, Send to Timeline
- i18n `navigation.timeline` / legacy `director` key maps to “Timeline”
- Co-Director product name preserved everywhere

## Compatibility

```text
workspace=director  →  resolveWorkspace()  →  timeline
adept_ui_last_workspace  →  read via resolve; write canonical timeline
```

Existing Director-created projects keep IDs, scenes, shots, media, and provenance. No destructive database migration. No second Timeline runtime or duplicate product tile.

## Gate conjunction (all true)

```text
TimelineCanonicalNameApplied
∧ StandaloneDirectorUiReferencesZero
∧ CoDirectorNamePreserved
∧ TimelineNavigationOperational
∧ TimelineWorkspaceOperational
∧ TimelineRouteCanonical
∧ LegacyDirectorRoutesCompatible
∧ LegacyProjectsCompatible
∧ TimelinePersistenceCompatible
∧ TimelineSearchAliasOperational
∧ TimelineApiNormalizationOperational
∧ TimelineCoDirectorIntegrationOperational
∧ TimelineMagiIntegrationOperational
∧ TimelineAccessibilityUpdated
∧ TimelineDocumentationUpdated
∧ TimelinePlaywrightPassed
∧ TimelineUnexplainedLegacyReferencesZero
→ wave4cGo
```

Evidence: `artifacts/m42/w4c/wave4c_gate_results.json` (`wave4cGo: true`, `missingRequirements: []`).

Evaluator: `studio-api/app/timeline_product/production_gate.py` → `evaluate_timeline_wave4c_gate()`  
API: `GET /api/magi/gate/wave4c`  
Stamp: `scripts/m42_w4c_timeline_stamp.py`

## Tests

| Suite | Path |
|---|---|
| Unit | `studio-api/tests/test_m42_w4c_timeline_rename.py` |
| Playwright | `tests/e2e/m42/m42-wave4c-timeline-rename.spec.ts` |

## Companion reports

| Report | Path |
|---|---|
| Audit / inventory | [M42_W4C_TIMELINE_RENAME_AUDIT.md](./M42_W4C_TIMELINE_RENAME_AUDIT.md) |
| Routes | [M42_W4C_TIMELINE_ROUTE_COMPATIBILITY_REPORT.md](./M42_W4C_TIMELINE_ROUTE_COMPATIBILITY_REPORT.md) |
| Projects | [M42_W4C_TIMELINE_PROJECT_MIGRATION_REPORT.md](./M42_W4C_TIMELINE_PROJECT_MIGRATION_REPORT.md) |
| Persistence | [M42_W4C_TIMELINE_PERSISTENCE_REPORT.md](./M42_W4C_TIMELINE_PERSISTENCE_REPORT.md) |
| Co-Director | [M42_W4C_TIMELINE_CODIRECTOR_INTEGRATION_REPORT.md](./M42_W4C_TIMELINE_CODIRECTOR_INTEGRATION_REPORT.md) |
| MAGI | [M42_W4C_TIMELINE_MAGI_INTEGRATION_REPORT.md](./M42_W4C_TIMELINE_MAGI_INTEGRATION_REPORT.md) |
| Playwright | [M42_W4C_TIMELINE_PLAYWRIGHT_REPORT.md](./M42_W4C_TIMELINE_PLAYWRIGHT_REPORT.md) |
| Final certification | [M42_W4C_TIMELINE_FINAL_CERTIFICATION.md](./M42_W4C_TIMELINE_FINAL_CERTIFICATION.md) |

Inventory JSON: `artifacts/m42/w4c/timeline_rename_inventory.json`

## Explicit non-goals (confirmed)

- No Timeline generation-engine redesign
- No Co-Director rename
- No MAGI runtime change
- No blind global replace of ordinary “director” / “directory” / “direction”
- No fabricated Conditional GO

## Final verdict

**GO** — Director has been safely renamed Timeline site-wide, Co-Director remains distinct, and routes, projects, integrations, persistence, accessibility, and compatibility checks pass.
