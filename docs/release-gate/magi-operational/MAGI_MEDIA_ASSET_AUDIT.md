# MAGI Media & Asset Audit

**Status:** Read-only Phase 0 audit.
**Date:** 2026-08-08

## 1. How MAGI consumes Adept UI assets

- **Source of truth:** `project.assets` passed as a prop (`ProjectEditor.tsx:732`), filtered into `videos/images/audioAssets/mediaAssets` (`MagiEditorWorkspace.tsx:276-279`).
- **Media URL:** `api.assetUrl(asset.id)` → `/api/assets/{assetId}/file` (`api.ts:5729`), used for thumbs (`:979`), viewer (`:1217-1218`), compare (`:1260-1266`).
- **Clip references assets by ID only:** `MagiClip.assetId: string` (`types.ts:34`). No copied paths in sequence documents.

## 2. Placement path (drag/drop)

- Click asset card → preview (`:968-971`).
- Drag sets `application/x-adept-asset` + `application/x-adept-kind` (`:972-976`).
- Timeline lane `onDragOver`/`onDrop` reads asset id; Shift ⇒ Overwrite, else Insert (`MagiSequenceTimeline.tsx:181-193`).
- `handleDropAsset` (`MagiEditorWorkspace.tsx:692-712`) → engine Insert/Overwrite → clip with heuristic duration (`engine.ts:104-109`: video 5s, audio 4s, image 3s). **Real media duration is never read.**

## 3. Asset lineage — current state

Conceptually required:

```
Project → Asset → MAGI clip → track → sequence → output
```

**Current reality:**
- Clips store only `assetId` — no `batchBlockId`, no `generationId`, no `takeId`, no source clip id.
- **`save_sequence` performs ZERO asset validation** (`store.py:81-97`): never checks asset exists, belongs to project, or is on disk. Stale/orphan `assetId`s persist silently.
- Overlay compose path **does validate** (`composition/service.py:20-27`): queries `Asset.id` + `Asset.project_id`, checks file exists; missing → `source_missing`.
- Overlay lineage is rich: provenance block (`service.py:85-105`), `parent_asset_id`, `derived_from` graph edge, version node (`lineage.py:48-81`).
- **Sequence has no lineage model at all.**

## 4. Cross-project leakage risk

- Sequence saves don't check project ownership of assets → a clip could reference another project's asset ID. Server must reject.
- Media pane caps grid at 18 assets via `slice(0, 18)` (`:1019`) — display limit only, not isolation.

## 5. Failed media handling — MISSING

- `<img>`/`<video>` elements have **no `onError`** (`:979, 1284-1286`, compare `:1260-1266`).
- No failed-clip badge, no replace/remove flow, no editor-recovery.
- Timeline clips are label-only blocks (no thumbnails) so no broken images there, but viewer will show a broken asset silently.

## 6. Clip identity

- **Stable IDs** via `engine.ts` `uid()` (`:9-11`): `clip_*`/`trk_*`/`mk_*`/`seq_*`. Timeline keys by `clip.id` (`MagiSequenceTimeline.tsx:198-200`); selection is ID-based. Not index-based. ✓
- **Exceptions:** FX/ADJ pass clips use ad-hoc `clip_fx_…`/`clip_adj_…` IDs and duplicate the base clip's `assetId` (`MagiEditorWorkspace.tsx:808, 832`).

## 7. Required repairs (m2)

1. Server validates every `clip.assetId`: exists, belongs to `project_id`, cross-project rejection with structured error.
2. Add optional lineage fields to `MagiClip`: `batchBlockId`, `generationId`, `takeId`, `sourceClipId`, `sceneId` (for W46-sourced clips).
3. Failed-media state: `onError` → failed-clip badge in viewer + timeline; editor remains usable; creator can replace/remove; save still works.
4. Preserve stable clip IDs; stop ad-hoc FX/ADJ id generation (route through `uid()`).

## 8. Media kinds supported

- image / video / audio all placeable. Audio renders placeholder in viewer (expected — transport focus).
- Generated outputs (via ImageEditIntent) and Timeline outputs arrive as `Asset` rows — MAGI treats them uniformly by `assetId`; lineage fields disambiguate origin once added.
