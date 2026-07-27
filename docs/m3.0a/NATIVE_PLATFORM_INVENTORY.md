# M3.0a Phase 0 — Native Platform Inventory

| Field | Value |
|-------|-------|
| Tip SHA | `e2f3ae8a9750d44ec37b64361cbede6a95351d3c` (`git rev-parse HEAD`) |
| Branch | `phase2/codirector-m2-9-production-suite` |
| Date | 2026-07-26 |
| Method | Repository inventory only (no guesswork) |
| Capability baseline | `config/capabilities/adept-ui-v1.0-native.json` |
| Runtime capability registry | `studio-api/app/capabilities/registry.py` |

## Registry note

`studio-web/src/sections/registry.ts` **does not exist** on this tip.

Native UI section inventory is taken from:

1. `studio-web/src/core/workspaces.ts` — `WORKSPACES` (Phase 0 workspace registry for ProjectEditor)
2. `studio-web/src/App.tsx` — top-level routes
3. `studio-web/src/components/dashboard/StudioChrome.tsx` — global nav links (flag-gated)

Project workspaces resolve via `/project/:id?workspace=<id>` or `?tab=<id>` (`ProjectEditor.tsx`).

---

## 1. Top-level App routes / nav

| Route / id | Component path | Primary API surfaces (`studio-web/src/api.ts`) | Related capability IDs (`adept-ui-v1.0-native.json`) |
|------------|----------------|-----------------------------------------------|------------------------------------------------------|
| `/` (Home) | `studio-web/src/pages/Home.tsx` | `listProjects` → `GET /api/projects`; `createProject` → `POST /api/projects`; `updateProject` / `duplicateProject` / `archiveProject` / `deleteProject`; `health` → `/api/health`; `capabilities` → `/api/capabilities` | `project.list`, `project.create`, `project.update`, `project.duplicate`, `project.archive`, `project.delete`, `health.read`, `capabilities.read` |
| `/project/:id` | `studio-web/src/pages/ProjectEditor.tsx` | `getProject` → `GET /api/projects/{id}`; workspace-specific APIs below | `project.read`, `project.scenes.*` |
| `/co-director` | `studio-web/src/pages/CoDirectorPage.tsx` → `CoDirectorFullScreen` / M2.14 `UnifiedExperienceWorkspace` | `codirectorChat` / `codirectorChatStream` → `/api/codirector/chat*`; `codirectorProviders`; proposals approve; `m214*` → `/api/codirector/m214/*`; `m211Dashboard` → `/api/codirector/m211/dashboard` | `codirector.chat`, `codirector.provider`, `codirector.tools`, `codirector.bible.*` (+ M2.14 kinds in `m214/kinds.py`, not all in native JSON) |
| `/source-manager` | `studio-web/src/pages/SourceManager.tsx` | `sourceManagerOverview` → `/api/source-manager/overview`; verify/delete; `setupDownloadSources` → `/api/setup/download-sources` | `source_manager.read`, `source_manager.refresh`, `source_manager.install`, `source_manager.repair`, `downloads.*`, `setup.read` |
| `/model-radar` | `studio-web/src/components/ModelRadarWorkspace.tsx` | `m28RadarRegistry` / `m28RadarDiscover`; `m28CompatEvaluate`; `m28Sandbox*`; `m28Promote*`; `m28Recipe*`; `m28ShotProfile*` → `/api/codirector/m28/*` | `m28.radar.discover`, `m28.compat.evaluate`, `m28.sandbox.*`, `m28.recipe.execute`, `m28.shot_profile.apply` |
| `/virtual-stage` | `studio-web/src/components/VirtualStageWorkspace.tsx` | `m28VirtualStageCreate` / `Get` / `Camera` → `/api/codirector/m28/virtual-stage*` | `virtual_stage.render` (baseline status: unavailable) |
| `/environment-studio` | `studio-web/src/components/EnvironmentStudioWorkspace.tsx` | `m213Status`, `m213CameraSpin`, `m213ApproveEnv`, `m213E2EGuided`, `m213PlanDashboard` → `/api/codirector/m213/*` | nearest native: `spatial.scene.read`, `references.*` (no dedicated m213 block in baseline JSON) |
| `/production-suite` | `studio-web/src/components/ProductionSuiteWorkspace.tsx` | `m29ImageGenerate`, `m29FramesGenerate`, `m29VideoGenerate`, `m29LipsyncGenerate`, `m29AudioGenerate`, `m29EditingPropose`, `m29Render`, `m29TimelinePropose`, `m29ControlDecompose` → `/api/codirector/m29/*` | `generation.image.queue`, `frame.generate`, `generation.video.queue`, `lipsync.generate`, `audio.dialogue.generate`, `editor.sequences.read`, `timeline` / director caps, `codirector.bible.propose` (control) |

