---
id: flux-kontext
kind: generator
modality: image
registry_ids:
  - flux-kontext-dev-local
aliases:
  - kontext
  - flux kontext
  - flux.1 kontext
spoken: Flux Kontext edits a still while trying to keep the same subject. It needs Image Runtime setup. It is not the Environment Reference Sheet engine.
workspace_tags:
  - image-generation
version: "2026.09.04"
authority: adept-integrated
---

# Flux Kontext

## Purpose

Local reference-aware edit stills.

## Identity

Adept row `flux-kontext-dev-local`. Not Flux Dev text-to-image. Not GPT Image 2.

## Supported modes

- Edit, inpaint, reference conditioning when the row is installed.

## Unsupported modes

- ERS generate.
- Default creator route when REQUIRES SETUP.
- Video.

## Inputs

Source still + instruction.

## Reference semantics

Keep the subject in the source. Do not restyle from an unnamed extra.

## Runtime semantics

Typically REQUIRES SETUP until weights are installed. Then READY on Image Runtime.

## Selection guidance

Use when the creator wants a Flux-family edit. If the row is REQUIRES SETUP, say so. Offer Qwen Edit if that row is READY — only with confirm, never silent.

## What Co-Director must never claim

That Kontext is installed when the registry says REQUIRES SETUP.

## Persistence

This project Library.

## Relationships

- Base Flux: `flux`
- Other editor: `qwen-edit-2509`
