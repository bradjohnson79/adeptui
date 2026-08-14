# Spatial Map Character/Prop Association Repair — Architecture Audit

**Date:** 2026-08-14 2:50 PM PT  
**Mode:** READ-ONLY. No source edits, no commit/push/deploy, no API bounce, no Character Creator edits. Live calls were GET only.  
**Repo:** `C:\AdeptFilmWorks\AIVideoStudio`  
**Live:** UI `http://127.0.0.1:8760` · API `:8758` and `:8761` (same document after refresh)  
**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`  
**Map:** `6bc36d92-d21a-4c2f-b85f-71d1f6aa9081`

**Verdict: READY TO IMPLEMENT**

Constraint: smallest UX/label repair + More-section association on the **existing** attach contract. Do **not** create a second store. Do **not** rename frozen relationship values. Do **not** rewrite XOR, attach/detach routes, ERS projection, or Character Creator.

---

## Executive return

### READY TO IMPLEMENT | NOT READY

**READY TO IMPLEMENT** for the three-concept split (Placement Active / Visible / Association) on the existing attach contract.

Not in this repair: renaming `held` → `held_by`, prop-to-prop, circular graphs, or a new Co-Director attach write tool. Those are contract amendments, not the Coffee Cup / Korri defect.

### Root cause (one sentence)

The card `role="switch"` is a **mutually exclusive placement-arm** (`beginPlacement` / one `placementMode` at a time), so turning Prop 1 ON un-arms Character 1’s switch (and selecting the Prop 1 card also steals the ACTIVE badge) **without hiding Korri or breaking the attach record** — users read that as “they cannot coexist.”

### Current three-concept map

| Concept | Exists today? | What it actually is | Missing vs this mission |
| --- | --- | --- | --- |
| **Placement Active** | Partial | Single in-memory `placementMode` `{action, kind, id, label}`. Switch `is-on` iff this entity is armed. `beginPlacement` replaces the previous arm. Escape / toggle-off calls `clearPlacementMode`. | No visible “Placement Active” label. Switch looks like presence/power. Auto-arm on load turns Character 1 ON first. |
| **Visible** | **Exists** | Separate **Visible** button on the card. Persisted `visible: bool` (default true). `handleToggleVisible` PATCHes the placement. Marker CSS `spatial-map__marker--hidden` / `data-visible`. Hide ≠ delete, hide ≠ un-arm, hide ≠ detach. | Independence already works. Do not rewrite. Switch must stop being confused with this. |
| **Association** | **Exists** | Frozen attach fields on the **same** `SpatialPropPlacement` row: `placementMode` independent\|attached, `attachedCharacterSlot` 1–4, `attachedCharacterId`, `relationship`, `attachmentPoint`. UI: card **Attach to Character** / **Edit** / **Detach & Place**, `PropAttachmentEditor`, `CharacterInspector`. Writes go through `/attach`, `/detach`, `/relationship`. | Not in **More** (More is mini-prompt only). No “Held By” control that bypasses the attach API. No prop-to-prop. Requested relationship names do not match the frozen enum. |

---

## 1. Slot toggle semantics (from current source)

File: `studio-web/src/components/CoDirector/SpatialMap/PlacementSlot.tsx`  
Wired in: `SpatialMapPanel.tsx`

The head-row control is `role="switch"` with `data-testid="{kind}-online-{index}"`.

- `aria-checked` / `is-on` = `placing` (parent: `placementMode?.kind === kind && placementMode.id === placement.id`).
- `aria-label` = `"{slot} placement on|off"` — **placement**, not visibility.
- Disabled when unassigned **or attached** (`aria-label` becomes `"{slot} is attached"`).
- Click when ON → `onToggleOff` → `clearPlacementMode()` (sets `placementMode` to `null` only).
- Click when OFF → `onSelect()` (not `onPlace` directly).

`onSelect` for an **independent** assigned character/prop:

```
beginPlacement(placed ? "move" : "place", kind, id, label, slot.index)
```

`beginPlacement` (panel ~597–608):

1. `setPlacementMode({ action, kind, id, label })` — **one** armed entity.
2. `setActiveSlot({ kind, index })`.
3. Selects that placement / camera.

So **Prop 1 switch ON** (independent cup):

- Arms the cup for place/move.
- **Clears Korri’s placing flag** (her switch goes OFF).
- Does **not** set `visible=false` on Korri.
- Does **not** detach or hide Korri’s marker.
- Does **not** write association.

**Attached cup (live Schnick state):** the Prop 1 switch is **disabled**. Clicking it is a no-op. “Activating Prop 1” then cannot be the switch; it is either the card (ACTIVE badge moves) or **Visible**.

Camera cards use the same switch: ON → `clearPlacementMode`, OFF → `beginPlacement`. Same XOR.

There is also an **ACTIVE** badge (`active && isAssigned`) meaning “this card is the selected slot,” which is a **third** visual, not placement and not visibility. Selecting the Prop 1 card (`onSelect` on an attached prop) sets `activeSlot` to prop and **does not** clear `placementMode`. Korri can stay armed while losing the ACTIVE badge.

Auto-arm (`SpatialMapPanel.tsx` ~667–688): first load arms Character 1 (or the first unplaced character). Korri’s switch starts ON, so the first Prop 1 arm looks like “turning Korri off.”

---

## 2. Visible control

**Yes, separate, already shipped.**

- Button label **Visible** on assigned character/prop cards (`data-testid="{kind}-visible-{index}"`).
- Camera has the same control.
- Optimistic local update + `spatialMapApi.updateCharacter|updateProp|updateCamera({ visible })`.
- Schema: `visible: bool = True` — “false hides marker only; assignment and coords stay” (`schemas.py`).
- Grid: `hidden = visible === false` → `spatial-map__marker--hidden`. Placement stays in `toGridPlacements` (hide ≠ delete). `SpatialGrid.test.ts` asserts this.

**Turning placement off does not hide the marker.** `clearPlacementMode` only nulls the in-memory arm. Markers follow `visible` + coords (or, if attached, the host badge).

Attached + `visible=false` (live Coffee Cup): relationship **persists**; P1 badge / tooltip **omit** the hidden prop (`visibleAttachedPropsForCharacter`, `attachedBadgeFor`). Test already exists: `attachmentUi.test.ts` “hidden attached prop stays related but is omitted from badge/tooltip.”

That is a second way the defect *looks* true: hiding the cup removes Korri’s P1 badge even though attach is intact.

---

## 3. Association UI

| Surface | Association? |
| --- | --- |
| Card switch | No (placement arm). Disabled when attached. |
| Card **Visible** | No. |
| Card **Attach to Character** | Yes — opens `PropAttachmentEditor`. Independent props only. |
| Card **Edit** / **Detach & Place** | Yes — attached props. |
| **More** | **No.** Expands a mini-prompt textarea + Save. Label is “More” / “Hide note.” |
| `PropAttachmentEditor` | Yes — Character, Relationship, Attachment Point, Apply. |
| `CharacterInspector` | Yes — attached list, Edit, Detach & Place, + Attach Prop. Rendered when a character marker/card is selected. |

**Can the user set Held By without the attach API?**  
**UI: no.** `handleApplyAttachment` always calls `spatialMapApi.attachProp` or `updatePropRelationship`.  
**Backend side door:** `PATCH .../props/{id}` (`update_prop`) will accept `placementMode` / relationship fields and run `validate_prop_attachment`. The Spatial Map UI does not use that path for association (it uses it for `visible` and grid moves). Do not add a second write path; keep using `/attach` + `/relationship`.

---

## 4. Relationship enum

**Frozen today** (Python `attachment.py` + TS `types.ts`, identical):

`held | carried | worn | using | interacting | associated`

Attachment points: `left_hand | right_hand | both_hands | head | upper_body | lower_body | back | waist | wrist | shoulder | unspecified`

**Requested:** `held_by, carried_by, worn_by, used_by, attached_to, on, near, interacting_with`

These are **not** the same set. Current values are host-centric verbs (ERS already renders “Korri is holding the Coffee Cup prop in the right hand.”). Requested values are prop-centric / spatial.

**Do not rename the frozen enum in this repair.** ERS `_RELATIONSHIP_GERUND`, contract tests, and live Schnick data all use `held`. Adding aliases or new values is a later contract amendment, not required to fix the switch XOR.

---

## 5. Tags

| Layer | What exists | Persist / hydrate |
| --- | --- | --- |
| Placement `tag: str` | Single friendly string. Comment: `"@Korri"` or `"#coffeecup"`. | Yes. On create/update bodies. Saved in `document_json`. |
| Document `tags: list[str]` | Map-level list. | Yes, via map PATCH. Live Schnick: `[]`. |
| Placement `tags[]` | **Does not exist.** | — |
| Add-slot write | `handleAddCharacter` / `handleAddProp` set `tag: option.name` (raw name, not `characterTag` / `normalizePropTag`). | Helpers exist in `types.ts` but the panel does not use them on add. |
| Live Schnick | Korri `tag=""` (empty). Cup `tag="#coffeecup"`. | Hydrates. |
| Entity resolver | `@Name` / `#prop-tag` parsers. Separate from Spatial Map card UI. | Consume-only. |

