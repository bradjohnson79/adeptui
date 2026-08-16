# Spatial Map Final Production Certification — ERS Source-Lineage Grounding

**Date:** 2026-08-15
**Branch:** `beta`
**HEAD at cert write:** `e4e88a1`
**Scope:** ERS semantic grounding (living-room defect), Scene Intent snapshot, preview/parity, semantic gate, staleness, Scene Creator handoff.
**Supersedes:** `SPATIAL_MAP_ERS_GENERATION_CERTIFICATION.md` (that report's chain is preserved; this document governs ERS grounding going forward).

## Verdict

**GO — ERS SOURCE-LINEAGE GROUNDING CERTIFIED END TO END ON LIVE BETA**

Independent visual verifier: **VERIFIED — ERS depicts the intended café environment** (café counter, espresso equipment, seating, menu boards across ERS panels; multi-panel production sheet; consistent with original "Korri Coffee House" reference and Atlas shot; no living-room content).

The original defect (ERS depicting a generic living room for the Schnick Coffee project) is repaired and certified against recurrence.

## Root cause (recap)

The compiled Qwen ERS prompt contained no café content: sheet description defaulted to `"Programmatically composed environment reference sheet."`, `masterEnvironmentPrompt` was empty, and source pixels were stripped at four layers. Atlas generation sent `context: {}` — no description, no source-image linkage. Qwen 2512 is architecturally T2I-only, so no pixel path existed to rescue semantic grounding.

## Fix architecture

Every Atlas Shot now snapshots a compact **Scene Intent JSON** at creation time (CD-assisted and Manual/Express paths share one contract):

- `scene_intent.py` — `SceneIntent` contract, deterministic builder, light validation rejecting empty/generic descriptions, `merge_scene_description_edit` preserving curated fields so `groundingFingerprint` round-trips.
- `SpatialMapDocument` carries `sceneIntent`, `originalEnvironmentReferenceAssetId`, `originatingUserPrompt`, computed `groundingFingerprint`; the same JSON is stamped into the atlas asset `prompt_meta_json`.
- `atlas_generate` accepts `attachment_asset_ids` + `scene_description`/`scene_intent` (dispatcher plumbed); manual/Express Atlas requires a Scene/Location Description with client-side validation.
- `ers_generate` resolves grounding in priority order (Scene Intent → original source asset → atlas → spatial state), populates the sheet `EnvironmentProfile` from intent, and stamps `sceneIntent`/`atlasAssetId`/`groundingAssetIds`/`groundingFingerprint` into provenance.
- `ers_compiler` prepends a source-grounding authority preamble (PRIMARY ENVIRONMENT IDENTITY, "do not replace with generic living room", exemplars are structure-only); `ERS_SPEC.md` gained the binding do-not-copy clause.
- Two-mode conditioning: Qwen = honest T2I text grounding (no silent fallback, no I2I carve-out); explicit GPT Image 2 = pixel grounding via Kie `input_urls` (original image + atlas + layout exemplars) using `settings.public_api_base_url`.
- `queue_worker` ERS commit hook persists Scene Intent lineage onto the asset and emits `derived_from` lineage edges (ERS → atlas → original image), then runs the advisory semantic gate.
- Semantic gate: `codirector/vision/ers_gate.py` (Kie Gemini VLM, `PASS | ERS_LAYOUT_NONCOMPLIANT | ERS_CONTEXT_NONCOMPLIANT | NOT_VERIFIED`, honest degrade — never a fake pass), verdict stamped on sheet provenance; Retry / Use Anyway creator override endpoint + UI.
- Staleness: sheet fingerprint vs document `groundingFingerprint` mismatch → "Needs Regeneration" banner, no auto-spend; restoring the description clears the banner (fingerprint round-trip proven by E2E test 9).
- Scene Creator workspace payload carries `scene_intent` snapshot from sheet provenance.

## Live local trace (Schnick Coffee, project 2347bf46)

- Map `6bc36d92-d21a-4c2f-b85f-71d1f6aa9081` — Scene Intent backfilled in place (`scripts/schnick_scene_intent_backfill.py`): `Schnick Coffee / coffee_shop`, Korri + coffee cup, `originalEnvironmentReferenceAssetId=4d3062e8`, fingerprint `ca3c670695a051ce`. Placements v91 preserved (Korri + attached cup + C1/C2/C3).
- Grounded ERS generated live through Qwen Image (Local): sheet `db095959-5678-4f11-98d1-e93e0810d119`, composite asset `21927403-e090-49dc-ab03-3169d446fd1f` (1280×720, ~1.28 MB).
- Provenance on the sheet: `sceneIntent`, `atlasAssetId=caa72759-d965-41f9-b1d5-77cdcf9b9614`, grounding asset ids, fingerprint.
- Semantic gate ran post-persist and stamped `NOT_VERIFIED` with `vlm_error` — correct honest-degrade behavior: the Kie account key is not authorized for `gemini-*` VLM models (external account limitation, not a code defect). No fake pass.
- Scene Creator handoff: workspace `resolved_ers` carries composite `21927403` + `scene_intent` snapshot (E2E test 10).

## Independent visual verification

Verifier compared generated ERS `21927403` vs original reference `4d3062e8` ("Korri Coffee House") vs Atlas `caa72759`:

- Environment identity: café — counter, espresso equipment, seating, menu boards across panels. No residential/living-room content.
- Structure: multi-panel production reference sheet (wide + angle views of the same space).
- Consistency: same warm coffee-house identity, comparable architecture and palette.
- Labels: coherent, legible captions.

**VERIFIED — ERS depicts the intended café environment.**

## Tests

- Unit/integration: `test_ers_scene_intent_grounding.py` + `test_ers_knowledgebase_compiler.py` + `test_ers_image_product.py` — **35 passed**.
- Playwright `tests/e2e/spatial-map-ers-scene-handoff.spec.ts` against live Beta (8760 web / 8761 API): **10 passed (38.3s)** —
  1. panel/grid load; 2. entity regression (chars=1 props=1 cams=3 still placed); 3. observe-only leftover-complete ERS present; 4. reload persistence; 5. Scene Creator slot bound to this ERS; 6. preview consumption carries `ers_composite_asset_id`; 7. Scene Intent lineage (map snapshot, sheet provenance, Scene Context UI); 8. generator select defaults to Qwen Image (Local), GPT Image 2 optional, Express/Standard parity (shared panel); 9. staleness — edit marks Needs Regeneration, restore clears (fingerprint `ca3c… → 2f02… → ca3c…`); 10. Scene Creator handoff carries Scene Intent + provenance.
- Frontend build: `tsc -b && vite build` clean; Beta serves fresh bundle `index-DzzMtB5O.js` (HTTP 200 on 8760 + 8758).

## Commit

`e4e88a1` — `feat(spatial-map): ERS source-lineage grounding via Scene Intent snapshot` (39 files, +5261/−195). Includes the previously untracked knowledgebase (`ERS_SPEC.md` + exemplar PNGs) — clean-clone blocker fixed.

## Known limitations (honest)

- VLM semantic gate currently degrades to `NOT_VERIFIED` because the Kie account key lacks `gemini-*` authorization; gate behavior itself is certified (advisory, honest, overridable). Obtain an authorized key to enable live PASS/FAIL verdicts.
- Qwen remains T2I-only; pixel-grounded ERS requires explicit GPT Image 2 selection (by design; no silent substitution).
- Semantic gate verdicts are advisory; creator override (Use Anyway) is recorded in provenance.

## Boundaries

This certification covers the Spatial Map → ERS → Scene Creator grounding chain only. Not Image Core complete, not Timeline, not Avatar. Production Character Creator candidate counts unchanged.
