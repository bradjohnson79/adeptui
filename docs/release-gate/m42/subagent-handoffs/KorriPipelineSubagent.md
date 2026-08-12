# Subagent Handoff

## Assignment
KorriPipelineSubagent — read-only wiring audit of Character Creator visual-sheet path (API + UI). Contract: `docs/release-gate/m42/subagent-assignments/KorriPipelineSubagent.md`.

## Scope completed
- Confirmed seed → generate → advance → owner-approve routes in `character_identity/api.py`.
- Confirmed `visual_sheet.py` enqueues real jobs, attaches roles, and `heal_pack_references` runs on pack GET / `list_references`.
- Confirmed UI uses current `project.id` for seed/generate (`CharacterProfileWorkspace`, `TimelineCharacterCreatorPanel`).
- Observed live primary-agent E2E on project `Korri Character Production` (`e32dae30-…`) with 15 roles and `OWNER_APPROVED`.

## Files changed
None (investigation / observation only).

## APIs consumed
- `POST /api/projects/{id}/characters/seed-korri`
- `POST .../visual-sheet/generate|advance|owner-approve`
- `GET .../visual-sheet`
- `GET .../references` → `{ items: [...] }` (15 after heal)

## APIs changed
None.

## Tests run
Primary live cert: `scripts/m42_w43_korri_visual_sheet_cert.py` (stable project policy).

## Test results
`passed: true`, `mock: false`, 15 roles, `OWNER_APPROVED`. Evidence: `artifacts/m42/governance/korri-e2e/`.

## Manual checks
Reload GET after cert: pack status `OWNER_APPROVED`, 15 `roleAssets`, 15 reference items.

## Evidence
- `artifacts/m42/governance/korri-e2e/cert-run.log`
- `artifacts/m42/governance/korri-e2e/visual_sheet_results.json`
- `artifacts/m42/governance/korri-e2e/reload-proof.json`

## Known issues
- Voice Performance readiness on this fresh project shows `approvedVoice: false`, `promptPackageAttached: false`, `readyForPerformance: false` — expected until Voice approve / prompt package attach (Voice track, not Character Creator image blocker).

## Risks
- Historical disposable `M42 W43 Korri Visual *` projects remain in the library from pre-policy certs (policy fixed going forward).

## Dependencies still pending
- ComfyWorkflowSubagent peer confirmation of builder/registry (code already on VAEEncode path).

## Recommended integration checks
- UI Character Profile category tabs show images via `api.assetUrl` for each role.
- Second open of project preserves sheets (reload-proof).

Ready for integration review.

---

## Independent explore verification

[Korri pipeline audit](cd56c131-499e-4b2f-8a9d-2758a3c420b2) (read-only) confirmed real non-mock wiring, heal-on-read, and category galleries from reference roles. It flagged that full pack progression requires repeated `visual-sheet/advance` and that the Timeline rail starts generate but does not expose advance/approve.

**Primary-agent resolution:** Not a Character Creator Comfy blocker. Live cert + Character Profile `VisualGatesPanel` drive advance → `READY_FOR_OWNER` → owner-approve (proven: 15 roles, `OWNER_APPROVED`). Timeline-only autonomy remains a UX follow-up, not a reopening of the Korri hard-stop GO.
