# Pack Install Workflow Fix

## Root cause

In `studio-api/app/setup/orchestrator.py`, `_checkpoint_for` always returned `_link_existing_checkpoint` for `asset_pack` components — including first-time **Download and Install**. That checkpoint text required `pack.json` and rejected empty folders, so new installs used Link Existing validation/UX.

## Fix summary

Download/Install and Link Existing are now separate workflows with distinct checkpoints, validation, UI actions, and staging.

### Install-folder vs link-folder validation

| | Download and Install / Choose Install Location | Link Existing Folder |
|---|---|---|
| Empty folder | Allowed | Rejected (`empty_folder`) |
| `pack.json` | Not required before download | Required |
| Pack ID / version | Checked after download (or reject incompatible existing `pack.json`) | Must match pack ID and supported version |
| Download / overwrite | Downloads into staging, promotes after verify | No download; bind only |
| Checkpoint copy | “Choose an empty folder or create a new folder…” | “Choose a folder that already contains this pack… pack.json required” |

### Why the server became unavailable

Pack install failures could surface as uncaught thread exceptions; aggressive FE polling kept hitting a dead API (`ERR_CONNECTION_REFUSED`). Mitigations:

1. Broad try/except around download/extract/GitHub/checkpoint paths; persist failed op state before returning
2. `sys.excepthook` / `threading.excepthook` / asyncio handler log stacks; thread hook does not kill the process
3. Staging always cleaned up; empty failed destinations removed so they do not look like linked installs
4. FE exponential backoff via `nextPollDelayMs` after consecutive network failures

### Interrupted operation recovery

Operations are persisted on create/update/pause/finish. On API restart, `_ensure_loaded` and `recover_stale_operations()` convert queued/running/configuring/awaiting_checkpoint (etc.) to `interrupted` + `recoverable`. UI is not left on “Estimating…” / “Configuring…”; user can Retry, Check Again, Choose Install Location, or Link Existing.

### GitHub diagnostics

`GitHubReleasePackProvider.diagnose_releases` reports owner, repository, release API path (no scheme/tokens), repo found, release counts, drafts/prereleases, selected tag, asset names, expected `{pack_id}-*.release.json` pattern, and selection reason. Source order: explicit pack URL → GitHub env → Hugging Face (not implemented) → “Download source not configured”. Link Existing is fallback-only when remote fails.

## Files changed

- `studio-api/app/setup/orchestrator.py` — split checkpoints; install vs link flows; `start_choose_install_location`
- `studio-api/app/setup/pack_install.py` — `validate_install_destination`, stronger `link_existing_pack`, pack-root `.adept-staging/<op>`
- `studio-api/app/setup/operations.py` — persist + recover stale ops
- `studio-api/app/setup/pack_providers/github_releases.py` — enriched diagnostics
- `studio-api/app/setup/pack_manifests.py` — refresh source order + diagnostic fields
- `studio-api/app/setup/status.py`, `diagnostics.py` — action labels / pack actions
- `studio-api/app/main.py` — exception hooks + startup recovery
- `studio-api/app/routers/extra.py`, `setup/__init__.py` — choose-install-location route
- `studio-web/src/components/SetupWizard.tsx`, `setup/helpers.ts`, `setup/types.ts`, `api.ts` — actions, copy, polling backoff
- Tests: `tests/test_pack_install_workflows.py` (+ updates to related pack tests)
- `studio-web/src/setup/pollingBackoff.test.mjs`

## Tests run and results

```text
studio-api/.venv/Scripts/python.exe -m pytest \
  tests/test_pack_install_workflows.py \
  tests/test_pack_install.py \
  tests/test_pack_providers_github.py \
  tests/test_setup_refactor.py -q --tb=line
→ 56 passed

node studio-web/src/setup/pollingBackoff.test.mjs
→ ok
```

All 12 required workflow cases are covered in `test_pack_install_workflows.py` (empty install OK, empty link reject, valid link, missing/wrong pack.json, GitHub no releases / no matching asset, download & extract failures without killing registry, restart → interrupted, polling backoff helper, retry starts fresh op).
