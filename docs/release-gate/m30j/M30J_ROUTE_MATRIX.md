# M3.0j Route Matrix

**Status:** IN PROGRESS — **NOT M3.0j YES**

**Source of truth:** `studio-web/src/App.tsx` (top-level routes), `studio-web/src/core/workspaces.ts` + `ProjectEditor.tsx` (project workspaces and Director sub-tabs).

**Legend**

| Cert status | Meaning |
|-------------|---------|
| **PASS** | Covered by existing deterministic or certified e2e in `tests/e2e/` |
| **PENDING_CERT** | Route/workspace exists; M3.0j Playwright or REAL_LOCAL proof not yet GREEN |

**Test mode labels**

| Label | Meaning |
|-------|---------|
| **DETERMINISTIC** | API/fixture/UI shell smoke — no GPU generation |
| **REAL_LOCAL** | Requires local Comfy / ACE / WAN / lip-sync execution |

---

## Top-level routes (`App.tsx`)

| Route | Component | Category | Cert | E2E coverage |
|-------|-----------|----------|------|--------------|
| `/` | Home | home | **PASS** | `smoke/startup.spec.ts` |
| `/project/:id` | ProjectEditor | project shell | **PASS** | `resilience/navigation.spec.ts`, `projects/project-crud.spec.ts` |
| `/co-director` | CoDirectorPage | codirector | **PASS** | `resilience/navigation.spec.ts`, `codirector/*`, `m30-completion/m30-completion-flags.spec.ts` |
| `/source-manager` | SourceManagerPage | setup | **PASS** | `setup/source-manager.spec.ts`, `setup/download-queue.spec.ts` |
| `/model-radar` | ModelRadarWorkspace | workspace (flag) | **PASS** | `codirector/capability-intelligence-m28.spec.ts` (flag on/off) |
| `/virtual-stage` | VirtualStageWorkspace | workspace (flag) | **PASS** | `codirector/capability-intelligence-m28.spec.ts` |
| `/environment-studio` | EnvironmentStudioWorkspace | workspace | **PASS** | `m30i/environment-360-character-scene.spec.ts` |
| `/production-suite` | ProductionSuiteWorkspace | workspace (M2.9) | **PASS** | `codirector/production-suite-m29.spec.ts` |
| `*` | Navigate → `/` | fallback | **PENDING_CERT** | No explicit unknown-path redirect test in M3.0j |

**Global shell:** `CoDirectorHost` mounts outside `<Routes>`; overlay hidden on full-screen `/co-director`.

---

## Project workspaces (`/project/:id?workspace=<tab>`)

Canonical IDs from `WORKSPACES` in `studio-web/src/core/workspaces.ts`.

### Key workspaces (M3.0j focus)

| Workspace | Label | Group | Cert | E2E coverage | Mode |
|-----------|-------|-------|------|--------------|------|
| `director` | Director | create | **PASS** | `m30h/filmmaker-smoke.spec.ts`, `m30h-local-first/local-routing-fixtures.spec.ts`, `m30i/director-timeline-generator.spec.ts`, `m30g/production-certification.spec.ts` | DETERMINISTIC |
| `editor` | Editor | finish | **PASS** | `m30h/filmmaker-smoke.spec.ts`, `m30i/director-timeline-generator.spec.ts`, `m30i/codirector-audio-timeline.spec.ts` | DETERMINISTIC shell; REAL_LOCAL for render |
| `library` | Library | organize | **PASS** | `m30j/project-library.spec.ts` (LIBRARY-01 API + LIBRARY-02 UI) | DETERMINISTIC |
| `setup` | Setup | additional | **PASS** | `setup/setup-page.spec.ts`, `resilience/navigation.spec.ts`, `a11y/m30g-keyboard-journeys.spec.ts` | DETERMINISTIC |
| `home` | Project Home | project | **PENDING_CERT** | Project shell loads via navigation; no dedicated home-workspace cert | DETERMINISTIC |

### Co-Director entry points

