# Timeline Visual Clip Remove + Inspector Accordion Restore

**Governing document for this gate.**

| Field | Value |
| --- | --- |
| Date | 2026-09-16 |
| Branch | `feat/character-creator-final-closure` |
| HEAD (committed baseline) | `99665cf76693e359cedc60c50c4405daf1b4e3a1` |
| Project | Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` |
| Cert scene | Disposable `Visual Remove Accordion Cert` (created and deleted by Playwright; Scene 12B / Walk untouched) |
| Review URLs | Creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/` |

## Verdict

**GO — TIMELINE VISUAL REMOVE + INSPECTOR ACCORDION RESTORE**

Unanimous three-LLM AGREE after one repair loop. Take vs placed Visual clip remain independent. Visual `×` / Delete detaches `director.video_clips` with `media_mode: "video"` and does not destroy Takes, candidates, `approvedClip`, Library assets, or the Batch. Batch Inspector fields sit in the existing `InspectorAccordion` stack. Production UI Take buttons read `Take A — use this take`. Source and rendered mojibake scans pass, including the `×` → `Ã—` family.

## Root cause

1. **Display ignored the empty-slot contract.** Visual track could render `playableTakes` when `sceneTakes` existed, even after `video_clips=[]` + `media_mode: "video"`. `×` filtered `video_clips` (sometimes a non-matching leftover row) while the track kept showing synthetic `bbclip_*` takes.
2. **Preview resurrected placement.** `resolveTimelineAtTime` fell through to `visualClips` / `approvedClip` / latest candidate after a successful detach.
3. **Batch Inspector never mounted accordions.** `InspectorAccordion` existed only on Scene / null selection. Selecting a Batch routed to a flat stack of the same Take / Generation / Advanced fields.
4. **UTF-8 punctuation was mis-saved as Windows-1252.** Creator-visible `—` `…` `'` `×` became `â€"` `â€¦` `â€™` `Ã—`. No charset hole in `index.html`; source bytes were wrong.

## Architecture (unchanged contracts)

- **Take** = `candidateVersions` / `approvedClip` / `sceneTakes`
- **Placed Visual clip** = `director_json.video_clips` + `media_mode`
- Empty Visual slot = `media_mode: "video"` and empty or filtered `video_clips`
- Persistence = existing shell `mutateTimeline` → `PUT /api/projects/{id}/scenes/{id}/director` → `dumps_director_timeline_preserving_embedded`
- Preview fallbacks to managed / approved / candidate only when `timeline` is null or `media_mode` is not `"video"`
- Previewing another scene take still uses membership
- Next Generate / Use this Take / `place_approved` may write `bbclip_*` again (re-place, not resurrection)

One mutation, two callers:

- `removePlacedVisualClip` in `studio-web/src/timelineMaster/playableVisualTakes.ts`
- `DirectorTracks.removeClip("video")`
- `TimelineEditorShell.deleteSelection` video path

No Inspector Remove control was invented. Keyboard on Batch still deletes the Batch after confirm.

## Implementation

- `displayedVisualVideoClips` always runs director clips through `filterVideoClipsForSceneTake` then `resolveVisualVideoClips`. The sceneTakes bypass that ignored `media_mode` is gone.
- `removePlacedVisualClip` filters the **displayed** list and always sets `media_mode: "video"`.
- `resolveTimelineAtTime` sets `visualPlacementAuthoritative = timeline?.media_mode === "video"` and skips take-owned fallbacks in that mode.
- Batch Inspector wraps existing fields in existing `InspectorAccordion`:

  | Accordion | Test id |
  | --- | --- |
  | Batch | `timeline-batch-accordion` |
  | Generation | `timeline-batch-generation` |
  | Takes | `timeline-batch-takes-accordion` (inner row `timeline-batch-takes`) |
  | Extend & Continuity | `timeline-batch-continuity` |
  | Advanced | `timeline-batch-advanced` |

  `TimelineSceneTakesPanel` stays on Scene selection only.
