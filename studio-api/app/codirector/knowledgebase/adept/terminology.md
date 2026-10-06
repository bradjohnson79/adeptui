---
id: adept-terminology
kind: adept
modality: platform
registry_ids: []
aliases:
  - glossary
  - terms
  - lexicon
spoken: In Adept, at-names are people, hash-names are places, percent-names are props. Timeline is Reference-to-Video. WAN is retired in v1.1 unless you are clearly talking about computer networks.
workspace_tags:
  - codirector
version: "2026.09.04"
authority: adept-integrated
---

# Adept terminology

## Purpose

Lock the words Co-Director may say so two meanings never collapse into one.

## Identity

Creator language first. Implementation words stay in Advanced / Diagnostics.

## Terminology disambiguation

| Creator says | Adept meaning | Not this |
| --- | --- | --- |
| **CRS** / Character Sheet | Character Reference Sheet — the approved multi-view identity page | A single pretty still, Front.png, or a beauty crop |
| **ERS** | Environment Reference Sheet — one production page for a place, GPT Image 2 only | A mood collage, four beauty angles, or a Qwen fallback sheet |
| **PRS** | Prop Reference Sheet — approved prop identity | A random mug in a prompt with no approved prop |
| **@Name** | Bind that character's CRS | Invent a person or use a front still as the sheet |
| **#Place** | Bind that place's ERS | Treat the last video frame as a new location |
| **%Prop** | Bind that prop's PRS when approved and in shot | Invent a prop sheet |
| **\*Motion** | Name the action in words unless that generator actually takes a motion clip | Pretend MiniMax received a video it did not |
| **WAN** | Retired in Adept UI v1.1. Do not restore. Use Timeline MiniMax H3 or LTX 2.5. | Current First/Last Frame product, WAN 2.6, WAN 3.0, or text-to-video |
| **WAN (networking)** | Only if the creator is clearly talking about networks | Do not treat networking talk as a video generator |
| **LTX** | LTX 2.5 is the current local family. LTX 2.3 is retired. Timeline LTX is not text-to-video. | One generic “LTX” dialect, or treating LTX 2.3 and 2.5 as the same |
| **H3** / MiniMax | Timeline = Local Video Runtime Reference-to-Video | Cloud Omni, empty-latent text-to-video, Route A |
| **Route A** | On Demand Local Video Runtime for MiniMax text-to-video / image-to-video | Timeline H3 |
| **On Demand** | The extra runtime is not running until needed | Broken, offline, missing product |
| **Spatial Map Atlas** | Rectangular picture at its real shape | A circular window around the picture |
| **Circles** (Spatial Map) | Circle-in-square placement grid overlay | A round crop of the Atlas |
| **PoseCraft** | Standalone Pre-Production pose room | A Co-Director Express tool |
| **Image Runtime** | Local stills engine | Video |
| **Local Video Runtime** | Timeline video engine | Route A On Demand path |
| **Prompt Names** | The people, places, and props named on a Timeline clip | Raw `@` markup as the only truth |

## What Co-Director must never claim

- That a circular viewport is how Spatial Map works.
- That Qwen local is an ERS backup.
- That WAN is a current v1.1 generator or text-to-video.
- That LTX 2.3 and LTX 2.5 are the same.
- That PoseCraft is Express.

## What Co-Director must confirm

If “MiniMax” could mean Timeline H3 or On Demand, ask which one — unless the open Timeline already selected a row. “LTX” means LTX 2.5 (LTX 2.3 is retired). If the creator says WAN, say it is retired in v1.1.

## Relationships

- Alias table: `lexicon.yaml`
- Reference marks: `reference-semantics`
- Prompt Names: `prompt-names`
- ERS law: `ers-law`
