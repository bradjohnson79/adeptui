# GitHub Releases Provider for Essential Packs — Completion Report

**Date:** 2026-07-23  
**Outcome:** **B — Architecture complete, publishing blocked**  
**Phase 1:** Not started

## Final confirmation

GitHub Releases is wired as the production pack source provider. Setup cards stay truthfully **Download Unavailable** until `ADEPT_PACK_GITHUB_OWNER` / `ADEPT_PACK_GITHUB_REPOSITORY` point at a repo that has published `{pack_id}-{version}.zip` + `.release.json` assets. No production LoRA binaries were invented; fixture `pack_sources/` exist only for builder/tests.

```text
pytest (full studio-api): 52 passed — exit 0
pytest (pack providers + pack install + setup refactor): 43 passed — exit 0
npx tsc -b (studio-web): exit 0
npm run build (studio-web): exit 0
```

## 1. GitHub repository configuration added

Env (prefix `ADEPT_PACK_`), loaded via `studio-api/app/setup/pack_settings.py`:

| Variable | Default | Role |
|----------|---------|------|
| `ADEPT_PACK_PROVIDER` | `github_releases` | Provider id |
| `ADEPT_PACK_GITHUB_OWNER` | _(empty)_ | GitHub org/user |
| `ADEPT_PACK_GITHUB_REPOSITORY` | _(empty)_ | Repo name |
| `ADEPT_PACK_GITHUB_CHANNEL` | `stable` | Release channel |
| `ADEPT_PACK_GITHUB_TOKEN` | _(empty)_ | Optional Bearer; env only, never logged/API/state |
| `ADEPT_PACK_STUDIO_VERSION` | `0.1.0` | Min studio gate for releases |
| `ADEPT_PACK_CACHE_TTL_SECONDS` | `900` | Local release metadata TTL |

Missing owner/repo → `pack_provider_not_configured` on Check Again / Install. No destination folders created.

## 2. Provider abstraction added

Sync Protocol (worker-thread compatible) under `studio-api/app/setup/pack_providers/`:

- `base.py` — `PackSourceProvider`, `PackRelease`, `ResolvedPackDownload`, `PackProviderError`
- `github_releases.py` — `GitHubReleasePackProvider`
- `registry.py` — `get_pack_provider()`; Hugging Face stub raises `pack_provider_not_configured`

Installer remains provider-agnostic: `resolve_pack_download()` → existing `install_asset_pack` staging pipeline.

## 3. GitHub API routes used

- `GET {GITHUB_API}/repos/{owner}/{repo}/releases` (paginated, bounded)
- Asset download via validated HTTPS `browser_download_url` (public) or authenticated asset API when token present
- `User-Agent: AdeptUI-GenStudio`; optional `Authorization: Bearer <token>`

## 4. Release-tag convention

Prefer tag `packs-v{version}` (e.g. `packs-v1.0.0`). Drafts ignored. Stable channel ignores prereleases; non-stable channels may allow them.

## 5. Asset-naming convention

Exact match only:

- `{pack_id}-{version}.release.json`
- `{pack_id}-{version}.zip`

## 6. Local manifest changes

All three `studio-api/app/setup/packs/*.json`:

```json
"source": {
  "type": "provider",
  "providerId": "github_releases",
  "channel": "stable"
}
```

`requiredFiles: ["pack.json"]` retained; sizes remain estimates. Bundled `version` is expected/minimum, not proof a release exists.

## 7. Refresh-source behavior

`refresh_component_source` / `refresh_pack_source(force_refresh=True)`:

1. Validate provider config  
2. Query GitHub (bypass cache on Check Again)  
3. Validate `.release.json` + ZIP asset presence  
4. Cache metadata only (no download URL, no token)  
5. Status: `source_available` + version when found; distinct issue codes otherwise  

Install requires cached discovery (or test-only direct URL override) before download starts.

## 8. Cache behavior

`pack_release_cache.py` under `{data_dir}/pack_release_cache/`:

- Stores pack_id, provider, repo, tag, version, asset name/id, expected_bytes, checksum, required_files, retrieved_at  
- TTL via `ADEPT_PACK_CACHE_TTL_SECONDS`  
- Check Again force-refresh bypasses stale cache  

## 9. Security controls

- Token from env only; never written to `setup_state.json`, Fernet secrets, client payloads, or cache  
- Host allowlist for provider downloads: `github.com`, `objects.githubusercontent.com`, `release-assets.githubusercontent.com` (+ localhost HTTP for fixtures)  
- Safe ZIP extract: path traversal / symlink / size / file-count limits  
- Internal `pack.json` id + version must match release  
- Size equality enforced only for provider exact `expectedBytes` (manifest sizes are estimates)  
- UI never surfaces download URLs or tokens  

## 10. Pack builder implementation

`python -m app.setup.pack_builder <pack_id>`

- Source: `studio-api/pack_sources/<pack_id>/`  
- Rejects empty/metadata-only packs  
- Emits deterministic ZIP + SHA-256 + `.release.json` → `dist/packs/{pack_id}/{version}/`  

## 11. Publisher implementation