**StudioChrome nav:** always Source Manager; Model Radar / Virtual Stage / Environment Studio / Production Suite gated by `health().operator` feature flags (`StudioChrome.tsx`).

---

## 2. ProjectEditor workspaces (`WORKSPACES`)

Source: `studio-web/src/core/workspaces.ts` (21 entries).

| Workspace id | Label | Component path | Primary API surfaces | Related capability IDs |
|--------------|-------|----------------|----------------------|------------------------|
| `home` | Project Home | `studio-web/src/components/ProjectHome.tsx` | `getProject`; asset URLs from project payload | `project.read`, `project.scenes.read`, `assets.read` |
| `setup` | Setup | `studio-web/src/components/SetupWizard.tsx` | `setupStatus` → `/api/setup/status`; `setupPrepare*`; `setupOperation`; `setupCheckpoint`; `setupLinkExisting`; `setupDiagnostics`; `setupAction` | `setup.read`, `setup.prepare`, `workflows.*`, `comfyui.health` |
| `settings` | Settings | `studio-web/src/components/ProjectSettings.tsx` | `updateProject`; `falKey*` → `/api/fal/key`; `vramPresets` | `project.update` |
| `imagegen` | ImageGen | `studio-web/src/components/ImageGenPanel.tsx` | `imagegen`; `imagegenModels`; `loraStack`; `getJob`; `promote` | `generation.image.queue`, `image.generate`, `image.reference.generate`, `image.upscale`, `generation.jobs.read` |
| `one` | 1 Frame | `studio-web/src/components/FrameModes.tsx` (`OneFramePanel`) in director shell | `render` → `POST /api/projects/{id}/render`; `uploadAsset`; `updateScene`; `getDirector` / `putDirector` | `frame.first.generate`, `frame.generate`, `generation.video.queue`, `director.timeline.*` |
| `txt2vid` | Txt2Vid | `studio-web/src/components/Txt2VidPanel.tsx` | `txt2vid`; `getJob`; `promote` | `generation.video.queue`, `video.generate` (where registered) |
| `three` | 3 Frame | `FrameModes.tsx` (`ThreeFramePanel`) | same as `one` + multi-frame timeline | `frame.sequence.generate`, `frame.first/last/transition.generate` |
| `director` | Director | `ProjectEditor.tsx` shell + `DirectorTracks`, `Timeline`, `LipSyncTracks`, `LivePreviewMonitor`, `AssetTray` | `getDirector` / `putDirector`; timeline references APIs; `render`; `lipsync`; `sendDirectorToEditor`; lip-sync track bake/apply | `director.timeline.read/update`, `project.timeline.propose/apply`, `generation.lipsync.queue`, `mouth.rectangle.generate`, `references.timeline_bindings`, `references.*` |
| `profiles` | Profiles | `studio-web/src/components/ProfilesWorkspace.tsx` | `listProfiles`; `createProfile`; `uploadProfile`; `deleteProfile` | `references.character_identity`, `references.style`, `assets.*` |
| `tools` | Character / Angles | `studio-web/src/components/ImageTools.tsx` + `JobPanel.tsx` | `characterSheet`; `multiAngle`; `listJobs`; `gpuStats` | `image.reference.generate`, `references.sheet.build`, `generation.jobs.read` |
| `spatial` | Spatial Map (alias: blocking) | `studio-web/src/components/SpatialSceneWorkspace.tsx` | `getSceneSpatial` / `putSceneSpatial`; `spatialPrompt`; `spatialGenerate`; `spatialSendDirector` | `spatial.scene.read`, `references.attach.scene`, `storyboard.generate` |
| `script` | Script / Storyboard | `studio-web/src/components/ScriptStoryboardWorkspace.tsx` | `getScript`; segment/panel CRUD; `storyboardGenerate`; `storyboardSendDirector`; `importScript` | `storyboard.generate`, `storyboard.read`, `generation.image.queue` |
| `shotlist` | Shot List | same component (`shotListOnly`) | same script/storyboard APIs | `storyboard.read` |
| `generate` | Generate Timeline | `studio-web/src/components/GenerateTimelinePanel.tsx` | `proposeTimeline` → `/api/projects/{id}/timeline/propose`; `applyTimeline` | `project.timeline.propose`, `project.timeline.apply`, `director.timeline.read` |
| `library` | Library | `studio-web/src/components/LibraryPanel.tsx` | `library`; `assetGraph`; `patchAssetMeta`; list mastersheets/avatars/sequences; `getEditor`; `promoteGlobal` | `assets.read/tag/file`, `references.read`, `editor.sequences.read` |
| `marketplace` | Marketplace | `studio-web/src/components/MarketplacePanel.tsx` | `marketplace`; `marketplaceInstall`; `loraStack` | `downloads.queue`, `extensions.comfyui.ready`, `models.image.ready` |
| `mastersheet` | Scene Master Sheet | `studio-web/src/components/SceneMasterSheetWorkspace.tsx` | `getMasterSheet` / `putMasterSheet`; `validateMasterSheet`; authority | `references.sheet.build`, `references.ic_lora.ready`, `references.attach.scene` |
| `avatar` | Avatar Studio | `studio-web/src/components/AvatarStudioWorkspace.tsx` | avatar session CRUD/validate/takes; `imagegen`; `txt2vid`; `uploadAsset`; `promote` | `generation.image.queue`, `generation.video.queue`, `frame.generate`, `audio.dialogue.generate` |
| `bible` | Production Bible | `studio-web/src/components/ProductionBibleWorkspace.tsx` | `getBible` → `/api/codirector/projects/{id}/bible`; versions; character approve/lock; import/export | `codirector.bible.read`, `codirector.bible.propose`, `codirector.bible.approve` |
| `editor` | Editor | `studio-web/src/components/EditorWorkspace.tsx` | `getEditor` / `putEditor`; director sequences; `sendDirectorToEditor` | `editor.sequences.read`, `director.timeline.read`, scene/timeline render caps |
| `audiostudio` | Audio Studio | `studio-web/src/components/AudioStudioWorkspace.tsx` | `library`; `uploadAsset`; `getEditor` / `putEditor` | `audio.dialogue.generate`, `audio.sfx.generate`, `audio.music.generate`, `assets.upload` |

