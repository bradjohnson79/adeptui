# Assets, Jobs, Library, and Resources Audit

## Executive conclusion

The backend already has one Asset and one Job table. Product fragmentation comes from inconsistent output registration, multiple browse/queue UIs, mixed-ID graph edges, and Marketplace framing. Job rows persist, but the in-memory queue does not recover on restart.

## Classification

| System | Class | Action |
|---|---|---|
| `assets` | A/B | Keep; canonicalize all outputs |
| `jobs` | A/B | Keep; type/recover/link Generation |
| `asset_versions` | B | Preserve |
| `asset_edges` mixed graph | C/D | Dual-read then replace with typed lineage |
| LibraryPanel | B | Convert to filtered unified Library |
| AssetTray | C | Replace list with ReferencePicker/Library drawer |
| Embedded JobPanel | C/D | Keep compact status; add Jobs workspace |
| Marketplace install approval | B | Reframe as Resources |
| Marketplace storefront UX | D | Deprecate |
| LoRA stack | B/D | Preserve data; wire through workflow adapter |

## Inconsistent Asset ingestion

- Uploads and most ImageGen/Tools outputs create Asset rows.
- Scene renders and lipsync often remain only as Scene paths.
- Profile media is a separate `media_path`.
- asset roots are split.
- global assets retain a creator project FK and cross-project tag resolution is incomplete.

## Job reliability

- One `jobs` table serves all current job kinds.
- UI polls from many components; no authoritative Jobs tab.
- queued/running database rows are not re-enqueued/reconciled after API restart.
- status vocabularies are not shared enums.

## Broken connections

1. Library graph assumes every edge endpoint is an Asset.
2. Scene/lipsync outputs may never enter Library.
3. LoRA selection does not change Comfy graphs.
4. installed Resources are not automatically synchronized to Comfy paths.
5. project duplication omits Assets and satellites.
6. queued/running jobs become stuck/orphaned across restart.
7. dashboard job cards cannot open a Jobs workspace.

## Target consolidation

- Asset is canonical media.
- Library is one filtered view; domain workspaces use compact pickers backed by it.
- Jobs is one workspace; headers/workspaces use shared JobProgress.
- Resources owns installed models, LoRAs, workflows, nodes, dependencies and compatibility.
- Lineage uses typed IDs, not a new graph database.

## Safe/unsafe removals

Safe only after parity: Marketplace wording, duplicate embedded JobPanel lists, Asset Graph sidebar, empty storefront categories.  
Unsafe now: Asset/Job tables, worker handlers, Library API, AssetTray drag/upload, resource state, asset versions, sequence/editor tables.

## Migration sequence

1. Startup reconciliation for queued/stale running jobs.
2. Register every output as Asset.
3. Add Library filters/source lineage.
4. Add Jobs workspace over current API.
5. Rename Marketplace→Resources while retaining endpoints/state.
6. Migrate mixed graph edges to typed lineage, then remove graph UI.

## Smoke tests

Upload/generate/render/lipsync → Library; global asset lookup; queued job restart; cancel; Resource install and LoRA workflow effect; Director→Editor lineage; persisted status after restart.

## Files inspected / unchanged

DB/graph/worker/routers/resource service and all Library/AssetTray/Job/Marketplace/LoRA consumers. No jobs, installs, or files were changed.

