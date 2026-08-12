# MAGI Architecture Audit

**Status:** Read-only Phase 0 audit — evidence-based, no modifications.
**Date:** 2026-08-08
**Milestone:** MAGI Editor Full Operational Audit, Repair & Refinement

## 1. Canonical state model

- **Authoritative sequence schema is defined in the FRONTEND**, not the backend:
  `studio-web/src/magiSequence/types.ts` (`MagiSequenceDocument`, `MagiTrack`, `MagiClip`, `MagiMarker`, `MagiEditCommandKind`). The M4.12 frozen contracts doc (`docs/release-gate/m412-magi/M412_FROZEN_CONTRACTS.md`) names these TS types as the frozen contract.
- **Backend persistence only:** `studio-api/app/magi/sequence/store.py` persists whole-document JSON; it does not own the schema or editing semantics.

## 2. Hierarchy

```
Project
└── Sequence (seq_<uuid>, persisted data/magi/sequences/{project_id}/sequence.json)
    ├── Tracks (trk_<kind>_<uuid>, 12 default; order is index-based)
    ├── Clips (clip_<uuid>, client-generated; trackId + assetId)
    └── Markers (mk_<uuid>)
```

- No server-side "scene" entity. Sequence is project-scoped only.
- Clip IDs are fully **client-owned** (`engine.ts:9-11`). Track IDs are random-per-instance; track identity is effectively index+label.
- **Blueprint duplication:** backend `DEFAULT_TRACKS` (`store.py:11-24`) duplicates frontend `DEFAULT_TRACK_BLUEPRINT` (`types.ts:96-109`); id generators differ between the two empty-sequence builders.

## 3. Backend modules

| Module | Responsibility | Verdict |
|---|---|---|
| `magi/api.py` | HTTP routes (readiness, gates, overlays, sequence) | Thin passthrough; no Pydantic models; raw dict bodies |
| `magi/sequence/store.py` | JSON file persistence | Real but schema-less, no validation |
| `magi/overlays/` | Composition CRUD/validate/fonts | Real, rich validation |
| `magi/composition/` | Deterministic Pillow render + derived asset lineage | Real, production-quality |
| `magi/readiness.py` | Surface honesty payload | Real, honest |
| `magi/production_gate.py` | Wave 4B gate evaluation | Real, artifact-driven |

## 4. Wiring

- Router registered in `main.py:378-382` (soft-fail try/except).
- QueueWorker branch `job.kind == "magi_overlay_compose"` at `queue_worker.py:560-563` — secondary; compose also runs synchronously (`service.py:214`).
- Co-Director: `magi.readiness` health probe (`codirector/status/registry.py:729-740, 938, 962`); **no tools** — `codirector/tools/exposure.py:235` `UNSUPPORTED_SYSTEMS = {"magi"}`.
- Timeline gate cross-ref: `timeline_product/production_gate.py:67` (`timelineMagiIntegrationOperational`).

## 5. Editing operations

- **All NLE editing semantics are client-side** in `studio-web/src/magiSequence/engine.ts` `applyEditCommand()` (Insert/Overwrite/RippleDelete/Trim/Split/Move/Duplicate/Paste/Marker/Transition/Select/Playhead).
- **No server-side editing endpoints exist.** Server is whole-document GET/PUT only.
- Server-side supported ops for overlays: save/get/list/validate/render (real).

## 6. Persistence

- Sequences: `data/magi/sequences/{project_id}/sequence.json`. Manual PUT only; no autosave server-side.
- Overlays: `data/image_product/{project_id}/overlays/` JSON + index. Validated on save.
- Derived overlay outputs: DB `assets` rows + file copies via `generation_tools/lineage.py` (provenance-rich).
- **Real-world data:** 18 `sequence.json` files exist, all `clips=[]` — no clip edit has ever persisted through the real server path.

## 7. Git provenance

- **Zero MAGI commits** in repo history (`git log --all --grep=magi` empty; `git ls-files` returns 0 for all MAGI paths). Entire subsystem is untracked working tree. W4B/W4C "GO" certifications are untracked artifact claims.

## 8. Dead / stale / duplicated

- `MagiContinuityPanel.tsx` — never imported (dead).
- `magiCommandParse.ts` — never imported; workspace inlines its own parser (`MagiEditorWorkspace.tsx:153-245`).
- Overlay-internal undo stack (`useMagiOverlayState.ts:62, 241-248`) — dead code; outer `historyRef` is authoritative.
- Engine ops `Lift/Extract/Slip/Slide/Join/AddTrack/ReorderTrack` — unreachable from UI.
- `test_m42_w4b_magi_command_parse.py` — re-implements a parser inside the test file instead of testing production code.

## 9. Missing tests

- Zero unit tests for `sequence/store.py` or sequence API endpoints.
- The only NLE e2e spec (`m412-magi-editor-nle.spec.ts`) **mocks the backend** via `page.route`, never exercising real persistence.
