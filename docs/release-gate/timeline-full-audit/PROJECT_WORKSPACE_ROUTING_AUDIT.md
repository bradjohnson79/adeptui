# Project / Workspace Routing Audit — Navigation & Workspace Memory

**Milestone:** ADEPT UI — TIMELINE FULL END-TO-END AUDIT, REPAIR & FINAL HARDENING (Addendum 1)
**Date:** 2026-08-07
**Status:** REPAIRED + CERTIFIED (NAV-1..NAV-7 Playwright, see `tests/e2e/navigation/project-workspace-routing.spec.ts`)

## 1. Reported defect

Opening a project sometimes redirected to `?workspace=timeline` unexpectedly: a creator who
last used Timeline was dropped straight back into Timeline on a plain Open Project, and a
single global workspace memory could contaminate a different project.

## 2. Full navigation path audit

### 2.1 Entry points that open a project (all verified bare-URL)

| Entry point | File | Navigation |
|---|---|---|
| Chrome Project menu — current project (on Home) | `AppChrome.tsx:161` | `/project/<id>` (bare) |
| Chrome Project menu — recent projects | `AppChrome.tsx:169` | `/project/<id>` (bare) |
| Chrome Project menu — duplicate result | `AppChrome.tsx:197` | `/project/<id>` (bare) |
| Command palette project open | `AppChrome.tsx:297` | `/project/<id>` (bare) |
| Home project cards / `openProject` | `Home.tsx:101` | `/project/<id>` (bare) |
| Project menu (in-project) open/recent | `ProjectMenu.tsx:70,114` | `/project/<id>` (bare) |
| Co-Director project suggestions | `CoDirectorSession.tsx:1145,1198` | `/project/<id>` (bare) |
| Co-Director page breadcrumb | `CoDirectorPage.tsx:75` | `/project/<id>` (bare) |

### 2.2 Explicit workspace navigation (legitimate `?workspace=` carriers)

| Entry point | File | Notes |
|---|---|---|
| Chrome Production menu workspace click | `AppChrome.tsx:105` (`goWorkspace`) | `tab` is the **clicked target**, never read from stored state |
| Home studio launch cards | `Home.tsx:385` | explicit workspace target per card |
| Project landing "Continue Production" | `ProjectHome.tsx:157,182` (`onGo(resumeTab)`) | **intentional** resume affordance, per-project keyed |
| In-project workspace switch | `ProjectEditor.tsx:563` (`go()`) | `home` → bare URL; named workspace → explicit param |
| Queue drawer job deep link | `QueueDrawer.tsx:78` | job's own `workspaceRoute` (server-provided) |

### 2.3 Search-string reuse audit

No navigation path reuses the current `location.search` when switching projects. The only
`location.search` readers are `returnTo` builders for the Create Project flow
(`AppChrome.tsx:139,143`, `ProjectMenu.tsx:98`), which return to the **same** project context.
Cross-project search-string inheritance: **none found**.

### 2.4 Workspace memory store

`studio-web/src/workspacePrefs.ts` — key `adept_ui_last_workspace`:

- **Now:** per-project map `{ [projectId]: workspace }` (`lastWorkspaceByProject` semantics).
- Legacy single-record shape `{ projectId, tab }` is migrated into the map on read.
- `NON_RESUME_WORKSPACES = { setup, home }` are never persisted and never returned — the
  Setup Wizard and the landing page cannot hijack the resume destination.
- Only consumer: `ProjectHome.tsx` "Continue Production" (intentional resume). Nothing else
  reads `loadLastWorkspace` — no silent consumer remains.

### 2.5 ProjectEditor routing effect

`ProjectEditor.tsx:528-548`:

```text
requested = resolveWorkspace(URL ?workspace|?tab)
next = requested || "home"        // NO loadLastWorkspace fallback — silent resume removed
```

Legacy `?tab=` and non-canonical aliases (`director` → `timeline`) are canonicalized in-place
with `navigate(..., { replace: true })` — the URL and the visible workspace always agree.

Save guard (`ProjectEditor.tsx:550-553`): workspace memory is only persisted when
`workspaceProjectId === id` — a workspace from project A can never be written into project
B's memory during a switch.

## 3. Root causes (historical) and repairs

| # | Root cause | Repair | Status |
|---|---|---|---|
| R1 | `ProjectEditor` fell back to `loadLastWorkspace(id)` when the URL had no workspace param — plain Open Project silently rerouted to the last workspace | `requested \|\| "home"`; resume only via the intentional Continue affordance which navigates with an explicit `?workspace=` param | FIXED (prior session), verified |
| R2 | `adept_ui_last_workspace` stored a single global `{projectId, tab}` record — cross-project contamination | Per-project map with legacy migration; setup/home excluded from resume | FIXED (prior session), verified |
| R3 | **Stale-render race:** on project switch, `refresh()` kept the previous project's `project` object while fetching the new one — the old project's data rendered under the new project's URL, and a foreign `selectedScene` id survived into the new project | `refresh()` now clears `project` up front when `id` differs from the loaded project (loading gate shows), and `selectedScene` is only kept if it exists in the newly loaded project | **FIXED this pass** (`ProjectEditor.tsx:484-498`) |

## 4. Final routing contract (locked)

1. **Open Project** (selector / list / card / palette) → `/project/<id>` landing. No workspace
   param, no silent resume. `requested || "home"`.
2. **Open Timeline** (explicit click) → `/project/<id>?workspace=timeline`.
3. **Resume-last-workspace** is an intentional, documented feature keyed per project
   (`lastWorkspaceByProject` map), exposed only as the "Continue Production" affordance on the
   landing page. It is never triggered by plain Open Project.
4. **Project switch never inherits** the old project's workspace query state, loaded data, or
   scene selection (stale-render guard).
5. **Deep links honored exactly:** bare URL → landing; `?workspace=timeline` → Timeline;
   refresh never converts one into the other; Back/Forward URL and visible workspace always
   agree.
6. The landing page is the bare URL — `go("home")` strips the workspace param rather than
   writing `?workspace=home`.

## 5. Regression evidence

- `studio-web/src/workspacePrefs.test.ts` — 7/7 unit tests (save/load, setup/home exclusion,
  legacy migration, per-project scoping, isolation).
- `tests/e2e/navigation/project-workspace-routing.spec.ts` — NAV-1..NAV-7 Playwright
  certification against live Beta (selector opens landing; explicit Timeline; return to
  Project; cross-project isolation A/B; deep links; refresh determinism; Back/Forward
  coherence). Results recorded in the final certification report.
