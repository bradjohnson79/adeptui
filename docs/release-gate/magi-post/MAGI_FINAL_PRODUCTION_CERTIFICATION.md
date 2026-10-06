# MAGI Final Production Certification

**Date:** 2026-09-14 (PT) / 2026-09-15 (UTC)  
**Branch:** `feat/character-creator-final-closure`  
**HEAD:** `99665cf76693e359cedc60c50c4405daf1b4e3a1` (working tree includes this closure; uncommitted)  
**Project:** Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`  
**Scene 12B:** `d774a22f-2b02-4eb2-b5ab-a98af9ff8f85`  
**Review URL:** `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=magi&sceneId=d774a22f-2b02-4eb2-b5ab-a98af9ff8f85`  
**Studio API:** `http://127.0.0.1:8758/` (`/api/healthz` HTTP 200)  
**Local creator UI:** `http://127.0.0.1:5173/` (HTTP 200)  
**Comfy `:8188`:** READ-ONLY. PID `45624` before and after. **COMFY RESTARTED?: NO**  
**API recycle:** `scripts/restart_studio_api_only.py` only (thumbnail contract, then hung-music recovery, then ingest-role fix). Last healthy PID `29732`. Comfy PID unchanged.

This is the governing report for MAGI final production closure (console + 4K/60 + Co-Director music/SFX).  
Sibling reports remain governing for their own gates:

- Split View live grade — `MAGI_SPLIT_VIEW_LIVE_GRADE_CERTIFICATION.md`
- Overlay tools — `MAGI_ACTIVE_GRAPHICS_OVERLAY_CERTIFICATION.md`
- Objects tracks + composition freeze — `MAGI_OBJECTS_TRACK_FINAL_CONVERGENCE.md`
- Library drawer / preview mixer wiring — `MAGI_LIBRARY_AUDIO_THUMBNAIL_CERTIFICATION.md`

Do not treat those GOs as this final production GO.

---

## Verdict

**GO — MAGI FINAL PRODUCTION CERTIFICATION**

---

## PHASE A — Console / thumbnail cleanup

### A1. `startTime` / `et.reportAllChanges` / `VM11583`

**Ownership: BROWSER / DEVTOOLS — not Adept.**

| Check | Evidence |
| --- | --- |
| `reportAllChanges` in Adept / `studio-web` | Absent |
| Page scripts | Vite `@vite/client` and `src/main.tsx` only |
| React DevTools hook | `window.__REACT_DEVTOOLS_GLOBAL_HOOK__` is an object |
| `reportAllChanges` on `window` | `undefined` (injected VM / Profiler, not app code) |

`VM11583` + `et.reportAllChanges` reading `PerformanceEntry.startTime` is React DevTools Profiler / injected instrumentation. **Adept code was not patched to silence it.** Excluded from Adept certification.

### A2–A4. Thumbnail 500s — root cause and contract

Live probe of all Korri assets **before** the contract fix: 347×200, 9×500, 26×400, 167 audio 404s, 1 missing-file 404.

| Class | What it was |
| --- | --- |
| 9×500 | `magi_color` rows tagged image/`.png` whose bytes are H.264. PIL `cannot identify image file` became `THUMBNAIL_FAILED` |
| 26×400 | Valid PNGs with **32-hex** ids (no dashes). `_UUID_RE` rejected them as `MALFORMED_ASSET_REQUEST` |
| Audio 404 | Honest `NOT_AN_IMAGE` — MAGI frontend never requests `/thumb` for audio |
| 1×404 video | Missing source file `70ff0a08-627c-4777-b349-f2c5158f1660` — `ASSET_FILE_MISSING` |

**Repair** (`studio-api/app/project_security/asset_file.py`):

- Accept UUID **or** 32-hex ids.
- Sniff bytes, not kind/extension.
- Audio kind or sniffed audio → **200** audio-card webp (`X-Adept-Thumb: fallback`).
- Video / H.264-named-png → ffmpeg poster; images → PIL.
- Generation failure → **200 placeholder**, never HTTP 500.
- Missing source file stays **404**.

