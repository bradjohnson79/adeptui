# M4.12 Section Continuity

Long-form Avatar Studio continuity is session-scoped, not clip-scoped.

## Rules

- Every section in one long-form job shares one `sharedStyleProfileId`
- Every section points back to one presenter identity through `identityProfileRef`
- Each section after the first stores `continuity.previousSectionId`
- Each non-first section marks `continuity.requiresContinuationFrame`
- Overlap windows are explicit through `overlapBeforeMs` / `overlapAfterMs`
- Transition validation is required before final assembly can mark the job complete

## Why this matters

These rules let Avatar Studio retry or replace only the broken section without silently regenerating the whole presentation or drifting to a new identity/style package.

## Current limitation

The continuity hooks are persisted now, but the live runtime path that consumes continuation frames is still experimental and not certified for production generation.
