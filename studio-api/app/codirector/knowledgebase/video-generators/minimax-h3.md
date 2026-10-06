---
id: minimax-h3
kind: generator
spoken: MiniMax H3 on Timeline is Local Video Runtime Reference-to-Video. It keeps your character, place, and voice pictures in the shot.
aliases:
  - h3
  - minimax
  - minimax h3
  - hailuo
registry_ids:
  - minimax-h3
  - minimax-h3-local
  - minimax-h3-t2v-local
  - minimax-h3-i2v-local
  - minimax-h3-i2v
product_ids:
  - minimax-h3
  - minimax-h3-local
  - minimax-h3-t2v-local
  - minimax-h3-i2v-local
  - minimax-h3-i2v
compile:
  dialect: h3_picture_tokens
  mechanism: h3_ref2va
  emit_image: "<Picture {n}>"
  emit_subject: "<Subject {n}>"
  emit_video: "<Video {n}>"
  emit_audio: "<Audio {n}>"
  max_images: 9
  max_videos: 3
  max_audio: 3
  tensor_slots: all_visual
  never_emit:
    - "lowercase <subject N>"
    - "@Image1"
    - "[R2V]"
---

# MiniMax H3 — Adept Timeline Reference-to-Video

Sources: live Comfy `:8188` `MiniMaxH3ReferenceToVideo` (2026-09-01); Adept `h3_ref2v_builder.py`; official MiniMax-H3 [Full-Reference Mode Rewrite Guide](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md); MiniMax platform `/v2/video_generation` reference roles.

## 1. Genuine R2V mode

Adept Timeline H3 is **Reference-to-Video** on `MiniMaxH3ReferenceToVideo` + the ref2va UNET. It is not empty-latent T2V and not `MiniMaxH3ImageToVideo` first-frame I2V. Both Production Control rows (`minimax-h3` and `minimax-h3-i2v-local`) share this graph.

Official cloud H3 also has T2V / I2V / first-last-frame / Omni Reference. Adept Timeline does **not** use those modes.

## 2. Supported reference media

| Media | Official H3 | Live Adept Comfy node | Adept Timeline adapter |
| --- | --- | --- | --- |
| Images | up to 9 | `ref_images` | wired, max 9 |
| Videos | up to 3 | `ref_videos` max 3 | wired (`maximumReferenceVideos=3`) |
| Audio | up to 3 | `ref_audios` max 3 | wired (approved voice + typed Library audio) |
| First/last frame | official I2V / keyframe | `MiniMaxH3ImageToVideo` only | **not used** on Timeline R2V |
| Mixed | official Omni, 12 files total | node accepts mixed | images + videos + audios within caps |

## 3. Counts and limits

Live builder: at least 1 image, at most 9 images, at most 3 videos, at most 3 audios (matches live Comfy COMFY_AUTOGROW caps). Length snaps to the 17k+5 frame grid at 24 fps (5s / 8s). Canvas uses the Timeline legal H3 canvas. A 4th video or audio is refused — never silently discarded.

## 4. Order, index, role

Bind order: CRS → ERS → PRS → prior-frame continuity → audio.

`ref_images[i]` is `<Picture i+1>`. `ref_audios[j]` is `<Audio j+1>`. Do not invent a number the graph did not receive.

## 5. Character identity

`@Name` binds the **approved Character Reference Sheet** as identity authority. Official rewrite language calls reusable people **subjects** defined from pictures.

Adept compiles official `<Subject N>` ↔ `<Picture N>` from Timeline's checked References. Subject N uses the same index as that character's Picture N. The creator Timed Prompt stays in names (`Addex sits…`); the adapter rewrites actions and speakers to `<Subject N>`.

Official example: `<Subject 1> is the young woman in <Picture 1>`. Adept emits `subject_definitions` plus Subject-bound action. It does **not** emit the full six-section rewrite dump, and it never asks the creator to type this syntax.

Never emit decorative lowercase `<subject N>` from Co-Director/creator prose. Strip those, then compile official Title-Case `<Subject N>` from the wired slots.

Never substitute a different Library photo (`hero_identity` / Front.png / profile still) when an approved CRS exists. MiniMax `<Picture n>` still needs **one person**, not the labeled multi-panel bible — Adept may upload a derived single-figure still **cropped from that same approved sheet**. The sheet remains authority. The crop is not new canon.

