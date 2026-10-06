# IMPLEMENT.md — Timeline Publish + MAGI (full pack)

**Machine:** BRAD-5090  
**Repo:** `C:\AdeptFilmWorks\AIVideoStudio`  
**Branch:** `feat/character-creator-final-closure` (dirty tree — **never `git add -A`**)  
**Evidence:** `C:\Users\bradj\theme_walk\timeline_publish\`  
**Updated (PT):** 2026-09-13 ~19:45 PT

---

## Status

| Gate | Verdict |
|------|---------|
| Creator click-test | **READY** — see `READY_FOR_CREATOR_CLICK_TEST.md` (VCD restored: `SCENE_FINISHED`, stitch present, `scenePublish=null` so PUBLISH shows) |
| Playwright A–E + MAGI 2-batch | **PASS** (6/6 live beta chromium) |
| Unit (pytest `test_scene_publish`) | **PASS** (10/10) |
| Unit (vitest `scenePublish.test.ts`) | **PASS** (7/7) |
| Architecture GO | **GO** — live E2E proven on Korri / Venture Corridor Dialogue against `:5173` + `:8758` |

---

## Product behavior

1. **PUBLISH** / **UPSCALE WITH MAGI** appear on Preview Monitor **only** after Final Check lifecycle is `SCENE_FINISHED` or `SCENE_FINISHED_WITH_ACCEPTED_ISSUES` **and** `sceneStitch.assetId` exists.
2. **PUBLISH** atomically registers a Library video with tag `video_published_master` from the full stitch, copying Final Check provenance (`lifecycleStatusSnapshot`, `creatorVerdictSnapshot`, `acceptedIssues`). Never auto-called from stitch/pass.
3. After publish with unchanged stitch → **Published** badge; PUBLISH hidden; UPSCALE remains.
4. After stitch identity moves (`sceneStitch.assetId` ≠ published `sourceSceneStitchAssetId`) → **Changes Pending** + **UPDATE PUBLISHED** (versioned, `expectedVersion` conflict-safe).
5. **UPSCALE WITH MAGI** hands only full stitch / published / prior upscaled master into MAGI apply. Per-batch assets refused. **`autoPublished: false` always.**
6. Timeline batch blocks are not flattened by publish.
7. GENERATE SCENE overlay / `sceneRenderProgress.ts` / Final Check authority / 12B media — **untouched**.

---

## Mission files

### Backend (new / touched)

| Path | Role |
|------|------|
| `studio-api/app/director_timeline_w46/scene_publish.py` | **NEW** — readiness, fingerprint, `publish_scene`, `magi_upscale_full_stitch`, `publish_status` |
| `studio-api/app/director_timeline_w46/contracts.py` | `ScenePublishState` + `master.scenePublish` |
| `studio-api/app/director_timeline_w46/service.py` | `publish_scene`, `magi_upscale_full_stitch` facades |
| `studio-api/app/director_timeline_w46/router.py` | `POST .../publish`, `POST .../magi-upscale` (structured `{ok,error,creatorMessage}` detail on refuse) |
| `studio-api/tests/test_scene_publish.py` | **NEW** — gate, refuse, atomic register, accepted-issues honesty, update/version, MAGI batch block |

### Frontend (new / touched)

| Path | Role |
|------|------|
| `studio-web/src/timelineMaster/scenePublish.ts` | **NEW** — FE gate / dirty / chrome / MAGI allow-list |
| `studio-web/src/timelineMaster/scenePublish.test.ts` | **NEW** — vitest chrome matrix |
| `studio-web/src/timelineMaster/contracts.ts` | `ScenePublishState` |
| `studio-web/src/api.ts` | `directorTimelinePublishScene`, `directorTimelineMagiUpscale` |
| `studio-web/src/components/LivePreviewMonitor.tsx` | Publish bar CTAs only (`live-preview-publish*`) — **no** GENERATE SCENE overlay edits |
| `studio-web/src/components/timeline-master/TimelinePreviewComposer.tsx` | Chrome resolve + publish/update/magi handlers |
| `studio-web/src/components/timeline-master/TimelineEditorShell.tsx` | `onMasterMutated={afterMutation}` reload |
| `studio-web/src/styles.css` | `.live-preview-publish-bar*` |

### E2E / evidence

| Path | Role |
|------|------|
| `tests/e2e/timeline/timeline-publish-magi-cert.spec.ts` | **NEW** — Tests A–E + MAGI 2-batch on VCD |
| `docs/release-gate/timeline-publish/artifacts/*` | Playwright JSON artifacts (mirrored under theme_walk) |

---

## API routes

| Method | Path | Notes |
|--------|------|-------|
| `POST` | `/api/director-timeline/projects/{project_id}/scenes/{scene_id}/publish` | Body: `{ update?, expectedVersion?, source?: "stitch"\|"upscaled"\|"published" }`. 400 structured refuse (`NOT_PUBLISH_READY`, `NO_CHANGES_PENDING`, `VERSION_CONFLICT`, …). |
| `POST` | `/api/director-timeline/projects/{project_id}/scenes/{scene_id}/magi-upscale` | Body: `{ engine?, model?, targetResolution?, assetId? }`. Full-stitch allow-list only. Returns `autoPublished: false`. |

---

## Gates (authoritative)

**Publish-ready iff:**

- `sceneFinalCheck.lifecycleStatus ∈ { SCENE_FINISHED, SCENE_FINISHED_WITH_ACCEPTED_ISSUES }`
- `sceneStitch.assetId` non-empty
- Stitch media file resolvable on disk

**Chrome:**

- `showPublish` = ready && !hasPublished
- `showUpdatePublished` = ready && hasPublished && dirty (stitch asset ≠ published source stitch)
- `showUpscaleWithMagi` = ready

**MAGI allow-list:** `sceneStitch.assetId`, `scenePublish.publishedAssetId`, `scenePublish.upscaledAssetId` only.

---

## How to verify

### Creator (manual)

See `READY_FOR_CREATOR_CLICK_TEST.md`:

1. http://127.0.0.1:5173 → Korri Anadriya → **Venture Corridor Dialogue** (NOT 12B)
2. Preview Monitor: **PUBLISH** + **UPSCALE WITH MAGI**
3. PUBLISH → Published badge + Library Video Published Master
4. UPSCALE → job queues; Timeline editable; no auto-publish

### Automated

```bat
cd C:\AdeptFilmWorks\AIVideoStudio\studio-api
python -m pytest tests/test_scene_publish.py -q

cd C:\AdeptFilmWorks\AIVideoStudio\studio-web
npx vitest run src/timelineMaster/scenePublish.test.ts

cd C:\AdeptFilmWorks\AIVideoStudio
set ADEPT_BETA_TARGET=1
set PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173
set STUDIO_API_BASE=http://127.0.0.1:8758
npx playwright test tests/e2e/timeline/timeline-publish-magi-cert.spec.ts --project=chromium
```

### API smoke (VCD ids)

- Project: `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`
- Scene: `ae8e5699-a5d8-4b9b-ad8e-0003d81d3639` (Venture Corridor Dialogue)

---

## Playwright coverage map

| Test | Proves |
|------|--------|
| **A** | CTA hidden before PASS; PUBLISH+UPSCALE after `SCENE_FINISHED` |
| **B** | API refuse before PASS → 400 `NOT_PUBLISH_READY` |
| **C** | Atomic publish register + provenance + Published badge + file reachable |
| **D** | Changes Pending + UPDATE PUBLISHED version bump after stitch clone |
| **E** | MAGI blocks batch; full-stitch entry ok; `autoPublished=false` |
| **MAGI 2-batch** | VCD ≥2 batches; second-batch asset still blocked |

Artifacts: `C:\Users\bradj\theme_walk\timeline_publish\playwright_artifacts\` and `docs/release-gate/timeline-publish/artifacts\`.

---

## Collision / non-goals

- **Do not** edit `sceneRenderProgress.ts` or GENERATE SCENE idle-hide (Primary-owned).
- **Do not** rewrite Final Check / Dialogue Authority.
- **Do not** overwrite Scene **12B** / Quarters Interview media.
- `LivePreviewMonitor.tsx` shared with Primary — only **additive** publish bar.

---

## Remaining gaps (non-blocking for GO)

1. MAGI Timeline entry often returns `upscaledAssetId: null` until async job finishes — surface `jobId` in announce/chrome when present.
2. FE dirty detect keys off stitch **asset id** change (matches UPDATE path); BE fingerprint also includes source batch/asset lists — keep in sync if fingerprint semantics expand.
3. Human creator click-test still recommended for UX polish (button placement / HMR).
4. Mixed dirty tree: commit only mission paths below when ready.

---

## Release hygiene — stage by path only

```bat
cd C:\AdeptFilmWorks\AIVideoStudio
git add -- ^
  studio-api/app/director_timeline_w46/scene_publish.py ^
  studio-api/app/director_timeline_w46/contracts.py ^
  studio-api/app/director_timeline_w46/service.py ^
  studio-api/app/director_timeline_w46/router.py ^
  studio-api/tests/test_scene_publish.py ^
  studio-web/src/timelineMaster/scenePublish.ts ^
  studio-web/src/timelineMaster/scenePublish.test.ts ^
  studio-web/src/timelineMaster/contracts.ts ^
  studio-web/src/api.ts ^
  studio-web/src/components/LivePreviewMonitor.tsx ^
  studio-web/src/components/timeline-master/TimelinePreviewComposer.tsx ^
  studio-web/src/components/timeline-master/TimelineEditorShell.tsx ^
  studio-web/src/styles.css ^
  tests/e2e/timeline/timeline-publish-magi-cert.spec.ts ^
  docs/release-gate/timeline-publish
```

**Never** `git add -A` on this tree.