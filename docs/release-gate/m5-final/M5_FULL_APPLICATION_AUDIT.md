# M5 Full Application Audit

## Run Context

- Audit timestamp: `2026-08-02T00:28:00-07:00`
- Branch: `feature/ai-guided-setup`
- SHA: `fa09c99d6395c29461cdec4555055faad116c435`
- Beta UI: `http://127.0.0.1:8760/`
- Beta API: `http://127.0.0.1:8758/`
- Anchor project used for live probes: `Korri Character Production` (`e32dae30-a014-4ea4-a2f2-69f4b7809bde`)

## Method And Fresh Evidence

- Re-read `docs/release-gate/setup/AI_GUIDED_SETUP_CERTIFICATION.md`: verdict is still `NO-GO`; Phases 2, 4, 6, and 7 remain open.
- Live API probes used in this pass:
  - `GET /api/health`
  - `GET /api/projects`
  - `GET /api/projects/{id}`
  - `GET /api/projects/{id}/dashboard`
  - `GET /api/projects/{id}/capabilities`
  - `GET /api/setup/status`
  - `GET /api/source-manager/overview`
  - `GET /api/codirector/status/registry`
  - `GET /api/codirector/status/latest?projectId=...`
  - `GET /api/codirector/providers`
  - `GET /api/codirector/providers/active/health`
  - `GET /api/voice-performance/m410/runtime/status`
  - `GET /api/voice-performance/m410/capabilities`
  - `GET /api/image-studio/providers`
  - `GET /api/video-runtime/hunyuan/providers`
  - `GET /api/projects/{id}/avatar-sessions`
- Focused Playwright audit run:
  - `13 passed`, `4 failed` in `3.6m`
  - Passing live surfaces:
    - `tests/e2e/setup/ai-guided-setup-lifecycle.spec.ts`
    - `tests/e2e/setup/source-manager.spec.ts`
    - `tests/e2e/m32a/brand-studio.spec.ts`
    - `tests/e2e/m411/m411-spatial-map-360-consistency.spec.ts`
    - `tests/e2e/m412-magi/m412-magi-editor-nle.spec.ts`
    - `tests/e2e/m47/m47-professional-scriptwriter-studio.spec.ts`
    - storyboard/API portions of `tests/e2e/m48-m49/m48-m49-cinematic-image-storyboard.spec.ts`
  - Failing live surfaces:
    - `tests/e2e/codirector/codirector-status-cross-check.spec.ts`
    - `tests/e2e/m410/m410-voice-performance-studio.spec.ts`
    - image/discoverability portions of `tests/e2e/m48-m49/m48-m49-cinematic-image-storyboard.spec.ts`

## Workspace Matrix

Chain order for every row: `UI -> API -> Persistence -> Queue -> Runtime -> Asset Library -> Timeline -> Co-Director -> Production Bible -> Status`

