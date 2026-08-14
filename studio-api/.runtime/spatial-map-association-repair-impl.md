# Spatial Map Association UX Repair — Implementation

**Date:** 2026-08-14 2:56 PM PT
**Mode:** Smallest UX/label repair. No attach-contract rewrite. No Character Creator edits. No commit/push/deploy. `:8758` not bounced.
**Repo:** `C:\AdeptFilmWorks\AIVideoStudio`
**Live:** UI `http://127.0.0.1:8760` · API `:8758`
**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`
**Map:** `6bc36d92-d21a-4c2f-b85f-71d1f6aa9081`

---

## What changed

Root cause was unlabeled mutually exclusive placement-arm (`beginPlacement`, one `placementMode`). Prop 1 ON un-armed Character 1 and stole the generic ACTIVE badge without hiding Korri or clearing attach. Users read that as they cannot coexist.

This pass splits the three concepts in the existing UI:

- **Placement Active** — card switch + Placement Active label + PLACEMENT ACTIVE badge when armed. In-memory placementMode only. One armed entity. Unchanged XOR.
- **Visible** — existing Visible button. Persisted visible PATCH. Independent of the switch.
- **Association** — More opens existing PropAttachmentEditor and calls handleApplyAttachment / handleDetachAndPlace. Frozen attach fields on the same prop row. No second store.

---

## Files changed

Source:

1. `studio-web/src/components/CoDirector/SpatialMap/PlacementSlot.tsx` — switch labeled Placement Active; badge PLACEMENT ACTIVE only when armed; generic ACTIVE removed (selection stays is-active border); Visible kept independent; More expands Association via PropAttachmentEditor plus note.
2. `studio-web/src/components/CoDirector/SpatialMap/SpatialMapPanel.tsx` — Prop More wired to existing handleApplyAttachment / handleDetachAndPlace; camera slots share Placement Active label + PLACEMENT ACTIVE badge.
3. `studio-web/src/components/CoDirector/SpatialMap/spatialMap.css` — Placement Active label / arm / badge styles only. Aurora tokens (--accent #2dd4bf, --muted).
4. `studio-web/src/components/CoDirector/SpatialMap/placementArm.ts` (new) — copy constants + in-memory arm helper. Arm replace does not write visible or attach fields.
5. `studio-web/src/components/CoDirector/SpatialMap/placementArm.test.ts` (new) — switch is placement-arm not visibility; arming a prop does not set character visible=false; association survives placement-arm change.

Generated: `studio-web/dist/` rebuilt (vite build). :8760 serves index-B0JfCgXs.js + index-C7Too6oe.css.

This note: `studio-api/.runtime/spatial-map-association-repair-impl.md`

Not edited: attach enum / XOR / routes / follow-on-move / SpatialGrid XOR / ERS / CharacterInspector / leftover slotIndex matcher / Co-Director / Character Creator / PropAttachmentEditor.tsx / attachmentUi.ts / types.ts / schemas.py / attachment.py.

---

## Exact visible labels

- Switch label (character / prop / camera): Placement Active
- Switch aria (assigned, not attached): {slot} Placement Active on / {slot} Placement Active off
- Switch aria (attached prop): {slot} is attached (switch still disabled)
- Badge when this slot is armed: PLACEMENT ACTIVE
- Badge when this slot is not armed: omitted (does not say OFF / hidden / generic ACTIVE)
- Visibility control: Visible (unchanged, independent)
- More toggle: More / Hide
- More association heading: Association
- Association editor: Character / Relationship / Attachment / Cancel / Apply (existing PropAttachmentEditor)
- More detach: Detach & Place
- Card attach shortcuts kept: Attach to Character / Edit / Detach & Place

Relationship dropdown still uses the frozen enum labels: Held, Carried, Worn, Using, Interacting, Associated. Not held_by / on / near / used_by.

---

## Live Coffee Cup visible restore

Yes. Restored. Not detached. Coords not rewritten.

PATCH /api/spatial-map/projects/2347bf46-.../maps/6bc36d92-.../props/61cd9b72-f832-4668-b187-38e58cb3d383
body { visible: true } via the existing update API (moveProp / update_prop).

Before GET v74 2:50 PM PT: visible=false, attached, held, right_hand, coords null, grid -1.
After PATCH v75 2:55:32 PM PT: visible=true. Attach fields unchanged. x/y/z null. normalizedX/Y null. gridRow/Column -1. Korri still visible=true at grid 8/9.

Korri P1 badge can show again (visibleAttachedPropsForCharacter / attachedBadgeFor). :8758 stayed up (GET 200 after the PATCH).

---

## Tests

npx vitest run placementArm.test.ts attachmentUi.test.ts types.test.ts SpatialGrid.test.ts
Test Files  4 passed (4)
Tests       30 passed (30)

New placementArm.test.ts:
1. Switch copy is Placement Active; badge only when armed.
2. Replacing the arm (Korri to cup) does not set character visible=false.
3. Cup attached / held / right_hand survives the arm change.

Existing attach / grid / types tests kept and still pass. No Playwright.

## 8760 bundle

- vite build succeeded in 1.57s at 2:56 PM PT.
- Served files: dist/assets/index-B0JfCgXs.js and index-C7Too6oe.css.
- GET 127.0.0.1:8760 200 references the new JS. Bundle contains Placement Active, PLACEMENT ACTIVE, Association.
- tsc -b still fails on pre-existing SetupWizard.tsx TS2345 (unrelated). Spatial Map typechecks clean.
- 8758 was not bounced.

## Leftovers (intentionally not in this pass)

- tags[] in More: placements have a single tag str (cup #coffeecup; Korri empty). No tags[] field. Not added.
- Extra relationships on/near/used_by/held_by/attached_to: frozen enum is held|carried|worn|using|interacting|associated. Not migrated.
- Co-Director attach write: consume-only. No spatial.attach_prop. Summary omits holding prose. Not added.
- Prop-to-prop / circular graphs: schema is prop to character only.
- Auto-arm Character 1 on load still happens; now labeled PLACEMENT ACTIVE.
- Card-level Attach/Edit kept as shortcuts. More is the Association home. Same attach API.
- Generic ACTIVE for card selection removed. Selection is the is-active border only.

Smallest repair. Attach contract frozen. Character Creator untouched. No commit/push/deploy.
