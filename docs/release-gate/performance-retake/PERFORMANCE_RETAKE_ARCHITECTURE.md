# Performance Retake — Governing Architecture & Contract

**Status:** GOVERNING DESIGN (milestone: Timeline Lip Sync → Performance Retake)
**Date:** 2026-09-11
**Authority:** Owner mission directive (2026-09-11) — root-cause replacement of windowed LatentSync. This document is the single governing architecture/contract doc for the milestone (Build Law #30). Historical LatentSync/media-retake reports remain historical.

---

## 1. Root-cause finding (why the old architecture is rejected)

The windowed LatentSync pipeline (`media_retake` executor → `build_latentsync_workflow` → crop/mouth-ROI composite) failed live on Scene 10 with two structural defects:

1. **Audio collision** — original dialogue remained audible under the new dialogue. The old design *layered* replacement audio over the source track instead of owning the window's audio outright.
2. **Facial corruption** — the face was sliced/distorted by the crop-and-paste composite. LatentSync re-animates a cropped mouth/face region and pastes it back; boundary mismatch and identity drift are inherent to the technique.

**Verdict:** facial patch-over is the wrong abstraction. A lip-sync request is a **performance replacement**: the original video+audio performance inside a defined window is *removed* and a *new performance is rendered* for that window. No crop composite, no audio layering.

---

## 2. Generator decision (live-verified, Comfy MCP)

### PRIMARY — Local MiniMax H3 Reference-to-Video (`:8188`, core pack `MiniMaxH3ReferenceToVideo`)

Live `object_info` + gallery template (`video_minimax_h3_r2v`, `local_check.runnable: true`) confirm:

| Capability | Live evidence | Performance Retake use |
|---|---|---|
| `ref_videos.ref_video_N` (type IMAGE, autogrow, ≤3) | Template node 136 slot present (unlinked); `LoadVideo` (core) → `GetVideoComponents` (core) → `images` feeds it | **Source window conditioning** — camera, composition, movement, shot identity |
| `ref_images.ref_image_N` (≤9) | Wired today via `h3_ref2v_builder.py` | Canonical character sheets (Anadriya, Korri) |
| `ref_audios.ref_audio_N` (≤3 live schema) | Wired today via `LoadAudio` | Per-character voice renders of the exact new dialogue lines |
| `ref_video_audios.ref_video_audio_N` | Present, **NOT wired by default** | Old-dialogue leak guard — see §6 |
| Prompt ref binding | `<Picture n>` / `<Video k>` / `<Audio j>` tags in connection order | Timecoded dialogue beats + silence constraints |
| Canvas | 1152×640 exact (step-32 legal) — matches Scene 10 master natively | No rescale, no letterbox |
| Duration | 17k+5 frame grid, ≤362 frames (15.08s) | Scene 10: 240.4 src frames → 243 gen frames (10.125s) → trim to 10.016s at stitch |
| Audio | Native joint stereo via `VAEDecodeAudio` → `CreateVideo` | Retake owns 100% of window audio |

All models present on `:8188` (`minimax_h3_ref2va_pruned_int8_convrot.safetensors`, `qwen3vl_32b_minimax_h3_nvfp4_awq`, video/audio VAEs, turbo LoRA). One render covers **both characters in a single pass** — no per-clip facial passes.

**Repo gap to close (the implementation):** `h3_ref2v_builder.py` wires `ref_images` + `ref_audios` only; adapter `minimax_h3_local.py` declares `supportsVideoReferences=False, maximumReferenceVideos=0`. The node supports video refs; Adept has not wired them. This milestone wires `ref_videos`.

**Ownership constraint (discovered at implementation time):** `h3_ref2v_builder.py` is *untracked foreign work* (H3 Timeline mission, uncommitted) and `minimax_h3_local.py` / `queue_worker.py` / `lipsync_tracks.py` carry foreign uncommitted hunks. Therefore the retake wires `ref_videos` by **composition, not modification**: a new `performance_retake/h3_retake_graph.py` calls `build_h3_ref2v(...)` and post-processes the returned graph dict to inject `LoadVideo` → `GetVideoComponents` → `ref_videos.ref_video_0`, with its own assert wrapper. Foreign files stay byte-untouched except two additive dispatch/routing hunks (`queue_worker.py` job-kind dispatch, `routers/api.py` apply-route default), staged hunk-level at commit. The Timeline batch adapter (`minimax_h3_local.py`) is NOT flipped — video-ref advertising on the batch path is out of scope.

### FALLBACK — Seedance 2.5 hosted (`seedance-2.5`, fal.ai)

Only other path accepting a source video reference + multiple image refs. Dialogue-audio behavior unverified. Used ONLY if the live H3 run fails; requires explicit disclosure (hosted, credits).

### QUARANTINED — LatentSync / sticky-mouth / `media_retake` windowed executor

Legacy. Not deleted (historical evidence + Scene 10 artifacts preserved). All creator-facing entry points re-route to Performance Retake; legacy path reachable only behind an explicit legacy/experimental flag. Full entry-point inventory: §8.

### Rejected alternatives (honest audit)

Wan2.2 Animate (not runnable: missing SAM2 pack/model/VAE/LoRAs; single-char; no audio), SCAIL-2, WAN VACE v2v, H3 Fun ControlNet, LTX-2.3 ID LoRA (no source video), Kling O1/O3 + Kling 2.6 + Wan2.7 + Gemini Omni (hosted, unverified, credits), LTX 2.5 FLF2V (start-frame-only certified), plain t2v/i2v (no source conditioning), Runway (dead endpoint), WaveSpeed rows (no execution path).

---

## 3. PerformanceRetake contract

```jsonc
{
  "specVersion": 1,
  "projectId": "…",
  "sceneId": "…",
  "window": {
    "startSec": 0.0,          // razor IN
    "endSec": 10.016,         // razor OUT
    "scope": "whole_shot",    // whole_shot | sub_window
    "boundarySource": "qwen_shot_analysis" // qwen_shot_analysis | creator_manual
  },
  "source": {
    "masterPath": "…/scene_8_65e7cdb1.mp4",   // immutable
    "masterSha256": "…",
    "width": 1152, "height": 640, "fps": 24.0
  },
  "beats": [
    {
      "characterId": "4c1c0bc8-…", "characterName": "Anadriya",
      "startSec": 0.0, "endSec": 3.0,
      "line": "We've neutralized Cade. The threat is over.",
      "voiceAssetId": "…",        // fresh Qwen3-TTS render of THIS line
      "kind": "dialogue"
    },
    { "characterId": "4a2e9cbe-…", "characterName": "Korri",
      "startSec": 4.0, "endSec": 7.0, "line": "We did it, sis!",
      "voiceAssetId": "…", "kind": "dialogue" },
    { "startSec": 7.0, "endSec": 10.016, "kind": "silence" }  // authoritative NO DIALOGUE
  ],
  "references": {
    "sourceVideo": true,               // wires ref_videos.ref_video_0
    "includeSourceAudio": false,       // DEFAULT FALSE — old-dialogue leak guard
    "characterSheets": [               // ordered → ref_image_0, ref_image_1
      {"characterId": "4c1c0bc8-…", "assetId": "42828ced-…"},
      {"characterId": "4a2e9cbe-…", "assetId": "a97963c4-…"}
    ]
  },
  "generator": "minimax-h3-r2v-local", // | "seedance-2.5-hosted-fallback"
  "quality": "quality",                // quality | fast (EasyCache)
  "qwen": { "preReview": true, "postReview": true }
}
```

**Invariants**

- Beats partition the window with no overlap; `silence` beats are explicit, never implied.
- Every dialogue beat carries a `voiceAssetId` rendered from its exact `line` by the character's approved Qwen3-TTS voice — voice renders are produced through the existing Voice Editor / voice-performance path (speaker-bound clips must fit inside the window; no silent stretching).
- `characterSheets` ≤ 8 (one slot reserved ceiling under the 9-image cap; source video occupies the video channel, not image slots).
- Window end ≤ master duration; sub-windows snap to complete-shot boundaries when Qwen shot analysis finds them inside ±0.5s.

---

## 4. Pipeline (executor stages)

```
PerformanceRetakeSpec
  → S1 RAZOR: lossless ffmpeg cut of window (whole_shot = master as-is)
  → S2 QWEN PRE-REVIEW: run_perception(window) — characters present, camera,
        movement, shot boundaries; sub-window adjusted to shot boundary or NO-GO
  → S3 VOICE: verify/render per-beat Qwen3-TTS line assets (exact dialogue)
  → S4 STAGE: copy master window + character sheets + voice lines to Comfy input
        (plain copy2, asset-id names — existing comfy_asset_stage)
  → S5 GRAPH: build_h3_ref2v(..., ref_video_comfy_name=<window>,
        ref_audio_comfy_names=<beat lines in order>) — NEW ref_videos wiring:
        LoadVideo → GetVideoComponents → images → ref_videos.ref_video_0
  → S6 PROMPT: performance prompt = Qwen pre-review observation (camera/action)
        + timecoded beats ("<Video 1> … [00:00-00:03] <Audio 1> Anadriya says:
        …" ) + explicit silence constraints for silence beats
        + NO old-prompt dialogue text
  → S7 RENDER: queue to :8188 (protected runtime; submission only, never restart)
  → S8 TRIM/STITCH: trim 243→exact window frames; whole_shot = replace;
        sub_window = splice into untouched master with boundary continuity check
  → S9 AUDIO AUTHORITY: window audio = H3 native output ONLY; original window
        audio discarded (never layered); outside-window master audio untouched
  → S10 QWEN POST-REVIEW: run_perception(retake) — whole-face integrity
        (sliced/deformed = automatic NO-GO), speaker timing per beat,
        old dialogue absent, no invented dialogue, camera/action continuity
  → S11 PERSIST: new retake file (master immutable); scene output pointer +
        provenance sidecar (spec, generator, seed, SHA256s, Qwen verdicts)
```

---

## 5. Persistence & frontend semantics

- The **Lip Sync track becomes the Performance Retake window definition** (track IN/OUT = window). Creator-facing language: "Performance Retake". One render per retake region.
- **Reuse `lipsync_output_path`** as the "current performance output" pointer — 12+ existing readers (preview composer priority, editor mix, job panel, live preview) already honor it; internal field name documented here, creator-facing copy changes to Performance Retake. Provenance sidecar records `producer: "performance_retake"` vs historical `latentsync`.
- Scene 10 master `scene_8_65e7cdb1.mp4` stays byte-immutable (SHA256 pinned).

## 6. Audio authority & leak guards

1. `ref_video_audios` is **never wired by default** — the source window's original audio is not fed to the generator (old-dialogue leak guard). Explicit opt-in only, disclosed.
2. Window audio after retake = H3 native joint audio only. The old `media_retake/audio_rebuild.py` layering approach is NOT reused for the window interior.
3. Silence beats compile to explicit prompt constraints ("no dialogue, no speech, ambient only") — silence is authoritative.
4. Old scene prompt dialogue text must not appear in the performance prompt (compile-time check).

## 7. Qwen2.5-Omni wiring

Existing committed path: `codirector/video_intelligence/worker_client.py` — `run_perception(video_path, model_id=…)` / `run_av_perception` (worker.py: "Qwen2.5-Omni AV perception: ingests video + audio track together"). Reused for S2 and S10. The uncommitted working-tree `analyze.video` capability is **out of scope** for this milestone (foreign work).

## 8. Quarantine plan (creator-facing entry points → Performance Retake)

| # | Entry point | Action |
|---|---|---|
| 1 | `LipSyncTracks.tsx` "Apply lip sync" (default `mode:"legacy"` → `dual_lipsync`) | Re-route to Performance Retake submit; legacy behind `?legacyLipsync=1` |
| 2 | `AssetTray.tsx` "Lip sync only" + `lipsync_enabled` checkbox + audio selector | Re-label/route to Performance Retake |
| 3 | `queue_worker.py:2974` auto-lipsync after render (`scene.lipsync_enabled`) | Disable auto-trigger; retake is explicit creator action only |
| 4 | `api.py` `POST .../lipsync-tracks/apply` `mode:"legacy"`/`"windowed"` | Default → performance retake; legacy modes 410-gated behind flag |
| 5 | `codirector/m29` lipsync endpoints + `ProductionSuiteWorkspace` M2.9 section | Route to Performance Retake |
| 6 | `voice.prepare_lipsync` / `voice_environment.prepare_lipsync` tools | Keep (they bind voice assets — input to retake), update copy |
| 7 | `media_retake` job kind + `dual_lipsync`/`lipsync` workers | Quarantined legacy; not deleted; flag-gated |

## 9. Scene 10 live certification plan

Project `beffd3d8-791d-4adf-9c4d-681ec9d4efb0`, scene `e11cd0d0-60e7-492e-a1de-c244fa7cbb12` (index 8), master `scene_8_65e7cdb1.mp4` (10.016s, 1152×640, 24fps).

Beats: `[0–3]` Anadriya "We've neutralized Cade. The threat is over." · `[4–7]` Korri "We did it, sis!" · `[7–end]` SILENCE.

Character sheets: Anadriya `42828ced-1300-4143-9702-31c132bd8f3d`, Korri `a97963c4-09b3-402b-8341-8f0539b4bc0b` (approved front stills `0c7d967f…` / `4d48b0b0…` as alternates).

**12 required verdicts:** SOURCE SHOT ANALYSIS · RETAKE GENERATOR CAPABILITY · CHARACTER IDENTITY · WHOLE-FACE INTEGRITY · ANADRIYA SPEAKER TIMING · KORRI SPEAKER TIMING · OLD DIALOGUE REMOVED · NO INVENTED DIALOGUE · CAMERA/ACTION CONTINUITY · AUDIO CONTINUITY · NON-DESTRUCTIVE MASTER · QWEN POST-REVIEW.

Final: `GO — TIMELINE PERFORMANCE RETAKE VERIFIED` only if the result looks originally filmed with the new dialogue. Pasted-on lip-sync look = NO-GO.

## 10. Test plan

- Unit: spec validation (beats partition, silence explicit, voice-asset presence, window bounds), prompt compiler (timecodes, ref tags, silence constraints, old-dialogue leak check), graph builder (`ref_videos` wiring, LoadVideo→GetVideoComponents shape, assert extension of `assert_h3_ref2v_graph`), stitch math (trim to exact window, sub-window splice boundaries).
- Regression: existing H3 R2V tests must stay green (builder changes are additive).
- Live: Scene 10 certification (§9) + Playwright creator workflow (track → retake → preview → reload persistence).
- Comfy protection: submission-only; COMFY BEFORE/AFTER/RESTARTED? = NO in the final report.
