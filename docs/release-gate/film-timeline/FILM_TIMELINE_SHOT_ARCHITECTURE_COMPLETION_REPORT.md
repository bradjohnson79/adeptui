# Film Timeline Shot Architecture — Unified Completion Report

**Date:** 2026-09-27  
**Branch:** `feat/character-creator-final-closure`  
**HEAD SHA:** `ca8f3c0cc25cf09e665047363cfb4ebecc2bb89b`  
**Working tree:** uncommitted. `studio-api/app/film_timeline/` and `studio-web/src/components/film-timeline/` are untracked. Edited production files include `studio-api/app/director_timeline_w46/router.py` and `studio-web/src/pages/ProjectEditor.tsx`.  
**This document** is the governing report for the Film Timeline shot-architecture cutover. Earlier Timeline completion reports describe the batch, window, and ContinuityBridge system and stay historical.

## Closure pass — 2026-09-27

The shell is now a 40/60 Film Timeline with no right column. Duration is a 3–15 second dropdown. Models come from `GET /api/film-timeline/capabilities`, split into Local and API, with unavailable API rows disabled. Voice, music, and ambience clips fold into one Audio lane and keep their role. SFX stays separate. Empty lanes are not rendered. Timed Prompt sits under the monitor.

Browser check on `http://127.0.0.1:5173/project/bd6a5e6a-33c2-44a8-a115-8d37301d9d56?workspace=timeline` showed Shot 01, the empty preview, a saved Timed Prompt, Generate Shot, Continue Shot, and Library actions Reference and Add to Timeline. No generation was started on that project.

`save_master` returns without writing when `filmTimeline.version` is already stored. `apply_build_shot` and `apply_propose_add_image_clip` place a reference through `add_to_timeline` and do not render.

`TimelineEditorShell` is deleted. The `DirectorTracks` component is removed; the file remains only as shared types for modules that are no longer the Timeline screen. `submit_batch_generation` now raises `FILM_TIMELINE_REQUIRED` before it can queue a batch. Continue Shot after reload and real provider jobs were not run.

## Verdict

**NO-GO — FULL-STACK E2E NOT VERIFIED**

Film Timeline is the mounted creator Timeline and the old generate, extend, retake, stitch, batch, and inpaint-submit routes refuse work on the live Studio API. Certification is not closed. Browser create, generate, continue, reload, and provider jobs were not run. `SceneTimelineMaster` can still be read, and some Co-Director tools can still write it.

## Owner unlocks used

- `Owner unlock: timeline`
- `Owner unlock: API multi-window pipeline`
- `Owner unlock: timeline-reference-identity`

The MiniMax H3 multi-window handoff row was not unlocked. `window_handoff` and the H3 adapter internals were not rewritten.

## Backup

Recovery only. This folder is not imported.

| Item | Value |
| --- | --- |
| Path | `backups/timeline-pre-simplification/2026-09-26-ca8f3c0cc25c/` |
| Restore notes | `backups/timeline-pre-simplification/2026-09-26-ca8f3c0cc25c/RESTORE.md` |
| Source SHA | `ca8f3c0cc25cf09e665047363cfb4ebecc2bb89b` |
| Date | 2026-09-26 |
| Contents | Timeline frontend trees, `director_timeline_w46`, Co-Director Timeline tools, `timeline_builder.py`, `studio-api/tests`, timeline-named e2e files |

Restore copies a tree back over the live path and recycles Studio API. It does not migrate `filmTimeline` documents backward.

## What landed

Creator actions are Create Shot, Generate Shot, Continue Shot, and New Shot. Provider duration, continuation strategy, frame chaining, and Comfy workflow stay inside the orchestrator.

| Authority | Production owner |
| --- | --- |
| Timeline UI | `FilmTimelineShell` on the Timeline tab and on the director workspace Timeline and Prompt panes |
| Persistence | `director_json.filmTimeline` via `studio-api/app/film_timeline/store.py` |
| Shot continuity | `ShotState` on the shot. Provider continuation handles stay on `segment.generationMetadata` |
| Video orchestration | `studio-api/app/film_timeline/orchestrator.py`, which calls the existing adapter registry |
| Media insertion | `add_to_timeline` and `studio-web/src/filmTimeline/addToTimeline.ts` |
| Co-Director render boundary | Authoring writes a shot and Timed Prompt. `generate_shot` and `continue_shot` are the render calls |