No tag editor on the card. More does not edit tags. Mission “tags” is a **gap** if it means a freeform `tags[]` on the placement; the single `tag` field already persists. Extend that field or add `tags[]` on the **same row** — do not create a tag store.

---

## 6. Follow-on-move

**Yes. Already implemented and tested. Do not rewrite.**

`update_character` (`service.py` ~469–471): “Character move updates only this character. Attached props keep attachment and must not receive independent grid positions from the move.”

Attached props have coords cleared (`clear_independent_grid_position`). Grid does not render an independent cup marker. Position is the host’s. No `resolvedX/Y` is written.

Test: `test_character_move_keeps_attachment_no_independent_pos`.

**Live proof during this audit (GET only):**  
- First GET `:8761` ~2:45 PM PT: map **v55**, Korri grid **9/10**, cup `normalizedX/Y=null`, `gridRow/Column=-1`.  
- Later GET both ports: map **v66** `updatedAt=2026-08-14T21:48:33Z` = **2:48 PM PT**, Korri grid **8/9**, cup still `-1/-1` / `x=y=z=null`, still `attached` / `held` / `right_hand`.  
Korri moved; cup coords were not written.

---

## 7. Detach & Place

**Exists.** Card + `CharacterInspector`. `handleDetachAndPlace`: `detachProp` then `beginPlacement("place", "prop", ...)`. Backend `apply_detach` → independent-unplaced (coords cleared). Caller then places. Matches frozen contract.

