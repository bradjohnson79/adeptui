# PROP CREATOR EXPRESS — ARCHITECTURE AUDIT

**Date:** 2026-08-14  
**Branch:** `beta`  
**Starting SHA:** `756bfd9f3592f99a2e4dabdba`  
**Status:** APPROVED — PROCEED WITH PROP CREATOR EXPRESS

Governing completion report (write last): [`PROP_CREATOR_EXPRESS_COMPLETION_REPORT.md`](./PROP_CREATOR_EXPRESS_COMPLETION_REPORT.md)

Do not cite Character Creator Props & Accessories as Prop Creator. They are different products.

Playwright is out. After automated certification: **READY FOR MANUAL BETA**. Creator GO is a later gate.

---

## Existing Prop Architecture

Two live stores exist. They must not be merged destructively.

1. **Project props — `PropEntity`** in [`ers_contracts.py`](../../../studio-api/app/spatial_map/ers_contracts.py), persisted as ProjectTrait `prop_entity` ([`ers_persistence.py`](../../../studio-api/app/spatial_map/ers_persistence.py)). Consumed by [`entity_resolver._prop_metadata`](../../../studio-api/app/codirector/entity_resolver.py) and Scene Creator.
2. **Character props — `character_props` / `CharacterPropRow`**. Props & Accessories ([`PropsWorkspace.tsx`](../../../studio-web/src/components/character/PropsWorkspace.tsx)). Max 4 per character. Generate is character-sheet locked (`zimage.ref_edit` against hero identity).

Spatial Map Saved Prop currently lists character props + Library tags. It does **not** list `PropEntity`.

---

## Canonical Prop Source of Truth

**BINDING.** Project props = extended `PropEntity`. No third store. No stuffing into `character_props`.

- `PropEntity.id` = canonical `propId`
- `approved_asset_id` = canonical visual identity
- `library_asset_id` may **mirror** `approved_asset_id` after approval only — not a competing identity
- Tag remains the `#coffee-cup` friendly reference

---

## Character Prop vs Project Prop

| | Prop Creator Express | Props & Accessories |
|---|---|---|
| Scope | Project-level | Bound to a character |
| Store | `PropEntity` | `character_props` |
| Generate | identity stills, 4 candidates | 1 job locked to character sheet |

Unified Spatial Map picker: **approved project props** → character props → tagged Library. Do not auto-convert.

---

## Image Generation Reuse

Reuse `enqueue_imagegen_job` and Scene Creator honest routing. Do **not** reuse `generate_character_prop`. Do **not** copy Character Creator Cloud trap.

- Local OFF = zero local jobs. API OFF = zero API jobs.
- API ON without a real hosted path = **API Generation — Not Available**
- Reference-capable: Reference Image > Description > Style → **Reference Conditioned**
- Txt2img (Illustrious XL / Qwen): Description > Style → **Description Guided**. Do not auto-disable because a reference exists. Never claim they consumed pixels.
- One canonical `PropEntity → Prop Generation Prompt` compiler
- Output: PROP IDENTITY IMAGES — centered complete prop, not a held-prop scene or four-view sheet

---

## Candidate / Approval Reuse

Four candidates. No auto-approve. **Use This Prop** sets `approved_asset_id` (and mirrors `library_asset_id`). Drafts save without approval.

---

## Library Integration

Generated images are Library assets. Reference upload/picker unlinks `reference_asset_id` only. Delete Prop deletes the profile row, not binaries. Warn + unlink Spatial Map placements.

---

## Spatial Map Integration

Consume `propId` + `approvedAssetId`. Never collapse an approved PropEntity into a generic Library item.

---

## Scene Creator Integration

Resolve placed project prop: PropEntity → approved visual → description → placement → shot context. Reference-capable scene generators use approved identity pixels where supported.

---

## Recommended Shared Components

- `CHARACTER_STYLE_OPTIONS`
- Library image picker (`CharacterReferenceAssetPicker`)
- Scene Creator local/API honesty
- `enqueue_imagegen_job` / `hosted_image_generation_available`
- `save_prop_entity` / `list_prop_entities`

New: `usePropCreator` / `PropCreatorCore` / `PropCreatorPanel`. Express only. Core stays Standard-ready.

---

## READY TO IMPLEMENT

**READY TO IMPLEMENT.** Binding clarifications 1–10 applied.

Final automated verdict after verifier: **READY FOR MANUAL BETA** (not GO).