Existing adapters were kept and called through that orchestrator: MiniMax H3 local, LTX 2.5, Seedance 2.0 / 2.5 / Mini / Fast, Kling, and Veo. No Happy Horse, Flux, or WAN adapter was added. WAN remains retired in the registry.

Duration planning refuses a length the selected model cannot compose. Veo 4/6/8 cannot be summed into a fake 15-second Veo call. A shot that already has a completed segment does not start another first generation. Continue Shot requires a completed segment and a new Timed Prompt. A planned later segment is submitted by sync only when `film.renderSessionId` matches the current Studio API session. Loading a film from a previous session marks in-flight segments interrupted and does not submit.

One-time migration turns ordered windows of a scene take into segments of one shot. Ambiguous audio is left unplaced.

H3 motion-context was audited and not adopted. `MOTION_CONTEXT_AVAILABLE` is `False` in `studio-api/app/film_timeline/strategies.py`. ComfyUI-H3-Motion-Context is not in this repository. Its license was not cleared, and its Timeline UI, stitcher, and clip planner were not imported. MiniMax continuation uses the model’s declared reference-video capability plus `ShotState`.

## Legacy execution closed on the live API

These production callers no longer submit the old batch orchestrator:

- `POST /api/director-timeline/.../generate` and batch generate
- extend, extend-segment retake, rematerialize execution windows
- retake, retake-range, stitch, place-visual-image-range, add-clip
- add, duplicate, and delete batch
- batch patch, complete, approve, reject, cancel, repair-range
- continuity-bridge retry, continue-without-bridge, and downstream reconcile
- inpaint submit and apply
- `review_and_extend`, `start_new_take`, `resume_scene_take`, `retake_extend_segment`
- Co-Director `timeline.propose_generate_scene`, `propose_add_batch`, `propose_retake`, and execute-inpaint
- “generate shot N” resolves `filmTimeline.shots`, not `batchBlocks`

Observed after Studio API recycle: `POST /api/director-timeline/projects/none/scenes/none/generate` returned **410** with `FILM_TIMELINE_REQUIRED`.

## Certification checklist

| Required confirmation | State |
| --- | --- |
| One live Timeline UI | **PARTIAL.** `ProjectEditor` mounts `FilmTimelineShell` for the Timeline tab and the director Timeline/Prompt panes. `TimelineEditorShell` and `DirectorTracks` remain on disk and are not mounted from `ProjectEditor`. |
| One Timeline persistence model | **PARTIAL.** Production reads and writes `filmTimeline`. `GET` master and scene-take list routes can still return `SceneTimelineMaster`. |
| One Shot continuity owner | **IMPLEMENTED** in `ShotState`. ContinuityBridge routes that used to mutate it now return 410. The bridge module remains in the package. |
| One video orchestrator | **PARTIAL.** Film Timeline submits through `film_timeline.orchestrator`. `director_timeline_w46.orchestrator.submit_batch_generation` remains in the package and is no longer called by the retired routes. |
| One media insertion path | **PARTIAL.** Library, Audio Studio, voice place, and the shell call `addToTimeline`. Co-Director `apply_build_shot` and image-clip proposal code can still write the old master. Pending audio lane choice is not fully wired in the shell. |
| One Co-Director Timeline boundary | **PARTIAL.** Authoring does not call render. Explicit generate and extend call Film Timeline. Older proposal tools that build shots and clips were not all removed. |
| No production dual-stack | **FAIL.** The previous package, shell, and master document remain in the repository and some read and write paths still reach them. |

## Runtime observed 2026-09-27

| Surface | Result |
| --- | --- |
| Studio API | `http://127.0.0.1:8758/api/healthz` **200**. Recycled only. Previous PID 29408, new PID 21628. |
| Creator UI | `http://127.0.0.1:5173/` **200**. Vite was already up. No production web build was run for this cutover. |
| Comfy before | PID **27852**, `GET http://127.0.0.1:8188/system_stats` **200** |
| Comfy after | PID **27852**, `GET http://127.0.0.1:8188/system_stats` **200** |
| Comfy restarted? | **NO** |

## Tests

