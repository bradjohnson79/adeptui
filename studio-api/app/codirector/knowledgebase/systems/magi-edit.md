---
id: magi-edit
kind: system
modality: system
registry_ids: []
aliases:
  - magi edit
  - finishing edit
  - nle edit
spoken: MAGI editorial trim, split, move, and overlay mutate are UI-only today. Co-Director must refuse and hand off to the MAGI editor.
workspace_tags:
  - magi
  - magieditor
version: "2026.09.14"
authority: adept-integrated
---

# MAGI Edit

## Purpose

Honest editorial guidance for MAGI finishing.

## Allowed CD tools (read / handoff)

- `magi.inspect_sequence`, `magi.inspect_tracks`, `magi.inspect_clip`, `magi.inspect_selection`
- `magi.inspect_post_context` (domains=edit)
- `magi.inspect_timeline_lineage`

## NOT_SUPPORTED (refuse)

- `magi.trim` / split / move / duplicate / overlay mutate via CD
- Overlay burn into final video (engine stub — Bot2)
- Dissolve / Stabilize placebos as real engines

## Honesty

Tell the creator to use MAGI Editor UI for trim/overlay. Do not invent CD edit mutators.
