# Subagent Handoff

## Assignment
LibraryScopeSubagent — one-project / one-library policy for Korri certs and character generations. Contract: `docs/release-gate/m42/subagent-assignments/LibraryScopeSubagent.md`.

## Scope completed
- `scripts/m42_w43_korri_visual_sheet_cert.py` uses `_resolve_stable_project()` with `Korri Character Production` / `ADEPT_PROJECT_ID` (no per-run UUID project names).
- `scripts/m33j_korri_create_from_brief.py` reuses the same stable name and existing Korri slug.
- `.cursor/rules/creator-first-ui.mdc` contains “One project, one library” clause.
- UI copy states generations stay in the open project’s Library.
- Live cert created/used `Korri Character Production` (`projectReused: false` on first creation; subsequent runs will reuse).

## Files changed
None in this investigation pass (policy already implemented prior to governance sprint).

## APIs consumed
`GET/POST /api/projects` for stable resolve.

## APIs changed
None.

## Tests run
Live cert run under `ADEPT_KORRI_PROJECT_NAME=Korri Character Production`.

## Test results
Project id `e32dae30-a014-4ea4-a2f2-69f4b7809bde`, name exact match, all 15 assets on that project.

## Manual checks
Listed projects: many historical disposable Korri Visual projects remain; new policy prevents further spam.

## Evidence
- `artifacts/m42/governance/korri-e2e/visual_sheet_results.json` (`stableProjectPolicy`, `projectName`)
- `artifacts/m42/governance/korri-e2e/cert-run.log`

## Known issues
- Pre-policy disposable projects still clutter Home/Library lists (cleanup optional; not required for GO).

## Risks
- Operators running old cert script versions without pull would reintroduce spam.

## Dependencies still pending
None.

## Recommended integration checks
- Second cert run should set `projectReused: true` against the same name.

Ready for integration review.

---

## Independent explore verification

[Library scope audit](c995784d-5496-460f-bd2b-a159c604646f) (read-only) confirmed stable-project reuse and UI `project.id` scoping. Non-blocking risk: if multiple projects share the name `Korri Character Production`, cert scripts may pick different IDs — prefer `ADEPT_PROJECT_ID` or keep a single stable project.
