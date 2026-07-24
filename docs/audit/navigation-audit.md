# Routing, Navigation, and Workspace Audit

## Current map

React Router exposes only:

- `/` → Home
- `/project/:id` → ProjectEditor
- `*` → `/`

Workspace state is stored in React + `adept_ui_last_workspace`, not the URL.

## Workspace classification

| Current ID | Destination | Class | Action |
|---|---|---|---|
| `home` | Project Dashboard | B | Keep outside main nav |
| `setup` | Setup utility | C | Keep button-only |
| `settings` | Settings | A | Keep |
| `script` | Story | B | Rename shell |
| `shotlist` | Story / Shot List view | C | Redirect |
| `mastersheet` | Scene Sheets | B | Rename + migrate |
| `spatial` | Scene Sheet / Blocking | D | Hide after blocking parity |
| `imagegen` | Generate / Image | C | Compatibility alias |
| `txt2vid` | Generate / Text to Video | C | Compatibility alias |
| `one` | Generate / Frames | C | Compatibility alias |
| `three` | Generate / Frames | C | Compatibility alias |
| `avatar` | Generate / Avatar | C | Compatibility alias |
| `generate` | Generate/Director orchestration | D | Resolve naming collision |
| `director` | Director | A | Keep |
| `audiostudio` | Audio | B | Rename label; deepen later |
| `editor` | Editor | B | Keep foundation |
| `profiles` | Profiles | B | Keep; unify data |
| `tools` | Profiles/Generate actions | D | Hide after parity |
| `library` | Library | A | Keep |
| `marketplace` | Resources | B | Rename/reframe |
| missing `jobs` | Jobs | F | Add workspace |

## Target navigation

- **Create:** Co-Director, Story, Scene Sheets, Generate, Director
- **Finish:** Audio, Editor
- **Organize:** Profiles, Library, Jobs
- **Additional:** Resources, Settings

## Broken connections

1. `Home.tsx` writes `?tab=...`; `ProjectEditor.tsx` never reads it.
2. Initial `"home"` state can overwrite saved last-workspace state before restore.
3. `adept_focus_scene` and `adept_director_sequence_id` are written but not consumed.
4. `AssistantPanel` does not provide router navigation to action execution.
5. Home Co-Director cannot execute project-workspace navigation.
6. Job cards route to Director because there is no Jobs workspace.

## Compatibility plan

Introduce one central workspace registry:

- canonical IDs, target group, label, feature flag, compatibility aliases
- query precedence: canonical `workspace`/legacy `tab` → handoff context → last workspace → `home`
- legacy aliases remain for two releases
- deprecated links show a non-blocking “Moved to…” banner
- `shotlist` redirects silently to Story’s Shot List view
- `spatial` redirects to Scene Sheet blocking only after migration parity

## Data ownership conflicts

- localStorage, query strings, props, and sessionStorage all compete for workspace/selection state.
- nested Director `settings` collides semantically with project Settings.
- Co-Director context and workspace routing are separate systems.

## Risks

- Breaking saved tabs/bookmarks during renames
- Hiding Spatial before blocking migration
- Unifying Generate before adapter parity
- Recipes retaining deprecated tab IDs

## Smoke tests

- Valid/invalid `?tab=` resolution
- Last workspace restoration per project
- Every current tab renders without “Unknown workspace”
- Editor → correct Director scene/sequence
- Home Explore → intended workspace
- Legacy aliases → canonical target and mode
- Final navigation contains only approved items

## Files inspected / unchanged

Inspected `App.tsx`, `workspacePrefs.ts`, `ProjectEditor.tsx`, `Home.tsx`, `ProjectHome.tsx`, menus/chrome, workspaces, Co-Director executor. No source files were modified.

