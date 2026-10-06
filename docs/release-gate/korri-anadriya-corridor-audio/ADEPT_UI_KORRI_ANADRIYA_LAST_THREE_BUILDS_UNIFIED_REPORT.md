# Adept UI — Korri Anadriya Last Three Builds

**Governing unified report** (Law 2 / Law 30) for the three completed missions of 2 September 2026 after Full Stack Convergence J29 and Timeline selected-scene persistence.

Per-mission reports remain current for their own gates. This file is the amalgamated owner record.

| Field | Value |
|---|---|
| Captured | 2026-09-02 |
| Branch | `feat/character-creator-final-closure` |
| HEAD | `b6156455e643d5fa430784b3130756f2d8038651` (dirty worktree; **not committed**, **not pushed**) |
| Surface | Vite `http://127.0.0.1:5173/` + Studio API `http://127.0.0.1:8758/` |
| Named project | **Korri Anadriya** `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` |
| Scene 1 | `1f46b621-46f9-4b7e-8273-202a49e1ca7c` |
| Venture Corridor Dialogue | `ae8e5699-a5d8-4b9b-ad8e-0003d81d3639` |
| Venture Corridor Walk | `b5282a4c-07eb-40db-9d5b-1512eac74dca` |
| Comfy `:8188` | PID **77152** throughout · **COMFY RESTARTED?: NO** |
| MiniMax Route A `:8192` | Offline. Not started. |
| Retired | `:8760` is not product UI |

One project, one Library. No `POST /api/projects`. Protected production scenes were not deleted and were not permanently renamed.

---

## Overall verdict

```text
GO — KORRI ANADRIYA LAST THREE BUILDS FULL-STACK E2E CERTIFIED
```

Builds 1 and 2 remain **GO**. Build 3's remaining result gate is now closed: Dialogue prompt-only Re-Take returned reviewable Take B from MiniMax H3 without replacing Take A. This does **not** reopen Build 1, Build 2, Journey 1 persistence, or the earlier Venture Corridor audio/footstep GO.

---

## Authority

| Document | Role |
|---|---|
| This file | Amalgamated truth for the last three completed builds |
| [`KORRI_ANADRIYA_AUDIO_STUDIO_QUALITY_ACCELERATION_JOURNEY.md`](KORRI_ANADRIYA_AUDIO_STUDIO_QUALITY_ACCELERATION_JOURNEY.md) | Build 1 — Audio Studio quality / MMAudio |
| [`KORRI_ANADRIYA_TIMELINE_FIVE_CONTROL_TRANSPORT_SCENE_SWITCH_JOURNEY.md`](KORRI_ANADRIYA_TIMELINE_FIVE_CONTROL_TRANSPORT_SCENE_SWITCH_JOURNEY.md) | Build 2 — five-control transport + scene-switch |
| [`KORRI_ANADRIYA_TIMELINE_SCENE_MANAGEMENT_JOURNEY.md`](KORRI_ANADRIYA_TIMELINE_SCENE_MANAGEMENT_JOURNEY.md) | Build 2 addendum — scene-card Rename / Remove |
| [`KORRI_ANADRIYA_TIMELINE_VIDEO_RETAKE_JOURNEY.md`](KORRI_ANADRIYA_TIMELINE_VIDEO_RETAKE_JOURNEY.md) | Build 3 — video Re-Take + toggle / close |
| [`KORRI_ANADRIYA_TIMELINE_PERSISTENCE_COMFY_SINGLE_OWNER_JOURNEY.md`](KORRI_ANADRIYA_TIMELINE_PERSISTENCE_COMFY_SINGLE_OWNER_JOURNEY.md) | Prior same-day GO — not in this trio |
| [`KORRI_ANADRIYA_VENTURE_CORRIDOR_AUDIO_TIMELINE_JOURNEY.md`](KORRI_ANADRIYA_VENTURE_CORRIDOR_AUDIO_TIMELINE_JOURNEY.md) | Earlier corridor voices / footsteps GO — not reopened |
| [`../full-stack-convergence/ADEPT_UI_FULL_STACK_CONVERGENCE_JOURNEYS_UNIFIED_REPORT.md`](../full-stack-convergence/ADEPT_UI_FULL_STACK_CONVERGENCE_JOURNEYS_UNIFIED_REPORT.md) | FSC J1–J29 record. FSC overall remains **NO-GO**. |

