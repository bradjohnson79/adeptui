# Current Project State

## Running Services (Beta Backend Manager)
- **Web (Vercel)**: https://adeptui-5uunxq106-anoint.vercel.app (latest Production deployment, 2026-08-11)
- **Studio API**: http://127.0.0.1:8758/api/health (managed by Beta Backend Manager)
- **ComfyUI**: headless backend, port 8188 (managed), cuda:0 NVIDIA GeForce RTX 5090 (32 GB VRAM)
- **Cloudflare Tunnel**: api-beta.adeptui.org -> localhost:8758 (managed)
- **Ollama**: port 11434 (managed); `qwen3.6:35b-a3b` listed but NOT loading into memory (env issue)
- **Hosted API**: https://api-beta.adeptui.org/api/healthz
- **Provider**: Ollama (qwen3.6:35b-a3b)
- **Co-Director capabilities**: 56 callable (includes `atlas.generate`, `ers.generate`, `scene.generate`)

## Current Branch / SHA
- **Branch**: `beta`
- **HEAD**: `4d899b4` (`feat(spatial): Spatial Map + Atlas Shot + ERS + Scene Creator`)
- **GitHub remote**: git@github.com:bradjohnson79/adeptui.git

## Backend Manager (NEW - replaces old :8760 supervisor)
- **Scripts**: `Start/Stop/Restart/Get-Status/Watch/Register-Startup/Unregister-Startup-AdeptBetaBackend.ps1` + `scripts/beta-backend/BetaBackendCommon.ps1`
- **State**: `.runtime/beta-backend/` (per-service PID/ownership)
- **Logs**: `logs/runtime/beta-backend/` (per-service `*.log` + `*_stdout.log`)
- **Auto-start**: opt-in via Windows Task Scheduler (`Register-AdeptBetaBackendStartup.ps1`)
- **Behavior**: start missing, reuse healthy, prevent duplicates, auto-restart with bounded retries/backoff, storm protection
- **Env loading**: `Import-BetaEnv` loads `config/beta-local.env` + `config/beta-local.local.env` into process env before launching Studio API

## Regression: Core Co-Director suite PASS (268); Full backend suite ~2173 tests collected
Core Co-Director Phases 2-11 + Cache + Knowledge Card + State Integrity + Certification tests: PASS.
Full backend suite (Co-Director + voice + spatial + magi + production dock + setup + posecraft + etc.): 2173 tests collected, 1 collection error (non-blocking).