MAGI frontend already used `failedThumbs` + `libraryThumbUrl` (audio never hits `/thumb`).

**After fix, live re-probe (554 assets):**

| Status | Count |
| --- | --- |
| 200 | **553** |
| 404 | **1** (missing source file — honest) |
| 500 | **0** |
| 400 | **0** |

Live MAGI Library: 385 thumb `<img>`s, **0 broken**, 0 Adept uncaught exceptions, 0 recurring thumb 500s, 0 request storms.

### A5. Console clean standard

| Gate | Result |
| --- | --- |
| Adept uncaught exceptions | **0** observed |
| Thumbnail 500s | **0** |
| Repeated media API failures | **0** |
| Hidden playback errors | None observed |
| Raw backend error banners | None |
| React DevTools info | Not a defect |

---

## PHASE B — Scene 12B 4K / 60 fps

### B1. Published source (re-probed live)

| Field | Value |
| --- | --- |
| assetId | `a85c2632-dd04-4450-be5d-214aa191e209` |
| File | `video_published_master_d774a22f_91230fbb.mp4` |
| Resolution | **864×480** |
| Duration | **30.048s** / 720 frames |
| FPS | ~23.994 (24) |
| Video | h264 |
| Audio | aac, present |
| Size | ~2.8 MB |

Source preserved. No overwrite.

### B3. 60 fps capability audit

`studio-api/app/magi/readiness.py` `frame_interpolation`:

- status **Deferred**, `executable: false`
- reason: “Frame interpolation and fps conversion are not implemented.”
- `notSupported` includes `frame_interpolation`

Co-Director `magi.propose_finish` for *“Finish Scene 12B as a 4K master at 60 fps if the available MAGI pipeline supports true interpolation.”* returned `NOT_SUPPORTED` for frame interpolation and warned the request would be refused.

**True 60 fps interpolation: NOT SUPPORTED.**  
No frame duplication. No container-metadata spoof. Encoded cadence remains **24.0 fps / 721 frames**.

### B2 / B4 / B6. 4K finish (real path)

Preferred MAGI picture pipeline:

Published master → approved color grade + overlays → **Real-ESRGAN-ncnn-Vulkan** late upscale → encode.

| Field | Value |
| --- | --- |
| Job | `322e2029-5af9-4d66-a62b-52686e4350d2` — done |
| Output asset | `d6614b8b-852c-4e1e-ba1c-83f4baa24471` |
| Tag | Scene 12B MAGI 4K Final Master |
| Parent | published master `a85c2632-…` |
| Resolution | **3840×2160** (16:9) — decoded, not metadata-only |
| FPS | **24.0** (721 frames / 30.042s) |
| Codecs | h264 + aac |
| Size | ~56.8 MB |
| Upscale | `realesrgan-ncnn-vulkan` / `realesr-animevideov3` |
| Grade | brightness 0.15, contrast 0.25, saturation 0.4 |

Visual inspect (early / mid / late + 2s / 6s vs source): same interview identity, title + lower third present, no freeze/tear. Evidence: `docs/release-gate/magi-post/evidence/4k_early.png`, `4k_mid.png`, `4k_late.png`.

VIDEO clip on the sequence remains the published master (correct). 4K is a **new Library row**.

### B5. Co-Director

`magi.propose_finish` + `magi.render` used the real MAGI finish path. Interpolation was not hallucinated.

### B7. Library deposit

**PASS** — new asset, parent = published master, source not overwritten. Named 4K Final Master (not 4K60).

---

## PHASE C — Co-Director music + SFX

### C1. Scene analysis

Live frames of Scene 12B (published master + 4K stills): wide establish (lounge / sofa / cameras) then close two-shot (silver-suited Adept + dark-haired counterpart).  

Creative decision recorded in `.runtime/_magi_cd_audio_enqueue.json`:

- Music: low dialogue-safe underscore, pads/piano, no drums
- SFX: soft HVAC / fabric room tone — not a sting or explosion

