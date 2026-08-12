# TIMELINE MULTI-BATCH STATE AUDIT

**Milestone:** Timeline Multi-Batch + Preview Monitor — Mandatory GO Closure
**Audit type:** Read-only architecture audit (independent)
**Date:** 2026-08-07
**Status:** ROOT CAUSE IDENTIFIED

## 1. Executive summary

The batch/clip loss defect is caused by a **split persistence model with a destructive legacy write path**. Timeline state lives in one JSON blob (`scenes.director_json`) but two incompatible sub-models:

- **Legacy tracks** (`DirectorTimeline`: `image_clips`, `prompt_segments`, etc.) — top-level JSON fields, mutated by `PUT /director`.
- **W46 master** (`SceneTimelineMaster`: `batchBlocks[]`) — `director_json.timelineMaster`, mutated by W46 APIs via `save_master()`.

The defect chain for "Batch 1 → add Batch 2 → add image → things vanish":

1. Add Batch 2 uses the W46 path (`directorTimelineAddBatch` → `save_master`), which correctly merges `timelineMaster` + legacy tracks.
2. Add image uses the legacy path (`DirectorTracks.save` → `PUT /director`), which **replaces the entire `director_json`** with only `DirectorTimeline` fields — **`timelineMaster` and `timelineWorkspace` are erased**.
3. `afterMutation()` calls `refreshMaster()` → `GET /director-timeline/.../master` → `load_master()` sees no `timelineMaster`, runs migration, and **re-derives a single "Batch 1"** from `image_clips`.
4. Batch 2+ is permanently lost from persisted state.

Image clip disappearance is the same write path plus a **non-aborted reload race** in `DirectorTracks`: concurrent `getDirector` responses can overwrite newer local/PUT state with stale data.

This is not speculation — the W46 Co-Director path already does the correct merge for image adds; the Timeline UI does not.

## 2. Data model — batches are a collection, not fixed slots

Backend W46 contracts — dynamic `batchBlocks` list, stable IDs:

```177:208:studio-api/app/director_timeline_w46/contracts.py
class BatchBlock(BaseModel):
    """Stable production container — ID never changes when approved media changes."""
    id: str = Field(default_factory=lambda: _nid("bb_"))
    sceneId: str
    order: int = 0
    label: str = "Batch"
    ...
    legacyImageClipIds: list[str] = Field(default_factory=list)

class SceneTimelineMaster(BaseModel):
    ...
    batchBlocks: list[BatchBlock] = Field(default_factory=list)
```

Frontend parity — `studio-web/src/timelineMaster/contracts.ts` lines 132–166.

Legacy Scene type — no batch fields; batches only in embedded JSON:

```30:58:studio-web/src/types.ts
export interface Scene {
  ...
  director_json?: string;
  ...
}
```

Legacy director tracks — separate model in `director_timeline.py`:

```112:129:studio-api/app/director_timeline.py
class DirectorTimeline(BaseModel):
    media_mode: Literal["image", "video"] = "image"
    duration_sec: float = 5.0
    image_clips: list[ImageClip] = Field(default_factory=list)
    video_clips: list[TimelineClip] = Field(default_factory=list)
    prompt_segments: list[PromptSegment] = Field(default_factory=list)
    ...
```

DB — single `director_json` TEXT column (`studio-api/app/db.py` line 80).

## 3. Clip identity — stable unique IDs, not array indices

Backend — UUID-based defaults:

```13:14:studio-api/app/director_timeline.py
def _nid() -> str:
    return uuid.uuid4().hex[:10]
```

Frontend — random hex IDs at creation:

```117:119:studio-web/src/components/DirectorTracks.tsx
function nid() {
  return Math.random().toString(36).slice(2, 10);
}
```

React keys use stable `clip.id` / `batch.id` (not indices) — e.g. lines 1411, 1445 in `DirectorTracks.tsx`. Keys are not the cause.

## 4. Reducer / state management — dual writers, full JSON replacement on legacy path

DirectorTracks keeps local `tl` state; `save()` optimistically updates then calls legacy PUT:

```561:580:studio-web/src/components/DirectorTracks.tsx
  const save = async (next: DirectorTimeline) => {
    const normalized = {
      ...next,
      lipsync: { tracks: normalizeLipSyncTracks(next.lipsync?.tracks) },
    } as DirectorTimeline;
    setTl(normalized);
    setSaving(true);
    try {
      await api.putDirector(project.id, scene.id, normalized);
      setSaveError(null);
      onChange();
    } catch (e) {
      ...
    } finally {
      setSaving(false);
    }
  };
```

Image add goes through that path:

```755:768:studio-web/src/components/DirectorTracks.tsx
  const addImageFromLibrary = async (assetId: string) => {
    ...
    await save({ ...tl, media_mode: "image", image_clips: [...imageClips, clip] });
    selectClip("imageClip", clip.id);
  };
```

Batch add uses a different API (safe merge path):

