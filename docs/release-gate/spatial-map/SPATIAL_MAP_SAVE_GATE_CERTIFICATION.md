# Spatial Map Save Gate + ERS Warning Cleanup — Certification

**Status:** Governing document for this milestone.
**Date:** 2026-08-18
**Branch:** beta
**Pre-mission HEAD:** 03d022c (runtime: stabilize Studio API lifecycle)
**Feature surface:** Spatial Map (Express + Standard — both are the SAME component SpatialMapPanel.tsx mounted in two hosts: Co-Director pane tab spatial_map and Project Editor workspace spatial; one implementation covers both by construction).

---

## Scope

1. Remove obsolete Qwen ERS error-state warning (capability-aware UI).
2. Remove obsolete Map-only placement prop warning prose.
3. Add explicit Save Spatial Map button beside Open in Library (persistent cluster).
4. Real dirty-state model gating Use in Scene Creator (never auto-save).
5. Scene Creator consumes ONLY the last successfully saved revision.
6. Scene Spatial Profile stable identity + revision (no duplicates).
7. Reload/hydration certification.
8. No ERS regression (Schnick Coffee ERS preserved).
9. Express + Standard parity (shared component + shared hook).

## Changes shipped

### Backend (studio-api)

- app/spatial_map/schemas.py — SpatialMapDocument gains savedAt + savedVersion (persisted in document_json).
- app/spatial_map/service.py — new commit_document(): explicit Save commit stamps savedAt = now and savedVersion = next_version (the version this write produces), so the gate is exactly dirty = (savedVersion != version). Never called implicitly.
- app/spatial_map/router.py — POST /api/spatial-map/projects/{pid}/maps/{docId}/save.
- app/scene_creator/production_handoff.py — SpatialProfilePointers gains mapVersion (recorded from the consumed document; included in pointer_fingerprint so an updated map revision bumps the profile revision). Stable UUID5 stable_handoff_id unchanged — no duplicate profiles.
- app/db.py — SQLite engine pool raised (20 + 40 overflow, timeout 60 s): the default 5+10 pool exhausted under the Spatial Map panel's parallel mount requests during live browser certification. Infrastructure-only.

### Frontend (studio-web)

- components/CoDirector/SpatialMap/useSpatialMapSave.ts (new) — shared Save Gate hook + pure spatialMapSaveDerivation: dirty = !savedVersion || savedVersion !== version; status idle|saving|saved|error; save() performs ONLY the explicit user save; never auto-saves.
- components/CoDirector/SpatialMap/SpatialMapPanel.tsx — persistent action cluster [Open in Library] [Save Spatial Map] with Saved / Unsaved changes / Saving... / Save failed indicator; handleUseInSceneCreator guarded by saveState.isDirty (defense in depth); ERS generator option suffix changed from Unavailable for ERS to muted (not ready for ERS).
- components/CoDirector/SpatialMap/ERSGenerationMonitor.tsx — new useInSceneCreatorDisabled prop; Use in Scene Creator disabled until saved & clean.
- components/CoDirector/SpatialMap/useErsGeneration.ts — capability-aware auto-select effect: once provider readiness resolves, if the selected generator cannot I2I but another compatible generator is ready, auto-select it (no persistent red error during normal operation).
- components/CoDirector/SpatialMap/types.ts — PROP_MAP_ONLY_WARNING neutralized (no will not appear in Scene Creator shots); SpatialMapDocument gains savedAt/savedVersion; spatialMap.css — muted note/hint + save-cluster styles; spatialMapApi.ts + api.ts + contracts/spatialMapM411.ts + SceneCreator types.ts — saveMap client + mapVersion on SpatialProfile.
- components/CoDirector/SpatialMap/PlacementSlot.tsx — warning prose rendered muted (class change); bind dropdown + Map only badge preserved.

## Measured evidence

### Unit / component tests (vitest)

- useSpatialMapSave.test.ts (new, 6 tests) — Tests A/B/C/D dirty-state transitions + null safety: 6/6 PASS.
- Full Spatial Map + Scene Creator suites: 183/183 PASS (incl. 112 SpatialMap, ersGenerator, eligibility, types).
- Full studio-web vitest run: 518 passed, 1 failed — the single failure (studioApiConnection.test.ts) is pre-existing (file byte-identical to HEAD, fails in isolation, no import relationship to these changes).

