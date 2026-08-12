# M42 W46 — Toolbar 2-row, Tracks Height, 20s Cap, Co-Director Wiring

**Verdict:** GO (Beta ready for manual review)

## Changes

| Item | Detail |
|------|--------|
| Scenes cap | Display + tip `Xs / 20s`; Add Scene blocks when remaining &lt; 0.5s; Co-Director `create_scene` max 20s |
| Toolbar | Two rows — Add (± groups) on row 1; Preflight/Generate/mode/Undo/Redo/Zoom/Snap/⚙ on row 2 |
| Tracks height | Tracks pane uses flex fill; `overflow: auto` (was clipped by `overflow: hidden`); board scroll fills remaining height |
| Co-Director | `timeline.propose_add_image_clip`, `timeline.propose_add_prompt_segment`; `propose_add_batch` returns `_uiFocus`; remove/add share persisted Director Timeline (no mocks) |

## Laws

- Law 1: Beta restarted
- Law 5/9: Toolbar ± ↔ ProposalService tools ↔ persistence ↔ UI focus
- Law 7: `mock: False` on new tool results
- Law 18: Shared selection via `_uiFocus` / `adept-timeline-focus`

## Beta

http://127.0.0.1:8760/
