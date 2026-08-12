# MAGI ↔ Timeline Interop Audit (incl. W46 contract)

**Status:** Read-only Phase 0 audit.
**Date:** 2026-08-08
**Governance:** Subject to the **Critical Timeline Handoff Law** (see section 7).

## 1. Executive finding

**There is NO real MAGI↔Timeline handoff wiring.** The W4C "Timeline-MAGI integration GO" (`docs/release-gate/m42/M42_W4C_TIMELINE_MAGI_INTEGRATION_REPORT.md`) was produced by a stamp script (`scripts/m42_w4c_timeline_stamp.py` writing `artifacts/m42/w4c/timeline_magi_results.json`) — no `sendToTimeline`/`placeTimeline` exists in MAGI frontend code, and no import/export API exists in the MAGI backend.

## 2. CURRENT certified Timeline contract — W46 (verified in source)

**Authoritative API surface** (wired in `studio-web/src/api.ts:3203-3340`):
```
/api/director-timeline/projects/{projectId}/scenes/{sceneId}/...
```
- `GET/PUT .../master` (`director_timeline_w46/router.py:34-51`)
- `POST .../batches` (`add_batch`, `:74-84`)
- `POST .../batches/{id}/duplicate`, `DELETE .../batches/{id}` (`:87-100`)
- `PATCH .../batches/{id}` (`touch_batch_config`, `:147-159`)
- `POST .../batches/{id}/clips` (`add_clip_to_batch`, `:132-144`)
- `POST .../batches/{id}/generate`, `.../complete`, `.../approve` (`:187-249`)
- `POST .../generate` (scene), `.../cancel`, `.../repair-ranges`, `.../preflight` (`:176, 252-288`)

**State model (FROZEN):**
```
Scene
└── SceneTimelineMaster            (persisted in scene.director_json, store.py:81-134)
    └── batchBlocks: [BatchBlock]  (immutable id "bb_…", contracts.py:213; batchBlockId NEVER changes)
        ├── visualClips / audioClips / sfxClips / cameraInstructions
        │     (BatchClip, contracts.py:177-202 — BATCH_OWNED_CLIPS invariant)
        ├── approvedClip           (ApprovedClip, lineage anchor)
        ├── executionSnapshots     (immutable, ExecutionSnapshot contracts.py:107-120)
        └── repairRanges / promptSegments / sourceAnchors
└── derived flattened director timeline (bbclip_ prefixed, generation/completion.py:178-231)
    → scene.director_json video_clips for NLE rendering
```

**Key invariants:**
- `batchBlockId` is immutable identity; `order` is mutable presentation. Reordering never rewrites IDs (`contracts.py:206-210`).
- BATCH_OWNED_CLIPS: adding media to one batch never mutates another batch's clips (`contracts.py:180-182`, `orchestrator.py:503-513`).
- Approved-state invalidation: changing batch config flips `ApprovedConfigurationChanged` and preserves prior playable clip (`orchestrator.py:518-523`).
- Migration from legacy scene-global clips → batch-owned (`director_timeline_w46/migration.py:118`).

## 3. Legacy / parallel Timeline pathways — NOT authoritative

`project.settings_json["timeline"]` is still written by legacy subsystems:
- `voice_performance/service.py:639`
- `voice_performance/m410_service.py:635, 686`
- `voice_environment/service.py:530`

These are the older Voice/Audio placement patterns and are **not** the certified W46 contract. MAGI must NOT follow them.

## 4. MAGI current relationship to Timeline

- **No import:** MAGI has no API to pull Timeline assets with lineage.
- **No export:** MAGI has no API to place approved media onto the Timeline.
- **Navigation only:** Co-Director `continuity_w5.py:121` deep-links "Open Timeline".
- **Timeline production gate references MAGI:** `timeline_product/production_gate.py:67` `timelineMagiIntegrationOperational` (artifact-driven).

## 5. What the mission requires

- MAGI import (lineage-preserving) and export routed through the **W46 authoritative surface**.
- No second legacy Timeline representation.
- Preserve existing W46 Timeline certification.

## 6. Required repairs (m5)

1. `app/magi/timeline_handoff.py`:
   - Import: `POST /api/magi/projects/{pid}/timeline/import` — accept `{assetId, projectId, sceneId, batchBlockId?, generationId?, takeId?, sourceClipId?}`; validate asset ownership; create MAGI clip preserving lineage.
   - Export: `POST /api/magi/projects/{pid}/scenes/{sceneId}/timeline/export` — route through W46 (`add_batch`/`PATCH` batch-owned clips or `add_clip_to_batch`); no regeneration; do not fabricate candidate/execution snapshots.
2. Frontend: "Send to Timeline" / "Open Timeline" buttons in MAGI calling these APIs; navigate to Timeline after send.
3. Extend `MagiClip` with lineage fields.
4. W46-master-preservation regression: MAGI export must not break `configFingerprint`/approved state or create parallel scene-global timeline state.

## 7. CRITICAL TIMELINE HANDOFF LAW (mandatory gate)

Before implementing MAGI → Timeline export, re-audit the CURRENT certified Timeline contract.
- Do NOT assume older Voice Studio / Audio Studio `project.settings_json["timeline"]` placement patterns are authoritative.
- MAGI must integrate with the currently certified W46 Timeline APIs/state model.
- If current Timeline ownership is `Scene → BatchBlock → batch-owned clips → immutable batchBlockId lineage`, MAGI output must use those authoritative APIs/contracts.
- Do NOT create a second legacy Timeline representation.
- Do NOT write directly into `project.settings_json["timeline"]` unless the current Timeline audit proves that remains an authoritative supported pathway.
- Timeline interoperability must preserve the existing Timeline certification.

**Verified outcome:** The W46 audit above confirms the Scene→BatchBlock→batch-owned-clips→immutable-batchBlockId lineage model is authoritative. MAGI export MUST go through the `/api/director-timeline/...` surface. `settings_json["timeline"]` writes are forbidden for MAGI.
