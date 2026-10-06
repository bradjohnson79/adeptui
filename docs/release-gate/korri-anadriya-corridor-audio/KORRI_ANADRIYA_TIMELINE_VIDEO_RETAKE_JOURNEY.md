# Timeline Video Re-Take Mini-Menu + Prompt + Mask + Range

Governing report for the Korri Anadriya Timeline video Re-Take journey. Does not replace Journey 1 (selected-scene persistence), Journey 2 (five-control transport), or the scene-management addendum.  
Amalgamated with the last three completed builds in [`ADEPT_UI_KORRI_ANADRIYA_LAST_THREE_BUILDS_UNIFIED_REPORT.md`](ADEPT_UI_KORRI_ANADRIYA_LAST_THREE_BUILDS_UNIFIED_REPORT.md).

Project: **Korri Anadriya** `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`  
Branch: `feat/character-creator-final-closure`  
HEAD: `b6156455e643d5fa430784b3130756f2d8038651` (this work is uncommitted)  
Dialogue (video): `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=timeline&sceneId=ae8e5699-a5d8-4b9b-ad8e-0003d81d3639`  
Walk (image gate): `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=timeline&sceneId=b5282a4c-07eb-40db-9d5b-1512eac74dca`  
Studio API: `http://127.0.0.1:8758/`

Protected scenes (never deleted; names left as production names):

| Scene | ID | Role in this journey |
|---|---|---|
| Scene 1 | `1f46b621-46f9-4b7e-8273-202a49e1ca7c` | Untouched |
| Venture Corridor Dialogue | `ae8e5699-a5d8-4b9b-ad8e-0003d81d3639` | Video Re-Take |
| Venture Corridor Walk | `b5282a4c-07eb-40db-9d5b-1512eac74dca` | Image gate |

No new project was created. Comfy was not restarted. Original Dialogue Take A remains the active take.

---

## Root-cause / migration audit

| Question | Answer | Class |
|---|---|---|
| What did the Mask Repair track own? | Visible lane over `batch.repairRanges`. It did **not** own unique persistable state. Repair ranges remain on the batch and are created internally on Re-Take submit. | **PRESENTATION ONLY** — track removed. `repairRanges` kept as **STATE AUTHORITY**. |
| Can the track be removed without losing repair state? | Yes. Re-Take now creates a repair range inside `retake_range` / `submit_video_retake`. Timeline highlight is a display-only overlay (`timeline-retake-mark`, pointer-events none). | Track retired. State kept. |
| What did the Inpaint button invoke? | `TimelineInpaintWorkspace`: extract a still at `repair.start` from the approved take, paint on that still, `submit_inpaint_repair` (zimage), `apply_inpaint_repair`. | **LEGACY UI** — unmounted. Backend kept. |
| Which backend is canonical Re-Take authority? | `POST /api/director-timeline/projects/{id}/scenes/{id}/batches/{id}/retake-range` → `orchestrator.retake_range`. Prompt-only → existing MiniMax/LTX **range_replacement**. Mask or Remove Background → `submit_video_retake` → same `submit_inpaint_repair` keyframe path. No second repair backend. | **EXISTS** |
| Why was the repair image stale/default? | Old workspace extracted a still from the approved take at `repair.start`, not the live Preview Monitor frame. A leftover still or batch image could appear instead of the current video. | Fixed: overlay paints on the live `<video>`; submit can upload a captured Preview frame as `frameAssetId`. |
| How is the Preview Monitor frame captured? | `VideoRetakeMaskCanvas.captureFrame()` draws the current `<video>` element to a canvas at source pixel size. Uploaded as `retake-ref-frame` when a mask or rembg is used. | Preview Monitor is authority. |
| How is temporal range represented? | Session: `rangeStart`, `rangeEnd`, `referenceFrameTime` (separate). Submit: batch-local `start` + `length` via `boundRetakeToBatch`. Timeline highlight is display-only. | WHEN ≠ WHERE |
| How are masks mapped to source pixels? | `mediaContainRect` maps pointer events to the object-fit contain rectangle only. Letterbox/pillarbox is not paintable. Export is PNG at `videoWidth` × `videoHeight`. | Source pixels only. |
| What background-removal already exists? | Perception `remove_background` (SAM/selection). HTTP `POST /api/perception/projects/{id}/remove-background` was disconnected; it is reconnected. Result is a pending mask, not a destructive edit. | **EXISTS** — reconnected. |
| How does repaired video re-enter Timeline? | Range replacement: existing batch generation + compose into the marked interval; original take stays as history. Keyframe repair: `apply_keyframe_repair_to_asset` → `complete_batch_candidate` as a **reviewable** candidate; current approved take stays active until the creator chooses the new one. | Existing take semantics. |

