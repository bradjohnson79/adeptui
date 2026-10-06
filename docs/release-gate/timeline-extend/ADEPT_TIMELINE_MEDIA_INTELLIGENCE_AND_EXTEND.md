# Timeline Media Intelligence + Long-Form Extend

**Milestone:** Timeline Qwen AV Intelligence + Co-Director Audio + Long-Form Extend  
**Status:** NO-GO  
**Authority:** Primary agent. Subagents returned `READY FOR PRIMARY REVIEW`.  
**Branch:** `feat/character-creator-final-closure` @ `b6156455`  
**Consumes:** `docs/release-gate/media-intelligence/ADEPT_MEDIA_INTELLIGENCE_ARCHITECTURE.md`  
**Does not replace:** Media Intelligence, Co-Director planner, Timeline, Retake, `AudioService.place_cue`.

## Frozen reuse

| Authority | Location | Role |
|---|---|---|
| Media Intelligence | `codirector/video_intelligence/` | Watch + hear Timeline media. Packet `media-intelligence-v1`. |
| Temporal continuity | `TemporalContinuityPacket` | Batch handoff observation. Never renamed. |
| Long-form Continuity Packet | `LongFormContinuityState` (`long-form-continuity-v1`) | Compiled scene continuation state on `SceneTimelineMaster`. |
| Audio placement | `AudioService.place_cue` | Only Timeline audio write path. |
| Planner | `ExecutionPlan` + capability handlers | `analyze.video`, `timeline.add_audio`, `timeline.extend`. |
| Generation | existing H3 I2V/R2V + batch generate | One legal H3 segment at a time. No Turbo/VDN/Sage. |
| Retake | existing Take A/B + `downstreamStale` | Selective rerender of one segment. |

## Hard rules

- No second Timeline, planner, or Media Intelligence authority.
- Qwen does not place audio. Co-Director decides; `place_cue` writes.
- Visible contact timestamps beat 0.55s cadence. Disclose `timingSource`.
- Existing Audio Studio / Library assets first.
- Extend adds the next Batch Block. Creator still sees one scene.
- One H3 generation resident at a time. Clean H3 path only.
- Stale downstream continuity must be invalidated when an earlier take is replaced.
- Comfy `:8188` is read-only for this mission. Route A `:8192` is the H3 runtime.

## Capabilities (additive)

- `analyze.video` → `capabilities/handlers/analyze_video.py`
- `timeline.extend` → `capabilities/handlers/timeline_extend.py`
- `timeline.add_audio` already exists — contact-first timing.

## Verdict language

`GO — TIMELINE QWEN AV INTELLIGENCE + CODIRECTOR AUDIO ORCHESTRATION + LONG-FORM EXTEND PIPELINE E2E CERTIFIED`  
or  
`NO-GO — TIMELINE MEDIA INTELLIGENCE OR EXTEND CONTINUITY STILL HAS A BROKEN BOUNDARY`

---

## Final verdict

**NO-GO — TIMELINE MEDIA INTELLIGENCE OR EXTEND CONTINUITY STILL HAS A BROKEN BOUNDARY**

**First failure:** Live H3 Review & Extend generation through the product UI/API was not executed. Scene 4 (`a4c85c6d-2f0e-4e49-8535-7c698306f398`) correctly refuses with `NO_PLAYABLE_SCENE_VIDEO`. Scene 1 has approved playable H3 takes, but a live 5s Route A generation (live drafts, duration growth, retake of the newest segment, downstream invalidation, reload of extend state, API-recycle resume) was not run. Source, unit tests, and Qwen AV proof do not close that boundary.

---

## QWEN TIMELINE AV PROOF

**LIVE VERIFIED** on Korri project `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`, Scene 1 Batch 2 approved H3 take `6ffc37c9-2887-4fd2-be27-25421807a610`.

Evidence: `.runtime/_mi_timeline_av_proof.json`

| Fact | Observed |
|---|---|
| Source | Real playable H3 MP4, not transcript/metadata |
| Audio stream | AAC, 32 kHz, stereo (`ffprobe`) |
| Ingestion | `useAudioInVideo=true`; video tensor `[10, 3, 308, 504]`; audio `[82944]` float32 |
| Model | `qwen2-5-omni-7b` invoked on `NVIDIA GeForce RTX 5090` |
| Runtime | load+infer 39.447s; 20.404 GB VRAM |
| Availability | `ready` |
| What it saw | Two characters walking a dim corridor |
| What it heard | Speech; Japanese transcription in `speechSegments[0]` |
| Timeline context | `projectId` / `sceneId` / `clipAssetId` / range `0–5.2s` |