| Workspace | Overall | Chain | Fresh evidence / blocker pointer |
| --- | --- | --- | --- |
| Project Home | PASS | `PASS / PASS / PASS / PASS / PASS / PASS / PARTIAL / PARTIAL / PARTIAL / PASS` | Live `GET /api/projects/{id}/dashboard` returned scenes/assets/jobs/queued counts for the active project. Route wiring lives in `studio-web/src/components/ProjectHome.tsx` and `studio-web/src/pages/ProjectEditor.tsx`. |
| Setup (AI-Guided / Source Manager) | FAIL | `PASS / PASS / PASS / PARTIAL / PARTIAL / PARTIAL / PARTIAL / FAIL / PARTIAL / PASS` | Fresh setup status is live (`ready=33`, `not_installed=4`, `needs_attention=0`), AI-guided and Source Manager specs passed, but certification remains `NO-GO` in `docs/release-gate/setup/AI_GUIDED_SETUP_CERTIFICATION.md` because Phases 2/4/6/7 are still open. Primary files: `studio-web/src/setup/lifecycle/AiGuidedSetupPanel.tsx`, `studio-web/src/components/SetupWizard.tsx`, `studio-api/app/setup/status.py`, `studio-api/app/source_manager/install_jobs/service.py`. |
| Library | PARTIAL | `PARTIAL / PASS / PASS / PARTIAL / PARTIAL / PASS / PARTIAL / PARTIAL / PARTIAL / PARTIAL` | Live project data shows `158` assets and library capability is `locally_verified`, but there was no fresh Library UI walkthrough in this pass. Files: `studio-web/src/components/LibraryPanel.tsx`, `studio-api/app/project_library/`. |
| Settings | PARTIAL | `PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL` | Route is wired in `studio-web/src/components/ProjectSettings.tsx`, but this pass did not perform a fresh creator workflow through project settings. |
| Cinematic Image Generator | FAIL | `FAIL / PASS / PASS / PASS / PASS / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL` | Live API/provider families were reachable, but the UI failed fresh verification: missing continuity label and missing primary action/discoverability affordances in `tests/e2e/m48-m49/m48-m49-cinematic-image-storyboard.spec.ts`. Primary surface: `studio-web/src/components/image-studio/CinematicImageStudio.tsx`. |
| Text to Video | PARTIAL | `PARTIAL / PARTIAL / PARTIAL / PASS / PASS / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL` | Video queue capabilities are live and Hunyuan providers are installed/executable, but there was no fresh Txt2Vid UI run in this pass. Files: `studio-web/src/components/Txt2VidPanel.tsx`, `studio-api/app/video_runtime/`. |
| Timeline Generator | PARTIAL | `PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL` | Live capability registry marks `project.timeline.propose` as `degraded` and `project.timeline.apply` as `partially_wired`; no fresh timeline generator creator-flow was run here. Files: `studio-web/src/components/timeline-master/TimelineEditorShell.tsx`, `studio-api/app/director_timeline_w46/`. |
| Storyboard Studio | PASS | `PASS / PASS / PASS / PARTIAL / PARTIAL / PASS / PASS / PARTIAL / PARTIAL / PARTIAL` | Fresh Playwright passed UI mount plus API add/replace/undo/prepare/confirm flows. Files: `studio-web/src/components/storyboard-studio/StoryboardStudio.tsx`, `studio-api/app/storyboard_studio/api.py`. |
| Character Creator (+ Voice) | FAIL | `PARTIAL / PASS / PASS / PARTIAL / FAIL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL` | Voice runtime itself is ready, but the fresh voice workspace test failed because `qwenVoiceDesign.ready` was false during live validation despite setup reporting ready. Blocker pointers: `tests/e2e/m410/m410-voice-performance-studio.spec.ts`, `tests/e2e/m42/helpers/korriVoice.ts`, `studio-web/src/components/CharacterProfileWorkspace.tsx`, `studio-web/src/components/VoiceStudioWorkspace.tsx`. |
| Project Profile | PARTIAL | `PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL` | Workspace is wired and project profile route exists, but no fresh Project Profile UI/API creator path was executed in this pass. Files: `studio-web/src/components/ProfilesWorkspace.tsx`, `studio-api/app/routers/api.py`. |
| Production Bible | PARTIAL | `PARTIAL / PASS / PASS / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PASS / PASS / PARTIAL` | Bible APIs are live and Scriptwriter exercised proposal/bible flow, but the dedicated Production Bible workspace was not freshly driven end-to-end in this pass. Files: `studio-web/src/components/ProductionBibleWorkspace.tsx`, `studio-api/app/codirector/bible/`. |
| Continuity | PARTIAL | `PARTIAL / PASS / PASS / PARTIAL / PARTIAL / PASS / PASS / PARTIAL / PARTIAL / PARTIAL` | Continuity API journeys passed inside the M48/M49 run, but the standalone Continuity workspace UI did not receive a fresh dedicated walkthrough. Files: `studio-web/src/components/continuity/ContinuityWorkspace.tsx`, `studio-api/app/continuity/`, `studio-api/app/image_studio/continuity.py`. |
| Scriptwriter | PASS | `PASS / PASS / PASS / PASS / PARTIAL / PARTIAL / PASS / PASS / PASS / PARTIAL` | Fresh Playwright passed full production path: edit, autosave, proposal, bible, scene link, timeline prepare, export, reload. Files: `studio-web/src/components/scriptwriter/ScriptwriterStudio.tsx`, `studio-api/app/scriptwriter/api.py`. |
| Scene Master Sheet | PARTIAL | `PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL` | Workspace is routed and API surface exists, but there was no fresh master-sheet creator workflow in this audit. Files: `studio-web/src/components/SceneMasterSheetWorkspace.tsx`, `studio-api/app/master_sheet.py`. |
| Spatial Map | PASS | `PASS / PASS / PASS / PARTIAL / PARTIAL / PASS / PASS / PARTIAL / PARTIAL / PARTIAL` | Fresh Playwright passed creator flow covering limits, 360 plan, scene assignment, and image-studio selection. Files: `studio-web/src/components/spatial-map/SpatialMapStudio.tsx`, `studio-api/app/spatial_map/router.py`. |
| Avatar Studio | FAIL | `PARTIAL / PASS / PASS / PARTIAL / FAIL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL` | Live avatar sessions persist and load, but required avatar runtimes are not installed: `LongCat Avatar 1.5`, `InfiniteTalk`, `MuseTalk 1.5`, `EchoMimicV2` are `not_installed` in live setup status. Files: `studio-web/src/components/AvatarStudioWorkspace.tsx`, `studio-api/app/avatar_studio.py`, `studio-api/app/avatar_runtimes.py`. |
| Brand Studio | PASS | `PASS / PASS / PASS / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL` | Fresh Playwright passed creator-facing campaign canvas persistence and generation path. Files: `studio-web/src/components/GenerationTools/BrandStudioWorkspace.tsx`, `tests/e2e/m32a/brand-studio.spec.ts`. |
| Audio Studio | PARTIAL | `PARTIAL / PASS / PASS / PARTIAL / PASS / PASS / PARTIAL / PARTIAL / PARTIAL / PARTIAL` | Live project dashboard shows fresh audio jobs and assets, and IndexTTS2 runtime is ready, but no fresh Audio Studio workspace UI walkthrough was run in this pass. Files: `studio-web/src/components/audio-studio/AudioStudioWorkspace.tsx`, `studio-api/app/audio_studio/router.py`. |
| MAGI Editor | PASS | `PASS / PASS / PASS / PARTIAL / PARTIAL / PASS / PASS / PARTIAL / PARTIAL / PARTIAL` | Fresh Playwright passed focus contract and persistence-after-reload for sequence mutations. Files: `studio-web/src/components/magi/MagiEditorWorkspace.tsx`, `studio-api/app/magi/api.py`. |
| Marketplace | PARTIAL | `PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL` | Workspace is routed but not freshly exercised in this pass. Files: `studio-web/src/components/MarketplacePanel.tsx`, `studio-web/src/core/workspaces.ts`. |
| Co-Director | FAIL | `PARTIAL / PASS / PARTIAL / PARTIAL / PASS / PARTIAL / PARTIAL / FAIL / PARTIAL / FAIL` | Provider health is live (`ollama` reachable, selected model present), but fresh status seeding failed and `/api/codirector/status/latest` returned `null`. Blocker pointers: `tests/e2e/codirector/codirector-status-cross-check.spec.ts`, `studio-web/src/components/CoDirector/CoDirectorStatusPanel.tsx`, `studio-api/app/codirector/status/router.py`. |
| Production Dock | PARTIAL | `PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL` | Dock chrome is wired, but the dock itself was not freshly creator-walked end-to-end in this audit and adjacent production capabilities remain partially wired. Files: `studio-web/src/components/production-dock/ProductionControlDock.tsx`, `studio-api/app/production_control/router.py`. |
| Status | FAIL | `PARTIAL / PASS / PARTIAL / PARTIAL / PARTIAL / PARTIAL / PARTIAL / FAIL / PARTIAL / FAIL` | `SystemStatusStrip` can render optimistic badges from health probes, but fresh Co-Director status cross-check failed and no latest status run exists for the project. Files: `studio-web/src/components/dashboard/SystemStatusStrip.tsx`, `tests/e2e/codirector/codirector-status-cross-check.spec.ts`, `studio-api/app/codirector/status/router.py`. |

