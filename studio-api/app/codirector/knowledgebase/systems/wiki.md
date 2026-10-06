---
id: wiki
kind: system
modality: system
registry_ids: []
aliases:
  - project wiki
  - bible
  - production bible
spoken: Wiki is this project's saved story facts — people, places, and rules you approved. Chat guesses are not Wiki until you keep them.
workspace_tags:
  - wiki
  - story
version: "2026.09.04"
authority: adept-integrated
---

# Wiki

## Purpose

Hold approved project knowledge the team can reopen later. Not a chat log.

## Standalone-Express-Standard

Express and Standard share the same project Wiki. There is no second Wiki per chat.

## Identity

Project-scoped. User-authored or user-approved entries win over Co-Director inference.

## Supported modes

- Read existing Wiki for the open project.
- Draft an update.
- Save only on an authorized approve / keep path.

## Unsupported modes

- Silently turning capitalized chat words into canon characters or places.
- Copying another project's Wiki.
- Treating Notes or a single chat turn as Wiki.

## Inputs

Creator text, approved Story / Script facts, and linked character or place names that already exist.

## Output contract

A versioned Wiki entry on this project. Not a generated picture.

## Adept integration

Wiki feeds Character Creator, Story, Script Writer, and Continuity. It does not generate CRS, ERS, or video by itself.

## Runtime semantics

READY when the project is open. No Image Runtime or Local Video Runtime required to read Wiki.

## What Co-Director may read

Wiki pages for the open project.

## What Co-Director may execute

Drafts and proposed edits.

## What Co-Director must confirm

Any write that changes canon names, relationships, or continuity rules.

## What Co-Director must never claim

- That a suggestion is already saved.
- That onboarding chat created a character record.

## Persistence

Survives reload on this `projectId`.

## Failure semantics

If save fails, keep the draft visible and say it is not saved.

## Relationships

- Notes are lighter: `notes`
- Story drafting: `story`
- Script pages: `script-writer`
- Authority: `adept-authority`