**Section counts:** 8 top-level routes + 21 ProjectEditor workspaces = **29 native UI section rows**.

### Production Suite sub-sections (M2.9)

From `ProductionSuiteWorkspace.tsx` `SECTIONS`:

| Suite section id | Flag key | Label |
|------------------|----------|-------|
| `image` | `imageProductionEnabled` | Image |
| `frames` | `frameProductionEnabled` | Frames |
| `video` | `videoProductionEnabled` | Video |
| `timeline` | `directorTimelineEnabled` | Director Timeline Generation |
| `lipsync` | `lipsyncProductionEnabled` | Lip Sync |
| `audio` | `audioProductionEnabled` | Audio |
| `edit` | `editingProductionEnabled` | Edit |
| `render` | `renderProductionEnabled` | Render |
| `control` | `codirectorProductionControlEnabled` | Control |

Baseline `sectionAuditClassification` (`adept-ui-v1.0-native.json`): Image/Frame/Video/Director Timeline/Lip Sync/Editing/Rendering/Co-Director Control = CONNECTED; Audio/SFX/Music = PARTIAL.

---

## 3. Core platform systems

| System | Status | Code pointers |
|--------|--------|---------------|
| Auth (app user auth) | **ABSENT** | No auth middleware / user auth module under `studio-api/app`. Provider CLI sign-in only via Source Manager / setup download sources. |
| Projects | **PRESENT** | `studio-api/app/routers/api.py` (`/api/projects*`); models in `studio-api/app/db.py`; UI `Home.tsx`, `ProjectEditor.tsx` |
| Assets | **PRESENT** | `POST /api/projects/{id}/assets` in `routers/api.py`; `uploadAsset` in `api.ts`; references subsystem `studio-api/app/references/api.py` |
| Jobs | **PRESENT** | Job model + `/api/projects/{id}/jobs`, `/api/jobs/{id}`; worker `studio-api/app/queue_worker.py`; UI `JobPanel.tsx` |
| Approvals | **PRESENT** (multi-layer) | Co-Director proposals; Bible approve; Vision `studio-api/app/codirector/vision/approval.py`; Executive mark-approval; M2.14 `m214/approvals.py` |
| Capabilities / registry | **PRESENT** | Runtime `studio-api/app/capabilities/registry.py` + `service.py` + `api.py`; baseline JSON above; UI `CapabilityPanel.tsx` |
| Feature flags | **PRESENT** | `studio-api/app/feature_flags.py` (`STUDIO_FEATURE_*`); health operator block; nav gating in `StudioChrome.tsx` |
| Setup / Source Manager | **PRESENT** | `studio-api/app/setup_wizard.py`, `/api/setup/*`; `studio-api/app/source_manager/`; UI `SetupWizard.tsx`, `SourceManager.tsx` |
| Queue worker | **PRESENT** | `studio-api/app/queue_worker.py` (Comfy/FAL render, lipsync, imagegen, pack export); started from `main.py` |
| Production Bible | **PRESENT** | `studio-api/app/codirector/bible/`; UI `ProductionBibleWorkspace.tsx` |
| Vision validation | **PRESENT** (flag-gated) | `studio-api/app/codirector/vision/api.py`; `STUDIO_FEATURE_VISION_VALIDATION_V1`; cap `codirector.vision.validate` |
| Pack install | **PRESENT** | `studio-api/app/setup/pack_install.py`; E2E under `tests/e2e/setup/pack-*.spec.ts` |

