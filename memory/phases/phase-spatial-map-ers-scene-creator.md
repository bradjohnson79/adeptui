# Phase: Spatial Map + Atlas Shot + ERS + Scene Creator

## Date
2026-08-11

## Branch / SHA
- Branch: `beta`
- HEAD: `4d899b4` (`feat(spatial): Spatial Map + Atlas Shot + ERS + Scene Creator`)
- Deployment: `https://adeptui-5uunxq106-anoint.vercel.app` (Production, Ready)

## Scope
Four-part spatial-continuity and scene-generation workflow integrated into Co-Director Project Building:
1. ATLAS SHOT - roofless top-down environment reference
2. SPATIAL MAP - 2D scene layout (10x10 grid) with character/prop placement
3. ENVIRONMENT REFERENCE SHEET (ERS) - deterministic composite from real directional views
4. SCENE CREATOR - scene image generation from ERS + shot requests

## Frozen Workflow
```
Story -> Script Writer -> Character Creator -> Atlas Shot / Master Environment
    -> Spatial Map -> ERS -> Scene Creator -> Timeline Generator
```

## Data Contracts (frozen in `studio-api/app/spatial_map/ers_contracts.py` + `schemas.py`)
- `SpatialPlacement` extension: `gridRow`, `gridColumn`, `slotIndex`, `colorKey`, `miniPrompt`, `tag`
- `EnvironmentReferencePackage`: atlas_asset_id, directional_assets{N,E,S,W}, ers_composite_asset_id, placements, orientation="atlas-north-up"
- `ShotRequest`: index, raw_text, character_ids, prop_ids, framing, angle, orientation, additional_instructions
- `SceneGenerationBatch`: id, project_id, ers_package_id, shot_requests, output_count, result_asset_ids, collection_id
- `@` resolver: SAVED Character Profiles only; longest exact match; primary UX = picker
- `#` resolver: project prop entities with Library image; normalized tags
- Capabilities: `atlas.generate`, `ers.generate`, `scene.generate`
- Surface types: `atlas_shot_generation`, `ers_generation`, `scene_generation`

## Key Files

### Backend
- `studio-api/app/codirector/capabilities/handlers/{atlas,ers,scene}_generate.py` - capability handlers
- `studio-api/app/codirector/entity_resolver.py` - @/# entity resolution, shot parser, prompt compilation
- `studio-api/app/codirector/execution/scene_shot_collection_builder.py` - Library collections for scene shots
- `studio-api/app/scene_creator/{router.py, timeline_handoff.py}` - REST API + Timeline handoff
- `studio-api/app/spatial_map/{ers_contracts.py, ers_persistence.py}` - ERS contracts + persistence
- `studio-api/app/spatial_map/{schemas.py, models.py, router.py, service.py}` - Spatial Map core (reused/extended)
- `studio-api/app/environment_reference_sheet/` - ERS orchestrator + composite renderer (reused)
- `studio-api/app/codirector/capabilities/registry.py` - 3 new capability definitions
- `studio-api/app/codirector/routing/{deterministic.py, unified_intent.py}` - routing patterns
- `studio-api/app/codirector/{service.py, project_context.py}` - context enrichment

### Frontend
- `studio-web/src/components/CoDirector/SpatialMap/` - SpatialMapPanel, SpatialGrid, PlacementSlot, EntityPicker, ErsResultDisplay, spatialMapApi, types, spatialMap.css
- `studio-web/src/components/CoDirector/SceneCreator/` - SceneCreatorPanel, ShotRequestInput, SceneResultGrid, SceneResultCard, ErsSelector, sceneCreatorApi, types
- `studio-web/src/components/CoDirector/navEntries.ts` - `spatial_map`, `scene_creator` in ContentTab + CONTENT_NAV (between "characters" and "library")
- `studio-web/src/components/CoDirector/CoDirectorProjectContent.tsx` - renders panels
- `studio-web/src/components/CoDirector/AgentWorkSurface/types.ts` - 3 new SurfaceType entries

### Tests
- `tests/e2e/codirector/spatial-scene-creator.spec.ts` - 970-line Playwright suite (S77-S89)

### Docs
- `docs/release-gate/spatial-map/SPATIAL_MAP_ATLAS_ERS_SCENE_CREATOR_COMPLETION_REPORT.md` - governing milestone report

## Character/Prop Slot Colors (frozen)
- Character 1 = Red, Character 2 = Blue, Character 3 = Orange, Character 4 = Green
- Prop 1 = Purple, Prop 2 = Brown, Prop 3 = Aqua, Prop 4 = Gray
- Accessible label required in addition to color

## Product Laws (25 consolidated)
1. Atlas Shot establishes spatial geography.
2. Atlas Shot is normally an input to Spatial Map.
3. Spatial Map is a 2D scene graph, not 3D.
4. Spatial Map is authoritative for placement.
5. `@` references saved Characters.
6. `#` references project Props with Library image references.
7. One cell = one explicit placement.
8. Character Creator owns Characters.
9. Library owns media.
10. ERS owns environment continuity package.
11. Scene Creator produces scene image assets.
12. Timeline remains downstream.
13. Co-Director orchestrates but does not own project truth.
14. Real generation only.
15. No fake progress.
16. No fabricated physical measurements.
17. Manual UI and Co-Director converge on same backend services.
18. Reuse before rebuild.
19. No partial/false GO.
20. A test not run is not a pass.
21. Queued is not completed.
22. Main agent double-checks implementation.
23. Independent verifier must pass.
24. Generated imagery cannot rewrite Spatial Map truth.
25. ERS final sheet is deterministic composition of real assets.

## Verification Status
- Implementation: COMPLETE (52 files, +9555/-2)
- Backend runtime: ONLINE (200 OK, RTX 5090, 56 capabilities)
- Frontend nav: VERIFIED (correct order, tabs render)
- Independent verifier (Subagent J): VERIFIED
- Playwright E2E: DEFERRED (Ollama hang, not code defect)
- Live GPU generation: DEFERRED (env blocker)
- Deployment: LIVE (Vercel Production Ready)

## Verdict
READY FOR MANUAL BETA REVIEW

## Environment Blockers (not implementation defects)
- Ollama `qwen3.6:35b-a3b` not loading into memory (`ollama ps` empty; 5-token generation times out at 60s)
- Vercel deployment SSO-gated (use local Vite for automated testing)
- Local :8760 web server retired (Law #15); use `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173` + `STUDIO_API_PORT=8758`