## Workspace Counts

- PASS: `6`
- PARTIAL: `11`
- FAIL: `6`

## Creator Journeys

| Journey | Result | Fresh evidence and break point |
| --- | --- | --- |
| Character -> Voice -> Performance -> Image -> Storyboard -> Timeline -> MAGI -> Render | PARTIAL | Character/voice chain breaks on live voice readiness truth: `tests/e2e/m410/m410-voice-performance-studio.spec.ts` failed before a trustworthy performance pass; image UI also failed fresh checks. Storyboard and MAGI are fresh-pass, but the end-to-end creator chain is broken mid-path. |
| Storyboard -> Image -> Video -> Timeline -> MAGI -> Export | PARTIAL | Storyboard API/UI and MAGI passed, but Cinematic Image Generator UI failed fresh affordance checks and Timeline Generator remains degraded/partially wired in live capabilities. |
| Character -> Voice -> Lip Sync -> Avatar -> Timeline -> Render | PARTIAL | Avatar sessions persist live, but voice truth mismatch plus four missing avatar runtimes (`LongCat`, `InfiniteTalk`, `MuseTalk`, `EchoMimicV2`) block an honest PASS. |

## Runtime Honesty Inventory

| Runtime / Provider | Installed | Running | Connected | GPU | Model | Provider | Version | Pinned | Certified | Last verified | Fresh note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ComfyUI | PASS | PASS | PASS | Unknown | Multiple local image/video stacks | local ComfyUI | `0.28.2` | PARTIAL | PARTIAL | `2026-08-02T07:23:37Z` | Fresh setup status says `ready`; setup cert confirms live reachability and Hunyuan extension node registration. |
| Hunyuan ComfyUI Extension | PASS | PASS | PASS | Unknown | Hunyuan wrapper nodes | Comfy extension | Unknown | Unknown | FAIL | `2026-08-02T07:23:37Z` | Representative extension path is live-ready, but broader Hunyuan workflow contract drift remains open in setup cert. |
| Z-Image Turbo | PASS | Unknown | PARTIAL | Unknown | `zimage-local` | local Comfy | Unknown | Unknown | PARTIAL | `2026-08-02T07:23:37Z` | Installed and surfaced as available; image UI still failed fresh affordance checks. |
| Qwen-Image-2512 | PASS | Unknown | PARTIAL | Unknown | `qwen_image_2512_models` | local Comfy | Unknown | Unknown | PARTIAL | `2026-08-02T07:23:37Z` | Models are installed; no fresh end-to-end ImageGen PASS in this audit. |
| HunyuanVideo 1.5 local | PASS | Unknown | PASS | Unknown | `hunyuan-video-1.5-local` | local video runtime | `1.5` | PASS | FAIL | live provider probe in this pass | Installed, healthy, executable, but `trueLocalT2vCertified = false`. |
| HunyuanVideo 13B local | PASS | Unknown | PASS | Unknown | `hunyuan-video-13b-local` | local video runtime | `13b` | PARTIAL | FAIL | live provider probe in this pass | Installed, healthy, executable, but `trueLocalT2vCertified = false`. |
| Ollama / Co-Director LLM | PASS | PASS | PASS | Unknown | `gemma4:31b-it-qat` | `ollama` | Unknown | Unknown | Unknown | live provider health in this pass | Provider is reachable and selected model is present, but Co-Director status flow itself failed fresh seeding. |
| IndexTTS2 | PASS | PASS | PASS | Unknown | `IndexTeam/IndexTTS-2` | `index-tts2-local` | `m4.10-index-tts2` | PASS | PARTIAL | live provider health in this pass | Runtime/capabilities are ready; recent real audio outputs exist in the active project. |
| Qwen3-TTS Voice Design 1.7B | PASS | Unknown | PARTIAL | Unknown | `qwen_voice_design_17b` | local voice sandbox | Unknown | Unknown | FAIL | `2026-08-02T07:23:37Z` | Setup says ready, but fresh live Character Voice test observed `qwenVoiceDesign.ready === false`; honesty conflict must be repaired. |
| Qwen3-TTS Voice Clone 1.7B | PASS | Unknown | PARTIAL | Unknown | `qwen_voice_clone_17b` | local voice sandbox | Unknown | Unknown | FAIL | `2026-08-02T07:23:37Z` | Setup says ready, but the same live voice test requires clone readiness and did not trust the chain. |
| Kie.ai hosted image providers | PASS | PASS | PASS | n/a | `flux-kie`, `nano-banana-kie` | Kie.ai | Unknown | Unknown | PASS | live provider response in this pass | `accountAccessible=true`, `liveProbeStatus=ok`, marked `Certified` by the image provider API. |
| fal.ai API | Unknown | Unknown | Unknown | n/a | Unknown | fal.ai | Unknown | Unknown | Unknown | not freshly probed in this pass | Present in setup catalog, but not freshly validated here. |
| Avatar runtimes (`LongCat`, `InfiniteTalk`, `MuseTalk`, `EchoMimicV2`) | FAIL | FAIL | FAIL | Unknown | various | local avatar runtimes | Unknown | Unknown | FAIL | live setup status in this pass | All four are `not_installed`; Avatar Studio cannot be scored PASS honestly. |

