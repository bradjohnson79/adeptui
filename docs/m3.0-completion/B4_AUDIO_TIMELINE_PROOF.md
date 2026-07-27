# M3.0 Completion - Phase 1: B4, Audio Reaches the Director Timeline

**Verdict: CLOSED for the import path, with named limitations.** Audio cues backed by a real file
on disk now land in `scene.director_json` and come back through the public
`GET /api/projects/{projectId}/scenes/{sceneId}/director` contract as `audio_clips` / `sfx_clips`.
Cues backed by a fixture id are still refused, on purpose. Proven by 8 pytest cases and 3
Playwright cases, all green.

| Field | Value |
|-------|-------|
| Blocker | **B4** - "M2.9 audio produces cues that never appear on the Director timeline" |
| Verdict | **Closed for real audio; generative audio provider still absent (see section 6)** |
| Plan file | Not edited |
| Commit | None |
| Flags required | `STUDIO_FEATURE_AUDIO_PRODUCTION_V1`, `STUDIO_FEATURE_DIRECTOR_TIMELINE_V1` (both still default OFF in `feature_flags.py`) |

---

## 1. What was actually broken

`AudioService.generate` wrote a row into `m29_audio_cues` and stopped there. `place_cue` existed
but only ever wrote another cue row - nothing touched `Scene.director_json`. So the sound path
reported success at every layer it owned while the timeline the editor and renderer read stayed
empty. Worse, in fixture mode the cue carried an `assetId` that names no file, so any naive
"place the cue" fix would have written a clip pointing at nothing and made the timeline lie.

Two rules follow from that, and both are enforced in code:

1. A cue is placed only when its asset resolves to **a file that exists on disk**.
2. Placement is asserted through the **public director read contract**, not the cue table.

---

## 2. Changes

### `studio-api/app/codirector/m29/audio/service.py`

| Symbol | Purpose |
|--------|---------|
| `resolve_real_audio_path(db, asset_id)` | The truth test. Checks the studio `assets` table via `m29.providers.resolve_asset_path`, then the M2.9 version ledger's `metadata_json.assetPath`. Returns `None` for a fixture id, which is what blocks placeholder placement. |
| `_write_scene_clip(...)` | The only writer of audio onto the timeline. Parses `Scene.director_json` through `director_timeline.parse_director_timeline`, upserts a `TimelineClip` on `sfx_clips` (kind `sfx`) or `audio_clips` (everything else), and re-serializes. Upsert keyed on `(asset_id, start)` so re-placing or re-gaining a cue never duplicates the clip. |
| `_wav_duration_sec(path)` | Reads the real duration out of the WAV header, so an imported clip occupies its true length instead of a guessed default. |
| `_cue_row` / `_cue_metadata` / `_update_cue` | Small cue-row helpers; `_update_cue` is the single place cue `status`, `scene_id`, and `metadata_json` change. |
| `AudioService._auto_place(...)` | Called at the end of `generate`. Places the cue when a real scene *and* a real asset exist; returns `False` otherwise, which is what keeps fixture mode honest. |
| `AudioService.place_cue(...)` | Now writes the timeline clip (via `_write_scene_clip`) in addition to the cue row, and reports `timelinePlaced`. |
| `AudioService.promote_cue_to_timeline(...)` | Explicit promotion for a cue that got its asset later. Raises on an unknown cue, a cue with no scene, a cue with no asset, and - the important one - a cue whose asset has no file on disk. |
| `AudioService.import_audio(...)` | The real-bytes path: validates `RIFF`/`WAVE` magic, writes the file under `data/assets/{projectId}/{assetId}.wav`, creates the `Asset` row and an M2.9 asset version carrying `assetPath` + `sha256` + measured duration, then cues and places it. |
| `AudioService.revise_cue_gain(...)` | Changes gain on the cue row *and* the placed clip in one call. |

### `studio-api/app/codirector/m29/api.py`

| Route | Body | Notes |
|-------|------|-------|
| `POST /api/codirector/m29/audio/import` | `AudioImportBody` (`projectId`, `contentBase64`, `filename`, `kind`, `sceneId`, `startSec`, `durationSec`, `volume`, `ducking`, `tag`) | 400 on malformed base64 or non-WAV bytes; 404 on unknown project |
| `POST /api/codirector/m29/audio/cues/{cueId}/promote` | `AudioPromoteBody` (`projectId`, `sceneId`, `volume`, `ducking`) | 404 unknown cue, **409** when the asset has no file on disk |
| `POST /api/codirector/m29/audio/cues/{cueId}/gain` | `AudioGainBody` (`projectId`, `volume`) | 404 unknown cue, 400 on negative gain |

All three sit behind `_require("audio_production_v1")`, so with the flag off they 404 exactly like
the rest of the M2.9 audio surface.

---

## 3. Backend proof - `studio-api/tests/test_m30_audio_timeline.py`

Every test drives the HTTP API through `TestClient` and reads placement back through
`GET .../director`. WAV bytes are generated with the stdlib `wave` module, so the duration
assertions describe real audio rather than a stub header.

