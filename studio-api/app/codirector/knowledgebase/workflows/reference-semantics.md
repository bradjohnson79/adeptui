---
id: reference-semantics
kind: workflow
modality: workflow
registry_ids: []
aliases:
  - at hash percent
  - binds
  - sheet tags
spoken: At-names are people, hash-names are places, percent-names are props, star-names are motion. Adept only sends a sheet that exists, is approved, and is in the shot.
workspace_tags:
  - timeline
  - character-creator
  - spatial-map
version: "2026.09.04"
authority: adept-integrated
---

# Reference semantics

## Purpose

Translate creator marks into the selected generator's real inputs.

## Identity

Marks are Adept meaning. Each generator file says how they compile.

## Supported modes

| Mark | Binds | Rule |
| --- | --- | --- |
| `@Name` | CRS | Official character sheet |
| `#Place` | ERS | Official place sheet (GPT Image 2) |
| `%Prop` | PRS | Only if approved and in shot |
| `*Motion` | Motion clip | Only if that generator actually receives a motion file |

## Unsupported modes

- Inventing a PRS because dialogue mentioned a mug.
- Treating last-take as `#Place`.
- Emitting MiniMax `<Picture N>` on LTX.
- Restoring WAN or emitting WAN 2.6 `@Video1` as if it were current Adept.

## Prompting semantics

Compile using `video-generators/*.md` for the selected row. Names stay human-readable.

## What Co-Director must never claim

That a mark became a tensor the graph did not receive.

## Relationships

- Timeline: `timeline`
- Prompt Names: `prompt-names`
- Current video contracts: `ltx-2.5`, `minimax-h3`