## Repair Queue For Subagent B

### Priority order

1. **Setup truth remains the hard gate**  
   Setup must stay `FAIL` until `docs/release-gate/setup/AI_GUIDED_SETUP_CERTIFICATION.md` closes Phases 2, 4, 6, and 7. Highest-priority pointers: `docs/release-gate/setup/AI_GUIDED_SETUP_CERTIFICATION.md`, `docs/setup/ai-guided-setup/full-catalog-audit.md`, `docs/setup/ai-guided-setup/setup-containment.md`.

2. **Repair Co-Director Status seeding / latest-run truth**  
   Fresh failure happened before UI review: `POST /api/codirector/status/check` did not seed successfully in `tests/e2e/codirector/codirector-status-cross-check.spec.ts`, and `GET /api/codirector/status/latest?projectId=...` returned `null`. Primary files: `studio-api/app/codirector/status/router.py`, `studio-api/app/codirector/status/runner.py`, `studio-web/src/components/CoDirector/CoDirectorStatusPanel.tsx`.

3. **Resolve voice readiness honesty mismatch**  
   Setup reports `Qwen3-TTS Voice Design 1.7B` and `Qwen3-TTS Voice Clone 1.7B` as ready, but the live voice studio test rejected the runtime chain as not ready. Primary pointers: `tests/e2e/m410/m410-voice-performance-studio.spec.ts`, `tests/e2e/m42/helpers/korriVoice.ts`, `studio-api/app/voice_performance/`, `studio-api/app/codirector/m210b/adapters/qwen_voice_design.py`, `studio-api/app/codirector/m210b/adapters/qwen_voice_clone.py`.

