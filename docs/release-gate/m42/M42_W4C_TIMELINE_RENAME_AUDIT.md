# M42 Wave 4C — Timeline Rename Audit

| Field | Value |
|---|---|
| **Phase** | M42 Wave 4C Director → Timeline |
| **Branch** | `phase2/m42-timeline-product-rename` |
| **Rule** | Rename product-facing Director only; KEEP Co-Director and ordinary English |

## Classification legend

| Class | Meaning |
|---|---|
| RENAME | User-facing product label → Timeline |
| KEEP | Co-Director / film role / directory / direction / historical |
| COMPATIBILITY_ALIAS | Accept `director` workspace id → resolve to `timeline` |
| MIGRATE | Persistence keys / defaults rewrite on read |
| REVIEW_REQUIRED | LEFT_STABLE internals documented |

## Inventory (priority)

| Location | Match | Class |
|---|---|---|
| `studio-web/src/core/workspaces.ts` `director` entry | Product registry | MIGRATE → `timeline` + alias |
| `StudioLaunchCards.tsx` | Director Generator card | RENAME |
| `Home.tsx` explore tile | Director | RENAME |
| `ProjectHome.tsx` | Director labels / default resume | RENAME + MIGRATE |
| `ProjectEditor.tsx` | Director shell / go("director") | RENAME + COMPATIBILITY_ALIAS |
| `LibraryPanel.tsx` | Open Director | RENAME |
| `codirector/types.ts` / `execute.ts` | Open Director / Send to Director | RENAME |
| `i18n/.../navigation.json` | director label | RENAME |
| `dashboardImages.ts` / aurora | director imagery | MIGRATE path labels |
| `api.ts` `getDirector` / scene `/director` | Shot-direction API | REVIEW_REQUIRED LEFT_STABLE |
| `DirectorTracks.tsx` etc. | Component filenames | REVIEW_REQUIRED LEFT_STABLE |
| Co-Director* strings | Product name | KEEP |
| Historical release-gate docs | Past milestones | KEEP (“Director, now named Timeline”) |
| Analytics event ids | Stable IDs | KEEP (Option A) |

## Non-goals confirmed

No Timeline runtime redesign; no Co-Director rename; no blind global replace.
