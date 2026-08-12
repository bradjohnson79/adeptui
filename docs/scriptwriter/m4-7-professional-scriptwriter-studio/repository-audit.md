# M4.7 Repository Audit — Professional Scriptwriter Studio

**Starting branch:** `phase2/m42-director-timeline-master`  
**Feature branch:** `feature/m4-7-professional-scriptwriter-studio`  
**Starting SHA:** `f758744`  
**Date:** 2026-08-01

## Current architecture

| Surface | Path | Reality |
| --- | --- | --- |
| Scriptwriter tab | `studio-web/.../ScriptwriterWorkspace.tsx` | Generate-and-persist form only |
| Script/Storyboard | `studio-web/.../ScriptStoryboardWorkspace.tsx` | Plain textareas; save-on-blur; 3-pane |
| Backend store | `studio-api/app/script_storyboard.py` | `script_docs` / `script_segments` / `storyboard_panels` |
| Co-Director | `script.list\|get\|search`, `propose_script_document` | Reads + create proposal; no structured edit tools |
| Import | Plain-text heuristics only | No Fountain/FDX/PDF |
| Revisions | Integer counters | No revision sets / compare |
| Transactions | None | Multi-element ops not undoable |

## Working features

- Template generation via Generation Tools → segments + Library asset
- Segment CRUD + storyboard panels
- Plain-text import (`INT./EXT.` / ALL-CAPS speaker)
- Co-Director script read tools + propose create

## Gaps / risks

- No structured `ScriptDocument` / typed elements
- No TipTap/ProseMirror in `studio-web` (to be added)
- `activeDocumentId` never wired from Scriptwriter
- Storyboard `send-director` creates Scene rows (wrong Timeline handoff)
- Migration must preserve existing segments as backup

## Reuse

- `import_plain_text` heuristics
- Bible `ProposalService`, Co-Director `MutationHandler`, m29 timeline propose
- Character identity / bible character context for voice
- PI as visualization side-channel only
