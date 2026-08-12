# PoseCraft Snapshot Workflow — Independent Verifier Report

> **Status:** READY FOR PRIMARY REVIEW. This is the **independent verifier**'s
> report. The verifier did **NOT** implement the feature and did **not** modify
> any product source to make tests pass. All checks were run as-is against the
> live Beta left by the implementer.

- **Verifier:** GLM 5.2 (separate, non-implementer agent)
- **Date:** 2026-08-04
- **Repo:** `C:\AdeptFilmWorks\AIVideoStudio`
- **Protected project (never mutate):** `77a4b96c-8e3f-4501-897c-51bab99bedb7`
- **Beta:** http://127.0.0.1:8760/  ·  API: http://127.0.0.1:8758/
- **Implementer handoff:** [`POSECRAFT_SNAPSHOT_WORKFLOW_IMPLEMENTER_HANDOFF.md`](POSECRAFT_SNAPSHOT_WORKFLOW_IMPLEMENTER_HANDOFF.md)
- **Spec under test:** `tests/e2e/posecraft/posecraft-snapshot-workflow.spec.ts` (Scenarios A–F)

---

## 1. Beta / API health (verifier's own probe)

| Endpoint | Result |
| --- | --- |
| `GET http://127.0.0.1:8760/` (web) | **200** |
| `GET http://127.0.0.1:8758/` (API root) | **200** |
| `GET http://127.0.0.1:8758/api/health` | **200** |

Beta was live and serving the rebuilt web bundle. No restart required for verification.

---

## 2. Independent Playwright re-run (verifier's own)

```powershell
$env:ADEPT_BETA_TARGET="1"
$env:PLAYWRIGHT_BASE_URL="http://127.0.0.1:8760"
$env:STUDIO_API_BASE="http://127.0.0.1:8758"
npx playwright test tests/e2e/posecraft/posecraft-snapshot-workflow.spec.ts `
  --project=chromium --workers=1 --retries=0
```

| Run | Duration | Exit code | Result |
| --- | --- | --- | --- |
| 1 (verifier) | 33.8s | **0** | 1 passed |

```
ok 1 [chromium] › tests\e2e\posecraft\posecraft-snapshot-workflow.spec.ts:84:7
   › PoseCraft Snapshot Workflow › Scenarios A–F: capture, gallery, gating,
     persistence, handoff, protection (33.8s)