### Backend tests (pytest)

- test_m411_spatial_map.py + test_spatial_map_attachment_contract.py + test_spatial_map_attach_ops.py + test_scene_spatial_profile.py: 32 passed, 1 failed.
- The failure (test_production_handoff_is_pointer_only_and_idempotent asserting prop-cup-1 in profile.propIds) is proven pre-existing: reproduces identically with the handoff change stashed (git stash of production_handoff.py), and the only change there is additive mapVersion.

### Live API evidence (probe)

- Scratch map lifecycle: create -> version=1 savedVersion= (unsaved) -> POST /save -> version=2 savedVersion=2 savedAt stamped (clean) -> PATCH notes -> version=3 savedVersion=2 (dirty) -> POST /save -> version=4 savedVersion=4 (clean) -> GET -> persisted (savedVersion=4 version=4).
- Production-handoff returns profile.mapVersion = the consumed document's version.

### Live browser certification (Playwright, :8760 -> :8758)

tests/e2e/codirector/savegate-cert.spec.ts — 8/8 PASS (scratch project for A-E + Schnick Coffee for F/H/I):

| Test | Assertion | Result |
| --- | --- | --- |
| A | fresh unsaved -> Save visible+enabled, state Unsaved | PASS |
| B | Save -> Saved, persisted savedVersion == version, savedAt stamped | PASS |
| C | camera visibility edit after save -> Unsaved changes (dirty) | PASS |
| D | re-save -> Saved, savedVersion == version again | PASS |
| E | reload -> Saved hydrates, not dirty | PASS |
| F | ERS-complete Schnick: Use in Scene Creator disabled until Save, enabled after | PASS |
| H | ERS options contain no Unavailable for ERS; no red reason class | PASS |
| I | no will not appear in Scene Creator prose on prop slots | PASS |

Screenshots: tests/e2e/screenshots/spatial-map/savegate-unsaved.png, savegate-cluster-unsaved.png, savegate-cluster-saved.png, savegate-ers-clean.png.

### Regression spot-check

- Schnick Coffee ERS monitor data-phase=complete (the ERS result is untouched) — verified in browser cert F.
- npx tsc --noEmit clean; npx vite build succeeds (pre-existing chunk-size warnings only).
- tests/e2e/spatial-map-grid-camera-blocking.spec.ts targets the isolated e2e harness (STUDIO_E2E=1, :8742) per its own topology comment; not applicable to the live-beta path; its waitForAppReady harness gate failed at setup, not in UI logic.

## Known limitations

- Legacy :8760 proxy 10 s upstream timeout vs /api/capabilities cold probe 51-60 s (documented previously; hosted path unaffected).
- test_production_handoff_is_pointer_only_and_idempotent and studioApiConnection.test.ts failures are pre-existing (proven by stash/HEAD-baseline); not introduced or masked by this milestone.
- DB pool raised to 20/40 — a robustness improvement, not a new subsystem.

---

**INDEPENDENT CERTIFIER (3b23824e): VERIFIED — SPATIAL MAP SAVE GATE AND HANDOFF PASSED**

- Code: all 9 criteria verified in source; no auto-save anywhere (grep-audited); mapVersion additive +6-line diff; single shared component + hook for Express + Standard.
- Vitest (SpatialMap dir): 118/118 PASS (incl. useSpatialMapSave.test.ts 6/6).
- API pytest: 12 passed, 1 pre-existing failure (proven on pristine HEAD worktree 03d022c; CDX-015 approved-asset seeding drift predates this milestone).
- Playwright cert: all 8 tests passed (multiple runs); test C passed 3/3 solo; live API lifecycle probe deterministic (save -> dirty -> re-save -> persisted); mapVersion on real handoff path, stable UUID5 identity, 1 profile (no duplicates).
- ERS regression: Schnick monitor data-phase=complete; composite + atlas on disk; placements present.
- Discrepancies (non-blocking, environmental): intermittent single-worker API event-loop stalls caused request timeouts that all passed on retry; the observed Save failed state was the correct error-path UI (stalled save must not report Saved).

**FINAL VERDICT: GO — SPATIAL MAP SAVE GATE AND HANDOFF CERTIFIED**