```1153:1153:studio-web/src/components/DirectorTracks.tsx
                    void api.directorTimelineAddBatch(project.id, scene.id, { plannedDuration: duration }).then(onChange);
```

TimelineEditorShell `mutateTimeline` — same destructive PUT:

```191:205:studio-web/src/components/timeline-master/TimelineEditorShell.tsx
  const mutateTimeline = useCallback(
    async (mutator, opts) => {
      ...
      const current = (await api.getDirector(project.id, selected.id)) as DirectorTimeline;
      const next = mutator(current);
      ...
      await api.putDirector(project.id, selected.id, next);
      if (opts?.refresh === false) return;
      await afterMutation();
    },
    [afterMutation, project.id, selected],
  );
```

There is no single reducer — two parallel mutation gateways.

## 5. Scene save/update APIs — `PUT /director` drops embedded master

Destructive write (root mechanism):

```933:944:studio-api/app/routers/api.py
@router.put("/projects/{project_id}/scenes/{scene_id}/director", response_model=DirectorTimeline)
def put_director(project_id: str, scene_id: str, body: DirectorTimeline, db: Session = Depends(get_db)):
    ...
    body = ensure_tags(body)
    scene.director_json = dumps_director_timeline(body)
    legacy = sync_legacy_fields_from_director(body)
    for k, v in legacy.items():
        setattr(scene, k, v)
    db.commit()
    return body
```

`dumps_director_timeline` serializes only `DirectorTimeline` — no `timelineMaster`:

```199:200:studio-api/app/director_timeline.py
def dumps_director_timeline(tl: DirectorTimeline) -> str:
    return tl.model_dump_json()
```

Correct merge path (what batch APIs use):

```103:143:studio-api/app/director_timeline_w46/store.py
def save_master(...):
    ...
    base = json.loads(dumps_director_timeline(director_tl))
    ...
    base["timelineWorkspace"] = ws
    for batch in master.batchBlocks:
        batch.updatedAt = _now()
    embedded = embed_master_into_director_dict(base, master)
    scene.director_json = json.dumps(embedded)
    db.add(scene)
    db.commit()
```

Co-Director image add also uses `save_master` (correct reference implementation):

```1280:1290:studio-api/app/codirector/tools/handlers/director_timeline_tools.py
    director_tl.image_clips = clips + [clip]
    store.save_master(
        ctx.db,
        ctx.project_id,
        scene_id,
        bundle["master"],
        director_tl=director_tl,
        workspace=workspace,
        bump_revision=True,
    )
```

## 6. Persistence hydration — re-migration collapses multi-batch → single batch

When `timelineMaster` is missing, migration builds one batch from legacy clips:

```57:62:studio-api/app/director_timeline_w46/migration.py
    if existing and existing.batchBlocks:
        existing.migratedFromDirectorJson = True
        existing.migrationNote = "Preserved existing BatchBlocks; ..."
        return existing
```

If `existing` is `None` (because `PUT /director` wiped it):

```64:127:studio-api/app/director_timeline_w46/migration.py
    batches: list[BatchBlock] = []
    if tl.image_clips or tl.prompt_segments or tl.video_clips:
        ...
        batch = BatchBlock(
            sceneId=scene_id,
            order=0,
            label="Batch 1",
            ...
            legacyImageClipIds=[c.id for c in tl.image_clips],
        )
        batches.append(batch)
```

Every `GET /master` persists migration (side effect on read):

```81:92:studio-api/app/director_timeline_w46/store.py
def load_master(...):
    ...
    master, tl, _data = load_or_migrate_scene_master(...)
    # Persist migration if newly created
    save_master(db, project_id, scene_id, master, director_tl=tl)
```

## 7. useEffect synchronization — reload clobbers local edits

DirectorTracks reload on `scene.director_json` + `reloadKey` — full state replacement, no abort/version guard:

```424:470:studio-web/src/components/DirectorTracks.tsx
  useEffect(() => {
    if (!scene) return;
    let cancelled = false;
    api
      .getDirector(project.id, scene.id)
      .then((d) => {
        if (cancelled) return;
        const next = { ...d, image_clips: freeImageClips(d as DirectorTimeline), ... };
        setTl(next);
        ...
      })
    ...
  }, [project.id, scene?.id, scene?.director_json, reloadKey]);
```

afterMutation bumps `reloadKey` after every legacy save:

```185:189:studio-web/src/components/timeline-master/TimelineEditorShell.tsx
  const afterMutation = useCallback(async () => {
    await refresh();
    await refreshMaster();
    setReloadKey((value) => value + 1);
  }, [refresh, refreshMaster]);
```

Race scenario: Batch-add triggers reload A; image-save triggers reload B; if A completes after B, `setTl` restores pre-image state → clip vanishes in UI (even if DB has the clip).

## 8. Undo/redo — DirectorTimeline only, batches not included

```87:88:studio-web/src/components/timeline-master/TimelineEditorShell.tsx
  const [undoStack, setUndoStack] = useState<DirectorTimeline[]>([]);
  const [redoStack, setRedoStack] = useState<DirectorTimeline[]>([]);
```