### Product rule — mask without prompt

Submit requires **prompt** or **Remove Background**. A painted mask with no instruction is blocked: *Describe what should change in the painted area, or use Remove Background.*

### Duplicate entry points (classified)

| Surface | Classification | Action |
|---|---|---|
| Preview Monitor bottom-center **Re-Take** | Canonical launcher | Kept |
| Preview Monitor top-center editor | Canonical workspace | Kept |
| Timeline toolbar Inpaint | Obsolete product language | Removed |
| Timeline toolbar Re-Take | Duplicate of the launcher | Removed |
| Inspector accordion (was “Re-Take”) | Full-shot **New take** + take switcher — different function | Renamed **Takes**. Copy points creators to Preview Monitor for range repair. |
| `TimelineMasterPanel` MiniMax Re-take drawer | Unused by `TimelineEditorShell` | **LEGACY** — left in place, not mounted on the creator Timeline |
| `TimelineInpaintWorkspace` / `TimelineRetakePromptModal` | Unmounted | **LEGACY** files remain; not rendered |

Native video inpaint is still unavailable. Masked Re-Take discloses: Adept repairs the painted area on this frame and applies that repair only to the selected time range.

---

## UX (canonical)

```
Preview Monitor video → bottom-center [Re-Take] → top-center editor
WHEN = Mark In / Mark Out
WHERE = optional Brush / Remove Background
WHAT = prompt
Re-Take = enqueue the same retake-range job
```

- Video displayed → launcher shown. Image / library / failed overlay → launcher hidden (not a disabled fake).
- Click pauses playback, keeps playhead, opens an empty pending operation. Does not submit.
- Prompt-only is valid. Brush is optional.
- Scene change resets pending mask / range / prompt (`useVideoRetake` on `sceneId`).
- Toolbar generate row: Preflight | Generate Draft | Video Finishing. No Inpaint. No second Re-Take.

---

## Live Korri proof

### Restore

Playwright prompt-only submit on Dialogue Batch 1 `bb_a062bbb7b274` started MiniMax H3 job `d562d5e2-170f-4266-99d3-c356d4ddf2ae`. The job **failed**:

`H3 R2V LoadAudio missing uploaded voices: ['studio/Anadriya Clone clone sample 4.wav']`

Watcher had set Batch 1 to Failed while Take A stayed approved (`cand_ceccb85364ec` / `5a2e74b3-8834-45b3-ba93-901af9120ef2`). Status was restored to **Approved** without activating a different candidate. Batches 2 and 3 remained Approved.

Watcher now keeps **Approved** when a playable `approvedClip` exists and a later Re-Take / new take fails (`PLAYABLE_TAKE_GUARD`). First-generation batches without an approved clip still become Failed.

### Primary browser (this session)

Dialogue, Video Finishing, Take A visible:

1. Bottom-center **Re-Take** appeared over the live corridor video.
2. Click opened the top-center editor: Mark In, Mark Out, Brush, Erase, Brush Size, Clear Mask, Remove Background, prompt, Cancel, Re-Take. Launcher hid. Video stayed underneath. No stale still.
3. Mark In at playhead 0, Batch Out, Mark Out → `Repair Range: 00:00.00 → 00:08.00` and `timeline-retake-mark` present.
4. Toolbar Inpaint count 0. Mask Repair lane count 0.
5. Scene change to Walk **while the editor was open**: overlay gone, range mark gone, launcher gone, `live-preview-image` shown.

