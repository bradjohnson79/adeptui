# MAGI m1 + m5 — Architectural Checkpoint

**Status:** Checkpoint evidence — MAGI Next Execution Pass (Phase A: m1 state/persistence/undo-redo; Phase B: m5 W46 Timeline handoff; Phase C: regression; Phase D: this report).
**Date:** 2026-08-08
**Governance:** Law 30 (one governing doc per milestone), Law 31 (evidence before completion), Law 26 (GPU designation — N/A; this pass is CPU state/interop work).

## 1. Result

**m1 (canonical state/persistence/undo-redo): GO**
**m5 (MAGI ↔ W46 Timeline handoff): GO**
**Overall:** `READY FOR M5→M6 REVIEW`. **PAUSE before any m6 Co-Director changes** (out of scope).

## 2. Deliverables — Phase A (m1)

| Item | Change | Evidence |
| ---- | ------ | -------- |
| A1 | Save-boundary canonical validation: `PUT /sequence` parses the full `MagiSequenceModel`; schema-invalid payloads → structured `validation_failed` 422 (no silent `setdefault`-persist of garbage). `parse_sequence`/`MagiSequenceModel` already canonical; PUT handler now the single validation gate. | `test_put_sequence_rejects_malformed_document`, `test_save_sequence_rejects_invalid_schema`, `test_save_sequence_rejects_negative_playhead` |
| A2 | GET read-only regression: repeated GET returns byte-identical doc (same revision/`updatedAt`); no file creation on read. | `test_get_sequence_does_not_persist_on_read`, `test_get_sequence_returns_empty_for_missing_file_without_side_effect`, `test_get_sequence_returns_identical_document_on_repeated_read` |
| A3 | Optimistic concurrency: optional `expectedRevision` on PUT; mismatch → structured `revision_conflict` 409 with current/expected, server doc untouched. Omission keeps backward-compatible last-writer-wins. Frontend sends last-known revision and surfaces `MagiSaveConflictError`. | `test_put_sequence_expected_revision_mismatch_is_409`, `..._match_succeeds`, `..._omitted_is_backward_compatible`, `..._malformed_is_422`; `studio-web/src/magiSequence/api.ts` |
| A4 | Asset ownership structured codes: `ASSET_NOT_FOUND`(400) / `ASSET_PROJECT_MISMATCH`(400) / `INVALID_CLIP_ASSET`(422) replacing the single `asset_ownership` code for sequence PUT. | `test_put_sequence_rejects_unknown_asset`, `test_put_sequence_rejects_cross_project_asset`, `test_put_sequence_rejects_clip_without_asset` |
| A5 | Overlay flush on unmount/`beforeunload`/`pagehide`/`visibilitychange` via single flush path (sequence + overlay store); debounce timers each cleared before flush; save-state honesty (`saving`/`saved`/`error` surfaced). Seek/scrub never marks dirty (locked in A6 engine tests). | `MagiEditorWorkspace.tsx` flush effect + `overlayPersistNowRef`/`overlayDirtyRef` |
| A6 | Undo/redo integrity: engine vitest (Move/Duplicate/Split/Delete/AddMarker/SetPlayhead/Trim preserve lineage fields + unique ids); `MagiEditorCommandStack` vitest (push/undo/redo/cap-100/800ms text coalescing/no-coalesce outside window). Dead overlay-internal undo/redo confirmed removed (single `historyRef`). | `src/magiSequence/engine.test.ts`, `src/components/magi/overlays/MagiEditorCommandStack.test.ts` |
| A7 | Backend save→reload certification: PUT full doc (real clips incl. lineage, playhead, markers) → GET reconstructs identical document. | `test_save_reload_roundtrip_preserves_full_document` |

## 3. Deliverables — Phase B (m5)

