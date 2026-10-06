---
id: posecraft
kind: system
modality: system
registry_ids: []
aliases:
  - pose craft
  - pose studio
  - mannequin
spoken: PoseCraft is a full Pre-Production pose room. It is not a Co-Director Express tool. Use it when you need exact body posing before you make a picture.
workspace_tags:
  - posecraft
  - character-creator
version: "2026.09.04"
authority: adept-integrated
creator_chat: false
---

# PoseCraft

## Purpose

Pose a character in a dedicated Pre-Production room, snapshot that pose, and optionally hand it to Image Generation.

## Standalone-Express-Standard

**Standalone only.** Not Express. Not a Co-Director tab tool. Character Creator may link here with the character id. The creator leaves Express to use it.

## Identity

A staging workspace (mannequin / joints). It is not a CRS. It is not Timeline video.

## Supported modes

- Joint posing and snapshots on this project.
- Send snapshot to Image Generation as a pose reference.
- Bind an existing character.

## Unsupported modes

- Running PoseCraft as Co-Director Express.
- Claiming the snapshot is already a CRS.
- Using PoseCraft as a video generator.

## Inputs

Character id, pose preset, joint state.

## Reference semantics

The snapshot is pose / staging. Identity still comes from the CRS when Image Generation runs.

## Output contract

Pose snapshot in Library or a handoff the Image room can consume. Not a four-view sheet by itself.

## Adept integration

Character Creator Advanced can open PoseCraft. Image Generation may read the handoff. Timeline does not pose from PoseCraft joints directly.

## Runtime semantics

READY for posing without Image Runtime. Image Runtime is only needed when the creator sends the snapshot to generate.

## What Co-Director may read

That PoseCraft exists and whether a snapshot / handoff is saved.

## What Co-Director may execute

Direct the creator to the PoseCraft room. Do not pretend Express posed the body.

## What Co-Director must confirm

Generate-from-snapshot (a real stills job).

## What Co-Director must never claim

- That PoseCraft is Express.
- That a joint change already changed the CRS pixels.

## Persistence

Pose data stays on this project when saved.

## Relationships

- Character: `character-creator`
- Image room: `image-generation`
- System map: `adept-system-map`