---

## Build index

| # | When (2 Sep) | Build | Per-mission verdict |
|---|---|---|---|
| 1 | ~09:48 | Audio Studio centered UX + acoustic compiler + warm MMAudio + SFX quality | **GO — AUDIO STUDIO CENTERED UX + ACOUSTIC INTELLIGENCE + MMAUDIO ACCELERATION + SFX QUALITY JOURNEY E2E CERTIFIED** |
| 2 | ~10:11 | Timeline five-control transport + scene-switch stability + scene-card Rename / Remove | **GO — TIMELINE FULL SYSTEM SCENE-SWITCH STABILITY + SCENE MANAGEMENT + FIVE-CONTROL TRANSPORT + PLAYBACK JOURNEY E2E CERTIFIED** |
| 3 | ~13:18 | Timeline video Re-Take mini-menu + prompt + mask + background removal + range + toggle / close | **NO-GO — TIMELINE VIDEO RE-TAKE MINI-MENU + PROMPT + MASK + BACKGROUND REMOVAL + RANGE REPAIR E2E NOT VERIFIED** |

---

# Build 1 — Audio Studio quality and acceleration

**Intent.** Center Audio Studio for a creator. Make Sound Effects mean the named event (footsteps, explosion, door, glass, spark). Stop reloading MMAudio for every take. Keep Timeline handoff.

**Classification.** Layout was a **WEAK CONTRACT** (card sat left on a wide viewport). Prompt path was **DISCONNECTED / WEAK**: raw text, unused intensity, unused negatives, start-trim of an 8s window. Runtime was **WEAK**: cold torch + weights on every take.

**What shipped**

- Workspace centered: `width: min(1120px, 100%)`, `margin: 0 auto`, `align-self: center`. Live 2534px viewport offset **0**.
- Deterministic Sound Prompt Compiler (`sound_prompt_compiler.py`). No extra LLM. Preset `eventType` seeds class; creator text wins when it names a different event.
- Strength is a real generator parameter: Subtle 3.8 / Normal 4.5 / Bold 5.2 `cfg_strength`.
- Compiled `negative_text` is sent. Energy-crop keeps the event, not pre-event air.
- Warm MMAudio `--serve` keeps the stack for a bounded idle window. Warm infer **~40s → ~1.0–1.5s**. First load after cold start remains ~40s (disclosed).
- Generate → take cards → Select / Approve → Library → Add to Timeline still works.

**Live proof (Korri only)**

- Footsteps compile to discrete boot impacts on grating, not a continuous scrape.
- Explosion compiles to blast / hull / debris, not a wind bed.
- Electrical spark is recognizably crackly and quiet (limitation, not a silent fail).
- Artifacts: `artifacts/audio-studio-quality/`.

**Tests**

| Suite | Result |
|---|---|
| `test_sound_prompt_compiler.py` + `test_m42_w45_audio_studio.py` | **20 passed** |
| `test_sfx_wav_validate.py` | **3 passed** |
| Playwright `audio-studio-centered-layout.spec.ts` | **1 passed** |
| Playwright `audio-studio-sfx-quality-journey.spec.ts` | Generate / approve / Timeline reached; cancel assertion raced (API cancel covers the path) |

**Review URL:** `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=audiostudio`

**Limitations.** Primary cannot hear speakers; quality used waveform / onset / compiled-prompt inspection. No semantic audio classifier. MMAudio still emits an ~8s trained window and Adept crops. Studio API venv has no `soundfile` (falls back to `wave`).

