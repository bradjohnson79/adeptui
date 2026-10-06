---
id: image-generation
kind: system
modality: image
registry_ids:
  - qwen-image-2512-local
  - qwen-image-edit-2509-local
  - flux-local
  - flux-kontext-dev-local
  - zimage-local
  - gpt-image-2-fal
  - krea2-turbo-local
  - illustrious-local
  - seedream-kie
  - nano-banana-kie
aliases:
  - stills
  - image studio
  - image generator
  - cinematic image generator
  - pictures
spoken: The Image Generator is the production-still authority in Adept UI v1.1. Pick the engine for ordinary stills. Environment Reference Sheets always use GPT Image 2 via Environment Creator Express — never as a Scene Creator Mini fallback.
workspace_tags:
  - image-generation
  - library
version: "2026.09.12"
authority: adept-integrated
---

# Image Generation

## Purpose

**Image Generator** (`imagegen`) is the production-still authority. Run stills jobs with the engine the creator picks. Character Creator and Prop Creator may still request identity stills; Environment Reference Sheets run only via Environment Creator Express + GPT Image 2.

## Identity

Image Runtime for local stills. Hosted API for paid stills. Not Local Video Runtime. Not Scene Creator Standard / Mini as the primary still room.

## Creator tokens (Adept tags stay creator-facing)

| Token | Meaning |
| --- | --- |
| `@Character` | Approved character / CRS identity |
| `%Prop` | Approved prop / PRS identity |
| `#Environment` | Approved environment / ERS place lock |
| `~GenericImage` | Generic image reference (Image Generator Other Image References) |

Speak these as creator tags; do not invent a second tagging dialect.

## Supported modes

Ordinary picker / production stills (Image Generator):

| Engine | Typical job |
| --- | --- |
| Qwen Image 2512 | Prompt-faithful local stills |
| Qwen Image Edit 2509 | Local edit / reference edit |
| Flux | Photoreal local stills |
| Flux Kontext | Local edit when that row is set up |
| Z-Image | Fast local drafts; reference-conditioned when wired |
| GPT Image 2 | Hosted stills; **exclusive ERS engine** (via Environment Creator, not Mini) |
| Krea 2 | Local or hosted stills |
| Illustrious XL | Stylized / anime Character sheets |
| Seedream | Hosted stills when that row is available |
| Nano Banana | Hosted stills / light edit when that row is available |

## Unsupported modes

- Scene Creator Standard / Mini as the primary production-still room in v1.1.
- Qwen (or any local stills engine) as an ERS fallback.
- Silent family swap.
- Recommending **hidden catalog-only** rows as ordinary choices.

## Hidden catalog (no full profile)

These exist only as catalog rows. Do not teach them. Do not write full knowledge pages. Mention only here:

CogView, HiDream, Lumina, PixArt, Kolors, OmniGen, Sana, Janus, Hunyuan Image.

If a creator names one, say it is not on the ordinary picker and REQUIRES SETUP / experimental.

## Inputs

Prompt, purpose (character / prop / general / production still), optional `@` `%` `#` `~` references, selected engine, aspect, batch, PoseCraft snapshot when present.

## Reference semantics

Purpose decides the bind. ERS purpose → GPT Image 2 only via Environment Creator Express. Character purpose → CRS pipeline. Production still → Image Generator composer state.

## Output contract

Stills in this project's Library with honest provenance.

## Adept integration

Image Generator owns production stills. Environment Creator Express owns ERS. Spatial Map is shelved — do not route stills through map → Mini.

## Runtime semantics

MODE-SPECIFIC. Image Runtime READY / NOT INSTALLED / REQUIRES SETUP. Hosted APIs REQUIRES SETUP without keys. On Demand is not the default stills word unless Adept labels that engine On Demand.

## Selection guidance

- Production still → Image Generator.
- ERS → Environment Creator Express + GPT Image 2 only.
- Anime / stylized character → Illustrious.
- Local prompt fidelity → Qwen 2512.
- Fast draft → Z-Image.
- Photoreal → Flux or Krea 2.
- Edit an existing still → Qwen Edit or Flux Kontext when READY.

## What Co-Director may read

Selected engine, purpose, Image Generator composer state, Library results, PoseCraft snapshot when published.

## What Co-Director may execute

Generate after confirm when the purpose is allowed for that engine. Open Image Generator for production-still intents.

## What Co-Director must confirm

Paid API. ERS generate (Environment Creator path). Replacing an approved sheet.

## What Co-Director must never claim

That Qwen made an ERS. That Scene Creator Mini is the primary still room. That a hidden catalog model is a normal recommendation.

## Persistence

Stills stay on this project.

## Failure semantics

Wrong purpose + engine → refuse. Do not swap.

## Relationships

- Per-engine pages under `generators/image/`
- ERS: `ers-law`, `ers-spec`, Environment Creator Express
- Character: `character-creator`
- PoseCraft: `posecraft`
