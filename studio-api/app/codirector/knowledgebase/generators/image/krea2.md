---
id: krea2
kind: generator
modality: image
registry_ids:
  - krea2-turbo-local
  - krea2-raw-local
  - krea2-turbo-fal
  - krea2-medium-fal
  - krea2-large-fal
aliases:
  - krea
  - krea 2
  - krea2 turbo
spoken: Krea 2 is a stills engine Adept can run locally or through a paid API. Turbo is the creator local row. It is not the Environment Reference Sheet engine.
workspace_tags:
  - image-generation
version: "2026.09.04"
authority: adept-integrated
---

# Krea 2

## Purpose

High-quality stills with optional reference conditioning.

## Identity

Local creator row: `krea2-turbo-local`. `krea2-raw-local` is a training base, not a creator default. Hosted turbo / medium / large are paid.

## Supported modes

- Text-to-image.
- Reference conditioning and LoRA on local Turbo.
- Hosted sizes when the creator picks fal rows.

## Unsupported modes

- Edit / inpaint on local Turbo (registry: does not support).
- ERS generate.
- Silent use of RAW as the default route.

## Inputs

Prompt, optional reference still.

## Strengths

Strong stills when READY. Hosted options if local VRAM is tight.

## Weaknesses

Local Turbo wants a large Image Runtime. RAW is REQUIRES SETUP and not creator-default.

## Output contract

Stills in Library with Krea 2 provenance (local vs hosted named).

## Runtime semantics

- krea2-turbo-local: READY or NOT INSTALLED.
- krea2-raw-local: REQUIRES SETUP, not creator default.
- Hosted: REQUIRES SETUP without keys.

## Selection guidance

Photoreal / richly lit stills. Not ERS. Confirm hosted spend.

## What Co-Director must never claim

That RAW is the everyday Krea. That Krea made an ERS.

## Persistence

This project Library.

## Relationships

- Flux: `flux`
- Image overview: `image-generation`
