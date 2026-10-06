---
id: illustrious
kind: generator
modality: image
registry_ids:
  - illustrious-local
aliases:
  - illustrious xl
  - illustrious xl 1.0
  - anime engine
spoken: Illustrious XL is the local engine for stylized and anime-leaning Character Sheets. Profile Guided means it works from the written profile, not from a locked photo.
workspace_tags:
  - character-creator
  - image-generation
version: "2026.09.04"
authority: adept-integrated
---

# Illustrious XL

## Purpose

Stylized / anime / realistic-anime Character Sheets and stills on Image Runtime.

## Identity

Adept row `illustrious-local`. Certified local character family when installed.

## Supported modes

- Text-to-image.
- Character Profile Guided four-view sheets.
- Ordinary stills when selected.

## Unsupported modes

- Native reference-conditioned tensor path as its certified default (use Z-Image or Qwen when the creator locked a photo).
- ERS generate.
- Video.

## Inputs

Character profile or stills prompt.

## Reference semantics

Profile Guided: profile is the identity source. Do not pretend a locked photo was used.

## Prompting semantics

Stylized character language. Keep wardrobe and body consistent across the four views.

## Strengths

Best Adept local pick for anime-leaning CRS.

## Weaknesses

Not the ERS engine. Not a photoreal Flux substitute.

## Output contract

Four views + composed sheet. Provenance example: Local — Illustrious XL — Profile Guided. Must remain after refresh.

## Runtime semantics

READY when Image Runtime has Illustrious. Otherwise NOT INSTALLED / REQUIRES SETUP.

## Selection guidance

Anime / stylized character. If the creator locked a photo, confirm whether they still want Profile Guided Illustrious or a reference-conditioned engine.

## What Co-Director must never claim

That Illustrious ran when Z-Image or Qwen was selected. That it produced an ERS.

## Persistence

This project Library.

## Relationships

- Character: `character-creator`
- Identity: `character-identity`
- Qwen: `qwen-2512`
- Z-Image: `z-image`