Walk stayed `image_planning`. No Re-Take launcher on the still.

A second MiniMax prompt-only submit was **not** repeated in this session (it would re-hit the missing-voice failure and spend another H3 job).

---

## Tests

| Suite | Result |
|---|---|
| `studio-web` `videoRetake.test.ts` + `previewVideoActionMenu.test.ts` | **9 passed** |
| `studio-api` `test_timeline_keyframe_repair.py` + `test_retake_failure_keeps_playable_approved_take` | **9 passed** (includes instruction gate) |
| `tests/e2e/timeline/timeline-video-retake.spec.ts` | **1 passed** (9.0s) on an earlier run — launcher, menu, range, brush, rembg click, cancel, prompt-only POST, Walk image gate. Spec now restores Take A after submit. **Did not wait for a completed Timeline result.** |

Playwright env:

```
ADEPT_ALLOW_KORRI_MUTATION=1
ADEPT_BETA_TARGET=1
PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173
STUDIO_API_BASE=http://127.0.0.1:8758
```

---

## COMFY

- **COMFY BEFORE:** PID 77152, HTTP 200 `/system_stats`
- **COMFY AFTER:** PID 77152, HTTP 200
- **COMFY RESTARTED?:** **NO**
- **WHY?:** Re-Take UX + API recycle only. `restart_studio_api_only.py` → `newPid=51004 comfyPid=77152 unchanged=True`.

---

## Files (this journey)

Frontend

- `studio-web/src/timelineMaster/videoRetake.ts` + `videoRetake.test.ts`
- `studio-web/src/timelineMaster/previewVideoActionMenu.ts` + `previewVideoActionMenu.test.ts`
- `studio-web/src/components/timeline-master/PreviewVideoActionMenu.tsx`
- `studio-web/src/components/timeline-master/TimelineRetakeOverlay.tsx`
- `studio-web/src/components/timeline-master/VideoRetakeMaskCanvas.tsx`
- `studio-web/src/components/timeline-master/useVideoRetake.ts`
- `studio-web/src/styles/timeline-master/timeline-retake-overlay.css`
- `studio-web/src/components/LivePreviewMonitor.tsx`
- `studio-web/src/components/timeline-master/TimelinePreviewComposer.tsx`
- `studio-web/src/components/timeline-master/TimelineEditorShell.tsx`
- `studio-web/src/components/timeline-master/TimelineToolbar.tsx`
- `studio-web/src/components/timeline-master/TimelineInspector.tsx`
- `studio-web/src/components/DirectorTracks.tsx`
- `studio-web/src/api.ts`

Backend

- `studio-api/app/director_timeline_w46/orchestrator.py` (`retake_range` dispatch)
- `studio-api/app/director_timeline_w46/inpaint_repair.py` (`submit_video_retake`)
- `studio-api/app/director_timeline_w46/generation/watcher.py` (keep playable Approved)
- `studio-api/app/director_timeline_w46/router.py` / `timeline_tools.py`
- `studio-api/app/codirector/perception/router.py`
- `studio-api/app/codirector/tools/handlers/director_timeline_tools.py`
- `studio-api/app/codirector/tools/definitions.py`
- `studio-api/app/codirector/routing/unified_intent.py`

Tests / cert wiring

- `studio-api/tests/test_timeline_range_retake.py`
- `studio-api/tests/test_timeline_keyframe_repair.py`
- `tests/e2e/timeline/timeline-video-retake.spec.ts`
- `tests/e2e/final-systems/helpers/finalSystemsCert.ts` (clicks `preview-video-retake`)
- `tests/e2e/final-systems/remaining-workspaces.spec.ts`

## Unrelated systems untouched

Comfy `:8188` lifecycle, MiniMax `:8192` lifecycle, Audio Studio, Walk footstep timing, five-control transport architecture, Character Creator, protected scene names/IDs.

Timeline canvas already uses `overflow: auto`. Mask Repair removal is not treated as a scroll fix.

