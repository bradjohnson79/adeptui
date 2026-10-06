---
id: flux
kind: generator
modality: image
registry_ids:
  - flux-local
  - flux-schnell-local
  - flux-fal
  - flux-kie
aliases:
  - flux
  - flux dev
  - flux schnell
spoken: Flux is a photoreal stills engine. Local Flux uses Image Runtime. Hosted Flux is a paid API you must choose. Flux is not the Environment Reference Sheet engine.
workspace_tags:
  - image-generation
  - character-creator
version: "2026.09.04"
authority: adept-integrated
---

# Flux

## Purpose

Photoreal stills. Local Dev is the ordinary Adept Flux. Schnell and hosted rows are separate.

## Identity

Prefer `flux-local` when READY. `flux-schnell-local` is REQUIRES SETUP unless installed. `flux-fal` / `flux-kie` are hosted.

## Supported modes

- Text-to-image.
- Inpaint on local Dev when wired.
- Character and general stills.

## Unsupported modes

- ERS generate.
- Flux Kontext edits (see `flux-kontext`).
- Video.

## Inputs

Text prompt, optional mask for inpaint.

## Prompting semantics

Photographic language. Not Illustrious anime tags.

## Strengths

Photoreal local stills.

## Weaknesses

Weaker than Illustrious for stylized / anime sheets. Schnell may be missing.

## Output contract

Stills in Library. Provenance must name Flux (local or hosted), not a silent Qwen swap.

## Runtime semantics

- flux-local: READY or NOT INSTALLED / REQUIRES SETUP.
- flux-schnell-local: REQUIRES SETUP until installed.
- Hosted: REQUIRES SETUP without keys.

## Selection guidance

Photoreal stills. Not ERS. Not the first pick for anime CRS.

## What Co-Director must confirm

Hosted Flux spend.

## What Co-Director must never claim

That Flux can replace GPT Image 2 for ERS.

## Persistence

This project Library.

## Relationships

- Kontext: `flux-kontext`
- Stylized alternative: `illustrious`
