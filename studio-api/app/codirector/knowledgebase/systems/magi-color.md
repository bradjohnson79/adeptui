---
id: magi-color
kind: system
modality: system
registry_ids: []
aliases:
  - color grade
  - color look
  - grading
  - cinematic grade
spoken: MAGI color applies a preset look to a Library asset and may record clip grade on the sequence. Source media stays intact.
workspace_tags:
  - magi
  - magieditor
version: "2026.09.14"
authority: adept-integrated
---

# MAGI Color

## Purpose

Task-aware color finishing via MAGI.

## Allowed CD tools

- `magi.inspect_grade` — clip grades + preset catalog
- `magi.inspect_post_context` (domains=color)
- `magi.inspect_sequence` / `magi.inspect_clip`
- `magi.color.apply` — propose → approve → apply → VERIFY (MagiActionReceipt)

## NOT_SUPPORTED (refuse)

- LUT import / interactive curves / scopes
- Vectorscope claims without receipt evidence
- Placebo Brighten as a real engine

## Workflow

ANALYZE (inspect_grade / post_context) → PROPOSE (magi.color.apply) → APPROVE → APPLY → VERIFY (receipt + re-read clipGrades / output asset).