- Continuity chip test id is `timeline-batch-continuity-status` so it does not collide with the accordion. `timeline-continuity-bridge-live.spec.ts` updated.
- Take button: `{label} — use this take` when `CandidateReady`; ` (active)` when approved.
- Source UTF-8 repair across production UI trees (Inspector, DirectorTracks, Co-Director, menus, startup, API display strings). Remove-button `×` (U+00D7) restored after a first-pass `Ã—` mis-encode. No runtime decoder of creator project JSON.

## Tests

| Suite | Result |
| --- | --- |
| Vitest `playableVisualTakes` + `resolveTimelineAtTime` + `TimelinePreviewComposer` + `uiMojibake` | **4 files, 56 passed** |
| Playwright `tests/e2e/timeline/timeline-visual-remove-inspector-accordions.spec.ts` live `:5173` / `:8758`, `ADEPT_ALLOW_KORRI_MUTATION=1` | **1 passed** (9.4s after repair; 7.9s pre-glyph repair) |

`uiMojibake.test.ts` forbids `â€` / `Â·` / `Â ` / `Ã—` (`C3 83 E2 80 94`) under `src/components`, `src/pages`, `src/core`, `src/i18n`.

## Peer LLM review

Question (verbatim): Does this implementation correctly preserve the distinction between a rendered Take and a placed Visual-track clip, allow the placed clip to be removed without destroying the Take, persist that removal across reload, restore the existing Batch Inspector accordion architecture including Takes and Advanced without rebuilding or duplicating it, avoid regressions to Timeline persistence, generation, or Take handling, and leave production UI free of mojibake / pseudo-language artifacts with Take buttons reading “Take A — use this take”?

| Reviewer | First pass | After `×` repair |
| --- | --- | --- |
| Kimi K3 Max | DISAGREE — DirectorTracks remove glyphs were `Ã—`; scan omitted that pattern | **AGREE** |
| GLM 5.2 Max | AGREE | **AGREE** |
| GPT-5.6 Sol | AGREE | **AGREE** |

Unanimous **AGREE**.

## E2E TRACE

| Step | Result |
| --- | --- |
| User action — open disposable Korri scene Timeline, select Batch | PASS |
| Frontend — Batch accordion headers Takes / Advanced / Generation / Extend & Continuity; collapse/expand Takes and Advanced | PASS |
| API — place `bbclip_*` via PUT director; Visual `×` → PUT director `media_mode=video`, clip absent | PASS |
| Backend — `dumps_director_timeline_preserving_embedded`; Batch still on master | PASS |
| Persistence — clip gone after reload; Library video asset still on the project | PASS |
| Runtime — no GPU generate required; Generate Draft/Final still offered | PASS |
| Result — Visual empty; Take history / New take remain | PASS |
| Reload — clip still gone; Inspector / startup / Co-Director body have no forbidden sequences | PASS |
| Downstream — Generate controls remain; Co-Director greeting/chrome scan clean | PASS |

## Runtime / Comfy

| Check | Result |
| --- | --- |
| COMFY BEFORE | PID **34484** / `GET :8188/system_stats` **200** |
| COMFY AFTER | PID **34484** / `GET :8188/system_stats` **200** |
| COMFY RESTARTED? | **NO** |
| WHY? | Frontend-only restore; Vite HMR; no supervisor / `:8188` lifecycle |
| Studio API | `http://127.0.0.1:8758/api/healthz` **200** |
| Creator UI | `http://127.0.0.1:5173/` **200** |

## Limitations

- Playwright places an existing Korri Library video as `bbclip_*`; it does not run a new GPU render. Re-place via Use this Take / Generate remains available.
- Accordion open/closed state is session UI only; it is not persisted (same as Scene accordions).
- Creator-authored project prose that already contains `â€"` is not rewritten.
- Working tree still contains unrelated uncommitted work from other missions. This gate certifies the Visual-remove + Batch-accordion + mojibake restore only.

## Manual review

1. Open `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=timeline`
2. Prefer a disposable scene, or place a Visual clip on a non-canonical scene.
3. Select a Batch → confirm Batch / Generation / Takes / Extend & Continuity / Advanced accordions.
4. Collapse and expand Takes and Advanced.
5. Click Visual `×` → clip leaves the track; Batch and Takes remain; Preview does not claim the removed clip.
6. Reload → clip still gone; Take button copy is `Take A — use this take` when CandidateReady.
7. Do not restart Comfy.