4. **Fix Cinematic Image Generator creator affordances**  
   Fresh failures show missing `.cis-continuity-label` and missing primary CTA/discoverability. Primary pointers: `tests/e2e/m48-m49/m48-m49-cinematic-image-storyboard.spec.ts`, `studio-web/src/components/image-studio/CinematicImageStudio.tsx`.

5. **Repair Avatar runtime honesty / installation gap**  
   Avatar sessions persist live, but required runtimes are not installed, so Avatar cannot be honestly ready. Primary pointers: `studio-api/app/avatar_runtimes.py`, `studio-api/app/avatar_studio.py`, `studio-web/src/components/AvatarStudioWorkspace.tsx`.

6. **Repair Timeline Generator degraded capability path**  
   Live capabilities still mark timeline propose/apply below PASS. Primary pointers: `studio-api/app/director_timeline_w46/orchestrator.py`, `studio-api/app/director_timeline_w46/service.py`, `studio-web/src/components/timeline-master/TimelineEditorShell.tsx`.

7. **Revalidate Production Dock / Status badges against real backends**  
   Dock and strip are wired, but fresh status evidence is not trustworthy enough to elevate. Primary pointers: `studio-web/src/components/production-dock/ProductionControlDock.tsx`, `studio-web/src/components/dashboard/SystemStatusStrip.tsx`, `studio-api/app/production_control/router.py`.

8. **Then address lower-priority PARTIAL surfaces with fresh creator runs**  
   `Library`, `Settings`, `Text to Video`, `Project Profile`, `Production Bible`, `Continuity`, `Scene Master Sheet`, `Audio Studio`, and `Marketplace` all still need direct fresh creator-path evidence before promotion.

### Previously certified and freshly live enough to skip engineering unless honesty regresses

- `Setup` representative component readiness only: AI-guided lifecycle + Source Manager route + representative Comfy/Hunyuan repair path are live, but overall Setup remains `FAIL`.
- `Storyboard Studio`
- `Spatial Map`
- `Scriptwriter`
- `Brand Studio`
- `MAGI Editor`
- `Project Home` dashboard API path

## Setup Gate Status