Co-Director tools invoked via `ToolContext` (`magi.audio.generate` preview + apply). Live NL chat send was not used this pass. Decisions match the inspected picture.

### C2. Music — real ACE-Step

| Field | Value |
| --- | --- |
| Intent | Quiet warm interview underscore, dialogue-safe |
| Tool | `magi.audio.generate` |
| Receipt | `magi_act_7c19148523254298` (queue); retry job after hang |
| Job (success) | `b353f3a0-4b71-4573-9eab-c56518151864` |
| Provider | ACE-Step `m2101-music-045` — **fixture: false**, CUDA, RTX 5090, bf16, 18 steps, 50.41s |
| assetId | `17442401-e760-486f-82f9-3fbce8ede501` |
| File | 5,742,248 bytes, 48 kHz stereo PCM, **29.91s** |
| Peak / RMS | 0.72 / 0.12 (not silence) |
| Placement | MUSIC track, frames 0–720, `ingestRole: music` |

First concurrent music job `ebbf26c1-…` **hung** (no ProductionJob, no ACE-Step process, GPU idle). Marked failed. API recycled. Sequential retry spawned ACE-Step and completed. Not a fixture substitute.

### C3. SFX — real MMAudio

| Field | Value |
| --- | --- |
| Intent | Subtle interview-studio room tone |
| Tool | `magi.audio.generate` |
| Receipt | `magi_act_6102be8d68a84d8c` |
| Job | `f9a923aa-0303-47f1-92ed-978baf8d3e6d` |
| Provider | MMAudio `m2101-sfx-031` — **fixture: false**, CUDA, warm_serve, 39.4s inference |
| assetId | `716a8d06-3d65-4777-b4bf-22c6f764e866` |
| File | 192,044 bytes, 16 kHz mono PCM, **6.0s** |
| Peak / RMS | 0.91 / 0.24 (not silence; mix ducks it) |
| Placement | SFX track, frames 0–144, `ingestRole: sfx` |

### Placement wipe (repaired this pass)

Published-master ingest treated untagged MUSIC/SFX clips as production leftovers and rebuilt VIDEO/AUDIO only (triggered on MAGI reload).  

**Repair:**

- `_place_on_sequence` writes `ingestRole: music|sfx` and `sceneId`
- Ingest keeps clips on MUSIC/SFX tracks
- Regression: `test_ingest_preserves_music_and_sfx_finishing_clips`

After reload: sequence still has 4 clips (`published_master`, `published_master_audio`, `music`, `sfx`).

### C4. Tracks

| Track | Content |
| --- | --- |
| VIDEO | published master `a85c2632-…` |
| AUDIO | same master AAC (dialogue) |
| MUSIC | CD ACE-Step cue |
| SFX | CD MMAudio room tone |
| GRAPHICS | existing title / lower third (not required for this test) |

No extra A2/A3 doubles.

### C5. Mix

Final-render authority: `sequence.finishing.audio`.

| Stem | Gain |
| --- | --- |
| Dialogue (picture audio) | 1.00 |
| Music | **0.28** |
| SFX | **0.35** |

Optional mix onto the 4K master (`-c:v copy`, MAGI `_mix_audio`):

| Field | Value |
| --- | --- |
| assetId | `0210fa91-edad-4cac-950b-c9db91d67a8b` |
| Tag | Scene 12B MAGI 4K Final Mix |
| Parent | 4K master `d6614b8b-…` |
| Picture | 3840×2160, 24 fps, 721 frames, 30.042s |
| Audio | aac stereo, 30.016s |
| Peak | all windows **below 0 dBFS** (hottest ≈ −0.74 dB) |
| Authority | `magi-finishing.audio` |

No clipping. No second copy of source dialogue stacked at 1.0.

### C6. Playback (live MAGI)

`MagiPreviewMixer` after reload + Play + seek to start:

| Stream | State |
| --- | --- |
| Dialogue `a85c2632-…/file` | playing, unmuted, ~0.85s, readyState 4 |
| Music `17442401-…/file` | playing, unmuted, ~0.82s, readyState 4 |
| SFX `716a8d06-…/file` | playing, unmuted, ~0.87s, readyState 4 |
| Picture `<video>` | playing, **muted** (AUDIO lane owns playback) |

