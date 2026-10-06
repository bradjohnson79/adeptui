# P6 MUTE PROVE — GO (mute path) / gate UNCERTAIN

**When:** 2026-09-18 18:52 PT  
**Take:** stk_ae5b66e9d0a7 · **W2:** b_b5794fa154fe · **prior_frame:** dfbe6d3f5aba4cdbb86941da77b5fc1a  
**Job:** bb41127… / job_c45856ff6418 · **Comfy:** acc8802…  
**Candidate:** cand_cbef635fc3aa · **Take:** 	ake_7dd602e798a9 · **Asset:** 1f9a69f7…

## Prove: generate_audio=false

| Check | Result |
|-------|--------|
| NR generate_audio | **false** |
| udio_generation | **false** |
| udioAuthority | silence_locked / nativeAudio=disabled / generateAudio=false |
| Comfy graph | **no** VAEDecodeAudio; CreateVideo inputs = fps/bit_depth/color_space/images only (no audio) |
| Regression unit | PASS |

## Speech

| Check | Result |
|-------|--------|
| Raw render scene_3_cc16f1f0.mp4 | **no audio stream** |
| Asset 1f9a69f7….mp4 | **no audio stream** |
| Instrumental speech | **SILENT** |
| Pre-mute v3 NR | generate_audio was **true** (foreign "the" speech) — contrast |
| Omni | **UNAVAILABLE** |
| dialogueQc | verdict **UNCERTAIN** reason **OMNI_UNAVAILABLE** → batch **NeedsDialogueRetake** (not speech detect) |

## Lighting

This run: **INCONCLUSIVE** (Omni continuity unavailable). Prior v3 instrumental lighting GO still stands historically; not re-measured here.

## Overall

- **GO** for Gen mute path (request → worker → Comfy video-only → silent stem).
- **No BP MUTE wording escalation** (reused hardened v3 text).
- Gate status NeedsDialogueRetake is CD Omni-unavailable UNCERTAIN, not residual H3 speech.
- Stuck-Generating briefly appeared (job done / batch Generating) then finalized to NeedsDialogueRetake with candidate — finalizer follow-up still open.

Evidence under wave6_live_cert/ + freeze orensic_freeze/20260918_184548/.