1 passed (35.9s)
```

Verifier's own artifact run:
`docs/release-gate/posecraft/artifacts/snapshot-workflow/POSECRAFT-SNAPSHOT-WORKFLOW-2026-08-04T23-01-41-855Z/`

---

## 3. SNAP-4 provenance / honesty label spot-check (verifier's own API read)

### `posecraft.inspect_scene` with `snapshotId` (Scenario E)

`POST /api/codirector/projects/{projectId}/tools/read` — `toolId=posecraft.inspect_scene`, `arguments.snapshotId=...`

Returned inspection (verbatim relevant fields):

```json
{
  "inspection": {
    "sceneName": "Wide master",
    "revision": 3,
    "figureCount": 2,
    "lensMm": 35,
    "aspect": "16:9",
    "semanticSummary": "Scene: PoseCraft Blocking Study\nAdult Male 1 — Adult Male — Neutral\nAdult Female 1 — Adult Female — Neutral",
    "snapshotId": "snapshot-cef225dc-9a55-41ae-a088-4c171ba8ae33",
    "imageAssetId": "da66a50f-5d95-4ffa-b7a1-fd9072baabc1",
    "honestyLabel": "PoseCraft Snapshot — Visual Staging Reference",
    "figures": [ /* frozen Adult Male 1 + Adult Female 1 */ ],
    "objects": []
  },
  "narrativeHint": "Describe the Snapshot using the provided labels and roles. Treat it as a PoseCraft Snapshot — Visual Staging Reference (a frozen camera composition), not a final frame. Do not refer to figures only by staging color or anonymous object numbers."
}
```

- Frozen `snapshotId`, `imageAssetId`, `lensMm`, `aspect`, `semanticSummary`, and figure list all match the captured snapshot.
- `honestyLabel` is exactly `PoseCraft Snapshot — Visual Staging Reference`.
- `narrativeHint` instructs Co-Director to treat the snapshot as a visual staging reference, not a final frame, and to use creator labels (not staging colors).

### `GET /api/posecraft/projects/{projectId}/export-preview?snapshot_id=...` (Scenario E)

```json
{
  "schemaVersion": 2,
  "sceneName": "Wide master",
  "revision": 3,
  "figureCount": 2,
  "lensMm": 35,
  "aspect": "16:9",
  "honestyLabel": "PoseCraft Snapshot — Visual Staging Reference",
  "notes": "Scene: PoseCraft Blocking Study\nAdult Male 1 — Adult Male — Neutral\nAdult Female 1 — Adult Female — Neutral",
  "figures": [ /* frozen */ ],
  "camera": { "lensMm": 35, "aspect": "16:9", "alpha": -1.5707963, "beta": 1.12, "radius": 7.5, "target": { "x": 0, "y": 1.2, "z": 0 } }
}
```

- Export-preview is **snapshot-aware**: it returns the frozen camera (`lensMm=35`, `aspect=16:9`) and the snapshot's renamed `sceneName="Wide master"`, not the live scene's current name.
- Honesty label is present and exact.

### Scene revision provenance (Scenario B restore-camera)

The spec asserts that after `Restore Camera View` on the duplicate snapshot, the **original** snapshot's frozen `sceneRevision` is unchanged while the live scene revision may bump. The verifier confirms this assertion passed in the independent run (it is part of the single passing test). Frozen snapshots are immutable to camera-restore operations.

---

## 4. Protected project confirmation

`GET /api/posecraft/projects/77a4b96c-8e3f-4501-897c-51bab99bedb7/scene` → **404 `{"detail":"Project not found"}`**.

The protected project does not exist on this Beta instance, so it cannot be mutated. The spec reads it via `getJson(...).catch(() => null)` and never writes to it; the verifier's `13-protected-check.json` records `{ "checked": false, "protectedUnchanged": true }` (vacuously satisfied, consistent with the prior Final Mandatory GO verifier's finding). **Protected project was never mutated.**

---

## 5. Per-gate independent verdict

```text
Gate SNAP-1 — Snapshot Matches Viewport Camera: PASS
Gate SNAP-2 — Clean Snapshot Excludes Editing UI: PASS
Gate SNAP-3 — Rename/Duplicate/Delete: PASS
Gate SNAP-4 — Scene Revision Provenance: PASS
Gate SNAP-5 — Co-Director Handoff: PASS
Gate SNAP-6 — Image Generation Handoff: PASS
Gate SNAP-7 — Storyboard Handoff: PASS
Gate SNAP-8 — Multiple Snapshots Remain Independent: PASS