## 6. Environment / place

`#VentureCorridorScene` binds ERS (approved composite; tagged still only if no ERS). Place is a Picture, not a first frame.

## 7. Props / products

`%CoffeeMug` binds PRS only when that prop is in the shot. Next free Picture index.

## 8. Prior-frame / prior-video continuity

Last-take still is a Picture used **only** as continuity. Never a new character. Never a place. When a character is joining, Adept may keep the last frame named and skip sending it as a Picture.

Prior **video** continuation is official `<Video N>` / `video continuation`. Adept Timeline wires Library `*video` refs into `ref_videos` (max 3).

## 9. Motion / camera / style video

`*WalkCycle` is a creator motion tag. When the binding is checked and the Library video is staged, Adept uploads it into `ref_videos` and the live node receives the media. A 4th `*` video is refused at capability/adapter/UI — never silently dropped.

## 10. Audio / voice

Approved character voice → `ref_audios` + `<Audio J>`. Official and Adept: `<Audio J> is the voice-timbre reference for <Subject N> (SN)` when that voice maps to a character Picture. Audio without a picture is refused by official Omni rules; Adept always has at least one picture.

## 11. Exact tokens the live path understands

Live Comfy description: `<Picture i> / <Video k> / <Audio j>` reference conditioning. Official Full-Reference rewrite also uses `<Subject N>` defined from `<Picture N>`. Adept compiles both.

Adept sends `subject_definitions` plus Subject-bound action. It does not send the unused official sections (`summary`, `retention_analysis`, `detailed_description`, `overall_soundscape`, `non_diegetic_music`) as a dump.

Never emit `@Image1`, `[R2V]`, or lowercase decorative `<subject N>`. Official Title-Case `<Subject N>` is required on H3 when characters are bound.

## 12. Structural vs prompt roles

Both. Images/audio are structural sockets. Prompt tags must match socket order. Role clauses in the prompt (`this person`, `the place`) are guidance, not extra sockets.

## 13. Identity retention

Use the approved CRS as identity authority. Upload one Picture per bound character. If the bound file is a labeled multi-panel sheet, the H3 tensor is a one-figure crop from that sheet (front turnaround), not a different beauty still and not the full collage.

## 14. Conflicts

No TeaCache / MiniMaxH3TeaCache. Fast uses EasyCache on the same pictures. No silent T2V/I2V fallback. Official standalone Picture entries are for first/last/storyboard frames — Adept Timeline R2V does not use that I2V node.

## 15. NEVER pretend

- That Adept H3 is T2V or first-frame I2V
- That official `<Subject N>` is decorative or unused on Full-Reference H3
- That a 4th video/audio was silently dropped
- That Front.png is a CRS
- That last-frame is a place or a new person
- Cloud Omni 12-file mixed media on this Timeline path

## Adept Timeline example

Creator:

```
@Anadriya @Korri #VentureCorridorScene %CoffeeMug
Anadriya points down the corridor. Korri answers.
```

Compile (no mug approved, last-take present):

```
subject_definitions:
<Subject 1> is Anadriya, the person defined by <Picture 1>. Preserve their facial identity, hair, body proportions, clothing, and distinguishing appearance from <Picture 1>.
<Subject 2> is Korri, the person defined by <Picture 2>. Preserve their facial identity, hair, body proportions, clothing, and distinguishing appearance from <Picture 2>.

CHARACTER IDENTITY
<Picture 1> Anadriya — Preserve the supplied visual identity. Do not invent a replacement person.
<Picture 2> Korri — Preserve the supplied visual identity. Do not invent a replacement person.
The people in this shot are <Subject 1> (<Picture 1> Anadriya) and <Subject 2> (<Picture 2> Korri).
These are the characters. Preserve them. The reference pictures are identity authority.

VISUAL STYLE
<project style>
Apply this style to the entire scene while preserving reference identity.

ENVIRONMENT
<Picture 3> VentureCorridorScene — keep this location.

ACTION
<Subject 1> points down the corridor. <Subject 2> answers.

CONTINUITY
<Picture 4> Previous take — continues the previous take only.
They are in <Picture 3>.
```

If `%CoffeeMug` is approved and in shot, it becomes the next Picture. `*WalkCycle` reaches `ref_videos` when checked on the scene References.
