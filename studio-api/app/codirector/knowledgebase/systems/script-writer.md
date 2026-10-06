---
id: script-writer
kind: system
modality: system
registry_ids: []
aliases:
  - script
  - screenplay
  - dialogue
spoken: Script Writer turns your story into scenes and spoken lines. It does not invent a new character sheet or a new project.
workspace_tags:
  - script-writer
  - story
version: "2026.09.04"
authority: adept-integrated
---

# Script Writer

## Purpose

Write scene headings, action, and dialogue for the open project.

## Standalone-Express-Standard

Express can draft a scene. Standard Script Writer holds the full pages. Same project.

## Identity

Words and structure. Not a video generator. Not Voice Creator.

## Supported modes

- Draft and revise scripts from Story / Wiki names.
- Keep character names aligned with Character Creator.
- Hand lines to Voice Creator when the creator asks.

## Unsupported modes

- Creating a new project per scene.
- Treating script action as a Timeline compile without Prompt Names and approved sheets.
- Silent voice generation.

## Inputs

Story beats, Wiki names, existing characters.

## Prompting semantics

Dialogue is for performance. Visual action still needs `@` `#` `%` binds on Timeline.

## Output contract

Saved script pages on this project.

## Adept integration

Script names should match CRS / ERS / PRS names. Voice takes use the character's approved voice, not a random engine voice.

## Runtime semantics

READY for text. Voice Engine is a separate confirm.

## What Co-Director may read

Script pages on the open project.

## What Co-Director may execute

Drafts and requested line edits.

## What Co-Director must confirm

Voice takes. Timeline generates. Wiki promotion of new names.

## What Co-Director must never claim

That writing a line already recorded the voice or made the shot.

## Persistence

Scripts stay on this project after reload.

## Relationships

- Story: `story`
- Voice: `voice-creator`
- Timeline: `timeline`