---

## 8. Downstream — what already says “Korri is holding the Coffee Cup”

| Consumer | Write back to map? | Payload |
| --- | --- | --- |
| `ers_projection.compile_structured_blocking` | No (Amendment #3) | Lines: `Character: Korri, Position: {cell}` + `Attached Prop: Coffee Cup, Relationship: Held, Attachment: Right Hand`. Prose: **`Korri is holding the Coffee Cup prop in the right hand.`** Attachments array with frozen fields. Does **not** infer attach from overlapping cells. Does **not** filter `visible`. |
| `compile_shot_prompt` (`codirector/entity_resolver.py`) | No | Appends those `lines` + `conceptual_prose` to the image prompt. |
| Scene Creator `_prop_from_placement` | No | Copies `placementMode`, slot, id, relationship, point; clears `position_label` when attached. |
| Live Scene Creator workspace GET | — | Coffee Cup `prop_id=a8d48a46-...`, `placementMode=attached`, slot 1, Korri id, `held` / `right_hand`, `position_label=""`. |
| Co-Director `spatial_map_summary` | No | Counts only (`id`, `title`, character/prop/camera counts, `has_ers`). **No attachment prose.** |
| Co-Director tools | Place/move only | `spatial.place_character` / `spatial.place_prop` / `spatial.move_placement` have **no** attach fields. **No** `spatial.attach_prop` / detach / relationship tool. |

---

## 9. Live Schnick Coffee state (GET only)

| | |
| --- | --- |
| Project | `2347bf46-3762-4763-86c5-4a6032522278` |
| Map | `6bc36d92-d21a-4c2f-b85f-71d1f6aa9081` title “Spatial Map” |
| Ports | `:8758` and `:8761` both **200**, same **v66** at 2:48 PM PT |
| Korri | placement `2b681b6a-...`, characterId `c49371ed-...`, **slotIndex 0 / Character 1**, `visible=true`, placed grid **8/9**, `tag=""`. Leftover `slotIndex=-1` Korri rows **gone** (cleaned earlier; one canonical row). |
| Coffee Cup | placement `61cd9b72-...`, propId `a8d48a46-ce0d-4b53-8a47-330779346eb0`, slotIndex 0 / Prop 1, **`placementMode=attached`**, `attachedCharacterSlot=1`, `attachedCharacterId=c49371ed-...`, **`held` / `right_hand`**, coords null / grid -1, `tag="#coffeecup"`, **`visible=false`**. |
| XOR | Cup has no independent marker. Because `visible=false`, Korri’s P1 badge is omitted. Attach record still present. |
| Workspace | Same attach fields hydrated on the Coffee Cup prop. |

`:8758` and `:8761` are the same document after refresh. Do not bounce either.

---

## 10. Gap vs this mission

| Ask | Status |
| --- | --- |
| **Placement Active** label | Missing. Switch is unlabeled; aria says “placement on/off.” ACTIVE badge ≠ this. |
| **Visibility independence** | **Passes.** Keep. Relabel the switch so it is not mistaken for Visible. |
| **Association More section** | Missing. More = note only. Add Held By / relationship / point here, calling existing attach API. |
| **Tags** | Single `tag` persists. No `tags[]`, no More editor. |
| **Prop-to-prop** | Missing. Schema is prop → character only (`attachedCharacterId` / `attachedCharacterSlot`). |
| **Circular safety** | Unnecessary today (DAG by construction). Required only if prop-to-prop is added. Do not invent a cycle checker for character-only attach. |
| **Co-Director write paths** | **Consume-only** for association. Place/move tools exist; attach tools do not. Summary omits holding prose. |

---

## Files to change (smallest repair)

Extend the **existing** attach contract. Do **not** create a second association store.

**Must change (UX split + More association):**

1. `studio-web/src/components/CoDirector/SpatialMap/PlacementSlot.tsx`  
   - Label the switch **Placement Active** (visible text + aria).  
   - Keep **Visible** as-is.  
   - Add Association block under **More** (Held By / relationship / point) that opens or inlines the existing editor contract — Apply still goes to attach/relationship APIs.  
   - Do not make switches independently “on” for placement (one armed entity is correct).

2. `studio-web/src/components/CoDirector/SpatialMap/SpatialMapPanel.tsx`  
   - Wire More association to `handleApplyAttachment` / `handleDetachAndPlace`.  
   - Do not add local association state.  
   - Optional: stop auto-arm from looking like “Korri is the only one on,” or show Placement Active text so auto-arm is obvious.

3. `studio-web/src/components/CoDirector/SpatialMap/spatialMap.css`  
   - Styles for the Placement Active label only.

**Do not change unless product explicitly amends the frozen contract:**

- `attachment.py`, `schemas.py` field names / XOR / enum  
- `ers_projection.py` gerunds  
- attach/detach/relationship routes  
- `SpatialGrid.tsx` XOR (`independentProps` filter + badge)  
- `PropAttachmentEditor.tsx` / `CharacterInspector.tsx` / `attachmentUi.ts` core helpers (reuse them)  
- Character Creator (any path)

**Tags / prop-to-prop / new relationship names / Co-Director attach tool:** out of the smallest repair. If tags are in-scope, add `tags[]` (or edit `tag`) on the same placement row in `schemas.py` + `types.ts` + existing update bodies — still one store.

---

## What already PASSES — do not rewrite

- Frozen attach contract (`studio-api/.runtime/spatial-map-attachment-contract.md`): field names, XOR, slot `attachedCharacterSlot = slotIndex + 1`.
- `apply_attach` / `apply_detach` / `apply_relationship_update` / `clear_independent_grid_position`.
- Routes: `POST .../attach`, `POST .../detach`, `PATCH .../relationship`.
- Character remove `CHARACTER_HAS_ATTACHED_PROPS` + leftover `slotIndex=-1` owner fix (`props_attached_to_character`).
- Follow-on-move (character PATCH does not write prop coords).
- Grid XOR: attached prop has no marker; host gets P1 / +N from **visible** attached props.
- Visible hide/show (persist + marker CSS + tests).
- `PropAttachmentEditor`, `CharacterInspector`, **Detach & Place**.
- ERS / Scene Creator / `compile_shot_prompt` consume path and “Korri is holding…” prose.
- Live Schnick attach record (cup `a8d48a46` held by Korri Character 1, right_hand).
- Tests (keep, extend if needed, do not replace):
  - `studio-api/tests/test_spatial_map_attachment_contract.py`
  - `studio-api/tests/test_spatial_map_attach_ops.py` (incl. move + leftover delete)
  - `studio-api/tests/test_spatial_map_attach_projection.py` (incl. `compile_shot_prompt` + no infer-from-overlap)
  - `studio-web/.../types.test.ts`
  - `studio-web/.../attachmentUi.test.ts`
  - `studio-web/.../SpatialGrid.test.ts`

Prior attach UI slice was **VERIFIED**, not CERTIFIED COMPLETE for this split. That still holds.

---

## Co-Director

**Consume-only for association.**

- Context: `spatial_map_summary` — counts, no holding line.
- Prompt compile: `compile_shot_prompt` reads ERS snapshot via `compile_structured_blocking`.
- Writes that exist: `spatial.place_character`, `spatial.place_prop`, `spatial.move_placement` — **no** attachment parameters; handlers do not call `attach_prop`.
- Writes that do **not** exist: `spatial.attach_prop`, detach, relationship.

Do not add a Co-Director attach tool in the smallest repair. If added later, it must call the existing `/attach` service, not a new store.

---

## Character Creator

No CC files in scope. Do not list or make CC edits.

---

## Implementation notes (for the next agent)

1. Relabel the switch **Placement Active**. Keep one-at-a-time `beginPlacement`. That *is* the product rule; the bug is the unlabeled power-switch affordance.
2. Leave **Visible** independent. Live cup is `visible=false` — restoring the P1 badge is a Visible click, not a re-attach.
3. Put Held By / relationship / point in **More**, Apply → existing `attachProp` / `updatePropRelationship`.
4. Do not rename `held` to `held_by`.
5. Do not give attached props an independent grid marker.
6. Do not bounce `:8758` / `:8761`. Do not edit Character Creator.

---

*Audit only. Source tree unchanged except this file.*