| Test | What it pins |
|------|--------------|
| `test_import_places_sfx_cue_on_director_timeline` | Import -> one clip in `sfx_clips` with the returned `assetId`, `start` 1.0, `length` matching the measured 1.5 s; `audio_clips` untouched |
| `test_import_dialogue_lands_on_audio_track` | Kind routes dialogue to `audio_clips`, not `sfx_clips` |
| `test_placement_persists_across_sessions` | Clip is durable: read back from a *new* `SessionLocal()` and again through the API after the writing session is closed |
| `test_import_rejects_non_wav_bytes` | 400 mentioning `RIFF` - no Asset row, no clip |
| `test_promote_cue_moves_existing_cue_onto_timeline` | Import with no scene leaves the timeline empty (`timelinePlaced: false`), promote then places it with the requested gain and flips cue status to `placed` |
| `test_promote_refuses_cue_without_a_real_asset` | Fixture-mode cue: `timelinePlaced: false` on generate, **409 "no file on disk"** on promote, timeline still empty |
| `test_revise_gain_updates_cue_and_timeline_clip` | Gain change updates both the clip and the cue metadata and does **not** duplicate the clip |
| `test_audio_import_requires_the_flag` | Flag off -> 404 |

**Result: 8 passed** (`python -m pytest tests/test_m30_audio_timeline.py -q`, run as part of the
20-test M3.0 Phase 1-3 batch that also passed).

---

## 4. Browser-level proof - `tests/e2e/m30-completion/m30-completion-audio-timeline.spec.ts`

API-level Playwright flow using the existing E2E helpers, run against the real E2E stack started by
`scripts/e2e-start.mjs` (which now enables the two M2.9 flags this path needs - see
`docs/m3.0-completion/` Phase 3 notes and `scripts/e2e-start.mjs`). It self-skips when
`audioProductionEnabled` or `directorTimelineEnabled` is off, so a flags-off regression run stays
green.

| Case | Assertion |
|------|-----------|
| Import WAV | Base64 WAV -> `sfx_clips[0].asset_id` equals the returned asset id in `director_json`, and `GET /api/assets/{id}/file` serves the bytes back |
| Promote + gain | A cue imported without a scene is absent from the timeline, promotes onto it, and a gain revision changes the single existing clip |
| Fixture honesty | A fixture-generated cue is never placed |

**Result: 3 passed** against the real E2E stack
(`npx playwright test tests/e2e/m30-completion/m30-completion-audio-timeline.spec.ts --project=chromium`).
The API log for the run shows the actual calls: `POST /api/codirector/m29/audio/import` 200,
`GET .../director` 200, `GET /api/assets/{id}/file` 200, `POST .../cues/{id}/promote` 200 and - for
the fixture cue - `POST .../cues/{id}/promote` **409**.

### Related Phase 3 changes this proof depends on

* `scripts/e2e-start.mjs` now starts the E2E stack with `STUDIO_FEATURE_DIRECTOR_TIMELINE_V1=1` and
  `STUDIO_FEATURE_AUDIO_PRODUCTION_V1=1`. Both stay OFF in `feature_flags.py`.
* `POST /api/e2e/feature-flags` (E2E-only, 404 without `STUDIO_E2E`) toggles a flag on the live
  flag object so a single spec can cover both ON and OFF without restarting the API.
* `tests/e2e/codirector/production-suite-m29.spec.ts` scenario 1 ("flags off: routes hidden") used
  to skip itself whenever any M2.9 flag was on, which is now the E2E default. It turns the nine
  M2.9 flags off for itself through that control and restores exactly what it found, so it runs
  for real again instead of skipping.

---

## 5. Contract shape

`GET /api/projects/{projectId}/scenes/{sceneId}/director` after one 1.5 s sfx import at 1.0 s:

```json
{
  "sfx_clips": [
    { "asset_id": "<asset uuid>", "start": 1.0, "length": 1.5, "volume": 1.0, "label": "sfx" }
  ],
  "audio_clips": []
}
```

The same clip shape is what `director_timeline.TimelineClip` already emitted for video, so no
consumer needed a schema change.

---

## 6. Honest limitations

1. **No generative audio provider is wired.** `AudioService.generate` still returns a fixture
   result unless a real provider is configured, and fixture cues are deliberately *not* placed.
   The import path is what makes B4 demonstrable today; the generate path will place cues the
   moment it returns a real asset, through the same `_auto_place` call.
2. **Placement is one clip per cue.** There is no crossfade, ducking automation, or overlap
   resolution - `ducking` is recorded on the cue and ignored by the timeline writer.
3. **WAV only.** `import_audio` rejects anything without `RIFF`/`WAVE` magic. MP3/AAC would need a
   decoder to measure duration honestly, so they are refused rather than guessed at.
4. **There is no UI control for import yet.** The path is proven at the API level, including from
   the browser, but nothing in the Production Suite calls it - an operator cannot import audio by
   clicking today.
