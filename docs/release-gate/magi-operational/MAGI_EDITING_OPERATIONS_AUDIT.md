# MAGI Editing Operations Audit

**Status:** Phase 7 operation verification — certification suite green (`magi-operational-integrity.spec.ts` 5/5).
**Date:** 2026-08-08

## 1. Operation inventory (UI → engine)

All real editing ops route through `pushSequenceCommand`/`mutateSequence` → `engine.ts` `applyEditCommand()` or overlay `commit`.

| Operation | UI entry | Engine | Real? |
|---|---|---|---|
| Insert / Overwrite | asset drop (`MagiSequenceTimeline.tsx:187-193`; `MagiEditorWorkspace.tsx:692-712`) | `engine.ts:80-115` | ✅ |
| RippleDelete | Delete/Backspace (`useMagiKeyboard.ts:41-46`) | `engine.ts:117-140` | ✅ |
| Trim (L/R) | trim handle drag (`MagiSequenceTimeline.tsx:271-287`; `handleTrim` 653-674) | `engine.ts:142-169` | ✅ |
| Move (incl. track) | clip drag (`:260-265`; `handleMove` 676-690) | `engine.ts:193-207` | ✅ |
| Split | toolbar ✂ (`:1515`) | `engine.ts:171-191` | ✅ |
| Duplicate | toolbar ⧉ (`:1516`) | `engine.ts:209-232` | ✅ |
| Paste | Ctrl/Cmd+V (`:609-618`) | `engine.ts:209-232` | ✅ |
| AddMarker | toolbar ◆ (`:1517`) | `engine.ts:234-241` | ✅ |
| SetPlayhead / Seek | ruler, transport, keyboard (`:646-651, 585-604`) | `engine.ts:66-69` | ✅ |
| Select / Deselect | clip click + lane empty-click (`:177-180, 255-259`; `handleSelect` 623-644) | `engine.ts:71-78` | ✅ |
| ApplyTransition | "Add Dissolve" proposal (`:797-802`) | `engine.ts:253-264` | ✅ |
| Recipes | recipe cards (`:908-922`) | `mutateSequence` | ✅ (image path) |
| ReplaceClip / Stabilize / Brighten | proposals (`:786-850`) | `mutateSequence` + ad-hoc ids | ⚠️ ad-hoc |
| Overlay add/patch/dup/delete/preset | toolbar + Graphics pane (`:1246-1252, 1046-1095`; `useMagiOverlayState.ts:176-239`) | overlay `commit` | ✅ |

## 2. Engine-supported but NO UI surface (unreachable)

`Lift`, `Extract`, `Slip`, `Slide`, `Join`, `ReorderTrack`, `AddTrack` (`engine.ts:117, 243-251`). No button/gesture invokes them.

## 3. Operation verification (per mission Phase 7)

For each real op, trace `UI action → canonical mutation → persistence → preview update → reload survival → undo/redo`:

- **Mutation:** all route through engine reducer → `setSequence` → `editVersion++` → debounced autosave PUT. ✓ chain exists.
- **Persistence:** real PUT after 500ms; survives reload (once m1 flush fix lands). ✓ with caveat.
- **Preview update:** sequence state change re-renders timeline; viewer reflects `currentAsset` — but NOT playhead-frame (m3 defect). ⚠️
- **Undo/redo:** snapshot stack restores sequence + selection + overlay. ✓ (double-stack cleanup in m1).

### Phase 7 certification evidence (2026-08-08)

`tests/e2e/magi/magi-operational-integrity.spec.ts` — **5/5 PASS** (real backend, harness on 5173/8742):

| Test | Scope | Verdict |
|---|---|---|
| OP-01 | Workspace surface: banner, docks, accordions, render queue, fullscreen distinction, zero console errors / request failures | PASS |
| OP-02 | Clip Properties shows real server-loaded clip data | PASS |
| OP-03 | Real save round-trip bumps server revision | PASS |
| OP-04 | Export to Timeline places clips on the W46 batch and records the ledger | PASS |
| OP-05 | Error taxonomy: structured envelopes, never raw traces | PASS |

Defects fixed to reach green:

1. **Overlay render loop (`useMagiOverlayState.ts`):** the persist-state effect depended on `options`, which the workspace passes as a fresh inline object every render → the effect re-ran on every render and called `setOverlayPersist` → `Maximum update depth exceeded` console storm (masked OP-01's console-error gate). Fixed by reading `options` through `optionsRef` so effect/callback identities are stable (deps now `[isSaving, persistError, savePending]`; `commit` deps now `[projectId, selectedOverlayId]`).
2. **OP-01 request-failure gate:** `net::ERR_ABORTED` on the initial `GET /api/projects/<id>` is an intentional superseded-fetch abort (React StrictMode double-mounts the editor; the second `refresh()` aborts the first in-flight fetch via `AbortController`, per the ROUTING CONTRACT in `ProjectEditor.tsx`). The test now ignores `net::ERR_ABORTED`, matching the app's own `isAbortError` handling; genuine failures still fail the gate.

Pre-existing (out of Phase 7 scope, reproduced with and without the fix): `tests/e2e/m42/magi-editor.spec.ts` "Scenario I/K shell" expects `magi-command` visible, but the Command pane is collapsed under the Default workspace preset — the spec does not expand it. Tracks as a separate M42 surface defect.

## 4. Destructive operation safety (mission Phase 8)

- Delete requires selection; keyboard Delete is gated by focus region (timeline owns focus) per M4.12 focus contract. Undo available via stack. ✓
- **Gaps:** no explicit confirmation for replacing an asset; no "clear sequence" (not present — fine); no track delete UI (not present — documented N/A); destructive trim (trim to zero) not guarded.

## 5. Track model

- 12 default tracks: V1-V3 (video), I1-I2 (image), A1-A3 (audio), T1 (text), FX, M (mask), ADJ (adjustment) (`types.ts:96-109`).
- Deterministic `order`; stable IDs. Rendering order follows `order`.
- **No collision/overlap policy enforced** — clips can overlap on a track silently.
- `AddTrack`/`ReorderTrack` engine support exists but no UI.

## 6. Required repairs (m4)

1. Keep real ops wired; add explicit destructive-safety affordances where missing.
2. Mark unsupported ops (Lift/Extract/Slip/Slide/Join/AddTrack/ReorderTrack) explicitly as **N/A in product scope** — document, do not fabricate UI.
3. Route FX/ADJ ad-hoc clip creation through the engine `uid()` path (id stability).
4. Add overlap/collision policy clarity (or document current behavior) — do not over-engineer.
5. Add regression tests for each real op (move/trim/delete/restore, split, duplicate) asserting IDs stable + media refs intact + undo coherence.
