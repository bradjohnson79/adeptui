# Co-Director Spatial Map Express Finalization

**Historical for the Local/API Express form.** Current governing document: `SPATIAL_MAP_API_ONLY_PRODUCTION_CERTIFICATION.md`. The prior dual-route start chooser remains historical for Co-Director entry. Standard remains the Home / Production Spatial Map workspace.

## Product split

```text
Co-Director Spatial Map tab = Express only
Home card + Production dropdown spatial workspace = Standard
```

No Express / Standard toggle inside Co-Director.

## Express empty state

```text
How would you like to create your Spatial Map?
Generation Method [ Local | API ]
Environment Description (?)
[ Select from Library ] [ Upload Reference Image ]
[ Generate Spatial Map ]
```

Local helper: **Local uses Adept’s local spatial reconstruction pipeline.** Do not name MoGe or VGGT.

## Generate readiness

- Local: requires a project-scoped reference.
- API: requires GPT Image 2 configured and at least a description or reference.

API Atlas engine is GPT Image 2 only. No silent Qwen / Z-Image / FLUX substitute.

## Downstream

Successful generation transitions into the existing Spatial Map workspace (characters, props, cameras, 1 m grid, Save, ERS). Do not rebuild those systems.

## Local review

`http://127.0.0.1:5173/` (Vite), `http://127.0.0.1:8758/` (Studio API). Never `:8760`.

## Evidence

- Frontend unit: `expressReadiness`, Express form, StartChooser, SpatialMapPanel, Prop Creator contracts, Scene Creator contracts — **42 passed**.
- Backend unit: `test_spatial_dual_route.py` + `test_atlas_generate_i2i.py` — **21 passed**.
- Playwright: `spatial-map-express-entry.spec.ts` + `spatial-map-dual-route.spec.ts` — **4 passed**. Named project already has an Atlas, so empty-form generate/upload branches annotated and skipped rather than deleting the production map.
- Auditors: frontend/wiring [READY FOR PRIMARY REVIEW](9e807d79-0a1f-448a-a093-2a741c62c7dd); backend/routing [READY FOR PRIMARY REVIEW](76812b1a-d4dc-4bee-9ed7-2a973d9e66fd).
- Peers: [PASS](650b9962-0deb-466c-a1df-0f630e581231), [PASS](6ae9a6bd-fc0d-40b7-9f0d-f1e5ce7e4fa2).
- Comfy MCP: N/A — Local Express reconstruct is the Spatial Map pipeline, not Comfy.
- Runtime: `http://127.0.0.1:5173/` Vite 200; `http://127.0.0.1:8758/api/healthz` 200.

## Remaining blockers for the full live GO

- Live Express empty-form Local generate (reference → local pipeline → GenerationJob → workspace) was not executed: the named project already has an Atlas and this mission must not wipe it.
- Live Express API GPT Image 2 generate was not executed in this session.
- VGGT weights remain gated if multi-view is later requested on Standard.

## Verdict

**E2E BLOCKED — LIVE EXPRESS EMPTY-FORM LOCAL/API GENERATE NOT EXECUTED ON THE NAMED PROJECT ATLAS**
