---
id: audio-sfx
kind: system
modality: audio
registry_ids:
  - ace-step-local
  - mmaudio-local
aliases:
  - sound
  - music
  - sound effects
  - audio studio
spoken: Audio covers music and sound effects for this project. ACE-Step writes music. MMAudio writes effects. Neither one is a character voice.
workspace_tags:
  - audio
  - magi
version: "2026.09.04"
authority: adept-integrated
---

# Audio and sound effects

## Purpose

Make music beds and sound effects that belong on this project.

## Identity

Music and effects. Not Voice Creator. Not Timeline dialogue.

## Supported modes

- ACE-Step: local music.
- MMAudio: local effects / picture-to-sound when that path is wired.
- MAGI Audio can place music and effects on a finishing sequence.

## Unsupported modes

- Using these engines as a character Voice Engine.
- Claiming stems if Adept does not expose stems.
- Silent hosted audio swap when local is missing.

## Inputs

Text prompt, optional picture or clip for effects, project id.

## Output contract

Audio assets in Library on this project.

## Adept integration

Timeline may attach music later. MAGI finishing can generate and mix. Voice stays on Voice Creator.

## Runtime semantics

MODE-SPECIFIC. Each engine READY, NOT INSTALLED, or REQUIRES SETUP. Hosted audio rows may be Unavailable.

## Selection guidance

- Song / bed: ACE-Step.
- Whoosh, room tone, hit: MMAudio.
- Spoken character: `voice-creator`.

## What Co-Director may read

Saved music and effects on this project.

## What Co-Director may execute

Generate after confirm.

## What Co-Director must confirm

Long music renders. Replacing a bed already on a MAGI sequence.

## What Co-Director must never claim

That music is the character's voice.

## Persistence

Audio stays on this project.

## Relationships

- ACE-Step: `ace-step`
- MMAudio: `mmaudio`
- MAGI: `magi`
- Voice: `voice-creator`
