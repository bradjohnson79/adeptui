---
id: ltx-2.5
kind: generator
spoken: LTX 2.5 is the active local video family. CREATE Text to Video uses ltx_25.t2v. Timeline and one-cond shots use ltx_25.i2v. It is not LTX 2.3 Ingredients.
aliases:
  - ltx 2.5
  - ltx25
  - ltx full
  - ltx distilled
registry_ids:
  - ltx-2.5-full
  - ltx-2.5-distilled
  - ltx-2.5-comfy
  - ltx_2_5_full
  - ltx_2_5_distilled
  - ltx_2_5_comfy
product_ids:
  - ltx-2.5-full
  - ltx-2.5-distilled
  - ltx-2.5-comfy
  - ltx_2_5_full
  - ltx_2_5_distilled
  - ltx_2_5_comfy
compile:
  dialect: ltx25_single_cond
  mechanism: ltx25_single_cond
  emit_image: "[R2V]"
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
---

# LTX 2.5 — Adept Timeline one-cond Reference-to-Video

Sources: live Comfy `:8188` `LTXVImgToVideo` + `LTXVBaseSampler` (2026-09-01); Adept `ltx_25_builder.py`. Product rows: `ltx-2.5-full`, `ltx-2.5-distilled`, `ltx-2.5-comfy`.

This is **not** LTX 2.3 Ingredients. Do not copy IC-LoRA rules here.

CREATE **Text to Video** is a separate local workflow (`ltx_25.t2v`) — words only, no start picture. Timeline remains one-cond Reference-to-Video. Do not hide CREATE T2V because Timeline is R2V.

## 1. Genuine R2V mode

LTX 2.5 Timeline conditions **one start picture** via `LTXVImgToVideo`. Extra CRS / ERS / PRS stay **named in the prompt**. They are not silently dropped and they are not extra tensors.

`LTXVBaseSampler.optional_cond_images` can load extra stills. That is **not** certified 3 Frame. 3 Frame requires first + last with proven semantics. Until Comfy MCP proves that contract, LTX 2.5 is **not** Ready on 3 Frame.

## 2. Supported reference media

| Media | Live Adept 2.5 graph | Handling |
| --- | --- | --- |
| One start image | `LTXVImgToVideo.image` | required for Timeline R2V |
| Extra images | prompt names only | `@` `#` `%` stay named |
| Video | none | no `*motion` socket |
| Audio | native decode exists | not a voice-reference socket |
| First/last | one start; no last-frame tensor | last-take may be the start cond |

## 3. Counts and limits

One conditioned image. Variants differ by checkpoint / VAE / Fast steps, not by prompt grammar. Negative prompt supported.

## 4. Order, index, role

Preferred start cond: place/ERS, else the mapped start. Characters and props are extras. No Picture index.

## 5–7. Character / place / prop

`@` `#` `%` appear as `[R2V] Opening picture is …` plus `[R2V] Also in this shot: Anadriya (character), …`. Identity extras are text, not MiniMax tags.

## 8. Continuity

Last-take may occupy the single start cond. Then named extras must still list the people. Do not call the last frame a new place.

## 9. Motion video

`*WalkCycle` is prose only. Do not emit `<Video N>` or `@Video1`.

## 10. Audio

No `<Audio J>`. LTX 2.5 can generate soundtrack; that is not a creator voice reference.

## 11. Exact tokens

`[R2V]` is Adept’s disclosure prefix for this one-cond path. The live CLIP encode sees ordinary English after that. Never `<Picture N>` or `@Image1`.

## 12. Structural vs prompt

One structural image. All other roles are prompt text.

## 13. Identity retention

Put the strongest identity sheet you can into the single start cond when that is the only tensor. Otherwise name CRS/ERS/PRS explicitly. Do not restyle from an unnamed extra.

## 14. Conflicts

Do not use Ingredients IC-LoRA rules. Do not invent `LTXV2*` class names (they are not on this runtime). Fast is fewer steps, not a smaller picture.

## 15. NEVER pretend

- That 3 Frame is Ready
- Multi-image tensor R2V as a certified 3 Frame path
- LTX 2.3 Ingredients on a 2.5 row
- MiniMax or Seedance tokens
- That extra sheets were dropped

## Adept Timeline example

Creator: `@Anadriya @Korri #VentureCorridorScene` , start = corridor.

```
[R2V] Opening picture is VentureCorridorScene (place).
[R2V] Also in this shot: Anadriya (character), Korri (character).
Anadriya points down the corridor. Korri answers.
```

`%CoffeeMug` is added to the “also” line only if approved. `*WalkCycle` stays in the action sentence.