---

## E2E TRACE

| stage | verdict |
|---|---|
| Creator Re-Take | PASS — Preview Monitor launcher + Mark In/Out + prompt |
| Timeline frontend | PASS — overlay submit → `retake-range` |
| API | PASS — `POST .../retake-range` `ok` + `jobId` `e4ffc62d-0749-4d0a-ae5b-739b63a3cfed` |
| retake-range | PASS — `range_replacement` on Batch 1 |
| dependency resolver | PASS — Anadriya + Korri approved voices by `voiceProfileId` / `assetId` |
| voice staging | PASS — `studio/{assetId}.wav` verified in Comfy Shared input |
| H3 workflow | PASS — 4 `LoadImage` + 2 `LoadAudio` + EasyCache `90`; no missing-voice fail |
| generation | PASS — job `done` / `Scene render complete` |
| output ingest | PASS — composed `retake_range_26c73016f8.mp4` 8.0s |
| candidate Take B | PASS — `cand_c355cb9e195c` reviewable, not auto-approved |
| Take A preserved | PASS — `cand_ceccb85364ec` / `5a2e74b3-…` stayed the approved take until creator action |
| reload | PASS — both candidates remain |
| approve/reject | PASS — activate Take B, reject Take B, restore Take A |

---

## Remaining (not this handoff)

Masked / Remove Background Re-Take still uses the disclosed zimage keyframe-repair path. Unit-tested. Not live-completed here. That does not reopen the H3 prompt-only result gate.

---

## Addendum — Re-Take menu toggle / close

The bottom-center pill is a true toggle. It stays visible while the editor is open and shows a teal `aria-pressed` active state. It does not move or resize the Preview Monitor.

All close routes call the same `close` action (`closedVideoRetakeSession()`):

- pill click while open
- X (`aria-label="Close Re-Take"`)
- Escape (including from the prompt field, unless another control already consumed Escape)
- Cancel

Close without submit clears prompt, In/Out highlight, mask overlay, and pending background-removal. No generation is sent. The source video is unchanged.

Live Dialogue verification (Vite `5173`, asset `ce5f4d3e-daf1-475a-be0e-8ea6189f246b` unchanged; zero `retake` / `inpaint` / `remove-background` POSTs):

| Route | Result |
|---|---|
| Click Re-Take → opens | PASS — top menu + X (`aria-label="Close Re-Take"`); bottom pill stays in place, teal / `aria-pressed=true` |
| Click Re-Take again → closes | PASS — menu gone; pill released |
| Open → type + Mark In → X → closes | PASS — prompt/marks gone; reopen prompt empty |
| Open → Mark In/Out + type → Escape from prompt → closes | PASS — range highlight (`00:00.00 → 00:08.00`) removed; reopen prompt empty |

All three close routes left the same clean session (`closedVideoRetakeSession`). The Preview Monitor video was not replaced.

---

## Addendum — compact mini-menu UI

UI-only compaction of the Preview Monitor Re-Take overlay. No workflow, payload, gate, mask, or range change.

Desktop density:

```text
RE-TAKE                                             [×]
[Mark In] [Mark Out] [Brush] [Erase] [Remove Background]
Size ──●────   [Clear Mask]
[ Describe what you want to change...              ] [➤]
```

X stays top-right. Footer **Cancel** / text **Re-Take** removed. Submit is `IconSend` (`data-testid="timeline-retake-submit"`). Enter in the single-line prompt calls the same `onSubmit`; Shift+Enter is ignored. Invalid submit still shows the existing gate (no POST).

Live Dialogue (Vite `5173`, asset `ce5f4d3e-daf1-475a-be0e-8ea6189f246b` unchanged; zero `retake` / `inpaint` / `remove-background` POSTs):

