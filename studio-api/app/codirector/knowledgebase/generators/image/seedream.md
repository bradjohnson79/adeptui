---
id: seedream
kind: generator
modality: image
registry_ids:
  - seedream-kie
aliases:
  - seedream
  - see dream
spoken: Seedream is a hosted stills engine. Adept only uses it when that row is available and you choose it. It is not the Environment Reference Sheet engine.
workspace_tags:
  - image-generation
version: "2026.09.04"
authority: adept-integrated
---

# Seedream

## Purpose

Hosted stills / light edit when the Seedream row is live.

## Identity

Adept row `seedream-kie` (Testing). Not Seedance video. Not GPT Image 2 ERS.

## Supported modes

- Text-to-image and edit if the hosted row accepts them.

## Unsupported modes

- ERS generate.
- Local Image Runtime Seedream (there is no local row).
- Seedance video grammar.

## Inputs

Prompt, optional source still.

## Runtime semantics

TESTING / REQUIRES SETUP / Unavailable depending on keys. Never call that “offline local.”

## Selection guidance

Only if the creator asked for Seedream or the ordinary picker shows it Available. Prefer local engines or GPT Image 2 for ERS.

## What Co-Director must confirm

Paid hosted generate.

## What Co-Director must never claim

That Seedream is Seedance. That it replaced GPT Image 2 for ERS.

## Persistence

This project Library.

## Relationships

- Image overview: `image-generation`
- Video Seedance: `seedance-2.0`
