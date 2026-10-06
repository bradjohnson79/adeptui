# DRAFT_PREVIEW_DESIGN.md

**Owner ask:** For all video generators, when UI shows `LIVE PREVIEW · Draft quality`, show an actual low-res low frame-rate draft **video** (rough motion) — not a static first frame.

**Repo:** `C:\AdeptFilmWorks\AIVideoStudio`  
**Evidence:** `C:\Users\bradj\theme_walk\draft_video_preview\`  
**Date:** 2026-09-05 (PT)

---

## 1. Current vs target

### Current
| Layer | Behavior |
|-------|----------|
| Comfy tap | `video_runtime/live_preview.py` reads Comfy WS latent previews (JPEG/PNG bytes). Failure never raises into the render. |
| Publish | `queue_worker` `_preview_frame` / Route A `_poll_route_a_with_preview` saves bytes via `preview_bus.save_bytes`, publishes `GenerationPreview` with **`mediaType="image"`** + `localPath`. |
| Bus | `preview_bus.GenerationPreview` already has `mediaType: image \| video`, `frameIndex`, SSE `preview_updated` / `preview_available`. Latest-only cache per job (`_latest[jobId]`). |
| Client | `LivePreviewMonitor` + `TimelinePreviewComposer.useGenerationState` keep **latest** still URL. During draft, stage shows updating **`<img>`**. **`<video>`** only for library/final (`mediaType===video` or `.mp4/.webm/.mov`). |
| Badge | Overlay pill: `LIVE PREVIEW · Draft quality`. |

### Target
| Layer | Behavior |
|-------|----------|
| Generators | Unchanged: duration / resolution / seed / prompt / generator untouched. |
| Publish | Still emit honest intermediate stills when the engine provides them. Optional later: `frameUrls[]` / assembled webm. |
| Client (preferred) | Buffer successive draft still URLs → play as **looping frame-sequence at ~4–8 fps** inside the same Live Preview Monitor. |
| Honesty | 0 frames → still/storyboard + “No draft frames yet” / engine caps copy. 1 frame → still + “waiting for more frames”. ≥2 → motion sequence. Preview failure never fails the real render. |
| Shared path | One path via `LivePreviewMonitor` for T2V / 1F / 3F / Timeline (`composition.generation_draft` or legacy SSE). |

---

## 2. Approach choice

| Option | Fit | Verdict |
|--------|-----|---------|
| **A) Client buffer → low-FPS sequence** | Uses existing `preview_updated` still stream; no server assemble; works for all surfaces that already share LivePreviewMonitor | **Selected (spike)** |
| B) Server assemble short webm/mp4 + `mediaType=video` | Heavier (ffmpeg/encode), more invasive, preview failure risk surface larger | Deferred Phase 2 |

**Why A first:** Frames already land as discrete files + SSE; Timeline composer and legacy monitor only needed a shared buffer + player; no seed/shape/preflight touch.

---

## 3. Engine coverage (honest)

From `preview_bus.ENGINE_CAPS`:

| Engine family | Live preview | Notes |
|---------------|--------------|-------|
| `ltx` / `ltx-2.5*` | frames | Comfy WS tap → sequence when ≥2 frames |
| `wan` | frames | Same |
| `minimax-h3` (Route A) | frames (may be sparse early) | May stay on single still longer — UI says so |
| `fal_*` | `supportsLivePreview=false` | Existing caps copy: no intermediate frames |

---

## 4. Architecture (spike)

```
Comfy WS latent JPEG/PNG
  → live_preview tap (never fails render)
  → preview_bus publish mediaType=image
  → SSE / getJobPreview
  → TimelinePreviewComposer | LivePreviewMonitor legacy poll
  → liveDraftSrc (streamed URL only)
  → appendDraftFrame buffer (max 48)
  → DraftSequencePlayer @ ~6fps loop  (≥2) | still (1) | empty honesty (0)
```

Optional payload fields (forward-compatible, client works without them):
- `frameUrls?: string[]` — server-side history if added later
- `playbackHint?: "still" | "sequence"`

---

## 5. Risks

| Risk | Mitigation |
|------|------------|
| Sparse frames (MiniMax early) | Honest still mode until ≥2 URLs |
| Memory from many JPEGs | Cap 48 URLs; revoke not needed (server paths, not blob URLs) |
| Timeline sole-source composer | Buffer from `composed.previewSrc` changes; do not bypass composer |
| Confusing motion vs final | Keep DRAFT badge + “Draft motion · N frames @ ~6fps” |
| Pause Updates | Player `paused={pauseUpdates}`; SSE already gated |
| Job switch / leave draft | Clear buffer on job id change / `showDraft=false` |
| Approach B encode cost | Not in spike |

---

## 6. Non-goals (this spike)

- No git commit
- No seed / shape / canvas preflight changes
- No server webm assembly
- No change to final/library `<video>` path
