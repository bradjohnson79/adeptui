---
id: adept-system-map
kind: adept
modality: platform
registry_ids: []
aliases:
  - system map
  - rooms
  - workspaces
spoken: Story and Wiki hold the words. Character, Voice, and Prop hold identity. Environment Creator Express plans place/ERS in v1.1. Image Generator makes production stills. Timeline makes motion. Library keeps everything in this project.
workspace_tags:
  - platform
version: "2026.09.12"
authority: adept-integrated
creator_chat: false
---

# Adept system map

## Purpose

Show how Adept rooms hand work to each other. One open project. One Library.

## Identity

Creator rooms, not engine graphs.

## Standalone-Express-Standard

| Room | Express in Co-Director | Standard / Home | Standalone |
| --- | --- | --- | --- |
| Wiki, Notes, Story, Script Writer | Yes, guided | Yes | — |
| Character Creator | Yes (Express) | Yes (full profile + sheet) | — |
| Voice Creator | Linked from Character | Yes | — |
| Prop Creator | Yes | Yes | — |
| Spatial Map | Shelved v1.1 (dormant) | Shelved v1.1 (dormant) | — |
| Environment Creator | Yes (Express / ERS) | — | — |
| Image Generator | Production stills | Yes (Cinematic Image Generator) | — |
| Scene Creator Standard / Mini | Not active still surface in v1.1 | Retired for creators | — |
| Timeline | Compile / generate with confirm | Yes | — |
| Library | Browse / attach | Yes | — |
| Image / Video / Audio | Through the room that owns the job | Yes | — |
| MAGI | Finishing tools | Yes | — |
| PoseCraft | **No** | — | **Yes — Pre-Production only** |

## Adept integration

Typical upstream → downstream (do not skip identity):

1. Wiki / Story / Script Writer name people, places, and beats.
2. Character Creator makes or approves a CRS. Voice Creator attaches a voice.
3. Prop Creator approves a PRS when a hero object matters.
4. In v1.1, Environment Creator Express plans environment/ERS identity (GPT Image 2 for ERS). Spatial Map is shelved — do not recommend it; project Spatial Map data is preserved.
5. Image Generator makes production stills (Qwen and other stills engines as listed). Qwen is not an ERS fallback.
6. Timeline turns approved sheets + Prompt Names into video for the selected generator.
7. Library stores every asset on this project.
8. MAGI finishes picture and sound. It does not replace Timeline generation.

PoseCraft can send a pose snapshot into Image Generation. It is not on the Express path.

## Runtime semantics

MODE-SPECIFIC. Each room uses the runtime its job needs. A stills job does not imply Local Video Runtime. Timeline H3 does not imply On Demand MiniMax.

## What Co-Director may read

Which room is open, which project is open, which sheets are approved.

## What Co-Director may execute

The tool for the room the creator asked about, after confirm rules in that room's page.

## What Co-Director must never claim

- A new project per image, sheet, or cert step.
- PoseCraft as Express.
- That Scene Creator Mini / Standard is the active production-still room, or that Mini and ERS share a generator rule.

## Persistence

All of the above stay on the open `projectId`.

## Relationships

- Each room file under `systems/`
- Character identity: `character-identity`
- Place law: `ers-law`
- Continuity: `continuity`
