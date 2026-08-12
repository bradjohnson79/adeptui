# MAGI Timeline Handoff — Implementation Audit (m5)

**Status:** Implementation truth (Phase B of the MAGI Next Execution Pass).
**Date:** 2026-08-08
**Governance:** Subject to the **Critical Timeline Handoff Law** (see
`MAGI_TIMELINE_INTEROP_AUDIT.md` §7). This document records the *implemented*
reality after the m5 handoff repairs and is the current governing document for
MAGI ↔ W46 Timeline interoperability.

> **Canon supersedes (Law 30):** where this document conflicts with the earlier
> read-only audit `MAGI_TIMELINE_INTEROP_AUDIT.md`, THIS document is the current
> truth. `MAGI_TIMELINE_INTEROP_AUDIT.md` remains the historical Phase-0 audit.

## 1. Implementation status (as-built)

The m5 handoff was implemented and certified against the **currently-certified
W46 Timeline contract** (`director_timeline_w46/`):

- **Import:** `POST /api/magi/projects/{pid}/timeline/import` →
  `magi.timeline_handoff.import_timeline_asset()` → validates asset ownership,
  returns a MAGI clip whose **lineage fields are FLAT** on the clip document
  (`batchBlockId`/`generationId`/`takeId`/`sourceClipId`/`sceneId`) to match the
  frozen `MagiClipModel` (backend) and `MagiClip` (frontend) contracts.
- **Export:** `POST /api/magi/projects/{pid}/scenes/{sceneId}/timeline/export` →
  `magi.timeline_handoff.export_to_timeline()` → routes through the certified
  W46 surface only: `service.add_batch` + `orchestrator.add_clip_to_batch`.
  - New-batch export: creates a batch via `add_batch` then appends clips.
  - Existing-batch export: **requires an explicit `batchBlockId`**; a missing or
    unknown batch is a structured `BATCH_NOT_FOUND` error (404) — there is
    **no silent `batches[0]` fallback**.
- **No legacy timeline writes:** MAGI never writes
  `project.settings_json["timeline"]`. The legacy Voice/Audio placement patterns
  recorded in the Phase-0 audit are NOT authoritative for MAGI.

## 2. W46 surface used (verified against `director_timeline_w46/`)

| Step | Function | Return contract |
| ---- | -------- | --------------- |
| New batch | `service.add_batch(db, project_id, scene_id, label=…, planned_duration=…)` | `{ok, batch:{id}, master}` |
| Add clip (new or existing batch) | `orchestrator.add_clip_to_batch(db, project_id, scene_id, batch_id, clip_data)` | `{ok, batch, clip:{id}, mock:False}` |
| Missing batch | same | `{ok:False, error:"BATCH_NOT_FOUND", mock:False}` |

- `BatchBlock.id` (`bb_…`) is immutable identity; `order` is mutable
  presentation. Reordering never rewrites IDs.
- BATCH_OWNED_CLIPS invariant: appending to one batch never mutates another
  batch's clips.
- `add_clip_to_batch` recalculates the target batch's `configFingerprint` on
  append (normal W46 behavior); export does not regenerate media and never
  fabricates candidate/execution snapshots (`mock:False` everywhere).

## 3. Lineage model

- **Import:** an existing project asset is pulled into a MAGI clip. Lineage
  fields describe where the clip came from on the W46 Timeline
  (`batchBlockId`, `generationId`, `takeId`, `sourceClipId`, `sceneId`).
- **Flat vs nested (schema fix):** the original implementation emitted a nested
  `lineage` object. The frozen frontend contract (`MagiClip`) and backend
  (`MagiClipModel`) both expect **flat fields**. The m5 repair flattens the
  returned clip so import output is directly insertable into a sequence.
- **Export ledger (MAGI-side):** the frozen W46 `BatchClip` has **no metadata
  dict**, so export provenance is kept MAGI-side in the canonical sequence
  document under `sequence.json.exportLedger`, keyed by `batchBlockId`, mapping
  W46 clip ids → MAGI clip ids/assets. This survives reload through normal
  sequence persistence and does not mutate the W46 contract.

## 4. Error contract (structured envelope)

All handoff errors share the MAGI envelope (`magi/errors.py`):

```
{"error": {"code": str, "message": str, "fields": {...}?}}
```

Mapped codes:

| Code | HTTP | When |
| ---- | ---- | ---- |
| `clips_required` | 400 | export body has no non-empty `clips` array |
| `asset_ownership` | 400 | export/import references an asset outside the project |
| `SCENE_NOT_FOUND` | 404 | export target scene does not exist in the project |
| `BATCH_NOT_FOUND` | 404 | existing-batch export references an unknown `batchBlockId` |
| `asset_id_required` | 400 | import body has no `assetId` |

`ok:False` W46 results are surfaced as structured MAGI errors (never raw 500s).

## 5. Invariants preserved

1. Source generation history is **never mutated** by export (X stays X; Y is a
   derived output with provenance). Export only appends batch-owned clips via
   the W46 surface and records the MAGI-side ledger.
2. No second legacy Timeline representation.
3. W46 Timeline certification preserved (all mutations go through
   `director_timeline_w46` orchestration).
4. `mock` is always `False` on handoff results.

## 6. Scope of this pass

- B2: flat import lineage (schema parity backend ↔ frontend).
- B3: explicit-batch export requirement, `BATCH_NOT_FOUND` propagation,
  `sequence.json.exportLedger` bookkeeping.
- B4: no generation-history mutation on export.
- B6: integration certification (import / existing-batch export / new-batch
  export / cross-project rejection / missing-batch / ledger reload).

## 7. Evidence

- Backend tests: `studio-api/tests/test_magi_sequence_repairs.py` (m5 handoff
  section) + handoff integration tests.
- Frontend: lineage contract in `studio-web/src/magiSequence/types.ts`.
- Checkpoint: `MAGI_M1_M5_ARCHITECTURAL_CHECKPOINT.md`.
