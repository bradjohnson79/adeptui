# Session Memory: 2026-09-26 23:26 through 2026-09-27 15:32

Last 24 hours. One chat: Timeline V2. Branch `feat/character-creator-final-closure`. HEAD `ca8f3c0cc25cf09e665047363cfb4ebecc2bb89b`. Work is in the working tree and was not committed.

Owner unlocks used: `timeline`, `API multi-window pipeline`, `timeline-reference-identity`.

Comfy `:8188` stayed PID 27852 and was not restarted. Studio API was recycled several times. Local creator UI is Vite `http://127.0.0.1:5173/`. Studio API is `http://127.0.0.1:8758/`.

Backup of the pre-cutover Timeline: `backups/timeline-pre-simplification/2026-09-26-ca8f3c0cc25c`. Continuity-mission backup: `backups/timeline-continuity/2026-09-27-ca8f3c0c`. Neither backup is imported.

---

## 1. FilmTimeline shot architecture

**NO-GO — FULL-STACK E2E NOT VERIFIED**

FilmTimeline is the production Timeline. Hierarchy is Project → Scene → Shot → Segment. ShotState is the shot authority. One orchestrator. One Add to Timeline path. Old generate, extend, batch, retake, and stitch routes answer HTTP 410 `FILM_TIMELINE_REQUIRED`.

Live MiniMax and LTX generation through a finished Continue-after-reload were not certified.

Evidence: `docs/release-gate/film-timeline/FILM_TIMELINE_SHOT_ARCHITECTURE_COMPLETION_REPORT.md`

## 2. Timeline V2 premium UX and V1 preview

Shipped in the working tree. 40/60 split, Inspector / Hot Keys / GPU, cinematic prompt toolbar (Scene, Camera, Color / Lighting, Template), and the V1 preview chrome (Publish, Update Published, Upscale with MAGI, eye, Re-Take, Full Screen). Local MiniMax is one row: MiniMax H3 — Reference to Video.

Not a certification. Generate had not been proven through a completed asset at the time of that pass.

## 3. Open-source infrastructure audit

**TIMELINE V2 OPEN-SOURCE INFRASTRUCTURE: GO**

ffmpeg, Comfy 0.34.5, and the H3/LTX weights were present. Motion Context was not installed. Omni was not installed. Paid APIs were not spent. Manual beta was described as wired, not certified.

## 4. Continuity engine

**NO-GO — TIMELINE V2 CONTINUITY**

`studio-api/app/film_timeline/continuity.py` extracts the last frame, a short tail, and a head still after a segment completes. The packet lives on `segment.generationMetadata["continuity"]`. MiniMax stays Reference-to-Video. LTX Continue uses the one-image start path. Duration menu is 3–20. Qwen2.5-Omni is registered for full review and is not a generation blocker. Motion Context and other extra systems were classified and not installed.

Unit tests passed. The disposable 40–60 second MiniMax and LTX Continue runs were not started.

Evidence: `docs/release-gate/film-timeline/TIMELINE_V2_CONTINUITY_ENGINE.md`

## 5. Preview layout

The preview height divider and the icon-only side-panel collapse are in the Film Timeline shell. Height, width, collapsed state, and the selected tab stay in workspace preferences. They are not part of the film document. Checked in the browser on the open Timeline.

## 6. Cancel Render and reference tags

The V1 red Cancel pill is mounted in the preview’s upper left and calls the existing queue halt for the active Film Timeline job. A hosted provider that cannot cancel stays running, and the UI says so.

Reference grammar matches V1: `@` character, `#` environment, `%` prop, `*` video, `&` audio. The References button sits beside Template. The preview does not show a reference image. A library row that is already bound shows a green check.

A live cancel of a running Comfy job was not clicked.

## 7. Render Shot — open

**RENDER SHOT: NO-GO**

Generate Shot on the open scene did reach MiniMax. Shot `shot_cadaa9caed3e`, segment `seg_23e6784ba3ed`, job `4d740ce8-0934-4cb6-8249-6fc1429b656a`. The scene canvas is 1920×824. MiniMax refused it because both sides must be multiples of 32. The segment is failed. The shot status stayed `generating`, and the preview did not show that error. Comfy’s queue was empty afterward.

A repair was started and not finished: Film Timeline should send the legal H3 canvas `1152x640`, settle the shot status when the segment fails, and show `segment.error`. The unit test for that canvas was added. The API was not recycled for it. No disposable generation was completed. Do not treat Render Shot as fixed.

---

## Still open

- Render Shot must complete one disposable MiniMax job into Comfy and back into the preview.
- Continue Shot after that job is not proven.
- Continuity live certification (several Continues toward 40–60 seconds) is not proven.
- Omni model is absent. Full continuity review is yellow. Generation must not wait on it.
- Working tree is uncommitted.