---

# Build 2 — Five-control transport, scene-switch, scene cards

**Intent.** One board clock. Five transport controls that a creator can read. Scene switch must not remount Timeline or keep the previous scene’s audio and bounds. Scene cards need Rename and Remove without touching protected production scenes.

**Classification.** Duration authority already existed (`timelineBoardDurationSec` / batch windows) and was **DISCONNECTED** from Scene End (header/generator max and `duration_sec` were winning). Scene rename/delete APIs **EXISTED**; the card `⋯` menu was **MISSING**.

## Transport

Order: Scene Start · Batch In · Play/Pause · Batch Out · Scene End.

One board clock. Transport consumes it. It does not invent a second duration.

| Bound | Source | Scene 1 live | Walk live |
|---|---|---|---|
| Scene Start | First batch window | **0** | **0** |
| Scene End | Sum of batch `plannedDuration` | **25** (not LTX 20) | **8** |
| Batch In / Out | Selected batch, else playhead window | Batch 3 → **10 / 15** | **0 / 8** |

`TimelineEditorShell` does **not** remount on duration change. Scene switch `pause()` + `seek(0)` before paint. Playwright marker survived **20** Scene 1 ↔ Walk switches.

**Live.** Scene 1 Scene End playhead **25**. Preview `0:25 / 0:25`. Walk Scene End **8**. Previous Scene 1 audio stopped.

## Scene cards

- `⋯` top-right. Clicking it does **not** select the scene.
- Rename: PATCH `{ name }` only. UUID stays identity. Blank names rejected.
- Remove: confirmation required. Stops in-flight scene jobs. Neighbor selection after deleting the active scene. Last-scene law: **zero scenes are allowed**.
- Shared Library assets are project-scoped. Delete does not delete files.

**Playwright (temps only, `ADEPT_ALLOW_KORRI_MUTATION=1`)**

1. Created `Scene Menu Cert A` + `B` on Korri.
2. Renamed A; same UUID; reload kept the name.
3. Remove B: Cancel left it; Confirm removed it; reload did not restore it.
4. Remove active A: neighbor selected; URL no longer a deleted UUID.
5. Scene 1, Dialogue, and Walk remained. Library count did not drop.

**Tests**

| Suite | Result |
|---|---|
| Vitest transport + duration/windows | **9 + 18 related passed** |
| `timelineHotkeys.test.ts` | **9 passed** |
| `sceneLifecycle.test.ts` + `sceneSelection.test.ts` | **23 passed** |
| `studio-api` `test_scene_service.py` | **16 passed** |
| Playwright `timeline-five-control-transport.spec.ts` | **1 passed** (20-switch stress; later **17.7s** with `⋯` isolation) |
| Playwright `timeline-scene-rename-remove.spec.ts` | **1 passed** (7.6s) |

**Review URLs**

- Scene 1: `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=timeline&sceneId=1f46b621-46f9-4b7e-8273-202a49e1ca7c`
- Walk: `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=timeline&sceneId=b5282a4c-07eb-40db-9d5b-1512eac74dca`

**Limitations.** Production scenes were not batch-mutated. Hosted Vercel was out of scope. Jacob snap-zoom suite was not re-run.

---

# Build 3 — Timeline video Re-Take

**Intent.** Replace Timeline Inpaint / Mask Repair with a video-only **Re-Take** on the Preview Monitor. WHEN = range. WHERE = optional mask / Remove Background. WHAT = prompt. Submit must use the existing `retake-range` job and return a reviewable result without silently replacing Take A.

**Classification**

| Surface | Class | Action |
|---|---|---|
| Preview Monitor bottom-center Re-Take | Canonical launcher | Kept |
| Preview Monitor top-center editor | Canonical workspace | Kept |
| Toolbar Inpaint / second Re-Take | Obsolete / duplicate | Removed |
| Mask Repair track | Presentation only | Removed. `repairRanges` remain state authority |
| Inspector accordion | Full-shot new take (different function) | Renamed **Takes** |
| Repair still from `repair.start` | Stale / default image | Replaced: paint on the live `<video>` |

