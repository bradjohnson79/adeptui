# Qwen Supplementary Environment View Assist

**Governing document for this mission.**  
**Version:** 2026.08.1

Qwen Image Edit is **not** the Atlas camera. MoGe-2 / VGGT reconstruct geometry. The deterministic renderer creates the Atlas. Qwen may add up to two inferred viewpoints for Co-Director reasoning only.

## Verdict

`NO-GO — QWEN SUPPLEMENTARY ENVIRONMENT VIEW ASSIST NOT CERTIFIED`

This is **not** `GO — ADEPT UI GEOMETRY-BASED SPATIAL MAP ATLAS PRODUCTION CERTIFIED`.

Live sequential `qwen2512.ref` ran on Adept Stability Cert. View A completed and stayed `INFERRED`. View B completed as a real Comfy job and failed the structure gate (near-solid color) on both the first live attempt and a seeded regenerate. Owner review: the two additional views do **not** help understand this corridor without contradicting or collapsing the source.

Do not promote this as an optional Express enhancement.

## Laws

- One Qwen generation per camera. No 4-grid sheet.
- Observed master remains highest authority.
- **INFERRED + INFERRED ≠ OBSERVED.**
- `FAIL_NO_INFORMATION_GAIN` if the camera does not expose new spatial relationships.
- Near-solid / no-structure outputs `FAIL` and cannot be accepted for spatial reasoning.
- View B targets remaining uncertainty after Master + accepted View A.
- Inferred views never satisfy VGGT’s 2-observed minimum.
- Experimental A/B isolation only: Atlas source-color pixels stay identical when MoGe inputs are identical.

## Live run (observed)

| Fact | Value |
|---|---|
| Project | Adept Stability Cert `2bc632b8-b329-4d3b-bc40-b68dc41b6bb1` |
| Map | `e6f64c3b-2533-4549-a476-bf0dcb90d298` |
| Master | copy of SenseNova corridor `1211dd83-e3f6-4d17-bf2b-669ec5961418` → `9f7d4571-9444-41fa-b4c2-29c27919736a` |
| Purpose / graph | `environment_supplementary_view` / `qwen2512.ref` |
| View A | `REVERSE`, job `93cb3124-…`, prompt `05a5f6e9-…`, asset `26dca283-…`, gate `PASS`, accepted for reasoning |
| View B (seeded regen) | `LEFT_SIDE`, job `f2dce012-…`, prompt `86b7c5e6-…`, ~129s, gate `FAIL` near-solid color, not accepted |
| Observed IDs after A+B | `[9f7d4571-9444-41fa-b4c2-29c27919736a]` only |
| Geometry A/B | `geometryPixelsIdentical: true` |

Owner question (not pretty): **Do these two additional views actually help me understand this environment better without contradicting the source?**

Answer: **No.** View A is a cyan restyle of the same facing corridor, not a clear reverse camera. View B is an unusable red field. Master wins.

## Implementation

- Purpose: `environment_supplementary_view` / `ENVIRONMENT_SUPPLEMENTARY_VIEW`
- Graph: certified `qwen2512.ref` (same family as ERS, distinct purpose — compile no longer rewrites this to ERS)
- Packet + document field: `supplementaryViews`; `sourceAssetIds` stay observed-only
- Job hydration reads `params_json.output_asset_id` and `comfy_prompt_id`; treats Studio job status `done` as success
- APIs under `/api/spatial-map/projects/{pid}/maps/{mapId}/supplementary-views`
- UI: Improve Spatial Understanding on Spatial Map (`http://127.0.0.1:5173/`)

## Tests

- `studio-api/tests/test_supplementary_views.py`: **16 passed**
- Playwright against Vite `http://127.0.0.1:5173/` + API `http://127.0.0.1:8758/`:
  - Improve Spatial Understanding panel / observed authority: **passed**
  - Live hydrate on Adept Stability Cert map (inferred A persists after reload; observed IDs stay master-only): **passed**
- Controlled A/B: `docs/release-gate/spatial-map/evidence/supplementary_views/ab_compare.json` — `geometryPixelsIdentical: true`

## Owner review strip

`docs/release-gate/spatial-map/evidence/supplementary_views/owner_review_strip.png`

Observed Master | Qwen View A | Qwen View B | MoGe Atlas | Reasoning Summary

Not geometry evidence.

## Limitations

- Information-gain / structure gates are pixel heuristics, not a VLM.
- Qwen `LEFT_SIDE` on this corridor produced a near-solid red field twice.
- View A passed pixel-delta but did not prove a true opposite-camera transform.
- Contact sheet / owner strip are UI/cert artifacts only.

## Peer review

- [GLM 5.2 architecture](441d9324-c277-44fd-9795-d7f154728cea): `READY FOR PRIMARY REVIEW` — observed/inferred isolation, packet, MoGe authority, and qwen2512.ref pin held; no silent ERS rewrite or Z-Image fallback.
- [Kimi K3 lifecycle](03f2e2c2-b836-4283-a178-70f6fc6a749b): `READY FOR PRIMARY REVIEW` — VGGT contract binding, no false-observed path, persist is document-backed, Playwright and owner strip match the NO-GO. Flagged that this work is still uncommitted (primary commit decision only).

## Promotion

Keep unimplemented-as-default. Do not promote. Revisit only if a later live run produces two views that clearly expose hidden spatial relationships without restyling or collapsing the master.
