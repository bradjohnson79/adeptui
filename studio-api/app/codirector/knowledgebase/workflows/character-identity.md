---
id: character-identity
kind: workflow
modality: workflow
registry_ids: []
aliases:
  - crs law
  - character identity
  - who is this
spoken: A Character Reference Sheet is the official look of a person. A pretty front picture is not enough. Timeline and Scene Creator must use the approved sheet.
workspace_tags:
  - character-creator
  - timeline
version: "2026.09.04"
authority: adept-integrated
---

# Character identity

## Purpose

Keep one official look per character on the open project.

## Identity

CRS = approved multi-view sheet. `@Name` binds that sheet.

## Supported modes

- Profile Guided sheets from the written profile.
- Reference Conditioned sheets from a locked photo.
- Approve / persist on this project.

## Unsupported modes

- Treating Front.png / hero_identity as the CRS when a sheet exists.
- New project per candidate.
- Silent engine swap.

## Reference semantics

People = CRS. Place = ERS. Prop = PRS. Last video frame = continuity only, never a new person.

## What Co-Director may read

Saved character + active CRS + provenance.

## What Co-Director must confirm

Replace approved CRS. Paid API.

## What Co-Director must never claim

That a beauty still is the sheet. That identity survived if Library lost the sheet after reload.

## Persistence

Approved CRS must remain after refresh.

## Relationships

- Room: `character-creator`
- Marks: `reference-semantics`
- Engines: `illustrious`, `qwen-2512`, `z-image`
