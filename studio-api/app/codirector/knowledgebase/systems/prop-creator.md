---
id: prop-creator
kind: system
modality: image
registry_ids: []
aliases:
  - props
  - prs
  - prop sheet
spoken: Prop Creator can compose a Prop Reference Sheet from an approved prop still. One canonical %Name tag. The sheet does not overwrite the original still and must keep identity from that source image. Timeline only binds it when the prop is approved and in the shot.
workspace_tags:
  - prop-creator
  - library
version: "2026.09.04"
authority: adept-integrated
---

# Prop Creator

## Purpose

Create and approve a Prop Reference Sheet (PRS) for a hero object on this project.

## Standalone-Express-Standard

Express and Standard share the same props on the open project.

## Identity

A PRS is an object identity page. It is not an Environment Sheet and not a Character Sheet.

## Supported modes

- Generate prop views with the ordinary stills picker.
- Upload custom views for Basic identity and Advanced Primary. Front / Back / Left / Right / Top / Bottom / Hero are optional extras.
- Approve Primary / Use This Prop so `%Name` can bind. Additional views are optional.
- Mixed uploaded + generated views on one Prop. Source does not change approval. Missing optional views do not block readiness or PRS.

## Unsupported modes

- Inventing `%CoffeeMug` when no prop is approved.
- Using a PRS as a place.
- Hidden catalog-only stills models as the default recommendation.

## Inputs

Prop description, optional reference photo, selected stills generator.

## Reference semantics

`%Name` binds the approved PRS only when the prop is in the shot.

## Output contract

Primary view + optional additional views + composed sheet in Library. Approve Primary to make it bindable.

PRS page contract (one system):
- Optional compose after a normal prop image (programmatic page; not a free redesign).
- Never overwrite the original approved still — new `prs_*.png` asset.
- Identity lock: hero tile is the approved source still.
- Formal fields: name, `%PascalCase` tag, description, source, style, notes.
- Prefix `%` only for props. `~` is generic Image Generator authority, not a prop tag.

## Adept integration

Timeline compile includes the PRS only after approve. Scene Creator may show the prop if the map or shot lists it.

## Runtime semantics

MODE-SPECIFIC. Needs Image Runtime or a hosted stills API. Not Local Video Runtime.

## What Co-Director may read

Saved props and approval state.

## What Co-Director may execute

Generate when asked.
"Use this image as the starfighter's top view" → `prop_creator.adopt_view`.
"Approve the uploaded back view" → `prop_creator.approve_view`.
"Generate a left view" → `prop_creator.generate_view`. Missing optional views are notes, not blockers.
"Create the prop reference sheet" → `prop_creator.generate_reference_sheet`.
"Which prop views are approved?" → `prop_creator.get_views`.
"Is this prop ready?" → ready when Primary is approved.
Do not create a new Prop for a view. Do not auto-approve an upload.

## What Co-Director must confirm

Approve / replace an approved PRS. Paid API.

## What Co-Director must never claim

That a mentioned object in dialogue is already a PRS.

## Persistence

Approved props stay on this project after reload.

## Relationships

- Marks: `reference-semantics`
- Timeline: `timeline`
- Image engines: `image-generation`