| Surface | Route / trigger | Cert | E2E coverage |
|---------|-----------------|------|--------------|
| Full-screen Co-Director | `/co-director` | **PASS** | `codirector/*`, `m30j/codirector-library-awareness.spec.ts` (API) |
| Co-Director overlay host | Global `CoDirectorHost` | **PENDING_CERT** | Best-effort in `m30h/filmmaker-smoke.spec.ts`; no overlay cert matrix |
| Library awareness (API) | `/api/projects/{id}/library/codirector-context` | **PASS** | `m30j/codirector-library-awareness.spec.ts` @DETERMINISTIC |
| Library awareness (REAL_LOCAL) | Post-generation storage report | **PENDING_CERT** | `LIBRARY-CD-20` skipped in M3.0j spec | REAL_LOCAL |

### Director sub-tabs (within `workspace=director`)

Sub-tabs use Director selection context (`workspaceTab` in `ProjectEditor.tsx`): `timeline`, `prompt`, `lipsync`, `settings`.

| Sub-tab | Cert | E2E coverage | Mode |
|---------|------|--------------|------|
| Timeline | **PASS** | Director shell tests; timeline generator M3.0i | DETERMINISTIC shell |
| Prompt | **PENDING_CERT** | No dedicated prompt-view cert | DETERMINISTIC |
| **Lip Sync** | **PENDING_CERT** | M2.9 `/production-suite` lipsync section only; no in-editor lipsync sub-tab e2e | REAL_LOCAL for generate |
| Settings (scene) | **PENDING_CERT** | No dedicated Director settings sub-tab e2e | DETERMINISTIC |

### Remaining project workspaces

| Workspace | Label | Cert | Notes |
|-----------|-------|------|-------|
| `settings` | Settings | **PASS** | `m30h/filmmaker-smoke.spec.ts`, `a11y/m30g-production-critical.spec.ts` |
| `imagegen` | ImageGen | **PASS** | `m30h-local-first/local-routing-fixtures.spec.ts` |
| `txt2vid` | Txt2Vid | **PASS** | `m30h-local-first/no-silent-fal-fallback.spec.ts` |
| `one` | 1 Frame | **PENDING_CERT** | Shell via Director composite; no isolated cert |
| `three` | 3 Frame | **PENDING_CERT** | Same as one-frame |
| `audiostudio` | Audio Studio | **PENDING_CERT** | No M3.0j workspace smoke |
| `bible` | Production Bible | **PASS** | `codirector/production-bible*.spec.ts` |
| `avatar` | Avatar Studio | **PENDING_CERT** | — |
| `mastersheet` | Scene Master Sheet | **PENDING_CERT** | — |
| `profiles` | Profiles | **PENDING_CERT** | — |
| `tools` | Character / Angles | **PENDING_CERT** | Legacy alias |
| `marketplace` | Marketplace | **PENDING_CERT** | — |
| `script` | Script / Storyboard | **PENDING_CERT** | — |
| `spatial` | Spatial Map | **PENDING_CERT** | — |
| `generate` | Generate Timeline | **PENDING_CERT** | Legacy |
| `shotlist` | Shot List | **PENDING_CERT** | Legacy |

---

## M3.0j Playwright suite (`tests/e2e/m30j/`)

| Spec | Label | Purpose |
|------|-------|---------|
| `routes.spec.ts` | @DETERMINISTIC | Primary route smoke skeleton |
| `project-library.spec.ts` | @DETERMINISTIC | API tree/folderMap + Library UI folder tree |
| `codirector-library-awareness.spec.ts` | @DETERMINISTIC (+ REAL_LOCAL skip) | Co-Director library resolve/preflight API |

**Artifacts:** `artifacts/m30j/playwright/` (run results), `artifacts/m30j/route-audit/route-matrix.json` (machine summary).

---

## Summary counts

| Status | Top-level routes | Project workspaces | Director sub-tabs |
|--------|------------------|--------------------|-------------------|
| PASS | 8 | 9 | 1 |
| PENDING_CERT | 1 | 13 | 3 |

**M3.0j route audit verdict:** **PENDING** — matrix recorded; M3.0j deterministic Playwright (14/14 pass, 3 REAL_LOCAL skipped). Lip Sync sub-tab and remaining workspaces not fully certified. Does **not** claim M3.0j YES.

**Playwright (2026-07-28):** `artifacts/m30j/playwright/deterministic-run.json` — PASS on E2E stack (`STUDIO_E2E=1`). Dev server on 5173/8742 cannot satisfy `waitForAppReady` (`/api/e2e/status` 404).