---

## 4. Co-Director departments / specialists (M2.11 / M2.14)

### Contract inventory

`studio-api/app/codirector/intelligence/contracts.py` defines **31** `SpecialistContract` IDs (also backed by prompts under `studio-api/app/codirector/prompts/specialists/`):

`animation-supervisor`, `art-director`, `asset-manager`, `bible-manager`, `casting-director`, `choreographer`, `cinematographer`, `code-director`, `compositing-supervisor`, `continuity-analyst`, `director`, `editor`, `lighting-supervisor`, `music-supervisor`, `performance-director`, `pipeline-manager`, `producer`, `production-designer`, `prompt-architect`, `qa-reviewer`, `screenwriter`, `script-supervisor`, `sound-designer`, `sound-producer`, `story-analyst`, `story-editor`, `storyteller`, `technical-director`, `vfx-supervisor`, `virtual-production-coordinator`, `vision-reviewer`

Loader: `studio-api/app/codirector/intelligence/specialist_registry.py`.

### M2.11 default pipeline

Source: `studio-api/app/codirector/m211/dag.py` `DEFAULT_PIPELINE`:

| Stage id | Specialist id | Label | Notes |
|----------|---------------|-------|-------|
| `storyteller` | `storyteller` | Storyteller | |
| `story` | `story-analyst` | Story Analyst | optional |
| `bible` | `bible-manager` | Production Bible Manager | approval boundary |
| `continuity` | `continuity-analyst` | Continuity Supervisor | approval boundary |
| `director` | `director` | Director | |
| `camera` | `cinematographer` | Camera Supervisor | |
| `sound_producer` | `sound-producer` | Sound Producer | |
| `sound` | `sound-designer` | Sound Supervisor | |
| `music` | `music-supervisor` | Music Supervisor | |
| `editor` | `editor` | Editor | |
| `vpc` | `virtual-production-coordinator` | Virtual Production Coordinator | optional, approval boundary |
| `qa` | `qa-reviewer` | QA Reviewer | approval boundary |
| `user_review` | `qa-reviewer` | User Review | approval boundary |

M2.11 platform honesty matrix: `studio-api/app/codirector/m211/platform.py` (`platform_matrix`).

### M2.14 unified experience

Source: `studio-api/app/codirector/m214/kinds.py`

| Item | Value |
|------|-------|
| Primary specialist IDs | `storyteller`, `sound-producer` |
| Capability IDs | 42 Product section-50 IDs, all registered `partially_wired` |
| Department prefixes | `codirector.attachment.*` (3), `codirector.project.*` (2), `codirector.media.*` (8), `storyteller.*` (11), `sound_producer.*` (6), `production_team.*` (12) |
| Project stages | `idea`, `discovery`, `treatment`, `screenplay`, `previs`, `production`, `post`, `delivery` |
| Messaging exchanges | storyteller ↔ sound-producer ↔ cinematographer ↔ editor ↔ virtual-production-coordinator ↔ continuity-analyst (`m214/messaging.py`) |

Services: `m214/storyteller.py`, `m214/sound_producer.py`, `m214/media.py`, `m214/approvals.py`, `m214/plan_view.py`, `m214/api.py`.

---

## 5. Native production platforms (PRESENT / PARTIAL / ABSENT)

Assessed from UI workspaces + API packages + capability baseline. **Count: 18 platforms.**