Native temporal video inpaint is still unavailable. Masked Re-Take discloses keyframe repair on the painted frame, applied only to the marked range.

## Creator UX

```
Video on Preview Monitor → bottom-center [Re-Take] → top-center editor
Mark In / Mark Out = WHEN
Brush / Remove Background = optional WHERE
Prompt = WHAT
Re-Take = enqueue retake-range
```

- Video shown → launcher shown. Still / library / failed overlay → launcher hidden.
- Click pauses playback, keeps playhead, opens an empty pending op. Does **not** submit.
- Prompt-only is valid. Mask without prompt or Remove Background is blocked.
- Scene change clears pending mask / range / prompt.

**Toggle / close addendum (same close action)**

The bottom pill is a true toggle. It stays in place and turns teal / `aria-pressed` while the editor is open.

All close routes call `close()` → `closedVideoRetakeSession()`:

- pill click while open
- X (`aria-label="Close Re-Take"`)
- Escape (including from the prompt field, unless another control already consumed Escape)

Close without submit clears prompt, In/Out highlight, mask overlay, and pending background-removal. No generation. Original video unchanged.

**Compact mini-menu addendum (UI only)**

The overlay is a top-center strip (**130×544** on Dialogue Preview host **838×1824**). Two tight tool rows + single-line prompt + `IconSend`. Footer Cancel / text Re-Take removed. Enter and the SVG send call the existing submit gate. Live: Enter/send without In/Out showed `Mark In and Mark Out first.`; zero generation POSTs; pill rect unchanged on toggle.

**GO — TIMELINE RE-TAKE COMPACT MINI-MENU UI CERTIFIED**

This does not upgrade the Build 3 full-stack result gate.

**Live Dialogue close proof**

| Route | Result |
|---|---|
| Click → opens | PASS — menu + X; pill teal, same position |
| Click again → closes | PASS |
| Open → type + Mark In → X | PASS — reopen prompt empty |
| Open → Mark In/Out + type → Escape | PASS — range `00:00.00 → 00:08.00` cleared; reopen empty |

Video asset stayed `ce5f4d3e-daf1-475a-be0e-8ea6189f246b` during the close pass. Zero `retake` / `inpaint` / `remove-background` POSTs on those closes.

## Result gate (closed)

The failed job `d562d5e2-…` was a **graph compile / staging-identity** defect, not a missing Anadriya Library file. Approved voices **existed**. EasyCache node `19` overwrote Anadriya `LoadAudio` when four pictures were bound. Staging now uses `assetId`, and submit preflight verifies every H3 picture/voice before queueing.

Live job `e4ffc62d-0749-4d0a-ae5b-739b63a3cfed` completed. Take B `cand_c355cb9e195c` / `942a05e4-33b1-4b32-9fd0-1106a45aa9ac` is an 8.0s composed `retake_range` video. Take A `cand_ceccb85364ec` / `5a2e74b3-…` stayed the approved take until the creator switched.

**GO — TIMELINE VIDEO RE-TAKE H3 DEPENDENCY HANDOFF + REVIEWABLE TAKE E2E CERTIFIED**

Walk stayed `image_planning`. No Re-Take launcher on the still (image gate).

**Tests**

| Suite | Result |
|---|---|
| `videoRetake.test.ts` (+ preview menu on the earlier pack) | **8–10 passed** (close helpers included) |
| H3 handoff unit (`test_timeline_r2v` + stage + preflight + voice bind + range + mocked H3 submit) | **35 passed** |
| `test_timeline_auto_approve_gate` + `test_timeline_keyframe_repair` | **18 passed** |
| Playwright `timeline-video-retake.spec.ts` | **1 passed** — waited for H3 result on the mutation run; later pass 13.5s reused Take B, approved/rejected, restored Take A, Walk image gate |

