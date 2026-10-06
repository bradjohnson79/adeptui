# 10 — Playwright (Gate J / L)

**Surface:** CURRENT DEVELOPMENT  
**Date:** 2026-08-30

Live Beta: Vite `http://127.0.0.1:5173/` + Studio API `http://127.0.0.1:8758/`.  
`ADEPT_BETA_TARGET=1`, `ADEPT_ALLOW_KORRI_MUTATION=1` (Schnick Coffee writes only).  
`--project=chromium`. Never `POST /api/projects`.

## Measured

```text
ok 1 [chromium] tests/e2e/home/home-library-hydration.spec.ts
   Home library hydration › does not show first-use empty while projects exist (6.0s)
ok 2 [chromium] tests/e2e/timeline/timeline-timed-prompt-x-canonical-delete.spec.ts
   Timed Prompt X canonical delete › X removes Timed Prompt from UI, Inspector,
   both lanes, and compiled payload; undo/redo/reload (11.6s)
2 passed (18.5s)
```

## What those tests proved

- Home: after load, “No Projects Yet” is absent while the live library has projects.
- Timed Prompt **X**: clip gone from the track; Inspector returns to Scene; `prompt_segments` gone; `batch.promptSegments` gone; compiled master text no longer contains the marker; toolbar **Undo** restores both lanes; **Redo** removes both; **reload** keeps the delete.

## Not run this pass

Full creator walk Playwright (Character / Prop / Spatial / ERS / Scene handoff / Generate / Retake / Stop). Those surfaces were API-walked earlier on SenseNova, not re-run as Playwright here.
