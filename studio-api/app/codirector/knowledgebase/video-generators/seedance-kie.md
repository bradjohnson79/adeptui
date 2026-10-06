---
id: seedance-kie
kind: generator
spoken: This Seedance row is not a live Adept Timeline path. Use the Seedance contract that is actually wired.
aliases:
  - seedance kie
registry_ids:
  - seedance-kie
product_ids:
  - seedance-kie
compile:
  dialect: unavailable
  mechanism: ""
  emit_image: null
  emit_video: null
  emit_audio: null
  max_images: 0
  max_videos: 0
  max_audio: 0
  tensor_slots: none
  never_emit:
    - "@Image1"
    - "@Video1"
    - "<Picture N>"
---

# Seedance (Kie) — Production Control row, no Timeline submit

Sources: `test_seedance_kie_never_binds_fal`; `video_readiness.py` (`Unsupported — Kie submit path is not implemented (will not use fal)`).

`seedance-kie` is listed in Production Control. Timeline has **no** adapter. Co-Director must not compile fal `@ImageN` tokens and must not silently switch to `seedance-fal`.

If the creator wants Seedance on fal, the live Adept paths are **`seedance-2.0.md`** and **`seedance-2.5.md`**. Never remap Kie onto either fal version.

## NEVER pretend

- That Kie Seedance received CRS/ERS/PRS
- Any reference tokens
- A silent fal fallback
