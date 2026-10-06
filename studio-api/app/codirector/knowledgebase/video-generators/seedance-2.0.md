---
id: seedance-2.0
kind: generator
spoken: Seedance 2.0 is a hosted fal.ai video path, separate from Seedance 2.5. Adept only uses the contract this project actually wired.
aliases:
  - seedance 2.0
  - seedance 2
registry_ids:
  - seedance-2.0
  - seedance-api
  - seedance-fal
  - fal_seedance
product_ids:
  - seedance-2.0
  - seedance-api
  - seedance-fal
  - fal_seedance
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

# Seedance 2.0 (fal) — Adept Timeline hosted R2V

Sources: fal `bytedance/seedance-2.0/reference-to-video` (official `@ImageN` / `@VideoN` / `@AudioN`, up to 9 / 3 / 3, 12 files); Adept `fal_catalog.build_seedance_r2v_arguments` + `seedance_api.py`.

Production Control also lists `seedance-kie`. That row has **no Timeline adapter** and must not compile as fal. See `seedance-kie.md`.

Seedance **2.5** is a separate hosted product (`seedance-2.5.md`). Do not execute 2.0 when the creator chose 2.5. Legacy tokens `seedance-fal` / `seedance-api` / `fal_seedance` mean **2.0** only.

## 1. Genuine R2V mode

Official fal R2V: prompt + `image_urls` + `video_urls` + `audio_urls`.

Adept Timeline uses that endpoint **only when a video reference is attached**. Without `*motion` / video ref, Adept calls Seedance **I2V or T2V** (`bytedance/seedance-2.0/image-to-video` or `text-to-video`). Do not emit `@ImageN` / `@VideoN` on those endpoints.

## 2. Supported reference media

| Media | Official fal R2V | Adept adapter |
| --- | --- | --- |
| Images | up to 9 (`@Image1`…) | cap **4**; builder will slice `image_urls[:9]` but capabilities say 4 |
| Videos | up to 3 (`@Video1`…) | **1** (`video_urls[:1]`) |
| Audio | up to 3 (`@Audio1`…); needs an image or video | **not sent** (`audio_urls` unused) |
| First/last | I2V endpoint `image_url` / `end_image_url` | used when no video ref |

## 3. Counts

Adept compile must honor **4 images + 1 video + 0 audio**. Do not emit `@Image5` or `@Audio1`. Official 9/3/3 is documented so Co-Director does not invent a different product — it is not what this adapter sends.

## 4. Order

Start/place image first if present, then extra `referenceAssetIds`, then the single video URL. Prompt indices follow that upload order: `@Image1` is the first URL in `image_urls`.

## 5–7. Character / place / prop

`@Anadriya` → first image URL + `@Image1` in the prompt. `#VentureCorridorScene` / `%CoffeeMug` → next `@ImageN`. Never MiniMax `<Picture N>`.

## 8. Continuity

Last-frame still may be an extra `@ImageN` or I2V `end_image_url` when not in R2V mode. It is not a Seedance “place.”

## 9. Motion video

`*WalkCycle` is the gate that selects the R2V endpoint. Then `@Video1` only. Extra motion videos are not sent (`video_urls[:1]`).

## 10. Audio

Official `@Audio1` exists. Adept **does not upload audio**. Never emit `@Audio1`.

fal `generate_audio` is on by default. That is Seedance’s own soundtrack (ambience, effects, and speech written in the prompt). It is not an uploaded voice file.

## 11. Exact tokens

On R2V: `@Image1`, `@Image2`, `@Video1` matching uploaded URLs. No other sigils.

On I2V/T2V: plain English + named extras. No `@Image` tokens the API will not see.

## 12. Structural vs prompt

URLs are structural. `@ImageN` / `@VideoN` must match array order.

## 13. Identity

Upload the CRS/ERS/PRS bytes. Mention the same `@ImageN` in the action. Do not restyle from an unuploaded sheet.

## 14. Conflicts

R2V requires a video URL in Adept. Audio-only official refs are unsupported. Do not bind `seedance-kie` to this file’s fal submit.

## 15. NEVER pretend

- `@AudioN` or 3 videos
- A resolution outside `480p`, `720p`, `1080p`, and `4k`
- MiniMax Picture tags
- That extras were uploaded if the I2V path ran
- Seedance 2.5 limits, endpoints, or readiness on a 2.0 job

## Adept Timeline example (video ref attached)

```
@Image1 Anadriya (character)
@Image2 Korri (character)
@Image3 VentureCorridorScene (place)
@Video1 WalkCycle (motion)
Anadriya points down the corridor. Korri answers.
```

Without `*WalkCycle`, same sheets compile as I2V/T2V **named extras** and no `@Image` / `@Video` tokens.
