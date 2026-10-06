---
id: spatial-map
kind: system
modality: system
registry_ids:
  - gpt-image-2-fal
  - gpt-image-2-kie
aliases:
  - spatial map
  - atlas
  - placement grid
  - floor plan
spoken: Spatial Map is shelved for Adept UI v1.1 and is not an active creator surface. Existing project Spatial Map data is preserved. For environment / ERS work use Environment Creator Express. Do not claim Environment Creator already has Spatial Map geometry.
workspace_tags:
  - spatial-map
  - scene-creator
version: "2026.09.12"
authority: adept-integrated
creator_chat: false
---

# Spatial Map

## Adept UI v1.1 release note (shelf)

Spatial Map is **shelved** for Adept UI v1.1 — not deleted. Co-Director must **not** recommend or open Spatial Map for creators. If the creator asks for Spatial Map, say it is not active in this release. Route create-environment / mess hall / ERS intents to **Environment Creator Express** (contentTab `scene_creator`). Production stills go to the **Image Generator**. Do not claim Environment Creator already has Spatial Map geometry. Tools and project data remain for compatibility and a later return.

## Purpose (dormant)

Historically: lock where people, cameras, and the place sit for this project. In v1.1 that creator path is inactive. Do **not** instruct creators to feed Scene Creator or Mini from the map.

## Standalone-Express-Standard

- **Active substitute:** Environment Creator Express for environment / ERS.
- **Shelved:** Home / Production Spatial Map Standard workspace.
- There is no Express / Standard toggle for Spatial Map inside Co-Director in v1.1.

## Identity (compatibility)

- **Atlas** = the place picture (when present on old projects).
- **Placement grid** = square world with circle-in-square overlay (Circles toggle) on dormant UI.
- **Circular viewport** = retired.

## Supported modes

Compatibility / dormant only: rectangular Atlas, grid overlays, save, and optional ERS enrichment when GPT Image 2 is used from Environment Creator. Co-Director must not execute Spatial Map creator flows while shelved.

## Unsupported modes

- Recommending Spatial Map as the usual start for ERS or stills.
- Feed-Scene-Creator / Mini instructions.
- Circular viewport / round clip of the Atlas.
- Qwen, Flux, SDXL, Scene Creator Mini, or Auto Select as an ERS generator.

## Inputs

Legacy: place reference, saved map, placements, cameras. Live v1.1: Environment Creator Express planning for ERS.

## Reference semantics

Approved ERS is the place authority for production. Atlas on a shelved map is not the live creator path.

## Output contract

Existing Spatial Map data is preserved on the project. New ERS work goes through Environment Creator Express + GPT Image 2.

## Adept integration

Do not tell creators that Scene Creator Mini reads the saved map for new stills. Timeline `#Place` binds the approved ERS.

## Runtime semantics

MODE-SPECIFIC. Map edit tools remain registered but gated. ERS generate: hosted GPT Image 2 — never fall back to Qwen.

## Selection guidance

ERS → Environment Creator Express + GPT Image 2 only. If GPT Image 2 REQUIRES SETUP, say so. Do not offer Qwen as the ERS backup. Do not open Spatial Map.

## Terminology disambiguation

- Circles button = placement grid overlay on dormant UI, not a round viewport.
- Unit-circle cell rule = where a marker may sit. Not a crop of the picture.

## What Co-Director may read

Saved maps / placements for continuity answers when already on the project. Prefer Environment Creator / approved ERS for live guidance.

## What Co-Director may execute

In v1.1: do not execute Spatial Map creator flows. Prefer Environment Creator Express for environment/ERS and Image Generator for production stills. Dormant tools remain registered for compatibility only.

## What Co-Director must confirm

ERS generate (paid API) via Environment Creator path. Reset Map only if a dormant compatibility path is explicitly un-shelved later.

## What Co-Director must never claim

- That Spatial Map is active in v1.1.
- That the Atlas is shown in a circle.
- That Qwen made the ERS.
- Port numbers or "start the image engine yourself."

## Persistence

`backgroundAlignment` and placements survive Library leave / reload when present. Shelf does not delete project data.

## Failure semantics

Missing GPT Image 2 setup → REQUIRES SETUP. Do not silently swap models. Shelved open/atlas intents → honest redirect.

## Relationships

- ERS law: `ers-law`
- ERS spec: `ers-spec`
- Environment Creator / Image Generator: `scene-creator`, `image-generation`
- GPT Image 2: `gpt-image-2`