| Check | Result |
|---|---|
| Video selected; bottom pill opens menu | PASS |
| Menu is a top-center strip | PASS — menu **130×544** vs Preview host **838×1824** |
| Row 1 one line | PASS — height 20px; Mark In / Mark Out / Brush / Erase / Remove Background; no wrap |
| Row 2 Size + Clear Mask | PASS |
| Prompt single-line | PASS — `INPUT type=text` |
| SVG send submits | PASS — `IconSend` SVG; same gate `Mark In and Mark Out first.` |
| Enter submits | PASS — same gate; no POST |
| X closes | PASS — `aria-label="Close Re-Take"`; prompt cleared |
| Bottom pill toggles close | PASS — overlay gone; pill `aria-pressed=false`; pill rect **1226,1049,82×31** unchanged |
| No overflow / no layout shift | PASS |
| Footer Cancel / text Re-Take gone | PASS |

This addendum certifies **layout only**. It does not upgrade the full-stack Re-Take result gate.

**GO — TIMELINE RE-TAKE COMPACT MINI-MENU UI CERTIFIED**

---

## Addendum — smaller floating menu (drag + resize)

Further compaction plus mouse move/resize, still clamped to the Preview Monitor. No workflow change.

Default open size **252×93** (was **544×130**). Labels: In / Out / Brush / Erase / No BG / Clear. Range hint lives in the title bar only after marks. Drag the **RE-TAKE** title or dotted grip. Resize from edges and the bottom-right corner. Position stays inside the monitor (pad 6px).

Live Dialogue: drag moved **1141,262 → 479,467**; resize grew **252×93 → 414×244**; drag past the top-left clamped to **362,262** and stayed inside the **1824×838** stage. SVG send still showed `Mark In and Mark Out first.`

---

## Addendum — H3 voice handoff + reviewable Take B

The failed job `d562d5e2-170f-4266-99d3-c356d4ddf2ae` was **not** a missing Library file. Classification:

| Boundary | Class |
|---|---|
| Anadriya / Korri approved voice profiles | **EXISTS** — `5c221441-…` / `283e8cf8-…` |
| Library preview assets | **EXISTS** — `e3a305b6-…` / `33a80b24-…` on disk |
| Comfy input copies under the display filename | **EXISTS** — `studio/Anadriya Clone clone sample 4.wav` was already in Shared input |
| Durable identity | **DISCONNECTED** — `_ensure_comfy_file` reused `asset.comfy_name` (`studio/<display filename>`) without verifying or restaging from `assetId` + path |
| H3 Fast graph compile | **BROKEN** — EasyCache was hardcoded as node `19`. Dialogue Re-Take binds **4 pictures + 2 voices**. Anadriya `LoadAudio` landed on node `19` and was overwritten. The assertion then reported `H3 R2V LoadAudio missing uploaded voices: ['studio/Anadriya Clone clone sample 4.wav']` |

Repair (generic — no character-name special cases):

1. EasyCache reserved at node `90`. `LoadImage` / `LoadAudio` allocate the next free id from 15.
2. `stage_library_asset` copies Library bytes to `studio/{assetId}{ext}` and verifies the file before compile.
3. Submit-time `preflight_generation_dependencies` stages every H3 picture/voice, checks the current take video, and dry-compiles the graph before the expensive queue.

Live Dialogue Re-Take job `e4ffc62d-0749-4d0a-ae5b-739b63a3cfed` — **done**, `Scene render complete`. Dependencies READY. Take B `cand_c355cb9e195c` / asset `942a05e4-33b1-4b32-9fd0-1106a45aa9ac` (`retake_range_26c73016f8.mp4`, 858208 bytes, 192 frames @ 24 fps = 8.0s). Take A stayed approved until the creator switched. Playwright later approved Take B, rejected it, and restored Take A.

Playwright `timeline-video-retake.spec.ts`: first mutation run waited through H3 + compose; later pass **1 passed** (13.5s) after reuse of that candidate. `--retries=0`.

Masked / Remove Background Re-Take remains the disclosed zimage keyframe path and was not re-certified in this addendum.

---

## FINAL VERDICT

**GO — TIMELINE VIDEO RE-TAKE H3 DEPENDENCY HANDOFF + REVIEWABLE TAKE E2E CERTIFIED**
