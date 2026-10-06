---
id: seedance-2.5
kind: generator
spoken: Seedance 2.5 is a hosted fal.ai video path, separate from Seedance 2.0. Adept only uses the contract this project actually wired.
aliases:
  - seedance 2.5
registry_ids:
  - seedance-2.5
  - fal_seedance_25
product_ids:
  - seedance-2.5
  - fal_seedance_25
compile:
  dialect: seedance_at_tokens
  mechanism: seedance_r2v
  emit_image: "@Image{n}"
  emit_video: "@Video{n}"
  emit_audio: null
  max_images: 4
  max_videos: 1
  max_audio: 0
  tensor_slots: hosted_urls
  never_emit:
    - "<Picture N>"
    - "<subject N>"
    - "[R2V]"
---

# Seedance 2.5 (fal) — Adept hosted video

Sources: fal `bytedance/seedance-2.5/{text-to-video,image-to-video,reference-to-video}`; Adept `fal_catalog.build_fal_arguments` / `build_seedance_r2v_arguments` + `Seedance25ApiAdapter`.

This is **not** Seedance 2.0. Do not execute `bytedance/seedance-2.0/*` for a 2.5 request. Do not paint 2.5 Ready because 2.0 is Ready.

`seedance-kie` and WaveSpeed Seedance are different products. Do not compile them as fal 2.5.

Adept-implemented caps (do not invent marketing modes): T2V / I2V / R2V (R2V only with a video ref), 4–30s, 480p/720p/1080p, max 4 images + 1 video, no uploaded audio refs. `generate_audio` is the model soundtrack and defaults on. No 4k. No three-still CREATE path.

## 1. Genuine R2V mode

Adept Timeline uses `bytedance/seedance-2.5/reference-to-video` **only when a video reference is attached**. Without a video ref, Adept calls 2.5 I2V or T2V. Do not emit `@ImageN` / `@VideoN` on those endpoints.

## 2. Supported reference media

| Media | Adept 2.5 adapter |
| --- | --- |
| Images | cap **4** |
| Videos | **1** |
| Audio | **not sent** |
| Three stills | **not implemented** |

## 3. Counts

Honor **4 images + 1 video + 0 audio**. Do not emit `@Image5` or `@Audio1`.

## 4–14. Tokens and identity

Same `@ImageN` / `@VideoN` grammar as Seedance 2.0, on **2.5** URLs only. Never MiniMax `<Picture N>`.

## 15. NEVER pretend

- That 2.5 ran as 2.0, or as generic “Seedance”
- 4k, 30 reference files, or `@AudioN` uploads. 1080p and `generate_audio` are sent. Duration on this adapter is 4–30s.
- A three-still CREATE workflow
- Kie or WaveSpeed as fal 2.5
