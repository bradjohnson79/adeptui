---
id: library
kind: system
modality: system
registry_ids: []
aliases:
  - project library
  - assets
  - media library
spoken: Library is this project's shelf. Character sheets, places, voices, stills, and video takes all stay here — not in a new project each time.
workspace_tags:
  - library
version: "2026.09.04"
authority: adept-integrated
---

# Library

## Purpose

Store and reopen every asset that belongs to the open project.

## Standalone-Express-Standard

One Library per project. Express and Standard read the same shelf.

## Identity

Project-scoped media. Not a second Wiki. Not a hidden cache.

## Supported modes

- Browse, attach, and return to Character, Spatial Map, Timeline, MAGI.
- Keep approved CRS / ERS / PRS / takes after refresh.

## Unsupported modes

- Creating a new project per generate.
- Showing another project's assets as if they belong here.

## Inputs

Any successful generate or upload on this project.

## Output contract

Durable assets with provenance. Approved identity sheets remain after reload.

## Adept integration

Every generator room writes here. Co-Director attaches from here. Spatial Map and Timeline hydrate from here.

## Runtime semantics

READY when the project is open. Generators may be ON DEMAND or REQUIRES SETUP; Library still holds finished files.

## What Co-Director may read

Assets on the open project.

## What Co-Director may execute

Attach / suggest an existing asset. Delete only with explicit confirm.

## What Co-Director must confirm

Delete or replace of an approved sheet.

## What Co-Director must never claim

That a job succeeded if Library has no asset.

## Persistence

Required. If it vanishes after refresh, the generate is not complete.

## Failure semantics

A generate that never lands here is a failure, even if a button said success.

## Relationships

- Character: `character-creator`
- Timeline: `timeline`
- MAGI: `magi`