`python -m app.setup.pack_publisher <pack_id> --repository owner/repo --tag packs-v1.0.0`

- Verifies built artifacts + checksum  
- Requires `--yes` or interactive confirm  
- Prefers `gh release create/upload`; else prints exact manual upload steps  
- Never stores token in generated files; never auto-publishes from Setup Wizard  

## 12. Real pack contents found

| Pack | Production marketplace content in-repo? | Fixture sources? |
|------|----------------------------------------|------------------|
| Photoreal | **No** | Yes — `pack.json`, README, one JSON preset |
| Anime | **No** | Yes — same pattern |
| Cinematic | **No** | Yes — same pattern |

Fixtures are **not** claimed as production LoRAs.

## 13. Whether any pack was actually published

**No.** No `ADEPT_PACK_GITHUB_*` publish target / token was available for a live release during this task.

## 14. Published tag and asset names

N/A — nothing published.

## 15. Checksums with no secrets

Builder computes SHA-256 of the ZIP into `.release.json`. Cache/API expose checksum digests only — never tokens or download URLs.

## 16. Real installation verification result

**Outcome B:** Live GitHub Install → Ready was **not** exercised against a real Release. Mocked GitHub HTTP fixture in `tests/test_pack_providers_github.py` proves Check Again → Install → Ready with filesystem truth. Without configured owner/repo + published assets, cards remain **Download Unavailable** (`pack_provider_not_configured` or `pack_release_not_found`).

## 17. Files changed (primary)

**New**

- `studio-api/app/setup/pack_settings.py`
- `studio-api/app/setup/pack_providers/{__init__,base,github_releases,registry}.py`
- `studio-api/app/setup/pack_release_cache.py`
- `studio-api/app/setup/pack_builder.py`
- `studio-api/app/setup/pack_publisher.py`
- `studio-api/pack_sources/pack_essential_{photoreal,anime,cinematic}/…`
- `studio-api/tests/test_pack_providers_github.py`
- `studio-web/public/favicon.ico` / updated `favicon.svg`
- `docs/audit/GITHUB_PACK_PROVIDER_COMPLETION.md`

**Updated**

- `studio-api/app/setup/packs/*.json`
- `studio-api/app/setup/pack_manifests.py`
- `studio-api/app/setup/pack_install.py`
- `studio-api/app/setup/diagnostics.py`
- `studio-api/app/setup/status.py`
- `studio-api/app/setup/orchestrator.py`
- `studio-api/tests/test_pack_install.py`
- `studio-api/tests/test_setup_refactor.py`
- `studio-web/src/components/SetupWizard.tsx`
- `studio-web/src/setup/helpers.ts`
- `studio-web/src/setup/types.ts`
- `studio-web/src/components/CoDirector/CoDirectorSession.tsx`
- `studio-web/index.html`

## 18. Tests and exact exit codes

```text
studio-api\.venv\Scripts\python.exe -m pytest -q
→ 52 passed, exit 0

studio-api\.venv\Scripts\python.exe -m pytest tests/test_pack_providers_github.py tests/test_pack_install.py tests/test_setup_refactor.py -q
→ 43 passed, exit 0
```

Covered: missing config; stable vs prerelease; exact asset match; rate-limit; mocked install; cache TTL; builder empty reject; checksum match; no URL persistence; prior pack-install regressions.

## 19. TypeScript result

```text
npx tsc -b → exit 0
```

## 20. Production-build result

```text
npm run build → exit 0 (vite production build succeeded)
```

## 21. Browser verification result

API/provider behavior covered by mocked tests. Live Setup Wizard against a published Release was **not** available (Outcome B). After API restart with owner/repo unset, packs should show Download Unavailable + **Check Again**.

## 22. React warning result

`useBindCoDirectorWorkspace` no longer calls `bindWorkspace` during render; binding runs in `useEffect`. Code-level fix applied in `CoDirectorSession.tsx`. Full interactive browser smoke (open project / switch scene / open Co-Director) not re-run in this session — expect the “Cannot update CoDirectorSessionProvider while rendering ProjectCoDirectorBridge” warning to be gone after refresh.

## 23. Favicon result

- `index.html`: `<link rel="icon" type="image/svg+xml" href="/favicon.svg" />` and `<link rel="icon" href="/favicon.ico" sizes="any" />`
- Gen Studio teal SVG replaces Vite purple mark
- `public/favicon.ico` (104 bytes) copied to `dist/favicon.ico` by Vite → `/favicon.ico` should return **200**

## 24. Remaining blockers preventing real downloads

1. No configured GitHub owner/repository with published pack assets  
2. No production Essential Pack archives in-repo (only fixture JSON presets)  
3. Optional token needed for private repos  

**Unblock path:** build fixture or real content with `pack_builder` → publish with `pack_publisher` → set `ADEPT_PACK_GITHUB_OWNER` / `REPOSITORY` → restart API → Check Again → Install → Ready.

## Explicit non-goals (honored)

- No Hugging Face provider implementation (registry stub only)  
- No invented production LoRA binaries or fake Ready  
- No Phase 1 feature work  
- No hardcoded temporary browser download URLs in manifests  
