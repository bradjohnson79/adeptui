# MAGI UI Usability Audit

**Status:** Read-only Phase 0 audit.
**Date:** 2026-08-08

## 1. Layout / panes

- Left dock: project/media/assets/recipes/graphics/actions/command (`MagiLayoutPersistence.ts:60-68`). Right dock: inspector. Center: viewer + timeline stack. Bottom: render queue.
- **Resizable:** left/right dock splitters (pointer drag `:924-942`; arrow keys `:1496-1499, 1550-1553`); viewer/timeline height divider via `TimelineWorkspaceStack` (`:416-436`) with project-scoped ratio persistence.
- **Movable/reorderable:** `paneMenu` arrows (`:944-959`) → `movePane`/`reorderPane` (`MagiWorkspaceLayoutProvider.tsx:135-160`).
- **Presets:** Default / Viewer Focus / Assembly / Mask Finishing / Compare Review / Custom (`:1439-1451`; `applyPreset` in MagiLayoutPersistence.ts:217-281).
- **Persistence:** localStorage `adept_magi_workspace_layout_v1` (`MagiLayoutPersistence.ts:38`), load/validate/migrate (`:152-207`), auto-persist (`:43-46, 92-94`).
- Responsive compaction <900/<1100/<1440px (`MagiWorkspaceLayoutProvider.tsx:72-84`).

## 2. Banner / header

- `.magi-strip` lava/glow animated banner `role="banner"` with copy "MAGI Editor: assemble, finish, and protect timing…" (`:1421-1427`; CSS `magi-editor.css:25-70`).
- Workspace bar `.magi-workspace-bar`: layout preset select, dock toggles, reset, save-state status (`:1429-1465`).

## 3. Inspector

- Right dock `inspector`, `data-testid="magi-inspector"` (`:1311-1403`).
- Header shows `currentAsset` name (`:1315`); Transform section shows `selectedClip?.name` (`:1338`); when overlay selected renders `MagiOverlayInspector` (`:1317-1326`) — substantive (text/typography/background/shape/transform; Animation flagged preview-only `:303-331`).
- **Non-overlay sections largely decorative:** Playhead/Selection read-only (`:1329-1339`); "Color → Look note" unbound text input (`:1341-1346`); "Prompt" textarea wired to `command` state (`:1350`); Lighting/Effects/Audio/AI Assist are proposal buttons (`:1353-1401`).

## 4. Confirmed UX defects

1. **No stale-selection-after-delete guard:** after deleting a clip, `selectedClip` may reference a removed entity; inspector can show stale entity until state clears.
2. **Overlay double-history** means undo/redo UX can desync between sequence and overlay if the two stacks diverge.
3. **Crowded header:** many toolbar controls inline; secondary clip controls not grouped into drawers/accordions (only overlay inspector uses `MagiAccordion`).
4. **Banner clipping risk:** artwork may be cut off; strip height cramped (mission: ~2×, `object-fit`, less text).
5. **Unreachable ops** (Lift/Extract/etc.) have no honest "not supported" affordance.
6. **Stubbed features visible as interactive:** Mask canvas no-op, shuttle no-op, Histogram/Vectorscope disabled — should be clearly labelled or hidden.

## 5. Mission UX goals (m7)

- Professional-editor feel: LEFT media/tools; CENTER viewer+edit; BOTTOM timeline; RIGHT inspector. ✓ current structure aligns — refine, don't redesign.
- Movable/resizable panes preserved; layout persisted; reset action available.
- Accordion/drawer grouping for secondary controls (Transform/Audio/Transitions/Effects/Clip Props/Export); keep high-frequency ops one-click.
- Banner ~2× height with fitted artwork, less text; editor workspace visually dominant.

## 6. Required repairs (m7)

1. Inspector: clear selection on delete; guarantee correspondence to authoritative selection; add track properties when a track is selected.
2. Group secondary controls into accordions; keep transport + core ops accessible.
3. Banner height ~2×, `object-fit` for artwork, trim copy.
4. Honest labels for stubbed/supported surfaces; document N/A ops.
5. Preserve layout presets + reset; regression test pane resize + persistence.
