# MINIMAX H3 1-FRAME GOLDEN WORKFLOW CONVERGENCE — Governing Report

Status: IN PROGRESS — Phase 1/2 (golden capture + baseline proof) running.
Owner directive: use the known-good default Comfy MiniMax H3 1 Frame workflow as the
canonical baseline; differentially add Adept enhancements while continuously proving
A/V fidelity. Do NOT keep patching the broken Adept output path blindly.

## Golden baseline authority

Source template: `c:\AdeptFilmWorks\Adept Chronicles\Sample scene\_Minimax 1 Frame.json`
(owner-provided, the default Comfy MiniMax H3 1 Frame workflow that produces clean A/V).

Golden graph (subgraph "Image to Video (MiniMax H3)" interior), captured to
`.runtime/_golden_h3_graph.py` / `.runtime/_golden_h3_graph.json`:

```
UNETLoader(minimax_h3_fl2va_pruned_int8_convrot, default)
CLIPLoader(qwen3vl_32b_minimax_h3_nvfp4_awq, type=minimax)
VAELoader(minimax_h3_video_vae_fp16)      # video VAE
VAELoader(minimax_h3_audio_vae_fp32)      # audio VAE
MiniMaxH3ImageToVideo(clip, vae, first_frame, prompt, w, h, length) -> positive + LATENT
RandomNoise(seed) / KSamplerSelect(res_multistep) / BasicScheduler(simple, steps, denoise=1)
BasicGuider(model, positive)
SamplerCustomAdvanced(noise, guider, sampler, sigmas, latent) -> joint LATENT
VAEDecode(latent, video_vae)       -> IMAGE
VAEDecodeAudio(latent, audio_vae)  -> AUDIO
CreateVideo(images, audio, fps=24, bit_depth=8) -> VIDEO
SaveVideo(video/MiniMax_H3, format=auto, codec=auto)
```

Golden defaults: 1344x768, length=73 (17k+5 grid, ~3.04s @24fps), steps=20, res_multistep,
simple scheduler, denoise 1.0. Duration logic: `max(5, round(a*24)) + (5-(max(5,round(a*24))%17))%17`.

**The golden graph has NO accelerator node, NO SpeedCache/SageAttention, NO LoRA, and NO
Adept post-process colorspace remux.** SaveVideo native output is the final artifact.

## Phase 3 — Adept vs Golden node-by-node diff (A/V finalization path)

Adept builder: `studio-api/app/minimax_h3/route_a_adapter.py::build_t2va_graph` /
`build_i2va_graph`. The node set is IDENTICAL to the golden subgraph interior. The only
differences are:

| # | Delta | Golden | Adept | Classification |
|---|-------|--------|-------|----------------|
| 1 | Accelerator | none — raw UNETLoader → BasicScheduler/BasicGuider | `apply_certified_accelerator` inserts `MiniMaxH3SpeedCache` (SageAttention, reuse_threshold=0.0) as node 16 and rewires scheduler+guider `model` to it | **ACCELERATOR — PRIME SUSPECT.** Alters the diffusion compute path that produces the JOINT AV latent → can shift BOTH video color AND audio. |
| 2 | Post-process remux | none — SaveVideo native MP4 is final | `finalize_h3_colorspace(mp4)` in `poll()` runs ffmpeg `-c copy` tagging smpte170m/bt601 + tv range, replacing the file | **SUSPECT (color only).** Claims lossless metadata tag; a prior mission added it to FIX a perceived shift. If the encode is actually bt709, tagging bt601 causes a color cast. |
| 3 | Settings | 1344x768 / 73f / 20 steps | 480x256 / 5f / 4 steps (EXPERIMENTAL_*) | **NECESSARY** (creator config, not an A/V-path defect). |
| 4 | LoadImage wiring | subgraph `first_frame` input | explicit LoadImage node 15 → `MiniMaxH3ImageToVideo.first_frame` | **NECESSARY ADEPT INTEGRATION.** |
| 5 | `format.codec: auto` sub-input | not present | added for Comfy 0.34.x validate | **NECESSARY ADEPT INTEGRATION** (validation compat). |

