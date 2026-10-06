---
id: character-creator
kind: system
modality: image
registry_ids:
  - illustrious-local
  - qwen-image-2512-local
  - zimage-local
  - flux-local
  - krea2-turbo-local
aliases:
  - characters
  - character sheet
  - crs workspace
spoken: Character Creator builds the Character Reference Sheet for a person in this project. The approved sheet is the face Timeline and Scene Creator must keep.
workspace_tags:
  - character-creator
  - library
version: "2026.09.04"
authority: adept-integrated
---

# Character Creator

## Purpose

Create, generate, approve, and keep one Character Reference Sheet (CRS) per character on the open project.

## Standalone-Express-Standard

- **Express** (Co-Director): guided profile + generate. Certification may use one candidate.
- **Standard**: full Character Profile. Production generate uses four candidates unless the creator changes it.
- Advanced rooms (Voice, PoseCraft, Props, Variants) are linked from the saved character. PoseCraft itself is Standalone Pre-Production, not Express.

## Identity

The CRS is the identity page: multiple views of the same person, not a single beauty still. `hero_identity` / Front.png is not a CRS.

## Supported modes

- Profile Guided stills (no locked photo).
- Reference Conditioned stills when the creator locks a photo.
- Local Image Runtime families Adept actually exposes: Illustrious XL, Qwen Image 2512, Z-Image, Flux, Krea 2, and others on the ordinary picker.
- Hosted stills when the creator chooses them.

## Unsupported modes

- Silent model swap (Illustrious must stay Illustrious).
- Using Qwen as an ERS fallback (ERS is not this room).
- New project per candidate.
- Hidden catalog-only stills models as ordinary recommendations.

## Inputs

Character profile, optional locked reference photo, selected generator, project id.

## Reference semantics

A locked photo is a look reference. The approved CRS becomes the `@Name` bind for later rooms.

## Prompting semantics

Profile Guided writes from the character profile. Reference Conditioned must keep the locked photo as the identity source.

## Strengths

One project Library. Provenance names the real engine (example: Local — Illustrious XL — Profile Guided).

## Weaknesses

A pretty front still is not enough for Timeline identity. Approve the sheet.

## Output contract

Four views plus a composed sheet per candidate (Express cert may produce one candidate). Approved CRS stays after refresh.

## Adept integration

Downstream Timeline, Scene Creator, and Spatial Map occupancy use the approved CRS, not a random still.

## Runtime semantics

MODE-SPECIFIC. Needs Image Runtime READY (or a configured hosted API). Local Video Runtime is not required.

## Selection guidance

- Stylized / anime-leaning: Illustrious XL.
- Prompt-faithful local stills: Qwen Image 2512.
- Fast local draft: Z-Image.
- Photoreal local: Flux or Krea 2 when those rows are READY.

## What Co-Director may read

Saved characters, active CRS, provenance, Library assets on this project.

## What Co-Director may execute

Generate after the creator asks. Express generate is a real job, not a mock.

## What Co-Director must confirm

Paid API. Changing an approved CRS. Switching the named generator.

## What Co-Director must never claim

- Success before views land in Library.
- That a front still is the CRS.
- That PoseCraft ran inside Express.

## Persistence

Character + approved sheet survive reload on this project.

## Failure semantics

If Image Runtime is NOT INSTALLED or REQUIRES SETUP, say so. Do not silently change models.

## Relationships

- Identity law: `character-identity`
- Voice: `voice-creator`
- Pose: `posecraft`
- Image engines: `image-generation`
