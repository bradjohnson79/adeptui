# 12 — Reload / persistence (Gate M)

**Surface:** CURRENT DEVELOPMENT  
**Date:** 2026-08-30

## Timed Prompt X

Playwright (`timeline-timed-prompt-x-canonical-delete.spec.ts`) on Schnick Coffee:

1. Seed legacy `prompt_segments` + master `promptSegments`.
2. X delete → both lanes empty; Inspector Scene.
3. API reload: director + master no longer contain the id/marker.
4. Undo restores both lanes and compiled text.
5. Redo removes both again.
6. Browser reload: clip stays gone; director + master stay gone.

## LTX approve

SenseNova batch `bb_c1eb5212d68b` remains **Approved** with `approvedClip.assetId=ffd1e38a-…` after later API reads in this session. Scoped file still 200. Asset row still in Library.

## Home

Browser + Playwright: existing library (SenseNova, Schnick, others) hydrates after “Loading projects…”. First-use empty state is not shown while projects exist.

## Spatial / characters

Earlier API walk: SenseNova spatial 200, characters 200. Not re-run as Playwright this pass.
