---
id: notes
kind: system
modality: system
registry_ids: []
aliases:
  - project notes
  - scratch notes
spoken: Notes are your working reminders on this project. They are not the Wiki and they are not an approved Character Sheet.
workspace_tags:
  - notes
version: "2026.09.04"
authority: adept-integrated
---

# Notes

## Purpose

Capture working thoughts without promoting them to canon.

## Standalone-Express-Standard

Available wherever the project is open. Express may show a short note. Standard holds the full list.

## Identity

Project-scoped scratch. Weaker than Wiki. Weaker than approved sheets.

## Supported modes

- Read and write notes on the open project.
- Point Co-Director at a note as context.

## Unsupported modes

- Using a note as a CRS, ERS, or PRS.
- Auto-copying notes into Wiki.

## Inputs

Creator text. Optional links to a scene or character the project already has.

## Output contract

A saved note. Not a generation.

## Adept integration

Co-Director may read notes for tone and reminders. Generation still binds approved sheets, not note prose alone.

## Runtime semantics

READY with the project. No generator runtime.

## What Co-Director may read

Notes on the open project.

## What Co-Director may execute

Create or edit notes when asked.

## What Co-Director must confirm

Promoting a note into Wiki or a character record.

## What Co-Director must never claim

That a note is production-ready identity.

## Persistence

Stays on this project after reload.

## Relationships

- Canon: `wiki`
- Beats: `story`
