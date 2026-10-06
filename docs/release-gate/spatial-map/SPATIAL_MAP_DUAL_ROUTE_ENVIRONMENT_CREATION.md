# Spatial Map Dual-Route Environment Creation

**HISTORICAL for Co-Director entry.** Co-Director Spatial Map empty-state is now governed by `CODIRECTOR_SPATIAL_MAP_EXPRESS_FINALIZATION.md`. This document remains historical truth for the Standard three-route surface and the design/reconstruct/supplied geometry-source contract.

Historical Qwen supplementary-view reports remain NO-GO and are not current production truth.

## Product split

```text
GPT Image 2  = design the environment you want     (geometrySource = designed)
MoGe-2/VGGT  = reconstruct the environment you have (geometrySource = reconstructed)
Existing Atlas = use the plate you already have     (geometrySource = supplied)
```

Qwen Image Edit is out of the critical Atlas path. Improve Spatial Understanding is not a production Express/Standard control.

## Authority

- designed: Environment Design Packet / SceneIntent is spatial authority; Atlas is visualization.
- reconstructed: MoGe/VGGT packet is geometry evidence. Preserve observed / inferred / unknown.
- supplied: user asset.

INFERRED + INFERRED ≠ OBSERVED. Generated views never count as VGGT evidence.

## Surfaces

Express and Standard share one backend and three start routes.

Local review: `http://127.0.0.1:5173/` (Vite), `http://127.0.0.1:8758/` (Studio API). Never `:8760`.

## Evidence

- Routing + Atlas generate unit/API: `studio-api/tests/test_spatial_dual_route.py` 15 passed; `test_atlas_generate_i2i.py` + intent tests passed.
- Frontend: Spatial Map panel + start chooser 17 passed. Prop Creator + Scene Creator contracts 20 passed.
- Playwright UX: `tests/e2e/codirector/spatial-map-dual-route.spec.ts` 1 passed (three-route surface or active Atlas; no Improve Spatial Understanding).
- Auditors: [product/routing](2e9a3c3d-f247-4c7f-8ac7-7e22f1191398) READY FOR PRIMARY REVIEW (one BLOCK repaired: observed image beats generic design wording). [geometry](0a7653e1-2807-444c-9071-a7b85974d887) READY FOR PRIMARY REVIEW, no BLOCKs.
- Peers: [architecture](34529ca0-8a7b-4a48-a4f7-228d155e604e) PASS. [lifecycle](a0147f25-6e94-40e0-bc63-e3d822b3472e) PASS after repair tickets A–C.

## Remaining blockers for the full live GO

- Live Express GPT Image 2 Atlas generate (paid API, visual gate, persist) was not executed in this session.
- Live Express MoGe-2 one-image reconstruct (GPU ~54s, deterministic Atlas, persist) was not executed in this session.
- VGGT-1B-Commercial weights remain `MODEL_ACCESS_GATED`. Standard multi-view is contract-tested, not live-unlocked.
- Studio API supervisor reused an existing `:8758` PID after Python changes. Recycle Studio API before live generate/reconstruct runs.

## Verdict

**E2E BLOCKED — LIVE GPT IMAGE 2 DESIGN GENERATE AND LIVE MOGE-2 RECONSTRUCT NOT EXECUTED; VGGT WEIGHTS GATED**