First product-path attempt failed `INSUFFICIENT_VRAM` (0.82 GB) because idle-warm Route A `:8192` held ~31 GB and Media Intelligence only called Comfy `:8188` `/free`. Fixed: `gpu_lease.best_effort_free_generator` now uses existing `free_route_a_models` and waits for VRAM (worker-async unload). After handoff, nvidia-smi showed ~30 GB free; Qwen then ran.

Scene 1 stitch `0bf05076-…` is **silent** (0 audio streams). It is not a valid hear-proof.

## MEDIA INTELLIGENCE PACKET

Frozen `media-intelligence-v1` with additive `contactEvents.timingSource`, `cueOpportunities[]`, `musicOpportunities[]`, `sceneChanges[]`, `cameraMotion[]`, `TimelineAnalysisContext`.

Live packet on the H3 take: 1 visual event, 1 audio event (`presentInAudio=true`), 1 speech segment. `contactEvents`, `cueOpportunities`, `musicOpportunities`, `motionEvents`, `sceneChanges`, `cameraMotion` were empty on this 5.2s window — Qwen did not invent them.

## CONTACT EVENTS

Schema + contact-first planner exist (`audio_timing.plan_contact_hits`). **Live clip returned zero contacts.** Footstep placement therefore used cadence and disclosed it.

## SFX OPPORTUNITIES

Schema + `analyze.video` question request them. **Live packet: none.** Co-Director still placed SFX via the footstep path using Library SFX (cadence fallback).

## MUSIC OPPORTUNITIES

Schema present. **Live packet: none.** Music start/duration therefore used scene length (12s), not a Qwen music window.

## CODIRECTOR AUDIO REASONING

Speech-act routes: watch/review → `analyze.video`; footsteps/SFX/music → `timeline.add_audio`; extend → `timeline.extend`. Qwen does not write Timeline audio. **Live CD planner/pending-brief UI journey was not run.** Handler-level reasoning + `place_cue` was.

## AUDIO STUDIO REUSE / GENERATION

Library-first. Korri already has `sfx_gen` (54), `ambience_gen` (2), `music_gen` (1). Live placement reused approved Library assets. No new SFX/music generation was started.

## AUDIO PLACEMENT

**LIVE VERIFIED** through `timeline.add_audio` → `AudioService.place_cue` on Scene 1.

| Kind | Result | Notes |
|---|---|---|
| Music | completed | Library music; start 0s, 12s |
| Ambience | completed | Library bed across the scene |
| Footsteps | completed | 44 hits for Korri + Anadriya |

Evidence: `.runtime/_mi_audio_place_proof.json`

Duck phrasing `"under the dialogue"` did not match `_DUCK_UNDER_DIALOGUE_RE` on the live music call (`ducking: false`). Regex now accepts optional `the`. Not re-placed after the fix.

## TIMELINE PLAYBACK

Cues were written through the canonical director/SFX path. **Browser playback of the new cues at intended times was not re-verified** after the 44 footstep placements.

## EXTEND ARCHITECTURE

`director_timeline_w46/extend_service.py` `review_and_extend`:

1. Same-project playable (stitch if current → approved take → latest output)
2. `analyze_asset` on that clip
3. `compile_longform_continuity`
4. Ending-anchor extract (disclosed if it fails)
5. `add_batch` with legal H3 duration snap `{5/24, 5, 8}` (never >8s)
6. Persist `ExtendSegment` + `longFormContinuity`
7. `orchestrator.generate_scene(scope="selected", batch_ids=[new])` only

No second Timeline. Clean H3 adapters only (`minimax-h3-t2v-local` / `minimax-h3-i2v-local`).

UI: **Review & Extend** (`timeline-header-review-extend`) on Vite. Clickable; if no approved playable, notice — not a dead button. Body: `{ prompt, durationSec: 5 }`.

Live API: Scene 4 POST `/extend` → **400** `NO_PLAYABLE_SCENE_VIDEO`. No H3 job started.

## CONTINUITY PACKET

`LongFormContinuityState` on `SceneTimelineMaster` (`long-form-continuity-v1`). Report name: Continuity Packet. **Not populated by a live successful extend.**

## ENDING ANCHOR SELECTION

Reuses `continuity.extract_last_frame_png` / last-frame helpers. Failure is disclosed (`anchorError`), not silent. **Not live-verified on an extend run.**

## H3 MODE SELECTION

`select_h3_mode`: R2V when multi-character / ERS / identity risk; I2V when last-frame is enough. Unit-covered. **Not live-verified.**

## CRS / ERS / PRS REBINDING