## Completed Items
- **Storyboard Style dropdown**: Pencil / Low Poly 3D / Image - in Create Project dialog
- **Preferred Video Generator dropdown**: capability-driven from `/api/knowledge-cards/video-generators` - in Create Project dialog
- **Health polling storm fix**: duplicate `useStudioHealth` 15s poller removed; single central monitor only
- **Orphaned T4 timer fixed**: RECOVERED->CONNECTED setTimeout tracked by healthTimer
- **Asset 500->404 fix**: null/empty asset path returns `ASSET_FILE_MISSING` instead of 500
- **Diagnostics endpoint**: `GET /api/diagnostics/run` - layered probe (ports, healthz, health, providers, PC)
- **Diagnostics page**: `/diagnostics` with system health, provider cards, timing, export
- **DEGRADED state**: liveness vs readiness - `/healthz` OK + `/api/health` fail = DEGRADED, not OFFLINE
- **504 loop fix**: `useProductionDock.refresh()` now checks `shouldSuspendDependentPolling()` before firing
- **Resilience certification tests**: 4 new tests (Production Dock suspension, DEGRADED/OFFLINE, asset 404, cache invalidation)
- **Co-Director Wiki User-Authority repair**: 9 files, 7 layers, 11 new tests - assistant scaffolding blocked from canonical Wiki
- **Production Control 504 resilience**: `model_inventory.py` stale-while-revalidate cache, 30s TTL, single-flight refresh
- **Vercel Aurora deployment**: `beta` branch at 2f2a338, 391 Aurora source files committed, adeptui.vercel.app Production URL
- **useStudioHealth fetch fix**: `useEffect` now fetches on mount (was stuck on "Checking...")
- **Central API origin abstraction**: `apiBase.ts` + VITE_API_BASE env var for hosted deployment
- **Cloudflare Tunnel**: api-beta.adeptui.org -> localhost:8758, `Start-CloudflareTunnel.ps1`, tunnel ID 822658ce
- **All Aurora visual assets committed**: hero images, workspace icons, template cards, UI motifs, empty states
- **Hosted Beta Infrastructure Certification**: GO - 79/79 Python tests, 16/24 Playwright tests, tunnel CONFIRMED
- **Krea 2 reclassified**: `models.image.krea2.ready` -> `DEFERRED_VERSION_1_2` (not a Beta blocker)
- **LTX IC-LoRA extension repaired**: `ComfyUI-LTXVideo` updated with rope-change fix; `LTXAddVideoICLoRAGuide` + `LTXICLoRALoaderModelOnly` load
- **Beta Backend Manager (NEW)**: persistent Windows supervisor for Studio API + ComfyUI + Cloudflared + Ollama; replaces old :8760 frontend server
- **CORS repair**: explicit allowed origins in `config.py` + `main.py` (no wildcard `*` with credentials); `STUDIO_CORS_ORIGINS` env var
- **Vision Validation flag enabled**: `Import-BetaEnv` loads `STUDIO_FEATURE_VISION_VALIDATION_V1=1`; `/api/vision/status` -> ONLINE
- **Capability Readiness zero false blockers**: 0 Blocking, 0 False blockers; Vision family correctly classified
- **Frontend Request Architecture Audit (read-only)**: identified emit->refetch feedback loop + zombie probe as root cause of `ERR_INSUFFICIENT_RESOURCES`; recommended Targeted Polling Repair
- **Frontend Request Storm Repair**: setSnapshot equality check, zombie probeInFlight unified finally, useStudioHealth transition-only refetch, requestCache.ts TTL+dedup, suspension checks on all pollers, SystemStatusBar passive consumer. 10-min soak: 2 health reqs (was 15,053), 0 ERR_INSUFFICIENT_RESOURCES. GO.
- **Production Control CORS repair**: `/resolved` cold project timeout caused CORS failure (Cloudflare 504 had no headers). Fix: fall back to `_global` cache, background refresh for project-specific entries.
- **Project Library Restoration**: `STUDIO_DATA_DIR=data` (relative) resolved to `studio-api/data/` when cwd=studio-api. Fixed to absolute path `C:\AdeptFilmWorks\AIVideoStudio\data`. 10 projects restored.
- **Four Pillars Implementation**: Story tool (backend+frontend), Foundation Status service, Project Building Pane (Wiki|Notes|Story|Script Writer|Storyboard|Character Creator|Library), Co-Director unified context retriever (`project.read_context` tool), active tab context hint, four-candidate character workflow with missing-description guard, FoundationStatusBar in Wiki, CharacterCandidatePanel. 27 files, 2440 lines. Build PASS, 88 tests PASS.
- **Four Pillars UX Closure**: Story editor upgraded to TipTap (bold/italic/headings/lists/undo/redo/autosave), Script Writer toolbar cleaned (removed Storyboard+Timeline buttons), 3 new Co-Director tools (script.estimate_timing, storyboard.estimate_runtime, foundation.compare_pillars), Wiki foundation section in page_compiler, foundation retriever bug fixed, active tab labels fixed. 14 files, 838 lines. Build PASS, 94 tests PASS. Live Playwright: 0 CORS errors, 0 console errors, 78 API reqs/2min, persistence PASS.
- **Story Entries + Wiki Restructure**: New `story_entries` table with structured fields (title/logline/shortSummary/longSummary/entryType/sortOrder). Multiple entries per project. Legacy migration. Wiki pulls Story from story_entries and Characters from character_profiles (not conversation-derived knowledge). Conversation suggestions become suggestion-only. StoryEntryEditor replaces StoryEditor in Co-Director pane. Wiki panel renders structured Story accordions + Character cards with casting images/personality/details. 15 files, 1753 lines. Build PASS, 71 tests PASS. Deployed.
- **Spatial Map + Atlas Shot + ERS + Scene Creator (2026-08-11)**: Four-part spatial-continuity workflow integrated into Co-Director Project Building. 52 files, +9555/-2 lines, commit `4d899b4`. New nav tabs: Spatial Map, Scene Creator (between Character Creator and Library). 3 new Co-Director capabilities (`atlas.generate`, `ers.generate`, `scene.generate`). Frozen contracts: SpatialPlacement grid extension, EnvironmentReferencePackage, ShotRequest, SceneGenerationBatch, @/# resolver. ERS composite is deterministic (code-assembled from real N/E/S/W assets, no LLM layout). 25 product laws consolidated. Independent verifier (Subagent J): VERIFIED. Playwright deferred to manual beta (Ollama hang, not code defect). Governing report: `docs/release-gate/spatial-map/SPATIAL_MAP_ATLAS_ERS_SCENE_CREATOR_COMPLETION_REPORT.md`. Phase memory: `memory/phases/phase-spatial-map-ers-scene-creator.md`.

## Known Issues
| Issue | Status |
|---|---|
| Beta server web process occasionally fails to start (timeout) | Workaround: Start-Process web_server.py separately |
| `studioApiConnection.ts` test_mock_not_allowed flaky in bulk runs | Fixed with patch.dict env isolation |
| `_voice_handoff` workspaceUrl strips deferred | Phase 5 consolidation |
| Playwright 7/24 failures are test-harness limitation, not product defects | Monitor |
| Asset ORB blocking on some project covers | ERR_BLOCKED_BY_ORB on `/api/assets/{id}/file` — browser security feature, not CORS |
| Ollama `qwen3.6:35b-a3b` not loading into memory (2026-08-11) | `ollama ps` empty; 5-token generation times out at 60s. Blocks Co-Director chat + Playwright onboarding dismissal. Investigate VRAM contention with ComfyUI or pull smaller model. |
| Vercel deployment SSO-gated | Production Vercel URL requires Vercel authentication; use local Vite (`STUDIO_API_PORT=8758`) for automated testing |
| Local :8760 web server retired (Law #15) | Playwright config defaults to 8760 when `STUDIO_API_PORT=8758`; set `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173` to override |
| Krea 2 model missing | `krea2_models` required_models_missing; deferred to v1.2; does not block spatial/scene workflow |
| Playwright spatial-scene-creator.spec.ts not green (2026-08-11) | Suite authored (970 lines, S77-S89); blocked by Ollama hang during onboarding dismissal, not code defect. Deferred to manual beta by user. |

## Key Commands
```powershell
# Beta Backend Manager (NEW - preferred)
.\Start-AdeptBetaBackend.ps1
.\Stop-AdeptBetaBackend.ps1
.\Restart-AdeptBetaBackend.ps1
.\Get-AdeptBetaBackendStatus.ps1
.\Watch-AdeptBetaBackend.ps1
.\Register-AdeptBetaBackendStartup.ps1   # opt-in auto-start

# Build frontend (Beta serves static dist)
npm --prefix studio-web run build

# Run backend tests
cd studio-api; python -m pytest tests/test_<name>.py

# Check endpoints
curl http://127.0.0.1:8758/api/healthz
curl http://127.0.0.1:8758/api/health
curl https://api-beta.adeptui.org/api/healthz
curl https://adeptui.vercel.app
```
