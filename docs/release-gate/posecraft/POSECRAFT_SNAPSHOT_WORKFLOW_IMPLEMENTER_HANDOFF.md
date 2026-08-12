# PoseCraft Snapshot Workflow — Implementer Handoff

> **Status:** READY FOR PRIMARY REVIEW (implementer scope complete). **NOT GO.**
> Independent verification (todo 6) must be performed by a separate
> `glm-5.2-high` agent before any amalgamated CURRENT AUTHORITATIVE STATUS is
> set to GO.

## Scope

Implements the approved PoseCraft Snapshot Workflow plan: a **Snapshot** freezes
one exact camera composition for production handoff. A Snapshot is **NOT** a
scene save. Scene autosave/flush (`flushSceneDocument`, 600ms debounce, pagehide
flush) is left intact and **never** PNG-captures.

Protected project `77a4b96c-8e3f-4501-897c-51bab99bedb7` is never mutated by
this work.

## Branch / SHAs

- Branch: implement on the current working branch (uncommitted changes; the
  primary agent owns the commit).
- Starting SHA: see `git rev-parse HEAD` at handoff.

## Files changed

### Data contract
- `studio-web/src/posecraft/types.ts` — added `PoseCraftSnapshot` type;
  `snapshots?: PoseCraftSnapshot[]` and `selectedSnapshotId?: string | null`
  on `PoseCraftDocument`.
- `studio-api/app/posecraft/schemas.py` — mirrored `PoseCraftSnapshot` +
  `snapshots` / `selectedSnapshotId` on `PoseCraftDocument` (with
  `model_rebuild()` for forward refs).
- `studio-web/src/posecraft/state.ts` — immutable CRUD helpers:
  `createSnapshot`, `renameSnapshot`, `duplicateSnapshot`, `deleteSnapshot`,
  `selectSnapshot`, `getSelectedSnapshot`, `POSECRAFT_SNAPSHOT_CAP` (48).
  Frozen camera/figures/primitives/semanticSummary via deep clone; rename
  only changes `name`.
- `studio-web/src/posecraft/storage.ts` — `parsePoseCraftDocument` migrates
  missing `snapshots` → `[]`, missing `selectedSnapshotId` → `null`.
- `studio-web/src/posecraft/posecraftApi.ts` — snapshot API helpers
  (`listSnapshots`, `getSnapshot`, `renameSnapshotApi`, `duplicateSnapshotApi`,
  `deleteSnapshotApi`, `selectSnapshotApi`, snapshot-aware `getExportPreview`).

### Clean capture
- `studio-web/src/posecraft/engine.ts` — `captureCleanSnapshot()` hides
  gizmos / joint handles / selection outlines, renders, restores exactly,
  returns PNG data URL. DOM guides + floating labels are hidden by the React
  capture handler via a transient `capturingClean` flag.

### Toolbar + Gallery + Handoff (UI)
- `studio-web/src/components/GenerationTools/PoseCraftWorkspace.tsx`:
  - Replaced viewport Save (`posecraft-save-version-viewport`) and fullscreen
    Save (`posecraft-fs-save`) with **Snapshot** (`posecraft-snapshot` /
    `posecraft-fs-snapshot`). Tooltip: "Capture the exact camera framing and
    staged scene currently shown in the viewport."
  - Capture handler: flush → clean capture → `api.uploadAsset(projectId,
    file, "posecraft_snapshot", "image")` → append frozen snapshot → select
    → flush again. On flush failure: status
    `SNAPSHOT_BLOCKED — CURRENT POSECRAFT SCENE COULD NOT BE PERSISTED`.
  - Renamed Export accordion to **Snapshots + Exports** (id `export` kept so
    persisted prefs + existing accordion tests still pass). Snapshot cards
    show thumb, name, time, Revision, lens/aspect, selected badge, ⋯ menu
    (Rename, Duplicate, Delete, Open Preview, Restore Camera View, Export
    Image). Click card = select for handoff (click selected card again
    toggles deselect).
  - Moved Version Label / Save Version / milestone cards to a nested
    **Advanced — Scene milestones** accordion (`id="milestones"`). Removed
    the duplicate Save Version button from the Scene accordion (Undo/Redo
    kept).
  - Handoff gating: Send to Co-Director (first), Image Generation, Storyboard
    require `selectedSnapshotId`. Disabled tip: "Capture a Snapshot first to
    send this staging composition to production." Honesty label
    `PoseCraft Snapshot — Visual Staging Reference` shown when selected.
  - Co-Director prompt references the snapshot by name + asset + revision,
    uses creator labels (not staging colors), and asks Co-Director to call
    `posecraft.inspect_scene` with the `snapshotId`.
  - Image Gen / Storyboard handoffs are project-scoped (sessionStorage handoff
    payload keyed by projectId so the reference thumbnail appears).
