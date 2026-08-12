# Timeline State & Persistence Audit

- **Date:** 2026-08-07
- **Auditor:** Read-only code auditor (subagent, GPT 5.4)
- **Scope:** W46 SceneTimelineMaster state persistence — batch lifecycle, per-batch clip ownership, save/autosave/reload, stale fetch, undo/redo isolation, migration idempotency, scene/project switching, mandatory invariants.
- **Repo:** `C:\AdeptFilmWorks\AIVideoStudio` (current code; backups under `backup/` ignored)
- **Method:** End-to-end code reading of the listed paths plus read-only Python probes confirming pure-function behavior. No repo/DB/service mutation. Anything not provable by reading is marked **NEEDS RUNTIME VERIFICATION**.

## Per-area verdict table

| # | Area | Verdict | Evidence |
|---|------|---------|---------|
| 1 | Batch creation / deletion / reorder / selection / batch ID stability | **OK** | `service.py:48-81` (add), `84-114` (duplicate), `117-146` (delete), `orchestrator.py:455-537` (touch); `BatchBlock.id` default-factory and never reassigned (`contracts.py:213`); `order` is mutable presentation field, `id` is immutable identity. |
| 2 | Clip IDs and per-batch ownership (image/prompt/audio/SFX/camera) | **OK** | `BatchClip.id` stable (`contracts.py:185`); `orchestrator.add_clip_to_batch` appends only to target batch array (`orchestrator.py:540-581`); `touch_batch_config` `setattr` only on the resolved batch object (`orchestrator.py:507-513`). Probe confirms legacy `legacyClipId` audit (`migration.py:122-191`). |
| 3a | `PUT /director` merge behavior | **OK** | `api.py:934-952` uses `dumps_director_timeline_preserving_embedded` (`director_timeline.py:203-227`); probe PROBE3 confirms `timelineMaster` survives. |
| 3b | `load_master` / `save_master` | **OK (with caveat)** | `store.py:81-106` NO_AUTO_PERSIST_ON_READ only persists when no embedded master; `save_master:109-149` preserves DirectorTimeline + other keys + workspace + new master. Caveat: relies on `timelineMaster` being present in blob — see Defect D1. |
| 3c | Migration collapse guards (`NEVER_COLLAPSE_EXISTING_MULTI_BATCH`) | **OK** | `migration.py:41-60` guard; probe PROBE1 confirms multi-batch preserved. |
| 3d | **Non-`PUT /director` writers of `scene.director_json`** | **DEFECT (D1)** | `assistant.py:409`, `codirector/m29/editing/service.py:257` (+undo/redo 184-197), `codirector/m29/timeline/service.py:229`, `codirector/m29/audio/service.py:158` all use plain `dumps_director_timeline(tl)` and wipe `timelineMaster`. Probe PROBE4/PROBE5 confirms the collapse mechanism. |
| 4 | Stale fetch handling in `DirectorTracks.tsx` | **OK** | `DirectorTracks.tsx:371-375` `loadTokenRef` generation token; `430-435` discards late responses. |
| 4b | Stale fetch in other Timeline loaders (`TimelineEditorShell.refreshMaster`, `Timeline.tsx`) | **NEEDS RUNTIME VERIFICATION** | `TimelineEditorShell.tsx:105-119` `refreshMaster` has no generation token; `Timeline.tsx:27-33` fans out GET /master across all scenes. No stale-guard; races are plausible but not provably harmful by reading alone. |
| 5 | Undo/redo isolation (track-level undo never rewrites batch state) | **OK (Timeline shell)** / **DEFECT (D2, m29 editing)** | `TimelineEditorShell.tsx:88-89,202-258` undo/redo operates on `DirectorTimeline` and persists via `api.putDirector` (merge path) — batch state untouched. But `m29/editing/service.py:181-204,206,257` undo/redo uses plain `dumps_director_timeline` snapshots that contain no `timelineMaster`; both undo and redo collapse batch state (D2). |
| 6 | Migration idempotency + `legacyClipId` audit trail | **OK** | `migration.py:41-60` idempotent guards; `BatchClip.legacyClipId` (`contracts.py:199-201`) and `BatchBlock.migrationMetadata` (`contracts.py:237-239`, `migration.py:192-203`) record original IDs/rule. Probe PROBE2b confirms. |
| 6b | Edge: `migratedFromDirectorJson=True` with empty `batchBlocks` | **NEEDS RUNTIME VERIFICATION (low)** | `migration.py:55-60`: empty-batchBlocks existing master falls through to re-migration (PROBE6). Unlikely in practice (migration always emits ≥1 batch) but not guarded. |
| 7 | Scene switching / project switching state handling | **OK** | `TimelineEditorShell.tsx:126-136` resets selection/playhead/undo and re-fetches master on `selectedSceneId` change; `ProjectEditor.tsx:105-107` resets playhead on scene change. |
| 8a | Invariant: adding media to Batch N never modifies unrelated batches | **OK** | `orchestrator.py:540-581` (add_clip_to_batch) and `507-513` (touch) mutate only the target `batch` object; `_batch_map` lookup isolates the target. |
| 8b | Invariant: reordering never changes immutable batch identity | **OK** | All reorder paths (`service.py:74-79,107-112,127-130`) mutate `order`, never `id`. |
| 8c | Invariant: reload never collapses multi-batch state | **DEFECT (D1)** | Holds only when `timelineMaster` is present in the blob. The D1 writer paths wipe it; the next `load_master` (`store.py:96-98`) re-migrates and persists a single Batch 1 (PROBE5). |

