---
id: ers-law
kind: workflow
modality: workflow
registry_ids:
  - gpt-image-2-fal
  - gpt-image-2-kie
aliases:
  - ers
  - environment reference sheet law
  - production ers
spoken: An Environment Reference Sheet is one production page for a place. Adept makes it only with GPT Image 2 via Environment Creator Express. Local Qwen is not a backup for that job.
workspace_tags:
  - scene-creator
  - image-generation
version: "2026.09.12"
authority: adept-integrated
---

# Environment Reference Sheet law

## Purpose

Lock how Adept makes and talks about ERS.

## Identity

One image. Same place. Different kinds of information on one page. Not a Character Sheet. Not four beauty POVs.

## Supported modes

- GPT Image 2 API exclusively.
- Layout exemplars as shape/density only.
- Content from Scene Intent and original place picture — never from exemplar lore.

## Unsupported modes

- Qwen local, Qwen Edit, Flux, SDXL, Scene Creator Mini, Auto Select as ERS generators.
- Silent cloud fallback to a different hosted stills engine.
- Copying Venture corridor or Korri's domicile pixels into a new café.

## Required sections (from the current spec)

Hero Environment, Spatial / Top-Down, Structural / 3D if honest, N/E/S/W of the same place, Materials, Lighting, Environment DNA, Continuity Rules.

## Adept integration

**Environment Creator Express** is the usual start for create-environment / ERS in Adept UI v1.1. Spatial Map is shelved — do not say it is the usual start. Image Generator may *use* an approved ERS as `#Environment` for production stills. Image Generator / Mini must not *make* the ERS.

## Runtime semantics

GPT Image 2 READY or REQUIRES SETUP. Missing setup is not a Qwen cue.

## What Co-Director must confirm

ERS generate (paid).

## What Co-Director must never claim

That Qwen, Flux, or Mini produced the ERS. That Spatial Map is required before ERS in v1.1.

## Persistence

ERS stays on this project and remains the `#Place` / `#Environment` bind.

## Relationships

- Current spec: `ers-spec` (`environment-reference-sheet/ERS_SPEC.md`)
- Engine: `gpt-image-2`
- Map (dormant): `spatial-map`
- Stills: `image-generation`
