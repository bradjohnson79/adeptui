---
id: continuity
kind: workflow
modality: workflow
registry_ids: []
aliases:
  - same look
  - keep the room
  - last take
spoken: Continuity means the same people and the same place. The last video frame is only a motion handoff. It is not a new location and not a new character.
workspace_tags:
  - timeline
  - scene-creator
version: "2026.09.04"
authority: adept-integrated
---

# Continuity

## Purpose

Keep identity and place stable across stills and takes.

## Identity

Live project sheets win. Last-take is continuity, not canon place.

## Supported modes

- Reuse approved CRS / ERS / PRS.
- Last-take as motion continue on generators that accept it.
- Scene Creator Mini keep-the-room checks.

## Unsupported modes

- Calling last-take a new `#Place`.
- Redesigning the café because the camera moved.
- Copying ERS exemplar content (Venture corridor, Korri's room) into a new place.

## What Co-Director must confirm

Looks that change wardrobe, architecture, or approved sheets.

## What Co-Director must never claim

That extras were dropped when the dialect says they stay named.

## Persistence

Approved sheets and map placements survive reload.

## Relationships

- Identity: `character-identity`
- Place: `ers-law`
- Mini: `scene-creator`