## Defect details

### D1 — Non-`PUT /director` writers wipe embedded `timelineMaster`, causing multi-batch collapse on next reload

- **Severity:** High (violates mandatory invariant 8c; silently destroys creator batch state)
- **Root cause:** Several backend writers persist `scene.director_json` with the plain serializer `dumps_director_timeline(tl)` instead of the merge helper `dumps_director_timeline_preserving_embedded(tl, scene.director_json)`. The plain serializer emits only `DirectorTimeline` fields (`director_timeline.py:199-200`), dropping the embedded `timelineMaster` and `timelineWorkspace` keys. The `PUT /director` milestone fix (`api.py:940-947`) was applied to exactly one writer; the others were missed.
- **Collapse mechanism (proven by probe PROBE4/PROBE5):**
  1. A writer sets `scene.director_json = dumps_director_timeline(tl)` → blob no longer contains `timelineMaster`.
  2. Next `GET /director-timeline/.../master` → `store.load_master` (`store.py:81-106`) → `load_or_migrate_scene_master` → `extract_master_from_director_dict` returns `None` (`migration.py:247-256`) → `migrate_director_to_master` with `existing=None` re-derives a **single "Batch 1"** from `image_clips`/`prompt_segments` (`migration.py:69-223`).
  3. `load_master` sees `existing_master = data.get("timelineMaster")` is `None` → calls `save_master` (`store.py:96-98`) → **collapsed single-batch state is persisted**, cementing the loss.
- **Affected writers (file:line):**
  - `studio-api/app/assistant.py:409` — `apply_scene_setup` → reachable via `POST /api/assistant/apply-setup` (`api.py:1423-1444`).
  - `studio-api/app/codirector/m29/editing/service.py:257` — `EditingService.execute_job` → reachable via executive handler `_handle_edit_apply` (`executive/handlers.py:670-673`) and `POST /api/codirector/m29/editing/apply` (`m29/api.py:579-583`).
  - `studio-api/app/codirector/m29/timeline/service.py:229` — `TimelineService.apply` → reachable via `POST /api/codirector/m29/timeline/{proposal_id}/apply` (`m29/api.py:557-561`).
  - `studio-api/app/codirector/m29/audio/service.py:158` — `_write_scene_clip` (called by `AudioService.place_cue`) → reachable via `POST /api/codirector/m29/audio/place-cue` (`m29/api.py:405-408`) **and** via the modern Audio Studio placement flow `audio_studio/service.py:629-652` and `generation_tools/ops.py:333`.
- **Reproduction reasoning:** Build a scene with ≥2 batches via the Timeline UI; persist. Trigger any of the above writers (e.g., place approved audio from Audio Studio, or apply an m29 editing proposal). Reload the Timeline. `GET /master` re-migrates and persists a single Batch 1; all other batches and their clips/snapshots/jobs are gone from the persisted blob.
- **Note:** `load_timeline_bundle` (`service.py:21-41`) also re-migrates but does **not** persist on its own; however `delete_batch` (`service.py:117-146`) calls `load_timeline_bundle` and then `save_master`, so a delete after a wipe would likewise persist the collapsed master.

### D2 — m29 editing undo/redo snapshots omit `timelineMaster`, so undo/redo collapse batch state

- **Severity:** High (same invariant violation as D1, with the added trap that "undo" cannot restore the lost batches)
- **Root cause:** `m29/editing/service.py:206` pushes `dumps_director_timeline(tl)` onto the undo stack — a snapshot containing only `DirectorTimeline` fields and no `timelineMaster`. `scene.director_json = undo_stack.pop()` (line 185) and `redo_stack.pop()` (line 197) therefore restore a `timelineMaster`-less blob. The redo stack is seeded from `scene.director_json or ""` (line 184) which, once line 257 has run, also lacks `timelineMaster`.
- **Result:** After any m29 edit op, both undo and redo produce a blob without `timelineMaster`; the next `load_master` collapses to a single Batch 1 (same mechanism as D1). There is no undo path that restores the prior multi-batch state.
- **File:line:** `studio-api/app/codirector/m29/editing/service.py:184-197,206,257`.

## Confirmations (provably correct)