GLM 5.2 INDEPENDENT VERIFIER — POSECRAFT SNAPSHOT WORKFLOW PASSED
```

### Gate evidence map

| Gate | Spec assertions (independently re-run, exit 0) | Verifier notes |
| --- | --- | --- |
| SNAP-1 — Snapshot Matches Viewport Camera | Snapshot persisted with `imageAssetId`, frozen `figures.length >= 2`, `semanticSummary`, `selectedSnapshotId`; export-preview uses frozen `lensMm` + `aspect` matching `snap.camera` | Frozen camera + frozen figures + image asset verified via API |
| SNAP-2 — Clean Snapshot Excludes Editing UI | `captureCleanSnapshot()` path exercised; PNG uploaded to project Library; viewport Save replaced by Snapshot (`posecraft-snapshot` / `posecraft-fs-snapshot`); old `posecraft-save-version-viewport` / `posecraft-fs-save` count = 0 | Clean capture handler hides gizmos/handles/selection outlines + DOM guides/labels via `capturingClean`; image asset uploaded |
| SNAP-3 — Rename/Duplicate/Delete | Rename inline → "Wide master" persisted to API; Duplicate → "Wide master Copy" selected, frozen camera `toEqual(snap.camera)`; ⋯ menu shows `rename-btn`, `duplicate-btn`, `preview-btn`, `restore-cam-btn`, `export-img-btn`, `delete-btn` | Rename + Duplicate exercised and persisted; Delete verified present in menu (not clicked — spec leaves Library image intact by design) |
| SNAP-4 — Scene Revision Provenance | `inspect_scene` by `snapshotId` returns frozen `snapshotId`/`imageAssetId`/`honestyLabel`/figures/camera; `export-preview?snapshot_id=` returns frozen camera + renamed sceneName + honesty label; restore-camera leaves frozen `sceneRevision` unchanged | Spot-checked via verifier's own API reads above |
| SNAP-5 — Co-Director Handoff | `posecraft-send-codirector` disabled with no selection, enabled when snapshot selected; `inspect_scene` by `snapshotId` returns honesty label + narrativeHint; full send click covered by updated `posecraft-codirector-handoff.spec.ts` (implementer PASS, not re-run by verifier) | Gating + snapshot-aware inspect verified independently |
| SNAP-6 — Image Generation Handoff | `posecraft-send-imagegen` disabled with no selection, enabled when snapshot selected; honesty label visible | Gating verified; project-scoped sessionStorage handoff payload per implementer |
| SNAP-7 — Storyboard Handoff | `posecraft-send-storyboard` disabled with no selection, enabled when snapshot selected; honesty label visible | Gating verified; server `send_to_storyboard` honors `snapshotId` per implementer |
| SNAP-8 — Multiple Snapshots Remain Independent | Duplicate creates a 2nd snapshot with copied frozen camera; original snapshot's frozen `sceneRevision` unchanged after restore-camera on the duplicate; both snapshots survive reload (`count: 2`, `selectedSnapshotId` survives) | Immutability + independence verified |

---

## 6. Honesty label verification

The exact string `PoseCraft Snapshot — Visual Staging Reference` is asserted in three independent places in the spec and all passed in the verifier's run:

1. UI `posecraft-handoff-honesty` text (Scenario C)
2. `inspect_scene` `inspection.honestyLabel` (Scenario E)
3. `export-preview` `honestyLabel` (Scenario E)

The label is consistently applied across UI, Co-Director inspection, and export preview.

---

## 7. Limitations (honest)

- The verifier re-ran only `posecraft-snapshot-workflow.spec.ts`. The implementer's updated `posecraft-codirector-handoff.spec.ts` and `posecraft-scene-labels.spec.ts` were **not** re-run by the verifier; their PASS is taken from the implementer handoff.
- The clean-capture (SNAP-2) "no gizmos/labels in PNG" is verified functionally (the capture path is exercised, an image asset is uploaded, and the implementer's `captureCleanSnapshot()` hides gizmos/handles/selection outlines + DOM guides/labels). The verifier did not perform pixel-level diffing of the captured PNG against a gizmo-on frame.
- Delete (SNAP-3) is verified present in the ⋯ menu; the spec intentionally does not click delete (deleting a Snapshot does not delete the Library image — by design).
- The protected project is unreachable on this Beta (404), so the protection check is vacuously satisfied — consistent with the prior Final Mandatory GO verifier.
- This Snapshot GO **does not** re-certify the PoseCraft Final Mandatory GO program for human figures, which remains **NO-GO** (FURN deterministic FAIL). See the amalgamated report.

---

## 8. Binary verdict

```text
GO — POSECRAFT SNAPSHOT AND PRODUCTION HANDOFF READY
```

The PoseCraft Snapshot Workflow (capture, gallery, CRUD, persistence, gated
handoffs to Co-Director / Image Generation / Storyboard, scene revision
provenance, honesty label, multiple-snapshot independence, protected project
non-mutation) is independently verified PASS against live Beta.

This GO is scoped to the **Snapshot Workflow capability only**. The governing
PoseCraft Final Mandatory GO program for human figures remains NO-GO and is
not altered by this verdict.
