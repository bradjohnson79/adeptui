# Spatial Map character-prop attachment contract (frozen)

Workstream A frozen types + validation. Workstream B added explicit ops:
- `POST .../props/{placement_id}/attach` (`attach_prop`)
- `POST .../props/{placement_id}/detach` (`detach_prop`) — independent-unplaced; caller may then place
- `PATCH .../props/{placement_id}/relationship` (`update_prop_relationship`)
Character remove rejects with `CHARACTER_HAS_ATTACHED_PROPS` (or `?detachAttachedProps=true`).
Field names and enums below stay frozen.

Canonical prop identity: `propId` = existing Spatial Map / Prop record id.
Do not create a second Prop record.

## Frozen field names (Python + TypeScript, identical)

| Field | Type |
| --- | --- |
| `placementMode` | `"independent"` \| `"attached"` |
| `attachedCharacterSlot` | `1` \| `2` \| `3` \| `4` \| `null` |
| `attachedCharacterId` | `string` \| `null` |
| `relationship` | `"held"` \| `"carried"` \| `"worn"` \| `"using"` \| `"interacting"` \| `"associated"` \| `null` |
| `attachmentPoint` | `"left_hand"` \| `"right_hand"` \| `"both_hands"` \| `"head"` \| `"upper_body"` \| `"lower_body"` \| `"back"` \| `"waist"` \| `"wrist"` \| `"shoulder"` \| `"unspecified"` \| `null` |

## XOR law

- A prop is **either** independent **or** attached. Never both as authoritative state.
- `placementMode="independent"`: attachment fields are cleared (`attachedCharacterSlot`, `attachedCharacterId`, `relationship`, `attachmentPoint` = `null`). Independent grid placement (`normalizedX`/`normalizedY`, `gridRow`/`gridColumn`) remains the physical authority.
- `placementMode="attached"`: no independent grid marker is required. Do not invent fake `x`/`y`. Requires `attachedCharacterId` **or** `attachedCharacterSlot` (1-4) **and** `relationship`. `attachmentPoint` is optional; `unspecified` is allowed.
- Missing fields on read default to `placementMode="independent"` and null attachment fields. No migration moves physical positions.

## Slot mapping (do not mix)

Product spec `attachedCharacterSlot` is **1-4** (Character 1-4).

Existing Spatial Map `CHARACTER_SLOTS` / `slotIndex` are **0-3**.

```
attachedCharacterSlot = slotIndex + 1
slotIndex             = attachedCharacterSlot - 1

slotIndex 0 -> Character 1 -> attachedCharacterSlot 1
slotIndex 1 -> Character 2 -> attachedCharacterSlot 2
slotIndex 2 -> Character 3 -> attachedCharacterSlot 3
slotIndex 3 -> Character 4 -> attachedCharacterSlot 4
```

Never store a 0-based value in `attachedCharacterSlot`. Helpers:
- Python: `attached_slot_from_slot_index` / `slot_index_from_attached_slot` in `app/spatial_map/attachment.py`
- TypeScript: `attachedSlotFromSlotIndex` / `slotIndexFromAttachedSlot` in `SpatialMap/types.ts`

## Validation

`validate_prop_attachment()` / `validatePropAttachment()`:
- default / unknown `placementMode` -> independent (backward compatible)
- independent + attachment fields -> clear attachment fields (independent wins)
- attached without character binding or relationship -> reject
- `attachedCharacterSlot` outside 1-4 -> reject (0 is `slotIndex`, not this field)

## Sources

- Python schema: `studio-api/app/spatial_map/schemas.py` (`SpatialPropPlacement`)
- Python helper: `studio-api/app/spatial_map/attachment.py`
- TypeScript: `studio-web/src/components/CoDirector/SpatialMap/types.ts`