**First structural divergence in the A/V finalization path = the accelerator insertion
(Delta 1).** It sits upstream of the sampler and changes the joint latent. The colorspace
remux (Delta 2) is downstream and color-only. Neither exists in the golden graph.

## Phase 1/2 — Golden baseline run — COMPLETE, A/V CLEAN

- Target: Comfy `:8188` (canonical, Comfy MCP target). H3 `:8192` was DOWN at mission start.
- GPU pre-state: freed to 30.4GB free after stopping the stalled Gate 1 Qwen worker
  (`.runtime/_gate1_run.py`, PID 6008 + parent 33904) — owner-approved. `:8188` untouched.
- Golden graph validated against live `:8188` via Comfy MCP: valid=true, 0 errors/warnings.
- prompt_id: daada03c-7e5f-40a1-bed6-4d99fd489c70. Wall time 140.1s (cold load + 20 steps).
- Output: `.runtime/golden_h3_1f_output.mp4` (575KB, 73 frames, 3.042s).

### Golden output — deterministic facts (CLEAN — this is the fidelity reference)

- VIDEO: h264 High 1344x768 yuv420p, 73 frames @24fps, **color_space=bt709,
  color_transfer=iec61966-2-1 (sRGB), color_primaries=bt709, range=tv** — properly tagged.
- AUDIO: aac LC **32000 Hz stereo**, 97 frames, 3.042s.
- A/V sync drift: **0.00033s** (in sync). Video 3.0417s / audio 3.0420s.
- Audio diagnostics: peak 0.124, RMS 0.023, **clipping 0.0%**, DC offset ~0, NaN/Inf 0,
  silence 1.6%, **noise floor −136.8 dB** → no static, no distortion, no clipping.
- Color diagnostics: mean RGB [69.3, 63.2, 62.9] (balanced, no cast), range=limited.
- Visual: golden frame 0 matches source `ref_korri_hero.png` — warm orange lighting, red
  garment, skin tones all faithful, **no hue shift / color cast / distortion**.

### CRITICAL FINDING — the bt601 remux premise is FALSE

The golden SaveVideo native output is **already correctly tagged bt709** (not "unknown").
This contradicts the assumption baked into Adept's `finalize_h3_colorspace`, which asserts
CreateVideo+SaveVideo emit NO colorspace metadata and that the encode is bt601 — so it
force-tags **smpte170m (bt601)**. On a stream that is actually bt709, that bt601 tag makes
players apply the wrong YUV→RGB matrix → **the exact color shift the owner observes.**

**Delta 2 (`finalize_h3_colorspace`) is therefore a confirmed color-fidelity REGRESSION,
not a fix.** Delta 1 (SageAttention accelerator) remains the suspect for the audio static
(alters the joint AV latent compute). Phase 5 A/B will isolate each.

## Phase 5 — A/B isolation — DECISIVE (both culprits identified)

Ran two arms against the golden reference (same seed/prompt/1344x768/73f/20 steps):

**ARM B = golden + SageAttention accelerator (MiniMaxH3SpeedCache), NATIVE SaveVideo (no remux).**
- prompt_id 03b2c848-1d2a-42ae-aab0-1e0f67140216, wall 80.0s (warm).
- Video: **bt709 / iec61966-2-1 / bt709 / tv** — CORRECT. Accelerator does NOT break color.
  Frame 36 visually clean (faithful skin tones / lighting, no cast).
- Audio: **noise floor −28.25 dB** (vs golden −136.8 dB) → **~108 dB elevated noise floor =
  the audio static/hiss.** Peak −6.85 dB, RMS −22.8 dB (hot). NaN/Inf 0.
- **VERDICT: the SageAttention accelerator introduces the AUDIO STATIC.** It does not harm
  video color. (Mechanism: it patches the joint AV diffusion compute; the audio VAE latent
  branch is degraded even though the video branch stays clean.)

