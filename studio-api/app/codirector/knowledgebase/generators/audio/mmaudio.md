---
id: mmaudio
kind: generator
modality: audio
registry_ids:
  - mmaudio-local
aliases:
  - mm audio
  - sound effects engine
  - sfx engine
spoken: MMAudio writes sound effects for this project. It can follow a picture or a short clip. It is not a singer and it is not a character voice.
workspace_tags:
  - audio
  - magi
version: "2026.09.04"
authority: adept-integrated
---

# MMAudio

## Purpose

Local sound effects.

## Identity

Adept row `mmaudio-local`. Certified effects path when installed.

## Supported modes

- Effects from text.
- Picture- or clip-conditioned effects when Adept wires that input.
- MAGI finishing effects.

## Unsupported modes

- Songs (use ACE-Step).
- Character Voice Engine.
- Dialogue replacement.

## Inputs

Text, optional still or clip.

## Output contract

Effects file in this project's Library.

## Runtime semantics

READY when installed. Otherwise NOT INSTALLED / REQUIRES SETUP.

## Selection guidance

Whooshes, rooms, hits, ambience.

## What Co-Director must never claim

That MMAudio is the character's voice.

## Persistence

This project Library.

## Relationships

- Music: `ace-step`
- Audio room: `audio-sfx`
