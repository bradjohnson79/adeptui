# DRAFT_PREVIEW_IMPL.md

**Spike:** Approach A — client draft frame-sequence playback  
**Date:** 2026-09-05 (PT)  
**No git commit** (per owner)

---

## Files touched

| Path | Change |
|------|--------|
| `studio-web/src/components/draftFrameSequence.ts` | **NEW** — buffer helpers, FPS/max constants, playback mode |
| `studio-web/src/components/DraftSequencePlayer.tsx` | **NEW** — low-FPS looping `<img>` sequence player |
| `studio-web/src/components/draftFrameSequence.test.ts` | **NEW** — unit tests for buffer / reset / mode |
| `studio-web/src/components/LivePreviewMonitor.tsx` | Buffer `liveDraftSrc` while `showDraft`; render `DraftSequencePlayer`; optional `frameUrls` / `playbackHint` on PreviewPayload; honest overlay meta |
| `studio-api/**` | **Unchanged** (preview stills remain `mediaType=image`) |
| seed/shape/canvas preflight | **Unchanged** |

---

## Behavior

1. While monitor is in draft states (`preparing` / `live_preview` / `processing` / `assembling` / `post`) and not library:
   - Collect successive **streamed** draft URLs (`previewSrc` / `composed.previewSrc` / optional `preview.frameUrls`).
   - Never buffer storyboard/source still alone as “motion.”
2. Render:
   - `draftFrames.length === 0` → existing empty/source `<img>` path + “No draft frames yet” when appropriate
   - `length === 1` → `DraftSequencePlayer` still mode + “waiting for more frames”
   - `length >= 2` → loop at **~6 fps** + “Draft motion · N frames @ ~6fps”
3. `pauseUpdates` freezes sequence advancement.
4. Job change or leaving draft clears the buffer.
5. T2V / 1F / 3F / Timeline all hit this via shared `LivePreviewMonitor` (Timeline still owns SSE in `TimelinePreviewComposer`).

---

## How to verify

```bash
cd studio-web
npx vitest run src/components/draftFrameSequence.test.ts
```

Manual: start a local Comfy-backed video job (LTX 2.5) that emits latent previews → Preview Monitor should cycle draft stills under `LIVE PREVIEW · Draft quality` with `data-testid="live-preview-draft-sequence"` and `data-draft-playback="sequence"` once ≥2 frames arrive.

---

## Follow-ups (not in spike)

- Phase 2 optional: server `frameUrls` in latest preview or short webm + `mediaType=video`
- E2E cert for draft-sequence testids on Timeline + T2V
- Tunable FPS via prefs
