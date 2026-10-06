---
id: qwen-edit-2509
kind: generator
modality: image
registry_ids:
  - qwen-image-edit-2509-local
aliases:
  - qwen edit
  - qwen 2509
  - image edit 2509
spoken: Qwen Edit 2509 changes an existing still on Image Runtime. It is not the Environment Reference Sheet engine and it is not Qwen 2512 text-to-image.
workspace_tags:
  - image-generation
version: "2026.09.04"
authority: adept-integrated
---

# Qwen Image Edit 2509

## Purpose

Local edit and reference-conditioned stills.

## Identity

Adept row `qwen-image-edit-2509-local`. Sibling of Qwen 2512, not a replacement.

## Supported modes

- Edit / reference conditioning / identity reference when the row is executable.
- In-place change of an existing Library still.

## Unsupported modes

- ERS generate.
- Fresh text-only sheets that Adept already routes to Qwen 2512.
- Timeline video.

## Inputs

Source still + edit instruction.

## Reference semantics

The source image is the edit plate. Do not treat a CRS as an environment plate.

## Prompting semantics

Say what to change and what to keep. Do not attach ERS exemplars.

## Strengths

Local edits without a hosted API.

## Weaknesses

May be Draft / not executable until Image Runtime is fully set up.

## Output contract

Edited still in Library with Qwen Edit provenance.

## Runtime semantics

Often REQUIRES SETUP or not executable until installed. When present: READY on Image Runtime. Never call that “offline.”

## Selection guidance

Use for “change this picture.” Use Qwen 2512 for a new still. Use GPT Image 2 for ERS.

## What Co-Director must never claim

That Edit 2509 is the ERS fallback.

## Persistence

This project Library.

## Relationships

- New stills: `qwen-2512`
- ERS: `gpt-image-2`
