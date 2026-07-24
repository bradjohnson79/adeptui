# Download Sources Implementation Report

**Date:** 2026-07-24  
**Branch:** audit/playwright-functional  
**Verdict:** Implemented foundation + critical path validated

## Summary

Added first-class **Download Sources** to the Setup Wizard with GitHub CLI / Hugging Face CLI detection, guided install/sign-in, manual Add Source URL verification (inspect-before-download), persisted per-component source overrides, and SSRF-safe URL validation. Integrated into existing pack/component install architecture without breaking `fixture_http` E2E.

## Files changed (primary)

### Backend
- `studio-api/app/setup/download_sources/__init__.py`
- `studio-api/app/setup/download_sources/security.py`
- `studio-api/app/setup/download_sources/url_parse.py`
- `studio-api/app/setup/download_sources/cli_detect.py`
- `studio-api/app/setup/download_sources/overrides.py`
- `studio-api/app/setup/download_sources/service.py`
- `studio-api/app/setup/state.py` (source_overrides + download_sources keys)
- `studio-api/app/setup/status.py` (add_source_url pack action, custom_source_active)
- `studio-api/app/setup/pack_manifests.py` (persisted override URL hydration)
- `studio-api/app/routers/extra.py` (download-sources + source verify/override routes)
- `studio-api/app/routers/e2e.py` (`/api/e2e/cli-mock`)
- `studio-api/tests/test_download_sources.py`

### Frontend
- `studio-web/src/components/DownloadSourcesPanel.tsx`
- `studio-web/src/components/AddSourceUrlDialog.tsx`
- `studio-web/src/components/SetupWizard.tsx`
- `studio-web/src/api.ts`
- `studio-web/src/setup/types.ts`

### Playwright
- `tests/e2e/setup/download-sources.spec.ts`

## CLI detection approach

- `gh` / `hf` / `huggingface-cli` via PATH + env overrides (`ADEPT_GITHUB_CLI_PATH`, `ADEPT_HF_CLI_PATH`)
- Version via `--version` / `version`
- Auth via `gh auth status` and `hf auth whoami` (non-destructive)
- Tokens never displayed; only `token_available` boolean
- Playwright uses `POST /api/e2e/cli-mock` → `ADEPT_CLI_MOCK_JSON`

## Supported URL formats

GitHub: repo, releases, tag, release asset, branch archive, tag archive.  
Hugging Face: repo, tree, blob, resolve, `hf://OWNER/REPO@REV/PATH`.

## Provider resolution order (packs)

1. Verified per-component user source override (persisted + in-memory)
2. Explicit manifest/direct URL
3. `ADEPT_PACK_PROVIDER=fixture_http` (E2E)
4. GitHub releases provider when configured
5. Hugging Face provider stub / manual Add Source URL
6. Link Existing Folder

Download Sources CLI preference for verification: GitHub CLI → anonymous/authenticated API → direct asset URL.

## Authentication handling

- Sign In returns guided CLI command only (`gh auth login` / `hf auth login`)
- No token capture or storage in Adept state
- Diagnostics redact Authorization / ghp_ / hf_ patterns

## Security protections

- HTTPS-only by default; localhost HTTP only in STUDIO_E2E
- Allowlisted provider hosts + CDN suffixes
- Reject file://, SMB, private IPs, localhost (prod)
- Redirect host revalidation helpers
- Source archives blocked as Essential pack sources
- Secrets redacted from install/CLI output

## Tests added / results

| Suite | Result |
|-------|--------|
| `pytest tests/test_download_sources.py` | **19 passed** |
| Playwright `@critical` | **17 passed / 0 failed** |
| Full deterministic E2E | **17 passed / 0 failed** |
| studio-web lint | exit 0 (existing warnings) |
| studio-web tsc | exit 0 |
| Backend alive after suites | YES |

## Commands run

```
pytest tests/test_download_sources.py -q
npm run lint  # studio-web
npx tsc -b
npm run e2e:stop && npm run e2e:start
npx playwright test --grep "@critical" --retries=0
npx playwright test --retries=0
```

## Remaining external-provider limitations

- Full GitHub CLI / HF CLI download job pipeline (progress/cancel/resume/atomic finalize) is stubbed at verify + override level; pack installs still use existing `install_asset_pack` / direct URL / fixture paths.
- Live private-repo end-to-end installs require real CLI auth (covered via mock detection + verify gates in CI).
- Hugging Face multi-file include/exclude UI is preview-list based; pattern editor can be expanded later.
- Package-manager CLI installs require user confirmation and may need elevation on Windows.

## UX copy

- Discovery failure: “Automatic source discovery did not find a compatible download.”
- Add Source URL help explains inspect-before-download.
- Ready / not authenticated CLI messages match product requirements.
