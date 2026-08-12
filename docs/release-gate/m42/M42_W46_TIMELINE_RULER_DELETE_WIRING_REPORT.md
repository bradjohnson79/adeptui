# M42 W46 — Timeline Ruler Alignment + Delete Wiring

**Verdict:** GO (wiring + Beta verification)

## Objective

1. Align Timeline ruler `0s` / playhead with the track lane start (not the track-label gutter).
2. Wire Timeline/MAGI Delete·Backspace and toolbar `−` end-to-end, including Co-Director operations (Laws 5, 9, 18).

## Scope completed

| Area | Change |
|------|--------|
| Ruler / playhead | Two-column gutter+lane layout matching track rows (88px / shell 132px) |
| Seek / hover | Ratio computed from lane width only |
| Co-Director `timeline.remove_item` | Supports batch + image/video/prompt/audio/sfx/camera clips; stashes; returns `_uiFocus` |
| Co-Director restore | Restores stashed track clips as well as Batch Blocks |
| UI batch delete API | `DELETE …/batches/{id}` now stashes (same restore surface as Co-Director) |
| MAGI | Delete/Backspace persists overlay delete; command path `overlay.proposeDelete` approve → `deleteSelected` |

## Laws checklist (selected)

- Law 1: Beta restart required after this change
- Law 5 / 9: UI ± / Delete and Co-Director remove share persisted Timeline state
- Law 8: Batch remove with content confirms in UI
- Law 10: Removals persist via director_json / timelineWorkspace.removedItems
- Law 18: One Timeline selection/focus bus (`adept-timeline-focus`); no parallel fiction state

## Manual review

1. Open Timeline → confirm `0s` sits at the start of the VISUAL/BATCHES lane (right of labels).
2. Scrub playhead — needle stays in the lane column.
3. Select a clip → Delete/Backspace → clip gone after reload.
4. Co-Director: `timeline.remove_item` with `itemKind=imageClip|promptSegment|batchBlock`.
5. MAGI: select overlay → Delete; or command “delete selected overlay” → approve.