- **Batch ID stability:** `BatchBlock.id` is a `Field(default_factory=…)` (`contracts.py:213`) and is never reassigned in `add_batch`, `duplicate_batch` (gets a fresh `BatchBlock().id` via `model_copy(update={"id": BatchBlock().id, …})`, `service.py:92-106`), `delete_batch`, `touch_batch_config`, or `add_clip_to_batch`. Reorder paths mutate `order` only.
- **Per-batch clip ownership:** `add_clip_to_batch` resolves a single `batch` via `_batch_map(master).get(batch_id)` and appends to that batch's kind-specific array only (`orchestrator.py:558-575`). `touch_batch_config`'s clip-replacement loop (`orchestrator.py:507-513`) calls `setattr(batch, _field, …)` on the one resolved batch object; sibling batches are not iterated. Invariant 8a holds.
- **`PUT /director` merge:** `dumps_director_timeline_preserving_embedded` (`director_timeline.py:203-227`) carries over every existing-blob key that is not a `DirectorTimeline` field, including `timelineMaster` and `timelineWorkspace`. Probe PROBE3 confirms `bb_x` survives.
- **Migration collapse guard:** `migrate_director_to_master` returns the existing master unchanged (modulo metadata flags) whenever `existing.batchBlocks` is non-empty (`migration.py:55-58`), and again when `existing.migratedFromDirectorJson` is true (`migration.py:59-60`). Probe PROBE1 confirms a 2-batch master is preserved across re-migration.
- **NO_AUTO_PERSIST_ON_READ:** `load_master` only calls `save_master` when `data.get("timelineMaster")` is absent (`store.py:96-98`), so a healthy blob is not re-written on every GET. This is the correct fix for the prior "every GET re-saved a collapsed master" bug — but it does **not** protect against the D1 writers that delete `timelineMaster` before the GET.
- **Stale fetch (DirectorTracks):** `loadTokenRef` (`DirectorTracks.tsx:375`) is incremented per load and checked before `setTl` (`DirectorTracks.tsx:435,454`); late responses from a prior scene/`reloadKey` load are discarded. This is the NO_STALE_RELOAD fix.
- **Track-level undo/redo isolation (Timeline shell):** `TimelineEditorShell` undo/redo (`TimelineEditorShell.tsx:220-258`) and `mutateTimeline` (`202-218`) snapshot/restore `DirectorTimeline` and persist via `api.putDirector`, which merges and preserves `timelineMaster`. Batch state is never rewritten by track-level undo/redo. (Distinct from D2, which is the m29 editing service's own undo/redo.)
- **Migration audit trail:** Every migrated `BatchClip` carries `legacyClipId` (`migration.py:132,146,161,175,188`) and the batch carries `migrationMetadata` with `rule` and per-kind `legacyClipIds` (`migration.py:192-203`). Probe PROBE2b confirms `legacyClipId="img1"`, `rule="all_legacy_clips_to_single_batch"`.
- **Scene/project switching:** `selectedSceneId` effect (`TimelineEditorShell.tsx:126-136`) resets selection/playhead/undo-redo and re-fetches master; `ProjectEditor.tsx:105-107` resets playhead. No stale cross-scene state observed in code.

## Items marked NEEDS RUNTIME VERIFICATION

- **N1 — `TimelineEditorShell.refreshMaster` race:** `TimelineEditorShell.tsx:105-119` has no generation token (unlike `DirectorTracks.tsx`). A scene-switch `refreshMaster` racing a mutation's `afterMutation → refreshMaster` could in principle let an older master response win. Not provably harmful by reading; needs runtime verification with a forced race.
- **N2 — `Timeline.tsx` fan-out:** `Timeline.tsx:27-33` issues `GET /master` for every scene on mount. Each call hits `load_master`, which persists only when `timelineMaster` is missing. If D1 is fixed, this is benign; until then it is a second trigger surface for the collapse. Needs runtime verification of fan-out timing against a D1-affected scene.
- **N3 — Empty-batchBlocks re-migration edge:** `migration.py:55-60` re-migrates when `existing.migratedFromDirectorJson` is true but `batchBlocks` is empty (PROBE6). Unreachable via normal migration (always ≥1 batch) but could occur if a future writer clears `batchBlocks` without clearing `migratedFromDirectorJson`. Low severity; needs runtime verification.

## Summary

The W46 Timeline persistence layer is internally consistent and the prior milestone fixes (PUT /director merge, NO_AUTO_PERSIST_ON_READ, NEVER_COLLAPSE guard, per-batch clip ownership, stale-fetch token) are correctly implemented and provable. **The mandatory invariant "reload never collapses multi-batch state" is violated by four non-`PUT /director` writers** (D1) that persist `scene.director_json` with the plain serializer, wiping the embedded `timelineMaster`; the subsequent `GET /master` re-migrates and cements a single Batch 1. The m29 editing undo/redo (D2) compounds this by snapshotting without `timelineMaster`, making the collapse unrecoverable via undo. No verdict issued (read-only audit).
