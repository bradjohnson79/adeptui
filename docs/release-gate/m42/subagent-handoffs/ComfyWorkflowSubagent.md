# Subagent Handoff

## Assignment
ComfyWorkflowSubagent — read-only audit of `zimage.txt2img` / `zimage.ref_edit` builders and registry. Contract: `docs/release-gate/m42/subagent-assignments/ComfyWorkflowSubagent.md`.

## Scope completed
- `build_zimage_ref_workflow` documents and uses `LoadImage → ImageScale → VAEEncode → KSampler(denoise<1)` with text-only Omni (avoids EmptyLatentImage shape crash).
- Character Creator visual sheet uses workflows `zimage.txt2img`, `zimage.ref_edit`, `character_sheet` (live cert evidence).
- Unit guard present: `studio-api/tests/test_zimage_ref_edit_latent_fix.py`.
- Live cert completed with `comfyOk: true`, `mock: false`, 15 roles — no mock asset path observed.

## Files changed
None.

## APIs consumed
Indirect via visual-sheet job enqueue → Image Product → ComfyUI `:8188`.

## APIs changed
None.

## Tests run
Live Comfy path exercised by primary E2E cert (2026-07-31). Unit file reviewed (not re-run in this handoff window).

## Test results
Live pack: details + performance phases completed (roles advanced through `details` and `performance`), proving `zimage.ref_edit` path executed.

## Manual checks
Comfy `/system_stats` returned HTTP 200 during beta READY/DEGRADED recovery and E2E.

## Evidence
- `artifacts/m42/governance/korri-e2e/visual_sheet_results.json` (`comfyOk`, workflows list)
- Code: `studio-api/app/workflows/image_tools.py` `build_zimage_ref_workflow`
- Registry: `config/image-workflows/certified-registry.json`

## Known issues
None blocking Character Creator path.

## Risks
- Registry `lru_cache` requires beta restart after fingerprint edits (ops note).

## Dependencies still pending
None for this scope.

## Recommended integration checks
- Keep cert `mock: false` assertion.
- Re-run latent unit test after any Omni/latent graph change.

Ready for integration review.

---

## Independent explore verification

[Comfy workflow audit](48d690f3-207d-42ab-bd9a-068338308b9a) (read-only) confirmed: VAEEncode img2img path, certified registry entries for `zimage.txt2img` / `zimage.ref_edit`, pack `mock: false`, and non-mock txt2img fallback only when source asset is missing. Aligns with primary live E2E (15 roles, details/performance phases completed).
