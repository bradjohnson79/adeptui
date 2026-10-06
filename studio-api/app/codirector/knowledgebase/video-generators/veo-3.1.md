---
id: veo-3.1
kind: generator
spoken: Veo is a hosted video path. Adept names people and places in ordinary language and does not invent MiniMax picture tags.
aliases:
  - veo
  - veo 3.1
  - google veo
registry_ids:
  - veo-api
  - veo-kie
product_ids:
  - veo-api
  - veo-kie
compile:
  dialect: veo_named
  mechanism: veo_r2v
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
    - "[R2V]"
---

# Veo 3.1 (Kie Timeline row) — official 3 images, Adept adapter 1

Sources: Google Veo 3.1 `referenceImages` (up to **three** images of a **single** person/character/product, `referenceType=asset`, 8s, first-frame XOR reference images); Adept `veo_api.py` (`maximumReferenceImages=1`, aliases `veo-api` / `veo-kie` only).

`veo-fal` is a Production Control row **without** a Timeline alias. See `veo-fal.md`.

## 1. Genuine R2V mode

Official Veo 3.1 supports **Ingredients / reference images**: up to 3 stills to preserve one subject’s appearance. That is not unlimited R2V and not mixed video/audio refs.

Adept Timeline adapter currently accepts **one** start image and does not POST `referenceImages`. Compile must not emit tokens for 3-image Veo until the adapter sends them.

## 2. Supported reference media (official vs Adept)

| Media | Official Veo 3.1 | Adept Timeline adapter |
| --- | --- | --- |
| Reference images | up to 3, one subject | **1** start image |
| First frame | I2V; **XOR** with referenceImages | treated as the one image |
| Last frame | some I2V paths | not wired |
| Video / audio refs | not this API | none |

## 3. Limits

Official R2V duration is **8 seconds**. Adept lists 5/10 — do not invent 10s official R2V. One subject across the three official images (person **or** product, not two named leads plus a place).

## 4–8. Adept tags

If Adept only sends one image: put the primary `@` CRS (or the one product) on that slot. `#` place and a second `@` cannot be official Veo multi-subject R2V. Name extras in English. Last-frame is not a Veo place.

When/if the adapter is upgraded to official 3-image `referenceImages`, still one identity — three views of **Anadriya**, not Anadriya + Korri + corridor.

## 9–10. Motion / audio

`*WalkCycle` unsupported. Native Veo sound is generated, not a creator `@Audio` ref.

## 11. Tokens

None on the Adept adapter. Official JSON uses `referenceImages[].referenceType = "asset"` — structural, not prompt sigils.

## 12–13. Retention

Official: three views of one subject. Adept today: one start still + named extras (disclose they were not sent as `referenceImages`).

## 14–15. NEVER pretend

- Unlimited R2V
- Two characters + a place as three official refs
- MiniMax / Seedance tokens
- That `veo-fal` is this Timeline adapter
- That Adept already sends 3 `referenceImages`

## Adept Timeline example

One start = Anadriya CRS.

```
Anadriya points down the corridor. Korri answers.
Korri (second character) and Venture Corridor (place) are named only — Veo 3.1 official R2V is one subject, and Adept currently sends one image.
```