**ARM C = golden native output + Adept `finalize_h3_colorspace` bt601 remux (no accelerator).**
- Video: retagged bt709 → **smpte170m/bt601** → the COLOR SHIFT.
- Audio: noise floor ≈ −73 to −75 dB (astats on AAC) — NOT elevated to −28 dB. The remux is
  lossless (`-c copy`) and does NOT touch audio content.
- **VERDICT: the bt601 remux introduces the COLOR SHIFT and leaves audio alone.**

### Two independent defects, two independent Adept deltas

| Defect (owner-observed) | Adept delta responsible | Evidence |
|---|---|---|
| Color / fidelity distortion | `finalize_h3_colorspace` bt601 remux | Golden native = bt709 (correct); remux mis-tags bt601 → wrong YUV→RGB matrix on playback |
| Audio static / distortion | SageAttention accelerator (MiniMaxH3SpeedCache) | Golden native audio noise floor −136.8 dB; +accelerator → −28.25 dB (static) |

The default Comfy H3 path (no accelerator, no remux) produces clean A/V. Both Adept
enhancements are implicated — and they are SEPARABLE.

## Phase 5b — SageAttention audio sweep — CONCLUSIVE (accelerator must be dropped)

Tested every `sage_attention` mode of `MiniMaxH3SpeedCache` (same seed/1344x768/73f/20 steps):

| Config | Audio noise floor | Result |
|---|---|---|
| Golden (NO SpeedCache node) | **−136.8 dB** | CLEAN |
| SpeedCache `sage_attention=auto` | −28.25 dB | STATIC |
| SpeedCache `sage_attention=enabled` | −28.25 dB | STATIC |
| SpeedCache `sage_attention=disabled` | −26.47 dB | STATIC |

**Every configuration of the SpeedCache node produces audio static — even
`sage_attention=disabled`.** The corruption is inherent to inserting the
`MiniMaxH3SpeedCache` node into the model path at all (it patches the joint AV diffusion
model; the audio VAE latent branch is degraded regardless of the SageAttention toggle).
The live node schema (`nodes get MiniMaxH3SpeedCache`) exposes NO video-only/audio-only
scope — `sage_attention` is only auto/enabled/disabled, and the remaining knobs control the
(disabled) residual cache, not application scope.

**CONCLUSION (owner-approved investigation):** The SpeedCache/SageAttention accelerator
CANNOT be used on MiniMax H3 without corrupting the native audio. Per Adept's absolute
Quality > Speed law (never trade audio quality for benchmark speed), the accelerator is
**DROPPED for H3**. Adept's H3 path reverts to the golden graph (no accelerator). The prior
"SageAttention certified" verdict is SUPERSEDED — it was benchmarked on a tiny 4-step/5-frame
smoke config where the audio static was not detected; at the real 20-step/73-frame config the
static is unambiguous. Speed is sacrificed for clean native A/V.

## Phase 4 — Freeze golden A/V path — COLOR FIX APPLIED

- `route_a_adapter.py::poll()` now calls `finalize_h3_colorspace_passthrough` (reads native
  bt709 tags for provenance, NO remux) instead of the bt601 `finalize_h3_colorspace` remux.
- The legacy `finalize_h3_colorspace` remains defined (unused in the live path) with its 3
  unit tests still passing; it is deprecated, not deleted, pending a cleanup pass.
- `route_a_adapter.py` syntax + import verified; 27/27 `test_route_a_adapter.py` pass.

## Phase 4/5 — CODE FIXES APPLIED (color + accelerator)

**Color fix (Phase 4):** `poll()` now calls `finalize_h3_colorspace_passthrough` (reads
native bt709, NO remux). Legacy bt601 `finalize_h3_colorspace` deprecated (unused in live
path). 27/27 route_a_adapter tests pass.