- Setup workspace overall: `FAIL`
- Reason: the live certification file still says `NO-GO`, explicitly because Phases `2`, `4`, `6`, and `7` remain open.
- Subagent B must not treat Setup as PASS until that certification file is honestly closed with fresh evidence.

## Bottom Line

- Workspace counts: `PASS 6 / PARTIAL 11 / FAIL 6`
- Journey results: `Character PARTIAL`, `Video PARTIAL`, `Avatar PARTIAL`
- Highest-priority repairs for B: `Setup hard gate`, `Co-Director Status`, `Voice readiness honesty`, `Cinematic Image Generator affordances`, `Avatar runtime installs`, `Timeline Generator degradation`
# M5.0 — Full Application Audit (Subagent A)

| Field | Value |
| --- | --- |
| Milestone | M5.0 Final E2E |
| Branch | `feature/ai-guided-setup` |
| SHA | `fa09c99d6395c29461cdec4555055faad116c435` |
| Beta UI | `http://127.0.0.1:8760/` |
| Beta API | `http://127.0.0.1:8758/` |
| Audit timestamp (UTC) | 2026-08-02T07:30:00Z |
| Auditor | Primary (Subagent A gate) |
| Verdict ownership | Primary — this file is the frozen repair gate for B |

## Hard gates observed live

| Gate | Live evidence | M5 treatment |
| --- | --- | --- |
| AI-Guided Setup Final Closure | `docs/release-gate/setup/AI_GUIDED_SETUP_CERTIFICATION.md` = **NO-GO** (Phases 2/4/6/7 FAIL) | Setup **cannot PASS** |
| Production Dock gate | `GET /api/production-control/gate` → `verdict=GO`, `productionDockGo=true`, `mock=false` | Fresh live PASS for Dock shell |
| Setup status performance | `GET /api/setup/status` ~371–608 ms (warm/cold samples this session) | Warm OK; cold under 3s |
| Co-Director status check | `POST /api/codirector/status/check` → 200 in ~3648 ms | Not hung; still **PARTIAL** (slow) |

## Scoring legend

- **PASS** — live chain UI→API→persist/runtime evidence holds; or Previously Certified with **fresh** live evidence this audit
- **PARTIAL** — wired but incomplete, Conditional prior cert, mid-journey break, or honesty Unknowns
- **FAIL** — hard gate fail, fake Ready risk, dead control, or blocked NO-GO cert

Chain columns abbreviated: UI · API · Persist · Queue · Runtime · Library · Timeline · CoDir · Bible · Status

---

## 1. Workspace matrix

