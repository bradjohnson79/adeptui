# MAGI State & Persistence Audit

**Status:** Read-only Phase 0 audit.
**Date:** 2026-08-08

## 1. State ownership

- **Canonical sequence state:** `MagiEditorInner` in `MagiEditorWorkspace.tsx:281-312` via React `useState` (`sequence`, `selection`, `viewerAssetId`, `compareAssetId`, `playing`, `command`, `editVersion`, `lastSavedEditVersion`, `saveState`, `saveError`, `serverRevision`).
- **No external state library** (no zustand/redux/jotai).
- **Pure reducer:** `engine.ts` `applyEditCommand()` — functional, immutable, stateless. Invoked via `pushSequenceCommand` (`MagiEditorWorkspace.tsx:462-482`) and `mutateSequence` (484-505).
- **Mirror refs** for async handlers: `sequenceRef/selectionRef/viewerAssetRef/...` (`:302-312`, refreshed `:333-340`).
- **Overlay store:** `useMagiOverlayState` owns composition state separately.

## 2. Competing stores / drift

1. **Double history stacks:** overlay edits pushed to both overlay-internal `stackRef` (`useMagiOverlayState.ts:62, 148`) and workspace `historyRef` (`MagiEditorWorkspace.tsx:301, 315-329`). Inner stack is dead code; grows unbounded.
2. **Track blueprint duplicated:** backend `store.py:11-24` vs frontend `types.ts:96-109`.
3. **Empty-sequence builders duplicated:** backend `empty_sequence` (`store.py:41-64`) vs frontend `createEmptySequence` (`engine.ts:17-38`) with different ID formats and defaults.
4. **`revision` double-owned:** server recomputes `current+1` (`store.py:86`); frontend bumps locally (`engine.ts:40-47`). Server value silently wins on every PUT.

## 3. Persistence paths

### Server
- `GET /api/magi/projects/{pid}/sequence` → `get_sequence` (`store.py:67-78`): **GET has a write side-effect** — creates + saves an empty sequence on missing file (lines 70-72); corrupt JSON silently reset (line 75). Reads byte-for-byte otherwise (reload-faithful).
- `PUT .../sequence` → `save_sequence` (`store.py:81-97`): whole-doc replace; forces `projectId`/`revision`/`updatedAt`; `setdefault` fills gaps; **no clip/asset validation**.

### Client
- Sequence autosave: debounced 500ms (`MagiEditorWorkspace.tsx:429-436`) → `saveSequence()` (524-545) → PUT. Stale-save guard via nonce (`saveNonceRef`, `:528`) and `capturedEditVersion` (`:527, 534-537`).
- Overlay autosave: debounced 400ms (`useMagiOverlayState.ts:101-113`) + in `commit` (158-169).
- Manual Save button → `saveAll()` = saveSequence + overlay persistNow (`:547-550`).

## 4. Dirty tracking

- `sequenceDirty = editVersion !== lastSavedEditVersion` (`:381`); `editorDirty = sequenceDirty || overlayPersist.dirty` (`:382`). Badges: `Draft`/`Certified` (`:1245, 1462-1463`).

## 5. Confirmed defects

### P1 — Lost save on unmount
Sequence debounce timer cleared without flush (`:432-435`); navigating away within the 500ms window silently drops the pending PUT. **No `beforeunload`/`pagehide`/`visibilitychange` guard anywhere in `components/magi/**`.**
Overlay `saveTimer` has **no cleanup** (`useMagiOverlayState.ts:101-113, 158-169`) — debounced PUT fires after unmount.

### P1 — Every seek dirties the document
`pushSequenceCommand` bumps `editVersion` for every command including `SetPlayhead` (`:479`). Ruler click, frame-step, Home/End, J/L jog all mark dirty and trigger autosave. (Playback interval writes `playheadFrame` directly at `:442-446`, bypassing this.)

### P2 — GET writes on read
Server `get_sequence` persists an empty doc on GET when missing — violates read-idempotency expectations.

### P2 — Revision conflict source
Server silently overwrites client revision. No conflict detection; last-writer-wins.

### P2 — No server-side validation
Corrupt/schema-invalid payloads are `setdefault`-filled and persisted; no rejection.

## 6. Undo / redo

- **Outer stack:** `MagiEditorCommandStack` (`overlays/MagiEditorCommandStack.ts:8-58`), snapshot-based, cap 100, 800ms text coalescing. History snapshot includes sequence/selection/viewer/overlay (`MagiEditorWorkspace.tsx:58-66`), captured via `structuredClone` (`:362-379`).
- Triggered by Ctrl/Cmd+Z, Shift+Z (`useMagiKeyboard.ts:100-105`); toolbar buttons (`:1185-1190`).
- **Overlay-internal undo/redo (`useMagiOverlayState.ts:241-248`) is dead code** and never surfaced.

## 7. Reload behavior

- Load on mount (`:395-427`); failure → fresh `createEmptySequence` fallback + message (`:418-421`). `serverRevision` tracked separately (`:297, 412`).
- Reload reconstructs same state from persisted JSON (verified on-disk) — but never proven against real clip data since all persisted sequences are empty.

## 8. Required repairs (m1)

1. Remove GET-write side-effect (GET returns without persisting).
2. Add Pydantic models + validation on PUT (m2 extends with asset ownership).
3. Flush pending autosave on unmount/route-change/`beforeunload`/`pagehide`; clear overlay save timer.
4. Dedupe history stacks — remove dead overlay-internal `stackRef`; keep single `historyRef`.
5. `SetPlayhead`/scrub must not bump `editVersion` (separate "transport changed" signal).
6. Backward-compatible `setdefault` migration for existing empty sequence files.