| Item | Change | Evidence |
| ---- | ------ | -------- |
| B1 | Implementation audit written FIRST (governing doc; supersedes `MAGI_TIMELINE_INTEROP_AUDIT.md` on conflict per Law 30). | `docs/release-gate/magi-operational/MAGI_TIMELINE_HANDOFF_IMPLEMENTATION_AUDIT.md` |
| B2 | Import lineage flattened: `import_timeline_asset` returns FLAT `batchBlockId`/`generationId`/`takeId`/`sourceClipId`/`sceneId` (matches `MagiClipModel` + `MagiClip`); nested `lineage` object removed. | `test_timeline_import_accepts_owned_asset` (asserts `"lineage" not in clip`) |
| B3 | Export: existing-batch export REQUIRES explicit `batchBlockId` (probe → single structured `BATCH_NOT_FOUND`, no `batches[0]` fallback); new-batch export via `add_batch` + `add_clip_to_batch`; `BATCH_NOT_FOUND`/`SCENE_NOT_FOUND` → 404; MAGI-side `sequence.json.exportLedger` keyed by `batchBlockId` (no revision bump). | `test_timeline_export_to_existing_batch_requires_explicit_batch_block_id`, `test_timeline_export_new_batch_records_ledger_and_survives_reload`, `test_timeline_export_to_existing_batch_places_and_ledgers` |
| B4 | No generation-history mutation on export: source clip lineage untouched. | `test_timeline_export_does_not_mutate_generation_history` |
| B5 | UI handoff: "Send to Timeline" button in MAGI Actions pane → `api.magi.exportToTimeline` (first scene, all clips). | `MagiEditorWorkspace.tsx` `handleExportToTimeline` |
| B6 | Handoff integration suite (import / existing-batch / new-batch / cross-project / missing-batch / ledger reload). | see B2–B4 rows + `test_timeline_import_rejects_foreign_asset`, `test_timeline_import_missing_asset_id`, `test_timeline_export_places_clips_on_w46_batch`, `test_timeline_export_requires_clips`, `test_timeline_export_rejects_foreign_asset` |

## 4. Regression (Phase C)

- Backend: `studio-api` pytest — **97/97 pass** in the relevant MAGI/W46/Timeline/Project/Scene suite. MAGI suite itself **27/27 pass**.
- Frontend: `tsc -b` clean; `oxlint` clean on all modified files; vitest **25/25** across engine + command stack + pre-existing workspaces tests; full suite 93 tests pass (13 pre-existing untracked files report "No test suite found" — unrelated to this pass).
- Known pre-existing (NOT caused by this pass): `test_closed_loop_m2_6_1.py::test_flow_e_pending_cleared_only_by_vision` fails in the WIP snapshot; references no MAGI code. Documented for the m5→m6 review, not fixed here (out of scope, would require Co-Director changes → PAUSE gate).

## 5. Invariants honored

- GET is read-only (A2 regression-locked).
- Revision is server-authoritative; conflicts are surfaced, never silently overwritten (A3).
- No legacy `project.settings_json["timeline"]` writes; W46 contract frozen; `mock:False` on all handoff results (B).
- Source generation history never mutated (B4).
- W46 Timeline certification preserved (all mutations via `director_timeline_w46` orchestration).

## 6. Files changed

- `studio-api/app/magi/sequence/validation.py`, `store.py`
- `studio-api/app/magi/api.py`, `timeline_handoff.py`
- `studio-api/tests/test_magi_sequence_repairs.py`
- `studio-web/src/magiSequence/api.ts`, `types.ts`, `engine.ts`
- `studio-web/src/components/magi/MagiEditorWorkspace.tsx`
- `studio-web/src/api.ts`
- `studio-web/src/magiSequence/engine.test.ts` (new), `studio-web/src/components/magi/overlays/MagiEditorCommandStack.test.ts` (new)
- `docs/release-gate/magi-operational/MAGI_TIMELINE_HANDOFF_IMPLEMENTATION_AUDIT.md` (new)

## 7. Binary gate

| Gate | Status |
| ---- | ------ |
| m1 canonical state/persistence/undo-redo | **GO** |
| m5 MAGI ↔ W46 Timeline handoff | **GO** |
| Product Law (#29) — all actions inside Adept UI | **GO** (handoff routed through MAGI API, no runtime ops) |
| MiniMax Timeline Re-take gate | Not in scope this pass (unchanged) |
| m6 Co-Director changes | **PAUSED** — do not begin without review |