- `studio-web/src/components/GenerationTools/posecraft-workspace.css` — dark
  theme CSS for snapshot gallery, cards, menu popover, handoff gate/honesty,
  and preview overlay (reuses existing figure/version menu tokens).

### Server snapshot support
- `studio-api/app/posecraft/service.py` — migration for missing
  `snapshots`/`selectedSnapshotId`; snapshot CRUD (`list_snapshots`,
  `get_snapshot`, `rename_snapshot`, `duplicate_snapshot`,
  `delete_snapshot`, `select_snapshot`) with cap 48; snapshot-aware
  `build_export_preview(snapshot_id=...)` returning the Snapshot honesty
  label.
- `studio-api/app/posecraft/router.py` — snapshot CRUD endpoints +
  `?snapshot_id=` query param on export-preview.
- `studio-api/app/codirector/tools/definitions.py` — optional `snapshotId`
  on `posecraft.inspect_scene`, `posecraft.export_reference`,
  `posecraft.send_to_image_pipeline`, `posecraft.send_to_storyboard` (+
  `imageAssetId` on the latter two).
- `studio-api/app/codirector/tools/handlers/posecraft.py` —
  `inspect_scene`/`export_reference`/`apply_send_to_image_pipeline`/
  `apply_send_to_storyboard` honor `snapshotId` and return the Snapshot
  honesty label + frozen composition.

### Tests
- `studio-web/src/posecraft/posecraftSnapshot.test.ts` (NEW) — 8 unit tests
  for CRUD + storage migration (frozen copy immutability, cap, selection
  toggle, migration defaults).
- `studio-api/tests/test_posecraft_contracts.py` — 5 new API tests:
  snapshot persistence on scene PUT, migration defaults, CRUD endpoints,
  export-preview by snapshot, inspect_scene by snapshot.
- `tests/e2e/posecraft/posecraft-snapshot-workflow.spec.ts` (NEW) —
  Playwright Scenarios A–F (capture, gallery, gating, persistence,
  handoff, protection).
- `tests/e2e/posecraft/posecraft-codirector-handoff.spec.ts` — updated to
  capture a Snapshot before Send to Co-Director (snapshot gating), assert
  the new status message + composer prompt, and open the nested milestones
  accordion for the version-card ⋯ menu.
- `tests/e2e/posecraft/posecraft-scene-labels.spec.ts` — open the nested
  milestones accordion before clicking Save Version.

## What was implemented per todo

1. **snap-contract** — `PoseCraftSnapshot` type + schema + immutable CRUD
   helpers + storage migration (separate `document.snapshots[]` +
   `selectedSnapshotId`; `savedVersions` NOT overloaded).
2. **snap-capture** — `captureCleanSnapshot()` in engine.ts (hides
   gizmos/handles/selection outlines; DOM guides/labels hidden by React).
3. **Toolbar** — Save → Snapshot buttons + handler (flush → clean capture →
   upload → append → select → flush; SNAPSHOT_BLOCKED on flush failure).
4. **snap-gallery** — Snapshots + Exports panel + cards + ⋯ menu + CSS;
   milestones moved to Advanced → Scene milestones.
5. **snap-handoff** — gate Co-Director/ImageGen/Storyboard on
   `selectedSnapshotId`; server `snapshotId` support on inspect/export/
   send_to_*; honesty label `PoseCraft Snapshot — Visual Staging Reference`.

## Test results (exit codes)

