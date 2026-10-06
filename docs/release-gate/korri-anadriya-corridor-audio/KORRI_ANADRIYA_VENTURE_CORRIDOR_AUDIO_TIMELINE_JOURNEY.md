# Korri + Anadriya Venture Corridor Scene + Voices + Timed Footstep SFX

Governing report for the live Korri Anadriya production journey. Historical Scene Creator / Audio Studio / Timeline reports remain historical.

**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `b6156455`  
**Review URL:** `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=timeline`  
**Studio API:** `http://127.0.0.1:8758/`

## Verdict

**GO — KORRI + ANADRIYA VENTURE CORRIDOR SCENE + VOICES + TIMED FOOTSTEP SFX TIMELINE JOURNEY E2E CERTIFIED**

## Live IDs

| Field | Value |
|---|---|
| PROJECT ID | `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` |
| NEW SCENE ID | `b5282a4c-07eb-40db-9d5b-1512eac74dca` |
| SCENE NAME | Venture Corridor Walk |
| CORRIDOR ASSET ID | `2b1f1901-af59-4368-b1ef-64175a8d1a23` (PNG 3,536,637 bytes) |
| KORRI CHARACTER ID | `4a2e9cbe-e1e0-4d87-a411-6a8851b2f0ed` |
| KORRI CRS ASSET ID | `a97963c4-09b3-402b-8341-8f0539b4bc0b` |
| ANADRIYA CHARACTER ID | `4c1c0bc8-a771-4998-b652-5d549b2a2b8d` |
| ANADRIYA CRS ASSET ID | `7e5a01f4-19cc-4b6b-b323-1b2e01bbf4ad` |
| KORRI VOICE ID | `283e8cf8-3c59-4a9e-8ba9-2f7ba1535ad2` — Korri Clone — `qwen3-tts` — APPROVED |
| ANADRIYA VOICE ID | `5c221441-44ae-4cae-b738-e461558b771e` — Anadriya Clone — `qwen3-tts` — APPROVED |
| KORRI DIALOGUE ASSET | `9eacb9f4-d946-41f8-ab97-18a64b4ce7f7` — RIFF WAV 157,484 bytes |
| ANADRIYA DIALOGUE ASSET | `06435046-0467-4010-98e3-6b73b7f1746a` — RIFF WAV 130,604 bytes |
| FOOTSTEP SFX ASSET | `667da9c9-bc74-4848-b895-08b1a4f2e60b` — RIFF WAV 32,044 bytes |
| KORRI FOOTSTEP CLIPS | 15 director `sfx_clips`, label `Korri footsteps`, starts `0.00 + n×0.55` |
| ANADRIYA FOOTSTEP CLIPS | 15 director `sfx_clips`, label `Anadriya footsteps`, starts `0.22 + n×0.55` |
| TIMELINE BATCH | Batch 1, `0.00s–8.00s`, MiniMax H3 |
| SPATIAL MAP | `7c7aac85-6932-4945-a13f-4a11fd69b79f` |
| ERS SHEET | `2a48dd6e-ad29-4dce-9c2f-2e9f2ed61f46` |
| HANDOFF | `aa2b1848-8298-52e0-a1a2-f7efd20661bf` |

Existing scenes were left intact: Scene 1 `1f46b621-…`, Venture Corridor Dialogue `ae8e5699-…`. No new project was created.

## Phase 1 classification

| Surface | Class | Note |
|---|---|---|
| Korri / Anadriya CRS | EXISTS | Canonical approved sheets; `@Korri` / `@Anadriya` resolve to those IDs |
| Assigned voices | EXISTS | Existing clones; not duplicated |
| Venture corridor Library image | EXISTS | Reused; not regenerated |
| Scene Creator / Spatial Map bind | EXISTS | Corridor + both CRS placements persisted |
| Audio Studio dialogue | EXISTS | Real Qwen3-TTS WAVs in Library |
| Co-Director “add footsteps…” | DISCONNECTED → repaired | Capability existed; live chat never reached `audio.place` |
| Timeline SFX / Lip Sync tracks | EXISTS | Director clips and chips visible |
| Timeline audio playback | DISCONNECTED → repaired | Tracks resolved; HTMLAudio pool was not consuming them |
| Frame-perfect foot contact | MISSING | Master visual is an assembled still; timing is inferred |

## Source repairs (not workarounds)

1. **Environment picker** hid corridor PNGs behind the first 100 mixed Library rows.
2. **Timeline Add Scene** duration incorrectly summed all scenes against a 20s cap.
3. **Co-Director `timeline.add_audio`** was advice-only / LLM-catalog: `_AUDIO_SFX_RE` missed “footsteps”, `audio.open` won first, `timeline.add_audio` pointed at an unregistered tool, and EXECUTION still used curated LLM tools (`toolInvocations: 0`). Reconnected to a deterministic `CAPABILITY_HANDLER` that calls existing `AudioService.place_cue`.
4. **Timeline transport played picture, not audio.** `resolveTimelineAtTime` computed active layers; nothing played them. Added `collectTimelineAudioAtTime` + `useTimelineAudioPlayback` on the existing Timeline shell.

Tests that detected the repairs:

- `studio-api/tests/test_audio_studio_speech_act.py` — 3 passed
- `studio-api/tests/test_timeline_add_audio.py` — 3 passed
- `studio-web/src/components/timeline-master/collectTimelineAudioAtTime.test.ts` — 2 passed

