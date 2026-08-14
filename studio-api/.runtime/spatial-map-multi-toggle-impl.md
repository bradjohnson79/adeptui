# Spatial Map MULTI-TOGGLE STATE REPAIR — Implementation

**Date:** 2026-08-14 3:07 PM PT
**Mode:** Unbind card switch from exclusive `beginPlacement`. No attach-contract rewrite. No Character Creator edits. No commit/push/deploy. `:8758` not bounced.
**Repo:** `C:\AdeptFilmWorks\AIVideoStudio`
**Live:** UI `http://127.0.0.1:8760` · API `:8758` (GET 200 after rebuild)
**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`
**Map:** `6bc36d92-d21a-4c2f-b85f-71d1f6aa9081`

---

## What changed

Prior label pass still wired the card `role="switch"` to `beginPlacement` / one `placementMode`. Korri ON → Coffee Cup ON → Korri switch OFF (and C1 ON → C2 ON → C1 OFF) because the switch was a cross-category radio.

This pass unbinds the switch from placement-arm:

- **Enabled / Visible (many):** card switch is independent per entity. ON = persisted `visible !== false`. OFF = only that entity hidden / not participating. Coordinates, FOV, associations, and tags are kept.
- **Placement target (one):** Place / Move / card click / map-click still set `placementMode` / selected id via `beginPlacement`. Changing the target does **not** flip other switches.
- **Badge:** `PLACEMENT ACTIVE` only on the current placement target. Unarmed enabled entities stay ON with no OFF/hidden implication.
- **Aria:** enablement (`{slot} enabled` / `{slot} disabled`), not placement-arm.

---

## Exact switch semantics

| Control | Meaning | Persist | Cardinality |
| --- | --- | --- | --- |
| Card `role="switch"` | Enablement. `aria-checked` / `is-on` = `visible !== false` (default true). Click calls existing `handleToggleVisible` → PATCH `{ visible }`. | Yes, existing update/visible API | Many |
| Visible button | Same field (`visible`). Left in place; not a second store. | Same PATCH | Many |
| Place / Move | `beginPlacement("place"\|"move", kind, id, label, index)` | In-memory `placementMode` only | One |
| Card click / camera card click | Independent assigned entity → `beginPlacement`. Attached prop → select card only (no independent place). Empty slot → `setActiveSlot`. | In-memory | One |
| Map cell click | Places/moves the current `placementMode` target. Unchanged. | Coords via existing update | One target |
| Badge | `PLACEMENT ACTIVE` iff this entity is `placementMode` | No | One |
| Association | Unchanged attach contract. Switch / select / C1↔C2 do not write attach fields. | Same row | Many |

Switch OFF does **not** clear coords, FOV, `held` / `right_hand`, `tag`, or `placementMode` (attach). Attached props can now use the switch (it is no longer disabled when attached).

---

## How Place / Move sets the target

Unchanged `beginPlacement` in `SpatialMapPanel.tsx`:

1. `setPlacementMode({ action, kind, id, label })` — singular arm.
2. `setActiveSlot({ kind, index })`.
3. Selects that placement / camera.

Callers:

- **Place** button → `beginPlacement("place", ...)`
- **Move** button → `beginPlacement("move", ...)`
- **Card click** (independent assigned character/prop/camera) → `beginPlacement(placed ? "move" : "place", ...)`
- **Map click** uses current `placementMode`; does not change other switches.
- **Detach & Place** still detaches then `beginPlacement("place", "prop", ...)`.
- Auto-arm on first load still arms Character 1 (or first unplaced character). That only sets the badge / placement target. Other enabled switches stay ON.

The switch no longer calls `beginPlacement` or `clearPlacementMode`.

---

## Files changed

Source:

1. `studio-web/src/components/CoDirector/SpatialMap/placementArm.ts` — enablement helpers (`isEntityEnabled`, `toggleEntityEnabled`, `setPlacementTarget`, `fovLayersForCameras`, `hydrateEnabledFromDocument`). Switch copy is **Enabled**. Badge still `PLACEMENT ACTIVE` for the singular target.
2. `studio-web/src/components/CoDirector/SpatialMap/placementArm.test.ts` — scenarios A–F plus aria, association-survive, legacy hydrate.
3. `studio-web/src/components/CoDirector/SpatialMap/PlacementSlot.tsx` — switch bound to `visible` / `onToggleVisible`. `onToggleOff` removed. Attached no longer disables the switch. Badge still only when `placing`.
4. `studio-web/src/components/CoDirector/SpatialMap/SpatialMapPanel.tsx` — character/prop `onToggleOff={clearPlacementMode}` removed. Camera switch bound to `handleToggleVisible`. Place/Move/card click still `beginPlacement`.
5. `studio-web/src/components/CoDirector/SpatialMap/SpatialGrid.test.ts` — multi-camera FOV is not selection-filtered.

Generated: `studio-web/dist/` rebuilt (`npx vite build`). :8760 serves `index-CZim3lHZ.js` + `index-D-psiwgb.css`.

This note: `studio-api/.runtime/spatial-map-multi-toggle-impl.md`

Not edited: Character Creator (any path). Attach enum / XOR / routes / follow-on-move / `SpatialGrid.tsx` renderer / ERS / `CharacterInspector` / `PropAttachmentEditor.tsx` / `attachmentUi.ts` / `types.ts` / `schemas.py` / `attachment.py`. Grid-circle placement, attach XOR, ERS, zoom untouched.

---

## Tests

```
npx vitest run placementArm.test.ts attachmentUi.test.ts types.test.ts SpatialGrid.test.ts
Test Files  4 passed (4)
Tests       37 passed (37)
```

Ran 3:05 PM PT. No Playwright.

New / updated assertions:

- A multi character: turning C2 ON does not turn C1 off.
- B multi prop: turning Prop 1 ON does not set Character 1 switch off.
- C multi camera: turning C2 ON does not turn C1 off; both FOV layers stay visible. Selection is not a filter.
- D mixed: select cup for place — Korri switch stays ON; Held By / right_hand / `#coffeecup` survive.
- E individual off: Korri OFF hides only Korri; coords + cup association + camera FOV stay.
- F selection independence: Place/Move/select changes target only; no switch flips.
- Aria is enablement (`enabled` / `disabled`), not Placement Active.
- Legacy: missing `visible` hydrates as enabled; coords not cleared.