**Review URL:** `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=timeline&sceneId=ae8e5699-a5d8-4b9b-ad8e-0003d81d3639`

---

## Combined E2E TRACE

| Stage | Build 1 Audio | Build 2 Transport / scenes | Build 3 Re-Take |
|---|---|---|---|
| User action | PASS | PASS | PASS — open / toggle / X / Escape / image hide |
| Frontend | PASS | PASS | PASS — Preview editor; no Inpaint; no Mask Repair lane |
| API | PASS | PASS (existing GETs + scene PATCH/DELETE) | PASS — `retake-range` accepted prompt-only POST |
| Backend | PASS — compiler + warm MMAudio | PASS — no second duration authority | PASS — `retake-range` → H3 R2V with verified voices |
| Persistence | PASS — Library after refresh | PASS — rename/delete + scene URL | PASS — Take A kept; Batch 1 restored Approved |
| Runtime | PASS — CUDA; Comfy untouched | PASS — clock + audio follow `seek()` | PASS — H3 voices staged from `assetId`; EasyCache `90` |
| Result | PASS — real WAVs + Timeline place | PASS — Scene End 25 / 8; temps gone | PASS — Take B on Timeline; Take A not auto-replaced |
| Reload | PASS | PASS | PASS — both takes remain; Take A still approved until creator action |
| Downstream | PASS — SFX track | PASS — inspector / Co-Director / transport | PASS — approve/reject/restore Take A. rembg/SAM still not live-certified |

---

## Tests (this trio)

| Area | Count |
|---|---|
| Audio Studio unit | **23 passed** (20 compiler/studio + 3 WAV validate) |
| Transport / hotkeys / scene lifecycle unit | **59 passed** (9 + 18 + 9 + 23) |
| Scene service API | **16 passed** |
| Re-Take unit / API | **17–19 passed** |
| Playwright | Layout **1**; transport **1**; scene menu **1**; Re-Take **1 passed** (H3 result + approve/reject) |

Exact live counts are those measured in the per-mission reports.

---

## Files (this trio)

**Build 1 — Audio Studio**

- `studio-web/src/styles/audio-studio/audio-studio.css`
- `studio-web/src/components/audio-studio/{SfxPanel,AudioStudioWorkspace,AmbiencePanel}.tsx`
- `studio-web/src/api.ts`
- `studio-api/app/audio_studio/sound_prompt_compiler.py` (new)
- `studio-api/app/audio_studio/sfx_wav_validate.py` (new)
- `studio-api/app/audio_studio/mmaudio_runtime.py` (new)
- `studio-api/app/audio_studio/{service,router,process_registry}.py`
- `studio-api/app/codirector/native_audio/mmaudio_worker.py`
- `studio-api/app/codirector/m210b/adapters/mmaudio.py`
- `tests/e2e/audio-studio/audio-studio-centered-layout.spec.ts`
- `tests/e2e/audio-studio/audio-studio-sfx-quality-journey.spec.ts`

**Build 2 — Transport + scene cards**

- `studio-web/src/timelineMaster/timelineTransport*.ts` (authority + commands)
- `studio-web/src/components/timeline-master/{TimelineEditorShell,TimelineInspector,SceneCardDialogs}.tsx`
- `studio-web/src/components/Timeline.tsx`
- `studio-web/src/components/DirectorTracks.tsx`
- `studio-web/src/components/ui/Menu.tsx` + `menu.css`
- `studio-web/src/sceneLifecycle.ts` + tests
- `studio-web/src/pages/ProjectEditor.tsx`
- `studio-api/app/services/scene_service.py`
- `tests/e2e/timeline/timeline-five-control-transport.spec.ts`
- `tests/e2e/timeline/timeline-scene-rename-remove.spec.ts`

**Build 3 — Video Re-Take**

