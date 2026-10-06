---
id: kling
kind: generator
spoken: Kling in Adept is hosted image-to-video with one start picture. It is not multi-picture Reference-to-Video.
aliases:
  - kling
  - kling 2.5
registry_ids:
  - kling-api
  - kling-fal
  - kling-kie
product_ids:
  - kling-api
  - kling-fal
  - kling-kie
compile:
  dialect: kling_named
  mechanism: kling_i2v
  emit_image: null
  emit_video: null
  emit_audio: null
  max_images: 1
  max_videos: 0
  max_audio: 0
  tensor_slots: start_only
  never_emit:
    - "<Picture N>"
    - "<subject N>"
    - "@Image1"
    - "@Video1"
    - "[R2V]"
---

# Kling 2.5 Turbo Pro — Adept hosted I2V (not multi-ref R2V)

Sources: fal `fal-ai/kling-video/v2.5-turbo/pro/image-to-video` (`image_url`, optional `tail_image_url`); Adept `kling_api.py` + `fal_catalog.py`.

PC rows: `kling-fal`, `kling-kie`. Timeline adapter id `kling-api`. Readiness may mark the adapter as **Testing** (in-memory job ledger unless a live submit path is added). Compile must still be honest about the **provider contract**.

## 1. Genuine R2V mode

Official fal path Adept catalogs is **image-to-video**: one first-frame `image_url`, optional tail. This is **not** Seedance/WAN/H3 multi-reference R2V.

Adept capabilities: `maximumReferenceImages=1`, `supportsVideoReferences=False`.

## 2–3. Media and limits

One start image. Optional end/tail image on the official schema. No reference-video array. No audio refs. Duration 5 or 10s.

## 4–8. Adept tags

`@` `#` `%` cannot all be uploaded. Put the **single** strongest identity/place still on `image_url`. Name every other bound sheet in ordinary English. Last-frame may map to `tail_image_url` if Adept ever sends it — today the Timeline adapter does not build fal args. Prior-frame is not a second character.

## 9–10. Motion / audio

`*WalkCycle` is unsupported. Do not emit `@Video1`. No voice ref.

## 11. Exact tokens

None. Prompt is English. Official fields: `prompt`, `image_url`, optional `tail_image_url`, `duration`, `negative_prompt`.

## 12–13. Retention

The first frame carries appearance. Extra CRS/ERS/PRS are prompt names only — disclose that they were not uploaded.

## 14–15. NEVER pretend

- Multi-image R2V
- MiniMax or Seedance tokens
- That `kling-kie` and `kling-fal` are different prompt grammars on Timeline (one adapter)
- That the in-memory adapter already uploaded files to fal

## Adept Timeline example

Opening picture = Anadriya CRS (the one tensor).

```
Anadriya points down the corridor. Korri answers.
Also keep Korri's look (character sheet named, not uploaded) and the Venture Corridor place (named, not uploaded).
```

No `@Image1`. No `<Picture 1>`. If `%CoffeeMug` is not the start image, name it only.