Existing attach / grid / types tests kept and still pass.

---

## 8760 bundle

- `npx vite build` succeeded in 1.55s at 3:06 PM PT.
- Served files: `dist/assets/index-CZim3lHZ.js` and `index-D-psiwgb.css`.
- GET `127.0.0.1:8760` 200 references the new JS.
- Bundle: `Placement Active` = 0, `PLACEMENT ACTIVE` = 1, `enablement unavailable` = 1, `enabled-label` = 2.
- `:8758` GET `/docs` 200 after rebuild. Not bounced.

---

## Leftover: enabled vs visible

**Collapsed to one field: `visible`.**

There is no persisted `enabled` on character / prop / camera rows (schemas + `types.ts` only have `visible?: boolean`, default true). The switch and the existing Visible button both write that field via `handleToggleVisible` → `updateCharacter` / `updateProp` / `updateCamera({ visible })`. No second store.

Reload restores which entities were ON because `visible` is already in `document_json`.

The Visible button is leftover UI for the same field. Not removed (existing `*-visible-*` testids stay). Product can drop it later; do not add an `enabled` column.

---

## Legacy

Maps that previously had one placement-active entity still load. `placementMode` was always in-memory; persisted state is `visible` + coords + attach fields. Auto-arm may badge Character 1 as `PLACEMENT ACTIVE` on first load. That does not turn other switches OFF and does not clear coords.

---

Smallest repair. Attach contract frozen. Character Creator untouched. No commit/push/deploy.
