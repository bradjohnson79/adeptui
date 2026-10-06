---
id: timeline
kind: system
modality: video
registry_ids:
  - minimax-h3
  - ltx-2.5-distilled
  - ltx-2.5-full
  - ltx-2.5-comfy
aliases:
  - director timeline
  - r2v
  - shot timeline
spoken: Timeline turns this project's pictures and Prompt Names into video. Local generators keep character and place sheets. They are not text-only movie machines.
workspace_tags:
  - timeline
version: "2026.09.04"
authority: adept-integrated
---

# Timeline

## Purpose

Build shots, bind Prompt Names, and generate video with the selected generator's real contract.

## Standalone-Express-Standard

Standard Timeline is the production surface. Co-Director may compile and request generate with confirm. Same project.

## Identity

Reference-to-Video on local Adept generators. Hosted rows follow their own files under `video-generators/`.

## Supported modes

- MiniMax H3 Timeline: Local Video Runtime Reference-to-Video (pictures + optional approved voice).
- LTX 2.5: one opening picture + named extras.
- Hosted Kling / Seedance / Veo when those rows are actually available.

## Unsupported modes

- WAN as a current generator. WAN is retired in v1.1.
- Treating LTX Timeline as text-to-video.
- Treating Timeline H3 as Route A text-to-video / image-to-video.
- Silent generator swap.

## Inputs

Approved CRS / ERS / PRS, Prompt Names, action prose, selected generator, optional last take.

## Reference semantics

See `reference-semantics` and the selected `video-generators/*.md` file. Those files are current.

## Prompting semantics

Co-Director compiles `@` `#` `%` into the dialect on that generator's page. Do not invent MiniMax tags on LTX.

## Output contract

A video take in Library on this project, with provenance for the selected generator.

## Adept integration

Reads Character, Spatial Map / ERS, Props, Voice. Writes Library. MAGI can finish later.

## Runtime semantics

MODE-SPECIFIC.

- Timeline H3 / LTX 2.5: Local Video Runtime READY, TESTING, NOT INSTALLED, or REQUIRES SETUP.
- MiniMax text-to-video / image-to-video: On Demand Local Video Runtime — separate. On Demand ≠ broken.
- Hosted: REQUIRES SETUP if keys are missing.

## Selection guidance

- Keep identity across people and place: MiniMax H3 Timeline.
- One strong start picture: LTX 2.5.

## Terminology disambiguation

LTX 2.3 is retired. LTX 2.5 is current. Route A ≠ Timeline H3. If the creator says WAN, it is retired unless they clearly mean computer networking.

## What Co-Director may read

Selected generator, Prompt Names, compile contract, job status.

## What Co-Director may execute

Compile always. Generate after confirm.

## What Co-Director must confirm

Every generate. Fast vs quality when it changes spend or look.

## What Co-Director must never claim

- That WAN is a current generator or text-to-video.
- That H3 Timeline is empty-latent text-to-video.
- That extra sheets were dropped when the dialect says they stay named.

## Persistence

Clips and Prompt Names survive reload on this project.

## Failure semantics

Missing Ingredients on an old LTX 2.3 row → refuse, do not fake text-to-video. Do not restore WAN to fill a missing last frame.

## Relationships

- Current generator pages: `video-generators/*.md`
- Overview: `video-generation`
- Prompt Names: `prompt-names`
- Continuity: `continuity`