`_scene_reference_bindings` by canonical IDs, not chat names. **Not live-verified.**

## SEGMENT GENERATION

Designed as one new Batch Block / one H3 segment. **Not live-generated.**

## LIVE DRAFT PREVIEW

Reuses certified H3 draft-preview. No special Extend preview engine. **Not live-verified for an extension segment.**

## CONTINUITY REVIEW

After each segment, `analyze_asset` is intended to refresh the packet and compile a multi-axis report (identity / environment / motion / camera / audio / seam). **Not live-verified.**

## RETAKE

`POST .../extend-segments/{segment_id}/retake` → existing Take A/B + `mark_downstream_stale`. **Not live-verified.**

## SELECTIVE RERENDER

Retake targets one segment’s batch only. **Not live-verified.**

## DOWNSTREAM INVALIDATION

`mark_downstream_stale` on later `ExtendSegment` rows. Unit-covered. **Not live-verified.**

## AUDIO CONTINUITY

Ambience/music are Timeline-level cues, not per-H3-segment restarts. Native H3 audio is preserved on takes that have it (Batch 2 has AAC). Scene stitch is silent — a full-scene hear-pass on the stitch cannot hear native H3 beds. **Cross-join audio continuity after extend: NOT VERIFIED.**

## LONG-FORM SCENE STATE

One scene, internal `extendSegments[]`. **No live multi-segment scene exists from this journey.**

## PLANNER

`timeline.extend` handler calls `review_and_extend`. Multi-step ExecutionPlan wiring exists as capabilities. **Live “three more shots” plan was not run.**

## CANCEL

Cancelled candidate stays off canonical history (`segment.status=cancelled`). **Not live-verified.**

## RELOAD

Review & Extend button survived Vite load. Extend segment state **has no live instance to reload.** Music/SFX/ambience cues are in director JSON (canonical persist). **Cue reload after browser refresh was not re-checked.**

## API RECYCLE

Studio API recycled twice (`restart_studio_api_only.py`).  
`oldPid=28516 → 18652 → 40256`. Comfy PID **26520 unchanged**.  
Cannot resume “extend another 5 seconds” — no durable extend segment was created.

## PROJECT ISOLATION

`resolve_asset_file` / playable resolution fail closed across projects. Unit-covered. **No cross-project live attack test.**

## PLAYWRIGHT AUDIO

Spec not written as a full cue-timing journey. Live `place_cue` was API-level.

## PLAYWRIGHT EXTEND

`tests/e2e/timeline-review-extend.spec.ts` — Scene 4 button + notice. **Harness failed:** Playwright Chromium missing in this environment (`chrome-headless-shell` not installed). Button **was** verified in the Cursor browser on `http://127.0.0.1:5173/` (`Review & Extend` visible, enabled, GPU tab present). Clicking Scene 4 does **not** start H3 (`canReviewExtend` is false → notice).

## COMBINED JOURNEY

“Review this scene, extend it… then add footsteps, ambience, and subtle music” through Co-Director PLAN → ACT in the real UI: **NOT VERIFIED.**

## PEER REVIEW

Independent GLM pass (source): 13 architecture boundaries PASS; item 14 live GPU E2E NOT VERIFIED at that time.

Primary live follow-up:

| Challenge | Result |
|---|---|
| Does Qwen actually see/hear Timeline media? | **YES** on Batch 2 H3 take (ingestion evidence). |
| Are timestamps real? | Speech/visual windows 0–2.5s from Qwen; not frame-perfect contacts. |
| Does CD place audio through canonical services? | **YES** — `place_cue` only. |
| Are visible contacts used for footsteps? | **NO on this clip** — 0 contacts; cadence disclosed. |
| Can music be placed without masking dialogue? | Music placed; live call did **not** duck (`under the dialogue` miss). Fix landed, not re-proven. |
| Does Extend use full-scene continuity state? | Implemented; **not live**. |
| Is H3 only rendering one segment at a time? | Designed; **not live**. |
| Are character refs rebound canonically? | Designed; **not live**. |
| Can segments be rerun independently? | Designed; **not live**. |
| Does Retake preserve prior approved work? | Designed; **not live**. |
| Is stale downstream continuity invalidated? | Designed + unit; **not live**. |
| Does audio continue naturally across joins? | **NOT VERIFIED.** |
| Survive refresh / API recycle? | API recycle proven; extend state N/A. |
| Project isolation strict? | Fail-closed in resolver; **no live leak test**. |
| Live draft preview still work? | Not exercised for Extend. |
| Clean H3 A/V preserved? | No Turbo/VDN/Sage added. Native AAC on Batch 2 left intact. |
| Second Timeline / planner / MI authority? | **No.** |
| Turbo/SpeedCache/VDN introduced? | **No.** |
| Combined UI journey complete? | **No.** |