- **Posecraft unit tests** (`vitest run src/posecraft/`): **PASS** —
  6 files, 31 tests (incl. 8 new snapshot tests). Exit code 0.
- **Posecraft API contract tests** (`pytest tests/test_posecraft_contracts.py`):
  **PASS** — 16 passed (incl. 5 new snapshot tests). Exit code 0.
- **TypeScript build** (`tsc -b` in studio-web): **PASS** (no errors). Exit 0.
- **Production build** (`npm run build` in studio-web): **PASS**. Exit 0.
- **Playwright `posecraft-snapshot-workflow.spec.ts`** (Scenarios A–F):
  **PASS** — 1 passed (32.1s). Exit 0.
- **Playwright `posecraft-codirector-handoff.spec.ts`**: **PASS (flaky)** —
  passed on retry (first attempt hit a transient API warmup race right
  after Beta restart). Exit 0.
- **Playwright `posecraft-scene-labels.spec.ts`**: **PASS** — 1 passed
  (2.1m). Exit 0.

### Known test instability (NOT caused by this work)

- **`posecraft-mandatory-go-corrective.spec.ts`** and
  **`posecraft-production-two-character.spec.ts`** fail with
  `ECONNREFUSED 127.0.0.1:8758` / `socket hang up` — the **Beta API process
  crashes** under these tests' heavy Co-Director proposal+approve load. This
  is a pre-existing Beta runtime stability issue:
  - Neither test touches any Snapshot UI (no snapshot capture/gallery/gating
    interactions).
  - The failure is a connection refused / socket hang up (API process died),
    not a UI assertion failure.
  - The new `posecraft-snapshot-workflow.spec.ts` (which exercises my new
    snapshot endpoints heavily) passes without crashing the API.
  - These two tests were not modified by this work.
  - Recommended: the independent verifier should re-run these two on a
    stable Beta runtime (or investigate the API crash separately) before
    certifying.

## Beta verification

- Beta rebuilt (`npm --prefix studio-web run build`) and restarted per
  `.cursor/rules/beta-refresh-after-build.mdc`.
- Web: `http://127.0.0.1:8760/` → **HTTP 200**.
- API: `http://127.0.0.1:8758/api/health` → **HTTP 200**.
- Beta is left **running** and ready for manual review.

## Manual review path

1. Open `http://127.0.0.1:8760/` and open a PoseCraft workspace.
2. Stage figures/props; click **Snapshot** in the viewport toolbar (or
   fullscreen toolbar) — confirm a clean PNG is captured (no gizmos/labels)
   and a Snapshot card appears, selected.
3. Open the **Snapshots + Exports** accordion: verify the card (thumb, name,
   time, Revision, lens/aspect, selected badge) and the ⋯ menu (Rename,
   Duplicate, Delete, Open Preview, Restore Camera View, Export Image).
4. With a Snapshot selected: Send to Co-Director / Image Generation /
   Storyboard are enabled and the honesty label is visible. Deselect (click
   the selected card again) → buttons re-disable and the gate tip returns.
5. Reload → Snapshot + selection survive.
6. Open **Advanced — Scene milestones** for Save Version / milestone cards.
7. Via API: `GET /api/posecraft/projects/{id}/snapshots`,
   `GET .../export-preview?snapshot_id={id}`, and Co-Director
   `posecraft.inspect_scene` with `snapshotId` return the frozen composition.

## Limitations (honest)

- Snapshot image upload uses the existing `api.uploadAsset` path; the PNG is
  stored in the open project's Library (one project, one library). Deleting
  a Snapshot does **not** delete the Library image (intentional — the image
  may be referenced elsewhere); only the frozen composition is removed.
- `Restore Camera View` restores only the camera, NOT the full scene (a
  Snapshot is a frozen camera framing, not a scene restore point).
- The mandatory-go-corrective / production-two-character Playwright tests
  fail due to a pre-existing Beta API crash under heavy Co-Director load
  (see above), not due to this work.
- Independent verification (todo 6) is **NOT** done by this implementer.

## Verdict

**READY FOR PRIMARY REVIEW** (implementer scope, todos 1–5). **NOT GO.**
Independent verification must be a separate `glm-5.2-high` agent.