| Platform | Status | Evidence |
|----------|--------|----------|
| image | **PRESENT** | `ImageGenPanel.tsx`; `queue_worker.py` Z-Image paths; M2.9 `m29/image/service.py`; cap `generation.image.queue` accepted |
| video | **PRESENT** | `Txt2VidPanel.tsx`; render + Comfy/FAL in `queue_worker.py`; `m29/video/service.py`; cap `generation.video.queue` |
| animation | **PARTIAL** | Specialists `animation-supervisor`, `choreographer` only; no dedicated native animation workspace |
| refs | **PRESENT** | `studio-api/app/references/api.py`; Visual/Timeline references UI; caps `references.*` |
| 3D | **PARTIAL** | `EnvironmentStudioWorkspace.tsx` + `m213/*`; flag `STUDIO_FEATURE_VIRTUAL_ENVIRONMENT_STUDIO_V1` |
| VP (virtual production / stage) | **PARTIAL** | `VirtualStageWorkspace.tsx`; `m28` virtual-stage APIs; specialist `virtual-production-coordinator`; cap `virtual_stage.render` unavailable |
| blocking | **PARTIAL** | Workspace `spatial` alias `blocking` in `workspaces.ts`; `SpatialSceneWorkspace.tsx` |
| camera | **PARTIAL** | Virtual-stage camera; M2.13 camera-spin; cinematographer specialist; shot profiles; M2.10b camera caps largely unavailable |
| lighting | **PARTIAL** | Specialist `lighting-supervisor`; image relight capability (conditional); no native lighting workspace |
| storyboard | **PRESENT** | `ScriptStoryboardWorkspace.tsx`; storyboard generate path; cap `storyboard.generate` accepted |
| screenplay | **PRESENT** | Same script workspace: segments/panels/import (`getScript` / `importScript`) |
| sound | **PARTIAL** | `AudioStudioWorkspace.tsx`; M2.9/M2.10b audio services; caps `audio.*` conditional / deferred generative path |
| timeline | **PRESENT** | `Timeline.tsx`, `DirectorTracks.tsx`, `GenerateTimelinePanel.tsx`; `/api/projects/{id}/timeline/*`; M2.9 timeline |
| edit | **PRESENT** | `EditorWorkspace.tsx`; editor sequences; M2.9 editing propose/apply |
| color | **ABSENT** | No color-grade UI/service found |
| comp | **PARTIAL** | Specialist `compositing-supervisor` / VFX supervisor only; no native comp workspace |
| subs | **ABSENT** | No subtitle/SRT/VTT generation UI or API found |
| delivery | **PARTIAL** | Project export / pack export; M2.9 render; M2.14 stage `delivery`; no full mastering suite |

**Platform status tallies:** PRESENT **8** · PARTIAL **8** · ABSENT **2**.

---

## 6. Playwright current layout

| Item | Value |
|------|-------|
| Config | `playwright.config.ts` |
| `testDir` | `tests/e2e` (`path.join("tests", "e2e")`) |
| Web server | `node scripts/e2e-start.mjs` → `http://127.0.0.1:5173` |
| Artifacts | `artifacts/functional-audit/` |

### Root suite (`tests/e2e`) — picked up by default config

Categories include smoke, projects, codirector (closed-loop, bible, executive, vision, M2.8, M2.9 suite, chat/tools), setup/pack, capabilities, director timeline-references, resilience, a11y, responsive. Helpers under `tests/e2e/helpers/`.

### `studio-web/e2e` — **outside** root `testDir`

| Spec | Purpose |
|------|---------|
| `studio-web/e2e/m213-environment-studio.spec.ts` | M2.13 Environment Studio smoke |
| `studio-web/e2e/m214-unified-experience.spec.ts` | M2.14 Unified Experience smoke |

**Note:** Default Playwright runs do **not** execute `studio-web/e2e/*`. Those specs require a separate invocation targeting that directory (or a config change).

---

## 7. Inventory summary counts

| Bucket | Count |
|--------|------:|
| Top-level routes | 8 |
| ProjectEditor workspaces | 21 |
| Native UI section rows (routes + workspaces) | 29 |
| Production Suite sub-sections | 9 |
| Specialist contracts | 31 |
| M2.11 DEFAULT_PIPELINE stages | 13 |
| M2.14 primary specialists | 2 |
| M2.14 capability IDs (partially_wired) | 42 |
| Production platforms assessed | 18 |
| Platforms PRESENT | 8 |
| Platforms PARTIAL | 8 |
| Platforms ABSENT | 2 |