## FILES CHANGED (this journey — primary + subagents)

Capabilities / MI / audio

- `studio-api/app/codirector/capabilities/registry.py`
- `studio-api/app/codirector/capabilities/handlers/analyze_video.py`
- `studio-api/app/codirector/capabilities/handlers/timeline_extend.py`
- `studio-api/app/codirector/capabilities/handlers/timeline_add_audio.py`
- `studio-api/app/codirector/conversation/foundation/speech_act.py`
- `studio-api/app/codirector/video_intelligence/media_packet.py`
- `studio-api/app/codirector/video_intelligence/media_analyze.py`
- `studio-api/app/codirector/video_intelligence/media_router.py`
- `studio-api/app/codirector/video_intelligence/worker.py`
- `studio-api/app/codirector/video_intelligence/gpu_lease.py`
- `studio-api/app/codirector/video_intelligence/audio_timing.py`
- `studio-api/app/codirector/m29/audio/service.py`

Extend

- `studio-api/app/director_timeline_w46/contracts.py`
- `studio-api/app/director_timeline_w46/longform_continuity.py`
- `studio-api/app/director_timeline_w46/extend_service.py`
- `studio-api/app/director_timeline_w46/router.py`
- `studio-web/src/timelineMaster/contracts.ts`

UI

- `studio-web/src/api.ts`
- `studio-web/src/components/timeline-master/TimelineEditorShell.tsx`
- `studio-web/src/components/timeline-master/TimelineInspector.tsx`

Tests

- `studio-api/app/codirector/video_intelligence/test_media_analyze.py`
- `studio-api/app/codirector/video_intelligence/test_gpu_lease.py`
- `studio-api/tests/test_analyze_video.py`
- `studio-api/tests/test_timeline_add_audio.py`
- `studio-api/tests/test_timeline_extend.py`
- `tests/e2e/timeline-review-extend.spec.ts`

## Tests run (measured)

- `test_timeline_extend.py` + `test_analyze_video.py` + `test_timeline_add_audio.py`: **30 passed** (earlier integration)
- `test_gpu_lease.py` + `test_timeline_add_audio.py`: **8 passed**
- `test_gpu_lease.py` alone after wait-for-VRAM: **2 passed**
- Playwright `timeline-review-extend.spec.ts`: **1 failed** (browser binary missing; not a product assertion)

## RUNTIME BEFORE / AFTER

| | Before | After |
|---|---|---|
| Studio API | PID 28516 / 18652 | PID **40256** (recycle only) |
| Vite | `http://127.0.0.1:5173/` | same, HTTP 200 |
| Studio API | `http://127.0.0.1:8758/api/healthz` | HTTP 200 |
| Comfy `:8188` | PID **26520** healthy | PID **26520** healthy |
| Route A `:8192` | idle-warm, ~31 GB | `/free` during Qwen lease; process left running |
| GPU | RTX 5090 32 GB | Qwen used 20.4 GB then unloaded (~1.6 GB) |

**COMFY BEFORE:** PID 26520 / `GET /system_stats` 200  
**COMFY AFTER:** PID 26520 / `GET /system_stats` 200  
**COMFY RESTARTED?:** NO  
**WHY?:** Ordinary API recycle + Media Intelligence. `:8188` read-only.

## Remaining to reach GO

1. Live Review & Extend on Scene 1 (approved playable exists) through UI or `POST /extend` — one legal 5s clean H3 segment on `:8192`.
2. Live drafts → final segment → Timeline duration grows → reload + API recycle resume.
3. Second extend, then Retake only the newest segment; prove prior segment unchanged and downstream continuity recomputed.
4. Full-scene Qwen pass on a stitch that actually contains audio (current Scene 1 stitch is silent).
5. Contact-timed footsteps on a clip that yields `contactEvents`.
6. Playwright audio + extend + combined journeys against installed Chromium.
7. Duck-under-dialogue re-proof after the regex fix.

## Manual review

- Local UI: `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=timeline&sceneId=1f46b621-46f9-4b7e-8273-202a49e1ca7c`
- Review & Extend is live. On Scene 1 it **will start a real H3 job** (approved playable exists). On Scene 4 it notices and does not generate.
- Scene 1 now has newly placed music, ambience, and 44 cadence footstep cues from this journey. Delete or keep as you prefer.
- Do not use Scene 4 for extend certification until a take is approved.
