---
id: z-image
kind: generator
modality: image
registry_ids:
  - zimage-local
aliases:
  - zimage
  - z-image
  - z-image turbo
spoken: Z-Image is a fast local stills engine. It is good for drafts and some reference-conditioned character work. It must not make Environment Reference Sheets.
workspace_tags:
  - image-generation
  - character-creator
version: "2026.09.04"
authority: adept-integrated
---

# Z-Image Turbo

## Purpose

Fast local stills on Image Runtime.

## Identity

Adept row `zimage-local`. Not Qwen. Not Illustrious.

## Supported modes

- Text-to-image drafts.
- Character Reference Conditioned when Adept wires `zimage.ref_edit`.
- Some Scene / Image Studio jobs when selected.

## Unsupported modes

- ERS generate.
- Silent fallback when another family was selected.
- Video.

## Inputs

Prompt, optional locked reference still.

## Reference semantics

When reference-conditioned, the locked photo is the identity source. Provenance must say Reference Conditioned, not Profile Guided.

## Strengths

Speed. Light VRAM.

## Weaknesses

TESTING in the registry. Weaker prompt lock than Qwen 2512. Weaker stylized identity than Illustrious.

## Output contract

Stills in Library. Example honest label: Local — Z-Image Turbo — Reference Conditioned.

## Runtime semantics

READY when Image Runtime has Z-Image. Otherwise NOT INSTALLED / REQUIRES SETUP. TESTING means not the certified default.

## Selection guidance

Drafts and locked-photo character jobs. Not ERS. Prefer Illustrious or Qwen when the creator asked for those.

## What Co-Director must never claim

That Z-Image ran when the creator picked Illustrious or Qwen.

## Persistence

This project Library.

## Relationships

- Character: `character-creator`
- Qwen: `qwen-2512`
