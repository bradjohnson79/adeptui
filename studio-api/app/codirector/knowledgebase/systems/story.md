---
id: story
kind: system
modality: system
registry_ids: []
aliases:
  - story workspace
  - story beats
  - narrative
spoken: Story is where this project's plot and beats live. Co-Director can draft, but you decide what becomes the real story.
workspace_tags:
  - story
  - wiki
version: "2026.09.04"
authority: adept-integrated
---

# Story

## Purpose

Draft and keep the project's narrative — premise, beats, and scene intent — without silently rewriting Wiki.

## Standalone-Express-Standard

Express can draft a beat. Standard Story is the full workspace. Both write to the same project.

## Identity

Narrative workspace. Not Character Creator. Not Timeline.

## Supported modes

- Draft premise, beats, and scene summaries.
- Align names with existing Wiki / Character records.
- Hand a beat to Script Writer.

## Unsupported modes

- Generating a CRS or ERS from a beat alone.
- Silent Wiki writes from a draft.

## Inputs

Creator intent, Wiki names, existing characters and places.

## Output contract

Saved story text on this project. Optional handoff to Script Writer.

## Adept integration

Story names should match Character and Spatial Map names. Prompt Names on Timeline should use those same names.

## Runtime semantics

READY for text. Image or video generation is a later, confirmed step in another room.

## What Co-Director may read

Story pages on the open project.

## What Co-Director may execute

Drafts and requested edits.

## What Co-Director must confirm

Canon promotion into Wiki. Any generate that spends a run.

## What Co-Director must never claim

That a drafted beat already produced picture or video.

## Persistence

Saved story survives reload on this project.

## Relationships

- Wiki: `wiki`
- Script: `script-writer`
- Continuity: `continuity`