**Accelerator dropped (Phase 5b):** `build_t2va_graph` / `build_i2va_graph` no longer call
`apply_certified_accelerator`. The production H3 graph is now the GOLDEN path — raw
UNETLoader `[1,0]` drives BasicScheduler + BasicGuider directly; no MiniMaxH3SpeedCache node.
Verified: T2V graph = 14 nodes, I2V = 15 nodes, zero SpeedCache, scheduler/guider model =
`["1",0]`. Provenance updated to `accelerator: none / sageAttention: disabled /
"MiniMax H3 Golden (no accelerator — clean native A/V)"`. Unused acceleration imports removed
from route_a_adapter. Tests updated to assert the accelerator-free golden path:
**57/57 minimax_h3 tests pass.**

`acceleration.py` module retained (apply_certified_accelerator contract still unit-tested) but
no longer wired into production graphs. `vram_viability.py` reads ACCELERATOR_PROVENANCE for
display only (unchanged, no crash). Stale smoke scripts (`_smoke_8192_t2v_sage.py`,
`_build_code_graphs.py`) still reference the accelerator — diagnostic only, not production.

**Net effect: Adept H3 1F/T2V now produce the golden clean A/V (bt709 color + clean audio),
at golden (unaccelerated) speed.** Speed was sacrificed for audio fidelity per Quality > Speed.

## Phase 8-13 — Live draft preview — MECHANISM PROVEN

**Root cause of "no live draft frames":** Comfy only emits WebSocket `PREVIEW_IMAGE`
latent-preview events when launched with `--preview-method auto|latent2rgb|taesd`. The
running Comfy `:8188` argv had NO `--preview-method` flag (default = PreviewMethod.NONE),
so sampling produced zero preview frames and the Preview Monitor correctly fell back to the
static source still. `--preview-method` appears nowhere in Adept's launch config.

**Adept's preview pipeline already exists end-to-end (no rebuild needed):**
- `video_runtime/live_preview.py` — WebSocket `/ws?clientId=` tap, decodes binary
  PREVIEW_IMAGE, filters by prompt_id, never fails the render.
- `queue_worker.py:4094` — Route A 1F tap saves frames to preview_bus, persists
  `job.preview_json`, updates status ("Draft frame N").
- `LivePreviewMonitor.tsx` — subscribes preview_updated, renders draft frames.

**Isolated proof (`.runtime/_preview_proof.py`):** launched a SEPARATE throwaway Comfy on
test port 8299 with `--preview-method auto` (did NOT touch protected :8188/:8192), ran the
golden H3 1F graph, and used Adept's real `tap_comfy_previews_sync`:
- Test Comfy up in 37s; prompt_id b637665e-31f1-4c24-b6f4-6fabe14c3f43.
- **20 draft frames received** over a 140.3s render; first frame at 16.9s (during sampling),
  steady ~5.9s cadence; ~26KB JPEG each.
- Frame 1 = blurred early latent; Frame 10 = Korri's face/red garment/lighting clearly
  resolved → genuine progressive generated content, not a placeholder.
- Render completed cleanly; test instance shut down. **SUCCESS=True.**

**The fix for production:** add `--preview-method auto` (or `latent2rgb`, lightweight, no
extra VAE cost) to the Comfy instance Adept talks to. For 1 Frame that is the `:8192` Route A
instance. This is a launch-flag change, not a graph change — the preview stays a
non-destructive observer (WebSocket tap only; does not touch the final render path).

**PRODUCTION WIRING APPLIED (2026-09-08):** `runtime_supervisor/services.py` —
`_route_a_preview_args()` helper added; both `start_route_a` and `start_route_a_on_demand`
now launch `:8192` with `--preview-method auto` (env override `ADEPT_H3_COMFY_PREVIEW_METHOD`,
"none" disables). 32/32 lifecycle tests pass. Route A relaunched Adept-owned: PID 8616,
`--preview-method auto` confirmed active, 32.5GB VRAM free.

