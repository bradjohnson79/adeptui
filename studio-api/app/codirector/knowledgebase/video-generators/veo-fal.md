---
id: veo-fal
kind: generator
spoken: This Veo row is not a live Adept Timeline path. Use the hosted Veo row that is actually available.
aliases:
  - veo fal
registry_ids:
  - veo-fal
product_ids:
  - veo-fal
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
    - "<Picture N>"
    - "@Image1"
---

# Veo (fal) — Production Control row, not a Timeline adapter

Sources: PC `veo-fal`; fal catalog `fal-ai/veo3.1` (T2V) and `fal-ai/veo3.1/image-to-video`; Timeline `VEO_ALIASES` = `veo-api`, `veo-kie` only.

Do not compile Timeline R2V as if `veo-fal` were wired. Official Veo 3.1 three-image rules live in `veo-3.1.md` and still do not apply until an adapter sends `referenceImages`.

## NEVER pretend

- Timeline submit to fal Veo from this row
- Three-image R2V on an unwired adapter
- Silent switch to `veo-kie`