| Workspace | Overall | UI | API | Persist | Queue | Runtime | Library | Timeline | CoDir | Bible | Status | Evidence / notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Project Home | PASS | P | P | P | — | — | P | — | P | — | P | Registry `home`; launchpad wired via `workspaces.ts` / `ProjectEditor.tsx` |
| Setup (+ AI-Guided / SM) | FAIL | P | P | P | P | PARTIAL | — | — | PARTIAL | — | P | AI-Guided cert **NO-GO**; Phase 2/4/6/7 open; live status `33 ready / 4 not_installed`; SM install-progress report still NO-GO for full live UX |
| Library | PASS | P | P | P | — | — | P | P | P | — | P | Project-scoped assets; M42 W2 certified library path + live Beta |
| Settings | PASS | P | P | P | — | — | — | — | — | — | — | Project/studio prefs; Dock prefs gate flags pass |
| Cinematic Image Generator | PARTIAL | P | P | P | P | P | P | P | P | P | P | Prior **CONDITIONAL GO** (`M48_M49_*`); local providers Ready on machine; not re-certified full image E2E this pass |
| Text to Video / Video Gen | PARTIAL | P | P | P | P | PARTIAL | P | P | P | — | P | M41/video Conditional history; Hunyuan/LTX present Ready; workflow-contract drift noted in AI-Guided cert |
| Timeline Generator | PASS | P | P | P | P | P | P | P | P | P | P | M42 W4C Timeline rename/cert GO; fresh Dock/timeline control surfaces present |
| Storyboard Studio | PARTIAL | P | P | P | P | P | P | P | P | P | P | Bundled with M48/M49 Conditional GO |
| Character Creator (+ Voice) | PASS | P | P | P | P | P | P | P | P | P | P | M42 W43 Character Creator **GO**; Korri path; voice studio present |
| Project Profile / Profiles | PASS | P | P | P | — | — | P | — | P | P | — | Identity/profile surfaces wired |
| Production Bible | PASS | P | P | P | — | — | P | — | P | P | P | M42 character→Bible sync certified; creative UX rebuild present |
| Continuity | PARTIAL | P | P | P | — | — | P | P | P | P | P | Workspace present; full continuity E2E not freshly proven |
| Scriptwriter | PARTIAL | P | P | P | — | — | P | — | P | P | — | M47 **CONDITIONAL GO** (FDX/collab limitations) |
| Scene Master Sheet | PARTIAL | P | P | P | — | — | P | P | P | P | — | Workspace `mastersheet` present; not freshly E2E-certified |
| Spatial Map | PARTIAL | P | P | P | P | PARTIAL | P | — | P | — | P | M411 spatial cert exists; Conditional/consistency scope |
| Avatar Studio | PARTIAL | P | P | P | P | PARTIAL | P | P | P | — | P | M4.12 audit-stage docs; long-form/retakes work in tree; no final Avatar GO |
| Brand Studio | PARTIAL | P | P | P | P | PARTIAL | P | — | P | — | — | Creative UX rebuild report; no final Brand GO |
| Audio Studio | PASS | P | P | P | P | P | P | P | P | — | P | M42 W45 **GO** (`audioStudioGo`); Dock audio diagnostics flag pass |
| MAGI Editor | PARTIAL | P | P | P | — | PARTIAL | P | P | P | — | P | M42 W4B foundation **GO**; M4.12 NLE rebuild in dirty tree / frozen contracts — not full NLE cert |
| Marketplace | PARTIAL | P | PARTIAL | PARTIAL | — | — | PARTIAL | — | — | — | — | Workspace registered; production commerce path not freshly certified |
| Co-Director | PARTIAL | P | P | P | P | — | P | P | P | P | PARTIAL | Tools/proposal gates present; status check ~3.6s; catalog-truth Phase 6 incomplete |
| Production Dock | PASS | P | P | P | P | P | — | — | P | — | P | Live gate **GO**; Install CTAs must deep-link Setup (containment Phase 4 still FAIL upstream) |
| Status Center | PARTIAL | P | P | — | — | PARTIAL | — | — | P | — | P | Cross-check responds; latency/honesty coupling to Setup/AI-Guided incomplete |

**Counts (overall):** PASS **8** · PARTIAL **14** · FAIL **1** (Setup)

---

## 2. Creator journeys

| Journey | Result | Break point / notes |
| --- | --- | --- |
| **Character** → Voice → Performance → Image → Storyboard → Timeline → MAGI → Render | **PARTIAL** | Character/Voice/Audio/Timeline strong; Image/Storyboard Conditional; MAGI NLE not full cert; Setup/runtime honesty gaps can break Ready selection mid-chain |
| **Video** → Storyboard → Image → Video → Timeline → MAGI → Export | **PARTIAL** | Generators present; Hunyuan workflow-contract drift + Setup NO-GO; MAGI export/NLE incomplete vs foundation |
| **Avatar** → Character → Voice → Lip Sync → Avatar → Timeline → Render | **PARTIAL** | Avatar audit/impl in progress (M4.12); Motion group all `not_installed` live (`longcat`, `infinitetalk`, `musetalk`, `echomimic`) |

---

## 3. Runtime honesty inventory

Live `GET /api/setup/status`: `overall_status=ready`, counts `ready=33`, `not_installed=4`, `needs_attention=0`, `components=37`.