**Runtime repair (same session):** Background Services manager (`:8759`) was down →
"Background Services unavailable". Fixed two real control-plane defects in
`runtime_supervisor/serve.py` `on_repair` (`_payload()` received duplicate `message`/`ok`
kwargs → HTTP 500). Repaired + relaunched manager. Full stack UP: Vite `:5173`, Studio API
`:8758` (healthy, rev b6156455), Route A `:8192`, Comfy `:8188` (external Comfy Desktop PID
39716 — Adept will not take it over per Protection Law; not blocking since 1F uses `:8192`),
manager `:8759`. Route A `:8192` previous instance (PID 8044, classified `reused`/not owned)
was owner-authorized stopped after re-verifying identity (Protection Law #4/#8), then fresh
Adept-owned spawn with the preview flag.

## Owner decision (2026-09-08) — VDN-H3 OUT OF SCOPE

VDN-H3 is **out of scope** for the current Adept UI release. It must NOT appear as an
accelerator choice, AUTO candidate, Production Control recommendation, Setup option, Source
Manager dependency, or Co-Director optimization route. It remains a future/experimental
research item only. **Audit: PASS** — zero VDN references in `studio-api` (Python) or
`studio-web` (TS/TSX); it exists only in `.runtime` scratch scripts and benchmark JSONs.

**Production law:** MiniMax H3 Golden Path = clean native A/V first. No accelerator is
preferable to an accelerator that compromises reliability or media fidelity. Accelerator
hunting is PAUSED; future candidates are limited to mature, isolated changes (no VDN, no
SpeedCache) and each must pass the same golden A/B test (clean color + clean audio + correct
sync FIRST, meaningful speedup SECOND).

## Preview integration — owner-approved requirements (all verified in existing code)

The proven `:8299` preview config was promoted to the owned `:8192` Route A launch authority
(`--preview-method auto`, owned by the runtime supervisor, not a manual shell command). The
existing preview wiring already satisfies every owner requirement — verified, no changes needed:

| Requirement | Where satisfied |
| --- | --- |
| Source still = reference placeholder before content ("Preparing — no generated draft frames yet") | `LivePreviewMonitor.tsx` mediaSrc/preparing = sourceStill |
| First real preview replaces placeholder | `_on_frame` → preview_updated → live_preview → DraftSequencePlayer |
| Never display a different execution/job's preview | tap filters by `prompt_id` (`live_preview.py`); frontend resets draftFrames on jobId change |
| Keep latest draft during final decode/encode | showDraft spans live_preview/processing/assembling/post |
| Replace with final MP4 on complete | final_output/complete → mediaSrc = finalSrc |
| Draft frames NOT persisted to Library | `preview_bus.save_bytes` → `preview_cache/{jobId}/`, `temporary: True`; only explicit "Save Preview Frame" copies to Assets |
| Draft frames NOT fed to Qwen | `analyze_asset` resolves via `db.get(Asset, asset_id)` — canonical final asset only |
| Keep native ~5.9s cadence (no forced 2–6fps interpolation) | no resampling/interpolation; frames play as they arrive |

## Next gates (pending)
- Phase 2: confirm golden output A/V clean (owner/manual + ffprobe + Media Intelligence).
- Phase 4: freeze golden A/V path; decide fate of `finalize_h3_colorspace`.
- Phase 5/6: add SageAttention as ONE isolated delta; A/B vs golden; STOP if A/V corrupts.
- Phase 7: add Realism People LoRA separately.
- Phase 8-15: live draft preview as non-destructive observer (Comfy MCP native mechanism).
- Phase 16/17: full creator proof + Media Intelligence OLD-broken vs NEW-golden comparison.
- Phase 18: extend golden A/V finalization to T2V/3F/Timeline-Re-Take after 1F GO.

## COMFY / runtime ledger

- COMFY :8188 RESTARTED?: NO (read-only /prompt submit + /history poll).
- H3 :8192: was DOWN at start; not touched.
- Gate 1 Qwen worker: stopped (owner-approved) to free VRAM; becomes Phase 17 baseline.