Mute chip: all three mixer nodes muted + paused; label **Unmute preview**. Unmute restores dialogue + music. SFX correctly goes inactive after 6s (clip window). Playhead smooth. No remount / double source audio.

Screenshot: `docs/release-gate/magi-post/evidence/magi_final_12b_playback.png` (VIDEO + GRAPHICS title + AUDIO + **Music — MAGI**).

### C7. Action receipts

| Action | Tool | Result |
| --- | --- | --- |
| Music intent + queue | `magi.audio.generate` | `magi_act_7c19148523254298` / job `b353f3a0-…` done |
| SFX intent + queue | `magi.audio.generate` | `magi_act_6102be8d68a84d8c` / job `f9a923aa-…` done |
| 4K finish | `magi.render` | job `322e2029-…` / asset `d6614b8b-…` |
| Mix | MAGI `_mix_audio` | asset `0210fa91-…` |
| Verify | live mixer + ffprobe + wav stats | as above |

Co-Director did not claim interpolation or fixtures that MAGI did not execute.

---

## Certification matrix

### PHASE A

| Item | Result |
| --- | --- |
| startTime error ownership | **BROWSER / DEVTOOLS** |
| Adept console exceptions | **0** |
| Thumbnail 500s | **0** |
| Library thumbnails | **PASS** |

### PHASE B

| Item | Result |
| --- | --- |
| Published source | **PASS** |
| 4K | **PASS** |
| True 60 fps interpolation | **NOT SUPPORTED** |
| Output resolution | **3840×2160** |
| Output fps | **24.0** |
| Duration | **30.042s** |
| A/V sync | **PASS** (aac present, duration matched) |
| Visual inspection | **PASS** |
| Library deposit | **PASS** |

### PHASE C

| Item | Result |
| --- | --- |
| CD scene analysis | **PASS** |
| Music generated | **PASS** (ACE-Step, CUDA, not fixture) |
| Music track | **PASS** |
| SFX generated | **PASS** (MMAudio, CUDA, not fixture) |
| SFX track | **PASS** |
| Mix | **PASS** |
| Playback | **PASS** |
| Action receipts | **PASS** |

---

## Tests

`studio-api` pytest: **28 passed** — `tests/test_magi_published_master_ingest.py` + `tests/test_project_lock_media.py` (includes hex32 + thumb fallback + music/SFX ingest preserve).

---

## Runtime

- Studio API **200** / Vite **200**
- **COMFY BEFORE:** PID 45624 healthy
- **COMFY AFTER:** PID 45624 healthy
- **COMFY RESTARTED?:** **NO**
- **WHY?:** Console thumbs, 4K enqueue, audio generate, and mix used API / isolated ACE-Step / MMAudio workers only. Comfy was read-only observe.

---

## Limitations

- Preview mixer plays MUSIC/SFX at master volume. Dialogue-safe ducking (**0.28 / 0.35**) is applied on MAGI final mix, not on the preview elements.
- SFX cue is **6s** at the head (room tone), not a 30s bed.
- First concurrent music+SFX generate hung the music MAGI thread before ACE-Step spawn. Sequential retry is the proven path.
- ACE-Step can be invoked twice (MAGI `execute_job` + Production Executive worker). This retry completed; do not treat double-exec as certified architecture.
- Audio adapters remain `sandboxOnly` / `productionApproved: false` (M2.10b lock). Files are real GPU wavs, not fixtures.
- Agent browser cannot prove room speakers. Playback proof is mixer element state + file probes.
- One Library video still 404s on `/thumb` because the source file is missing — honest, not hidden.
- Live Co-Director chat send was not used; tools ran through the same MAGI CD handlers.

---

## Regression freeze

Certified MAGI color, overlay store, Split View, preview Fit, and published-master VIDEO/AUDIO binding were not redesigned. Spatial Map / PoseCraft / Fire3D / SceneCraft remain shelved (v1.1).