```text
studio-api\.venv\Scripts\python.exe -m pytest tests\test_film_timeline.py tests\test_timeline_architecture_guard.py -q --tb=line
8 passed in 0.67s
```

Covered by those tests: duration plans for 5/10/15, Veo 15 refused, window-to-one-shot migration, ambiguous audio not auto-routed, reference-video strategy chosen ahead of motion-context, and `generate_scene` containing `_film_timeline_only()` and not `orchestrator.generate_scene`.

| Check | State |
| --- | --- |
| Film Timeline unit tests | **TESTED** — 8 passed |
| Frontend contract tests | **NOT VERIFIED** this session. Source expectations were updated. Vitest was not re-run. |
| Playwright creator workflow | **NOT VERIFIED** |
| Reload, then Continue Shot | **NOT VERIFIED** |
| Real MiniMax, LTX, Seedance, Kling, or Veo media | **NOT VERIFIED** |
| Full `studio-api` Timeline suite | **NOT VERIFIED**. Older tests still call retired extend and take functions and will fail if run. |

## E2E trace

| Hop | State |
| --- | --- |
| User action | **NOT VERIFIED** in the browser |
| Frontend | **IMPLEMENTED.** `FilmTimelineShell` is the mounted Timeline |
| API | **LIVE VERIFIED** only for health and the retired generate route returning 410 |
| Backend | **IMPLEMENTED** for Film Timeline commands |
| Persistence | **IMPLEMENTED.** Reload survival was not executed on a project |
| Runtime / provider | **NOT VERIFIED.** No generation job was submitted |
| Result / Library | **NOT VERIFIED** |
| Reload | **NOT VERIFIED** |
| Downstream | **NOT VERIFIED** |

## Provider capabilities

These rows are the capability objects in the existing adapters. They are not live generation proof. No new adapters were created.

| Model | Durations the adapter declares | Continuation signals the strategy registry can see |
| --- | --- | --- |
| MiniMax H3 local | No fixed list. `maxDurationSec` 15. Longer shots chunk at that max. | `supportsVideoReferences` and `supportsReferenceToVideo`. `supportsImageToVideo` is false. |
| LTX 2.5 | 5, 8, 10, 15, 20 | Image-to-video, start frame, end frame, reference-to-video. `supportsVideoReferences` is false, so reference-video is not selected. |
| Seedance 2.0, Mini, Fast | 4 through 15 | Image-to-video, start and end frame, video references |
| Seedance 2.5 | 4 through 30 | Same reference flags as 2.0 |
| Kling | 5, 10 | Image-to-video and start frame. A 15-second shot plans as 5 then 10. Video references are false. |
| Veo 3.1 | 4, 6, 8 | Image-to-video and start frame. A 15-second request raises `DurationUnsupported`. |

## Open source evaluated

| Candidate | Decision |
| --- | --- |
| ComfyUI-H3-Motion-Context / OBVPM-style latent continuation | **Evaluated, not adopted.** License, compatibility, and runtime were not confirmed. External Timeline UI, stitching, and clip planning were not imported. |
| Happy Horse, Flux, WAN | **Not added.** WAN is already retired. Happy Horse and Flux have no Timeline adapter in this repository. |

## Remaining before GO

1. Remove or stop the remaining `SceneTimelineMaster` read and write paths, including Co-Director shot-build and image-clip tools, so production has one persistence model.
2. Delete unmounted Timeline production UI after confirming no live import, instead of leaving it beside Film Timeline.
3. Run the creator workflow in the browser: Create Shot, Generate Shot, Continue Shot, New Shot, Add to Timeline for each lane, reload, and confirm the continued shot still inherits `ShotState`.
4. Run one real job per supported adapter that is available in this environment, and record returned media. Do not mark a model working from its capability flags.
5. Re-run the Film Timeline tests plus the frontend contract tests, and either update or remove Timeline tests that still require the retired batch runtime.
6. Wire the pending-placement lane picker so ambiguous audio is placed only after the creator chooses Voice, Music, SFX, or Ambience.

## Manual review path

1. Open `http://127.0.0.1:5173/` and a project Timeline.
2. Confirm the visible actions are Create Shot, Generate Shot, Continue Shot, and New Shot.
3. Do not use this screen as certification until a generated segment survives reload.