| Runtime / provider class | Installed | Running | Connected | GPU | Model loaded | Provider reg | Version | Pinned | Certified | Ready | Last verified |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Python (studio-api venv) | Yes | Yes | Yes | N/A | N/A | N/A | 3.11.15 | Unknown | detect | Yes | From status payload |
| ComfyUI | Yes | Yes (`:8188` v0.28.2 prior pass) | Yes | Unknown* | Unknown* | Yes | 0.28.2 | Unknown | Partial | Yes (component) | AI-Guided live evidence |
| `comfyui_hunyuan_nodes` | Yes | Yes (after real Desktop restart) | Yes | Unknown* | N/A | Yes | Wrapper loaded | Unknown | Probe 6/6 | Yes | Job `ij_comfyui_hunyuan_nodes_0074784d12` |
| Local image (Qwen/FLUX/Sana/SDXL…) | Yes (machine) | On demand | Yes | Unknown* | On demand | Yes | Per component | Unknown | Partial | Yes (status) | setup/status |
| Local video (Hunyuan 1.5/13B, LTX…) | Yes | On demand | Yes | Unknown* | On demand | Yes | Per component | Unknown | Partial | Yes (status) | setup/status; contract drift open |
| Voice (IndexTTS2, Qwen voice) | Yes | On demand | Yes | Unknown* | On demand | Yes | Per component | Unknown | Partial | Yes | setup/status |
| Motion/Avatar providers | No | No | No | — | — | Catalog | — | — | No | **not_installed** | setup/status (honest) |
| fal / API keys | Present as utilities | N/A | Unknown | N/A | N/A | Partial | N/A | N/A | Partial | Partial | Folded into Utilities — Phase 2 gap |
| Production Dock resolvers | Yes | Yes | Yes | Flagged via diagnostics | Via prefs | Yes | Gate GO | Frozen contracts | Yes (dock) | Yes | `/api/production-control/gate` |

\*GPU/VRAM must be re-probed per job under Law 26 during B/D — do not treat component Ready as GPU-verified generation.

Unknown must remain **Unknown** in UI — never promote to Ready without verify.

---

## 4. Previously Certified (skip engineering unless regression / honesty fail)

| Surface | Prior cert | Fresh live this audit |
| --- | --- | --- |
| Timeline Generator | M42 W4C GO | PASS — keep |
| Character Creator | M42 W43 GO | PASS — keep |
| Audio Studio | M42 W45 GO | PASS — keep |
| Production Dock | M42 Dock GO | PASS — gate live GO |
| MAGI foundation | M42 W4B GO | PARTIAL — foundation only; NLE not skip-PASS |

---

## 5. Prioritized repair queue for Subagent B

1. **P0 — AI-Guided Setup Final Closure** — Finish Phases 2, 4, 6, 7 → flip `AI_GUIDED_SETUP_CERTIFICATION.md` to GO. Until then Setup stays FAIL. Files: `studio-api/app/setup/catalog.py`, containment UI deep-links, Co-Director setup tools, `tests/e2e/setup/*`, cert docs.
2. **P0 — Setup group model** — First-class Music, Avatar, API Providers, Creative Packs (Phase 2).
3. **P0 — Universal Install CTA containment** — Dock/Status/studios → Setup only (Phase 4); competing installers = FAIL.
4. **P1 — Co-Director catalog-truth + Status latency** — Phase 6 spot checks; keep `/api/codirector/status/check` &lt;1s warm target if feasible.
5. **P1 — Source Manager install progress live UX** — prior NO-GO boundary; progress/SSE/stall honesty.
6. **P1 — MAGI NLE** — Keyboard focus ownership, Delete/Space/JKL; finish M4.12 NLE vs foundation-only.
7. **P1 — Avatar Motion runtimes honesty** — Keep `not_installed` honest; wire Install→Setup; do not fake Ready for MuseTalk/InfiniteTalk/etc.
8. **P2 — Image/Storyboard/Scriptwriter/Spatial/Brand** — Close Conditional GO gaps only as discovered partial workflows (Addendum 1 — no feature creep).
9. **P2 — Hunyuan workflow-contract node-id drift** — Align certified workflows with live wrapper node ids.
10. **P2 — Error UX** — What/Why/How/Repair/Details on Setup + generation failures (Addendum 5).

---

## 6. Explicit non-goals for B

- No new creator-facing features unless required to finish a PARTIAL workflow discovered here
- No M5.1 production audit yet
- No inherited GO without live evidence
- No silent CPU fallback / fake Ready

---

## 7. Beta health snapshot

| Probe | Result |
| --- | --- |
| `GET /api/health` | 200 |
| `GET /api/setup/status` | 200; ~371 ms this sample; 33 ready / 4 not_installed |
| `GET /api/production-control/gate` | 200; verdict GO |
| `POST /api/codirector/status/check` | 200; ~3648 ms |

---

## Gate decision for Subagent B

**A audit landed.** B may begin repairs against the prioritized queue above. Setup overall remains **FAIL** until AI-Guided Final Closure GO.

`READY FOR PRIMARY REVIEW`