Undo/redo calls `putDirector` (lines 225–226) → same `timelineMaster` wipe. Undoing a clip edit can silently destroy batches.

## 9. Secondary risks

| Risk | Mechanism |
|------|-----------|
| Any legacy PUT wipes master | Also hit from `FrameModes.tsx`, `VisualReferencesPanel.tsx`, `ProjectEditor.tsx`, playhead focus handler, undo/redo |
| Read-modify-write clobber | `mutateTimeline` GET → mutate → PUT; concurrent edits drop each other's clips |
| GET /master always writes DB | `load_master` auto-`save_master` on every fetch can persist bad migrations |
| No revision/token on legacy PUT | W46 workspace has `timelineRevision`; legacy PUT has no conflict detection |
| Batch/image decoupling | Visual-track adds don't bind clips to selected batch; multi-batch planning semantics inconsistent |
| Frontend clip IDs use `Math.random()` | Weaker than backend UUIDs; collision unlikely but not impossible |

## 10. Architectural note: image clips are scene-global, not per-batch

Visual-track images live in `director_json.image_clips`. Batches live in `timelineMaster.batchBlocks`. Adding via the Visual track does NOT update `legacyImageClipIds` or batch `sourceAnchors`. Batch-scoped images use Inspector "Start Image" → `directorTimelinePatchBatch` (safe path, lines 378–401 in `TimelineInspector.tsx`).

This decoupling is a core reason the per-batch ownership model (Phase 2 of the plan) is required: until clips are owned by batches, adding a visual to one batch can affect scene-global state that other batches reference.

## 11. Files / functions that must change

### Backend (critical)

| File | Function | Change |
|------|----------|--------|
| `studio-api/app/routers/api.py` | `put_director` (lines 933–944) | Merge into existing `director_json` via `save_master()` pattern; never replace entire blob |
| `studio-api/app/director_timeline_w46/store.py` | `save_master` | Expose shared helper for legacy-track updates (director_tl + preserve master/workspace) |
| `studio-api/app/director_timeline_w46/store.py` | `load_master` (lines 91–92) | Stop auto-persisting on every GET unless migration actually changed state |
| `studio-api/app/director_timeline_w46/migration.py` | `migrate_director_to_master` | Defensive: never collapse existing multi-batch state when re-migrating |

### Frontend (critical)

| File | Function | Change |
|------|----------|--------|
| `studio-web/src/components/DirectorTracks.tsx` | `save` (561–580) | Route through unified W46 bundle save (or backend merge PUT), not raw `putDirector` |
| `studio-web/src/components/DirectorTracks.tsx` | reload `useEffect` (424–470) | AbortController / request generation counter to prevent stale `getDirector` overwrites |
| `studio-web/src/components/timeline-master/TimelineEditorShell.tsx` | `mutateTimeline`, `applyHistorySnapshot` | Same unified save path |
| `studio-web/src/api.ts` | `putDirector` / new helper | Add API that updates legacy tracks without dropping `timelineMaster` |

### Frontend (follow-on)

| File | Notes |
|-------|-------|
| `studio-web/src/components/timeline-master/TimelineInspector.tsx` | `updateClip`, `mutateTimeline` callers |
| `studio-web/src/components/FrameModes.tsx` | Direct `putDirector` usage |
| `studio-web/src/components/VisualReferencesPanel.tsx` | Direct `putDirector` usage |
| `studio-web/src/pages/ProjectEditor.tsx` | Direct `putDirector` usage |

### Reference implementation to mirror

`studio-api/app/codirector/tools/handlers/director_timeline_tools.py` — `apply_propose_add_image_clip` (lines 1255–1290): updates `director_tl.image_clips` AND calls `store.save_master()` preserving `bundle["master"]`.

## 12. Summary diagram

```mermaid
sequenceDiagram
    participant UI as DirectorTracks
    participant BatchAPI as POST /batches
    participant LegacyPUT as PUT /director
    participant MasterGET as GET /master
    participant DB as director_json

    UI->>BatchAPI: Add Batch 2
    BatchAPI->>DB: save_master (merge timelineMaster OK)
    UI->>LegacyPUT: Add image clip
    LegacyPUT->>DB: dumps_director_timeline ONLY (timelineMaster LOST)
    UI->>MasterGET: afterMutation refreshMaster
    MasterGET->>DB: migrate to single Batch 1 then save_master
    Note over UI,DB: Batch 2 gone; image may vanish from UI via stale GET race
```

## 13. Verdict

The primary root cause is **`PUT /director` full replacement of `director_json` without preserving `timelineMaster`**, triggered by every Visual-track / Inspector clip mutation, followed by **`load_master` re-migration collapsing batches to one**. Image disappearance is the same write path plus **un-guarded concurrent `getDirector` reloads** in `DirectorTracks`.

The fix requires persistence unification (Phase 1) and per-batch clip ownership (Phase 2) so that adding media to one batch can never mutate or delete another batch's state at the data layer.
