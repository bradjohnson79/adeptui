# Script Writer Story Document

Governing document for native Story inside Script Writer Standard.

**Supersedes (this behavior only):** the Script Writer simplification report’s rule that the Story button routes to Co-Director Story Express (`/co-director?contentTab=story`). Story Express remains the lightweight Co-Director planning surface. It is no longer the destination of Script Writer → Story.

## Product model

```
Co-Director
└── Story Express     lightweight planning / AI assistance

Script Writer Standard
├── Story             full editable story document
└── Script            screenplay document
```

Both Story surfaces read and write the same `story_entries` row (`project_story`). No `storyExpressText` / `storyWriterText` split. Legacy `story_documents` stays migration-only.

## Audit

| Area | Classification |
| --- | --- |
| `story_entries` + `/story-entries` | EXISTS — canonical |
| Co-Director Story Express (`StoryEntryEditor`) | EXISTS — connected |
| Co-Director live Story/Script context | EXISTS — `story_script_context_block` |
| Legacy `story_documents` / `StoryEditor` | STALE — fallback / unmounted |
| Script Writer Story button → Co-Director | DISCONNECTED — removed |
| Script Writer native Story document | was MISSING — added |

## Behavior

- `[Script] [Story]` switches the Script Writer canvas. Story never navigates away.
- Story is a formatted document (title, headings, paragraphs, bold/italic/underline, lists). Not screenplay formatting.
- Autosave writes `title` + `longSummary` (HTML) on the primary `project_story` entry.
- Story Express keeps logline / short summary as lightweight fields and edits the same `longSummary` document.
- A same-tab event keeps Express and Script Writer Story in sync when both are mounted.
- Co-Director chat still reads `story_entries` live; HTML treatment is flattened to text.

## Live verification (2026-09-11)

Project: Korri Anadriya / The Venture (`beffd3d8-791d-4adf-9c4d-681ec9d4efb0`). No new project created.

- Script Writer → Story stayed on `workspace=scriptwriter`. No `/co-director` navigation.
- Story document edited and persisted on `story_entries` (`679d445f…`). Reload showed `CERT_STORY_DOC_20260911`.
- Co-Director Story Express showed the same document.
- Co-Director chat quoted the live synopsis and named `EXT. EARTH'S HORIZON - SPACE` as the first script scene.
- Switching back to Script restored the unchanged screenplay and scene list.

Tests: `test_codirector_story_script_access.py` 12 passed; frontend `canonicalStory` + `scriptwriterStoryView` 7 passed.

## Verdicts

| Gate | Result |
| --- | --- |
| STORY NATIVE IN SCRIPT WRITER | PASS |
| NO CO-DIRECTOR NAVIGATION | PASS |
| FORMATTED STORY EDITOR | PASS |
| CANONICAL STORY AUTHORITY | PASS — `story_entries` only |
| STORY EXPRESS SYNC | PASS |
| CO-DIRECTOR STORY ACCESS | PASS |
| CO-DIRECTOR SCRIPT ACCESS | PASS |
| SAVE / RELOAD | PASS |
| SCRIPT MODE REGRESSION | PASS |

**GO — SCRIPT WRITER STORY DOCUMENT VERIFIED**

`COMFY BEFORE: PID 45624 / healthy`  
`COMFY AFTER: PID 45624 / healthy`  
`COMFY RESTARTED?: NO`
