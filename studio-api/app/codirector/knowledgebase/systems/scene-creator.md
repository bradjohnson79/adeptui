---
id: scene-creator
kind: system
modality: image
registry_ids:
  - qwen-image-2512-local
  - zimage-local
  - flux-local
  - gpt-image-2-fal
aliases:
  - scene creator mini
  - scene stills
  - camera stills
spoken: Scene Creator Standard and Mini are not the active production-still surfaces in Adept UI v1.1. Production stills go to the Image Generator. Environment create and ERS go to Environment Creator Express.
workspace_tags:
  - scene-creator
  - image-generation
version: "2026.09.12"
authority: adept-integrated
---

# Scene Creator

## Adept UI v1.1 release note

**Scene Creator Standard / Mini are not active production-still rooms in v1.1.** Creators do not open Standard or Mini for production imagery.

- **Production stills** → **Image Generator** (Cinematic Image Generator / `imagegen`).
- **Environment create / ERS** → **Environment Creator Express** (contentTab `scene_creator`).
- **Spatial Map** is shelved (dormant). Do not claim stills from a saved Spatial Map as the live path.

Legacy ids and compatibility code may remain; spoken guidance must stay honest about the active surfaces.

## Purpose

Historical: camera-true stills from a saved Spatial Map. In v1.1 that path is retired for creators — route to Image Generator or Environment Creator Express as above.

## Standalone-Express-Standard

- **Environment Creator Express** owns create-environment / ERS planning (not Scene Creator Standard).
- **Image Generator** owns production stills.
- Scene Creator Mini / Standard UI is not the fuller production surface in this release.

## Identity

Not the ERS room. Not Timeline video. Not the v1.1 production-still authority.

## Supported modes (compatibility only)

Dormant Mini / Standard tooling may still exist for old project load. Co-Director must not recommend them for new stills or ERS.

## Unsupported modes

- Presenting Standard / Mini as the active still room.
- Using Mini (or any local stills engine) as the ERS generator.
- Inventing a Spatial Map that was not saved, or claiming Spatial Map is required for Image Generator stills.

## Inputs

For live work: Image Generator composer (prompt, refs, engine) or Environment Creator Express planning. Do not require a saved Spatial Map for production stills.

## Reference semantics

Place lock for ERS comes from Environment Creator / approved ERS (GPT Image 2). People come from approved CRS. Do not treat a CRS as the environment plate.

## Output contract

Production stills land in Library via Image Generator provenance. ERS via Environment Creator Express.

## Adept integration

Route creators to Image Generator for stills and Environment Creator Express for place/ERS. Timeline may use an approved still later; that does not revive Mini as a Timeline generator.

## Runtime semantics

MODE-SPECIFIC. Image Runtime for ordinary stills. ERS = hosted GPT Image 2 only.

## Selection guidance

- Production still → Image Generator.
- Environment / ERS → Environment Creator Express + GPT Image 2.
- Never Qwen for ERS — see `ers-law`.

## What Co-Director may read

Active Image Generator / Environment Creator state; Library stills; approved ERS.

## What Co-Director may execute

Open Image Generator or Environment Creator Express when the creator asks. Do not open Spatial Map creator flows while shelved.

## What Co-Director must confirm

Paid hosted stills. ERS generate. Regenerating an approved take.

## What Co-Director must never claim

That Mini or Standard produced the Environment Reference Sheet, or that Standard is the fuller production-still surface in v1.1.

## Persistence

Takes and ERS stay in this project's Library after reload.

## Failure semantics

Wrong room for the job → redirect honestly. Do not silently swap engines or revive shelved Spatial Map.

## Relationships

- Image Generator: `image-generation`
- Environment / ERS: Environment Creator Express, `ers-law`
- Spatial Map (dormant): `spatial-map`
- Continuity: `continuity`