Playwright was not used against this named production project. Certification used the live Vite Timeline plus API director GET.

## Co-Director placement

Creator request (Timeline workspace, scene `b5282a4c-…`):

> Add footsteps for Korri and Anadriya and time them to their walking. Use the approved metal grate footstep SFX already in Audio Studio

Live stream: capability `timeline.add_audio`, status **completed**, **30/30** child jobs. Director then contained 15 Korri hits and 15 Anadriya hits on asset `667da9c9-…` at volume `0.32`. Dialogue lip-sync tracks were unchanged.

**FOOTSTEP TIMING METHOD:** inferred 0.55s walk cadence + 0.22s companion offset across the 8s still. **Not frame-perfect.** The played visual is the existing Deck 5 corridor still (`#VentureCorridorScene`). There are no visible foot-contact frames.

## Playback (live Timeline)

Observed on `http://127.0.0.1:5173/` after selecting Venture Corridor Walk:

- `|<` Go to Batch In → playhead `0`
- Play → 38 samples with live `<audio>` over ~7.6s
- Korri dialogue, Anadriya dialogue, Korri footsteps, and Anadriya footsteps each reached `paused: false`
- Mid-scene (~3.98s): Anadriya line at volume `1.0` plus both footstep lanes at `0.32`
- First sample (~0.18s): only Korri footsteps (Anadriya lane starts at 0.22s)
- Play completed the 8s batch and released
- `>|` Go to Batch Out → playhead `8`, live audio `0`

The agent cannot hear workstation speakers. Playback certification is HTMLAudio state + real RIFF bytes + director clip timing.

Screenshot: `docs/release-gate/korri-anadriya-corridor-audio/evidence/venture-corridor-walk-timeline.png`

## Reload

Full page reload of the same Timeline URL defaulted to Scene 1 (existing product behavior). Re-selecting Venture Corridor Walk restored:

- scene name and 8s MiniMax H3 batch
- corridor still
- both dialogue chips
- 30 SFX trim handles
- director GET: 30 `sfx_clips` + 2 lip-sync tracks, same asset IDs and starts

## E2E TRACE

| Stage | Result |
|---|---|
| User action — open Korri Anadriya, create Venture Corridor Walk | PASS |
| Frontend — Scene Creator / Timeline / Audio Studio / Co-Director | PASS |
| API — scene, director, character CRS, voice, assets | PASS |
| Backend — Audio Studio TTS, MMAudio SFX, `place_cue` | PASS |
| Persistence — director `image_clips` / `sfx_clips` / `lipsync` | PASS |
| Runtime — Qwen3-TTS + local MMAudio GPU SFX (no Comfy job this journey) | PASS |
| Result — real WAVs + corridor PNG + 30 timed SFX + 2 voices | PASS |
| Reload — scene/audio state returns after refresh + reselect | PASS |
| Downstream — Timeline Play mixes dialogue + independent footsteps | PASS |

## Peer review (10 questions)

Primary challenge after live verification. A specialized GPT 5.4 reviewer was not launched; Task model allow-list does not include `gpt-5.4-medium`.

1. **Approved Korri CRS?** Yes — CRS GET `has_approved_reference: true`, asset `a97963c4-…`. Spatial Map placement uses that sheet.
2. **Approved Anadriya CRS?** Yes — `7e5a01f4-…`.
3. **Voices from existing assignments?** Yes — Korri Clone / Anadriya Clone APPROVED. No new voice profiles created for this scene.
4. **Real Audio Studio assets?** Yes — RIFF WAVs 157484 / 130604 / 32044 bytes. Not placeholders.
5. **Co-Director placed/timed SFX?** Yes — `timeline.add_audio` wrote 30 director clips. Not advice-only.
6. **Independently timed footsteps?** Yes — two labels, 0.22s offset, both lanes played overlapping.
7. **Timeline playback audibly wired?** Yes at the HTMLAudio layer. Speaker-level listen was not available to the agent.
8. **Legacy surface used?** No. Current Vite Timeline + current Co-Director handler + current Audio Studio assets.
9. **Errors repaired at source?** Yes. Place path and Timeline audio consumption were reconnected; no DB injection to fake clips.
10. **Reload preserves state?** Yes, after re-selecting the scene.

## Limitations (honest)

- Master visual is an assembled corridor still, not a generated walking two-shot. Character identity is bound through approved CRS / ERS / prompt, not visible walking figures in the Timeline picture.
- Footstep sync is cadence-inferred, not contact-frame locked.
- Optional ship ambience was not added.
- Playwright suite was not run on this named project.
- Scene Creator integrity badges for Character/Environment were not greened by regenerating the corridor.
- Two Python processes currently advertise Comfy `main.py --port 8188` (PID `77152` and `32824`). This journey did not start, stop, adopt, or restart Comfy.

## Runtime fence

- `COMFY BEFORE:` PID `77152`, `GET :8188/system_stats` 200
- `COMFY AFTER:` PID `77152` still present; `GET :8188/system_stats` 200
- `COMFY RESTARTED?:` **NO**
- `WHY?:` Audio/Timeline/Co-Director journey. No Comfy workflow change. API recycles used `scripts/restart_studio_api_only.py` only. Frontend playback used Vite HMR.

## Manual review

1. Open `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=timeline`
2. Select **Venture Corridor Walk** (not Scene 1)
3. Press Go to In, Play, listen for Korri then Anadriya over staggered metal-grate steps
4. Press Go to Out — playhead should sit at 8.00s