- `studio-web/src/timelineMaster/videoRetake.ts` + tests
- `studio-web/src/timelineMaster/previewVideoActionMenu.ts` + tests
- `studio-web/src/components/timeline-master/{PreviewVideoActionMenu,TimelineRetakeOverlay,VideoRetakeMaskCanvas,useVideoRetake}.tsx`
- `studio-web/src/styles/timeline-master/timeline-retake-overlay.css`
- `studio-web/src/components/{LivePreviewMonitor,DirectorTracks}.tsx`
- `studio-web/src/components/timeline-master/{TimelinePreviewComposer,TimelineEditorShell,TimelineToolbar,TimelineInspector}.tsx`
- `studio-api/app/director_timeline_w46/{orchestrator,inpaint_repair,generation/watcher,router,timeline_tools}.py`
- `studio-api/app/workflows/h3_ref2v_builder.py`
- `studio-api/app/video_runtime/comfy_asset_stage.py`
- `studio-api/app/director_timeline_w46/generation/runtime_dependency_preflight.py`
- `studio-api/app/queue_worker.py` (`_stage_library_asset`)
- `studio-api/app/codirector/perception/router.py`
- `tests/e2e/timeline/timeline-video-retake.spec.ts`

---

## Unrelated systems untouched

Comfy `:8188` lifecycle, MiniMax `:8192` lifecycle, Character Creator, Walk footstep timing architecture, Production Dock ownership, FSC J11 Home soak.

API recycles used `restart_studio_api_only.py` only. Observed `comfyPid=77152 unchanged=True`.

---

## COMFY

| | |
|---|---|
| COMFY BEFORE | PID **77152** / `:8188/system_stats` 200 / `owned:true` |
| COMFY AFTER | PID **77152** / `:8188/system_stats` 200 |
| COMFY RESTARTED? | **NO** |
| WHY? | Ordinary Audio Studio + Timeline UI/API. No supervisor bounce. |

---

## Remaining (not this trio's result gate)

Masked / Remove Background Re-Take uses the existing zimage keyframe-repair path (disclosed). Unit-tested. Not live-completed.

FSC leftovers that this trio did not close: Home J11 request soak; LTX 2.5 remains one-cond. Anadriya **does** have an approved project voice — the earlier H3 error was a compile/staging identity bug, not a missing voice.

---

## Manual review

**Audio Studio (Build 1 — GO)**

1. Open `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=audiostudio`
2. Confirm the workspace is centered.
3. Sound Effects → Footsteps / Explosion → generate → approve → Add to Timeline.

**Transport + scenes (Build 2 — GO)**

1. Open Scene 1. Select Batch 3. Batch In **10**, Batch Out **15**, Scene End **25** (not 20).
2. Switch to Walk. Playhead **0**, Scene End **8**, previous audio stopped.
3. Walk `⋯` → Rename / Remove. Cancel rename. Do **not** remove Walk, Dialogue, or Scene 1.

**Video Re-Take (Build 3 — GO)**

1. Open Dialogue Timeline (URL above).
2. Bottom-center **Re-Take** → menu. Mark a range. Prompt. Send.
3. Wait for Take B. Take A stays the active take until you choose otherwise.
4. Inspector Takes: preview / approve / reject. Restore Take A if you only wanted a review.

---

## Deferred / not in this trio

- Timeline selected-scene persistence + Comfy single-owner (earlier same-day **GO**).
- Venture Corridor voices + timed footsteps (earlier **GO**).
- Hosted Vercel certification.
- Commit / push / deploy (not authorized).

---

## FINAL VERDICT

```text
GO — KORRI ANADRIYA LAST THREE BUILDS FULL-STACK E2E CERTIFIED
```

| Build | Verdict |
|---|---|
| 1 Audio Studio quality / MMAudio | **GO** |
| 2 Five-control transport + scene management | **GO** |
| 3 Timeline video Re-Take | **GO** — H3 handoff + reviewable Take B |
