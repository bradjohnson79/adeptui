# Avatar Studio Architecture Audit

**Scope:** read-only. No implementation, commit, push, deploy, API bounce, or source edit.  
**Repo:** `C:\AdeptFilmWorks\AIVideoStudio` · **branch:** `beta`  
**Date:** 2026-08-14 (PT)  
**Mission:** focused cleanup + refinement + E2E wiring of EXISTING Avatar Studio. Not a redesign.  
**Preserved concept:** Select Avatar → Script or Approved Voice → Presentation Style → Framing → Background → Generate → Review → Timeline.

Visual baseline (CONFIRMED against live UI copy in `AvatarStudioWorkspace.tsx`, matching the user screenshot on adeptui.vercel.app / workspace=avatar / Schnick Coffee / Korri): header `character_name · session.name`, session dropdown, New Session, Open Setup, Save Draft, large Avatar Preview with Talking Head + Presenter Frame / Direct Presenter / Not Installed badges, empty-state “Preview grows here after you choose a reference image or generate a take.”, right CREATE “Long-Form Presenter” + Provider Mode Best Match, Select Avatar cards, Mode cards Talking Head / Presenter / Full-Body Presenter / Existing Video Dubbing, workflow path in header.

---

## Avatar Studio Source of Truth

**CONFIRMED — root workspace**
- UI monolith: `studio-web/src/components/AvatarStudioWorkspace.tsx` (~2,700 lines). This is the only Avatar Studio surface.
- Types / empty session / prompt / client validation: `studio-web/src/avatar/types.ts`.
- Backend sessions + long-form jobs: `studio-api/app/avatar_studio.py` (FastAPI router `tags=["avatar-studio"]`).
- Runtime install/inspect: `studio-api/app/avatar_runtimes.py`.
- Co-Director tools (same session/job store): `studio-api/app/codirector/tools/handlers/avatar_m412.py` + tool IDs in `studio-api/app/codirector/tools/definitions.py`.
- Router mount: `studio-api/app/main.py` `app.include_router(avatar_studio_router, prefix="/api")`.
- Client: `studio-web/src/api.ts` (`listAvatarSessions` … `prepareAvatarTimeline`).

**CONFIRMED — ProjectEditor tab / Production menu / App routes**
- Workspace id: `avatar` in `studio-web/src/core/workspaces.ts` (aliases `avatar-studio`; group `create`; menuGroup `characters`).
- Production menu: `studio-web/src/core/productionMenu.ts` Creative Studios → Avatar Studio, `action: "workspace"`, `workspace: "avatar"`, `requiresCharacter: true`.
- Explore roster: `studio-web/src/core/exploreWorkspaces.ts` `avatar`.
- `ProjectEditor.tsx` line ~698: `tab === "avatar"` → `<AvatarStudioWorkspace />`.
- URL contract: `/project/:id?workspace=avatar` (also `?tab=`). `resolveWorkspace("avatar-studio")` canonicalizes to `avatar`. No dedicated App.tsx route.
- `studio-web/src/App.tsx` routes: `/`, `/project/:id`, Co-Director, Source Manager, diagnostics. **Vercel-safe: do not add an App.tsx route.** Hosted `workspace=avatar` already works.

**CONFIRMED — one session store**
- SQL table `avatar_sessions` (`id`, `project_id`, `name`, `data_json`, `updated_at`). Blob is the session.
- Jobs: `avatar_project_jobs` (child of session, not a second session store).
- Co-Director `createAvatarSession` / `avatar.*` tools read/write the same tables.
- `LibraryPanel.tsx` lists the same sessions via `api.listAvatarSessions`.
- `sessionStorage` keys `adept_avatar_profile` / `adept_selected_character` are character-handoff hints only, not a session store.

**INFERENCE**
- Docs under `docs/avatar-studio/m4-12/` and `docs/release-gate/m412/` describe the same M4.12 contract. Treat source as truth if docs drift.

**PROPOSAL**
- Keep this file set as the only SOT. Do not add `avatar2/`, a second registry, or a new workspace id.

---

## Session Data Model

**CONFIRMED — `AvatarSession` (`studio-web/src/avatar/types.ts` + `_empty()` in `avatar_studio.py`)**
- Identity: `id` (`avs-…`), `project_id`, `name`, `character_profile_id`, `character_name`, `continuity_lock`.
- Mode: `AvatarMode` = `talking_portrait` | `cinematic_character` | `full_body` | `stylized` | `existing_video_lipsync`.
- UI Mode cards (workspace) remap four of those: Talking Head / Presenter / Full-Body Presenter / Existing Video Dubbing. `stylized` is **not** a Mode card (tip says stylized lives in Advanced; Advanced has no Mode control — only `stylized_performance` style).
- Look / camera / performance / voice / mouth_mask / lip_sync_method.
- Input: `input_mode` `script` | `approved_voice`.
- Presenter choices: `presentation_style`, `framing_choice`, `background_choice`, `duration_class`, `presentation_plan`.
- Provider: `provider_mode` `best_match` | `choose_provider` | `compare`; `provider_choice`; `model_id` default **`ltx_2_5_distilled`** (not an avatar runtime id).
- Assets: `source_still_asset_id`, `source_video_asset_id`, `voice.audio_asset_id` / `fallback_audio_asset_id` / `approved_record_id` / `approved_take_id`.
- Links: script document/scene, voice record/take, unused `master_sheet_id` / `storyboard_panel_id` / `scene_id`.
- Takes: `takes: AvatarTake[]` (legacy per-session list).
- Jobs: `active_job_id` → `avatar_project_jobs`.

**CONFIRMED — persist / load**
- Save Draft → `persistSession` → `PATCH /avatar-sessions/{id}` (full blob + built prompt).
- New Session → `POST /avatar-sessions` with same `character_profile_id` / name, empty presenter defaults.
- Session `<select>` → `GET /avatar-sessions/{id}` + `loadJobs`.
- Open Setup → `buildAiGuidedSetupPath({ source: "avatar_studio" })` → **AI Guided Setup / Source Manager**, not “open a saved setup file”.
- Card clicks call `patchSession` (React state only). **Not persisted until Save Draft or Generate.**
- Bind-on-character: if a session already has that `character_profile_id`, it is reused; else a new row is created.

**CONFIRMED — jobs**
- `AvatarProjectJob`: sections, assembly stub, presentationPlan copy, voice/script provenance, `timelineProposal` (`timelineWritten: false` always).

**INFERENCE**
- `data_json` merge on PATCH is last-write-wins. Concurrent Co-Director plan apply + Save Draft can clobber.

**PROPOSAL**
- Keep one `avatar_sessions` blob. Persist presenter-card changes on Save Draft / Generate only (already the contract). Do not add localStorage session clones.

---

## Character / Avatar Integration

**CONFIRMED**
- Load: `api.listProfiles("character")` + `api.listCharacterProfiles(project.id)` merged by id.
- Mapped to `{ id, name, kind: "character" }` only. `media_path` from profiles is dropped. Character Creator fields (`approval_status`, `active_version_id`, `sheetAssetId`, `hero_identity` view, references) are **never fetched**.
- `getCharacterProfile` exists (`api.ts` ~6852) and is unused here.
- Select Avatar cards: first-letter glyph, not a portrait.
- Preview image: `source_still_asset_id` (Advanced library dropdown) **or** first take `asset_id`. Not character hero/sheet.
- Job `identityProfileRef` / `avatarId` = `character_profile_id || character_name || session_id` (string only).
- Prompt builder uses `character_name` + camera/style notes. No approved identity text, sheet, or hero asset.
- Deep link: `?profile=` or `?characterId=`, else `sessionStorage` handoff from Character Creator / Profiles.
- Empty gate: `needsCharacter` → Choose Avatar / Open Character Profiles (`onGo("characters")`).
- Production menu `requiresCharacter: true` is menu-level; workspace still has its own gate.

**CONFIRMED — approved identity is a silent text-only fallback**
- Character Creator SOT (`studio-web/src/components/character/types.ts`): `CharacterProfile` + `CharacterCandidate.sheetAssetId` + view role `hero_identity`.
- Avatar Studio does not read those. Selecting Korri stores id + display name. Preview stays empty until a manual still or a take exists.

**INFERENCE**
- Washed-out Korri card in the screenshot is this letter-tile + light-card CSS, not a missing CDN image.

**PROPOSAL**
- On bind: `getCharacterProfile` + approved/canonical reference (hero / sheet / portrait). Set `source_still_asset_id` and preview from that. Reuse Character Creator types. Do not create an avatar-side character store.

---

## Voice Integration

**CONFIRMED**
- Types comment: “TTS providers stubbed, not executed.” Voice this pass = metadata + uploaded/approved audio.
- Script vs Approved Voice toggle. Approved Voice lists M4.10 records via `api.voicePerformanceM410.listProjectRecords` filtered by `characterId`, requiring `approvedTakeId` + `audioAssetId`.
- Readiness: `api.voicePerformanceReadiness(characterId, project.id)`.
- Attach writes `voice.audio_asset_id` / `approved_record_id` / `approved_take_id` / `profile_id` and `links.voice_*`.
- Backend `_require_approved_voice` on job create. `_resolved_audio_asset_id`: approved mode uses approved audio only; script mode uses fallback || audio.
- `avatar.replace_voice` Co-Director tool updates linkage only (no regenerate).
- Open Voice Studio: `onGo("voicestudio")`. “Open Audio Mix” also goes to Voice Studio (not Audio Studio), though `_audio_mix_linkage.openWorkspace` is `"audiostudio"`.
- Fallback audio: Advanced `<select>` over `api.library()` audio items.

**INFERENCE**
- Script-only generate is intended to plan sections from text; live lip-sync still wants audio. Frontend `canGenerate` allows script-only; backend validate treats `lip_sync_method: "external"` (the default) without audio as **bad**, so Generate often dies after click.

**PROPOSAL**
- Keep Voice Studio as SOT for approved takes. Align `canGenerate` + `_validate` so Script mode can plan without audio, and Approved Voice stays strict. Do not add a second voice registry.

---

## Script Integration

**CONFIRMED**
- Script mode: Scriptwriter document + scene selects (`api.scriptwriter.documents` / `document` navigator).
- “Use Scene Dialogue” → `api.scriptwriter.prepareTimeline` → joins `proposal.dialogue[].text` into `dialogue_original`, writes provenance links.
- Manual `dialogue_original` textarea (`data-testid="avatar-script-input"`). Advanced `dialogue_spoken` rewrite.
- Open Scriptwriter: `onGo("scriptwriter")`.
- Job sections chunk `dialogue_spoken || dialogue_original` (`_chunk_script`). Approved-voice with empty text gets a single “Approved voice performance” chunk.
- Presentation plan sections are derived from the same chunker.

**INFERENCE**
- `prepareTimeline` is Scriptwriter’s own timeline-prep helper, not Director Timeline write.

**PROPOSAL**
- Keep this link. Do not embed a second script editor. Optional: auto-fill dialogue when a scene is selected (today requires the extra button).

---

## Generation Pipeline

**CONFIRMED — Long-Form Presenter**
- CREATE heading “Long-Form Presenter” is **marketing/UX copy**.
- The **orchestrator is real**: `POST .../jobs` builds sections, overlap, presentationPlan, pause/resume/cancel/retry/approve/assemble.
- **Live video is not certified.** `_execute_section_generation` always returns `_runtime_dispatch_result`, which returns `ok: False` even when `runtimeReady` (`PROVIDER_NOT_CERTIFIED`). Comment: “honest default is failure until a provider-specific runtime is certified.” Tests monkeypatch this seam.
- Assemble writes `assembly.stub: true`, `compositeVideoAssetId: null`.
- Co-Director `get_provider_status` returns `supportsLiveGeneration: False`.

**CONFIRMED — Existing Video Dubbing**
- **Not a dead card.** Mode `existing_video_lipsync` shows a Library video `<select>`, copy says MuseTalk is repair/dubbing not full gen.
- Generate → “Prepare Lip-Sync Repair”: requires MuseTalk not “Not Installed”, `createAvatarJob({ providerId: "musetalk-1-5-local", startImmediately: false })`.
- `avatar.repair_lipsync` records a plan with `executed: False`. Does not run MuseTalk.

**CONFIRMED — provider / eligibility**
- Hardcoded `PROVIDER_ORDER`: longcat, infinitetalk, musetalk, echomimic. Filtered from `api.setupStatus()`.
- `bestMatchProvider`: dubbing→musetalk, full_body or stylized_performance→longcat, else infinitetalk||longcat. **Not capability-driven** (no creative_role / VRAM / OS / benchmark from `AvatarRuntimeSpec`).
- Frontend `canGenerate` does **not** check install/certify. Badge can say Not Installed while Generate stays enabled.
- Backend `_select_provider`: requested || `provider_choice` || `model_id` || `infinitetalk-local`. Default `model_id` `ltx_2_5_distilled` is a leftover if frontend sends no provider.
- `inspect_runtime`: files/venv/models/import probe. Ready health is always `"experimental"` (`benchmark_ready` defaults false).
- `AvatarRuntimeInstallPanel` lives on Source Manager, not in Avatar Studio.

**CONFIRMED — audio / lip-sync**
- Default `lip_sync_method: "external"`, `mouth_mask.placed: false` (warn).
- No TTS execution. No MuseTalk execution. No local vs hosted video generator call from this pipeline.
- Routing is local-runtime ids only (no cloud avatar provider path in this module).

**INFERENCE**
- Compare provider mode is UI-only (side-by-side cards). It does not run two jobs.

**PROPOSAL**
- Keep the honest certify gate. Wire eligibility so Generate is disabled with the same badge reason. Do not invent a second generator router. Do not claim live video in Phase 1.

---

## Candidate / Review Flow

**CONFIRMED**
- Two models: (1) job `sections` (long-form, current), (2) session `takes` (legacy).
- Review tabs: sections / takes / progress / completed.
- Sections: status, overlap, continuation-frame hook, presentation notes, `versionHistory` + `retakeHistory` (non-destructive snapshot on retake).
- Retake actions → Co-Director proposals (`avatar.request_retake` / `avatar.repair_lipsync`), not immediate overwrite.
- Approve section, pause/resume/cancel, validate transitions (flag only), assemble stub.
- Legacy takes: Retake (scroll + message), Send to Timeline via `api.promote(..., target: "scene_new")` + `addAvatarTake`.
- No in-monitor video player. Preview is a still `<img>` or empty state.

**INFERENCE**
- Non-destructive for section retakes (history arrays). Legacy takes append; Send to Timeline marks a take approved/final.

**PROPOSAL**
- Keep section jobs as the review SOT. Do not add a third candidate store. Optionally hide empty legacy takes when a job exists.

---

## Library Integration

**CONFIRMED**
- `api.library(project.id)` fills Advanced still, fallback audio, and dubbing video `<select>`s (`tag || filename`).
- No shared picker (`CoDirectorAssetPicker`, `CharacterReferenceAssetPicker` unused).
- No background Library picker — Background is four preset cards writing `background_notes` / `look.background`.
- `LibraryPanel` “Avatars” section lists sessions (looks/voice/takes copy). Not an ingest pipeline.
- Generated section `outputVideoAssetId` is only set if `_execute_section_generation` returns ok (never in production).
- `_register_asset` imported in `avatar_studio.py` from character identity voice runtime — **unused** in the file.

**PROPOSAL**
- Reuse an existing picker for still / video / optional background plate. Do not add an avatar-only library. Ingest only when a real asset id exists (promote / register), not fake composites.

---

## Timeline Integration

**CONFIRMED — handoff exists without shipping Timeline WIP**
- `POST /avatar-jobs/{id}/timeline/prepare` + Co-Director `avatar.prepare_timeline`.
- Builds a proposal (`avatar-presenter` / `avatar-alternates` tracks, clips, provenance). **`timelineWritten` is always `False`.** Preview text: “does not write the Timeline.”
- UI: Full Presentation / Send Selected Section / Replace Section / Create Alternate Take → Co-Director approval, not `prepareAvatarTimeline` directly (client method exists, unused by the workspace).
- Legacy: `api.promote(project.id, { asset_id, target: "scene_new" })` creates a **new scene** from a take asset. Does not edit `DirectorTracks.tsx`, `director_timeline_w46`, or Timeline Master.

**CONFIRMED**
- Do **not** edit Timeline / DirectorTracks / `director_timeline_w46` for this cleanup. Handoff API already exists.

**INFERENCE**
- `promote` → new scene is the only path that can appear on Timeline today, and only for legacy takes with an `asset_id`.

**PROPOSAL**
- Keep proposal-only handoff. If a take/section has a real asset, reuse `promote` / existing prepare API. No Timeline file edits unless a write API already exists (it does not write today).

---

## Current UX Defects

Mark: screenshot baseline vs code.

| Defect | Class | Evidence |
| --- | --- | --- |
| Unselected Mode / Avatar cards washed-out white-on-light | **CONFIRMED** | `.avatar-choice-card { background: rgba(255,255,255,0.72) }`; selected is only a slightly greener white gradient (`styles.css` ~3954–3984). Matches screenshot. |
| Korri card is letter tile, not portrait | **CONFIRMED** | `item.name.slice(0,1)`; no `media_path` / hero. |
| Preview empty until manual still or take | **CONFIRMED** | Empty copy matches screenshot exactly. Approved character unused. |
| Not Installed badge while Generate stays enabled | **CONFIRMED** | Chip from `runtimeStatus`; `canGenerate` ignores provider. |
| Open Setup ≠ open a saved presenter setup | **CONFIRMED** | Navigates to AI Guided Setup. Session open is the dropdown. |
| CREATE column overloaded vs stated flow | **CONFIRMED** | Extra Duration cards + Presentation Plan + Advanced in the same column as the 6-step path. |
| Compare is a third provider mode with no compare run | **CONFIRMED** | Toggle only. |
| Open Audio Mix goes to Voice Studio | **CONFIRMED** | `onGo("voicestudio")` vs backend `openWorkspace: "audiostudio"`. |
| Card choices vanish on refresh if Save Draft skipped | **CONFIRMED** | `patchSession` is local. |
| Stylized Avatar mode exists in types, not in Mode cards | **CONFIRMED** | `AVATAR_MODES` vs `MODE_CARDS`. |

**PROPOSAL (cleanup, not redesign)**
- Contrast: selected = solid/darker surface; unselected = readable muted, not white-on-white.
- Bind approved hero/sheet to card art + preview.
- Disable Generate with the same reason as the badge / validate issues.
- Relabel or move Open Setup; keep session dropdown as Open Session.
- Collapse Duration + Plan + Advanced so the stated path stays first.

---

## Current Wiring Defects

| Defect | Class | Evidence |
| --- | --- | --- |
| Approved character identity unused | **CONFIRMED** | id+name only; silent text fallback in prompt. |
| Live generation always uncertified | **CONFIRMED** | `_runtime_dispatch_result` never `ok: True`. |
| Existing Video Dubbing plans only | **CONFIRMED** | Job created, MuseTalk not executed. |
| Eligibility not capability-driven | **CONFIRMED** | Hardcoded ids + mode ifs; specs unused. |
| `canGenerate` vs `_validate` mismatch | **CONFIRMED** | Script-only enables the button; default `lip_sync_method: "external"` makes validate `ok: false` without audio. |
| Default `model_id: ltx_2_5_distilled` | **CONFIRMED** | Not in `PROVIDER_ORDER`. Fallback if setupStatus empty. |
| Background has no Library plate | **CONFIRMED** | Preset notes only. |
| Framing/style do not change preview media | **CONFIRMED** | They patch camera/look/prompt only. |
| Two take models | **CONFIRMED** | `session.takes` vs `job.sections`. |
| Timeline proposal never writes | **CONFIRMED** | Intentional honesty; UI copy still says “send to Timeline”. |
| Assembly stub | **CONFIRMED** | No composite asset. |
| `_register_asset` unused | **CONFIRMED** | Import only. |
| Frontend best-match vs backend select | **INFERENCE** | Workspace sends `selectedProvider.id` on generate, so usually OK; if `runtimeComponents` empty, backend gets `ltx_2_5_distilled`. |
| `links.master_sheet_id` unused | **CONFIRMED** | Field only. |

---

## Reusable Shared Components

**CONFIRMED — reuse, do not fork**

| Existing | Use |
| --- | --- |
| `AvatarStudioWorkspace.tsx` + `avatar/types.ts` | Only UI + client model to edit |
| `avatar_studio.py` + `avatar_runtimes.py` | Only backend session/job/runtime |
| `avatar_m412.py` + `definitions.py` | Co-Director plan/retake/timeline/voice |
| `api.ts` avatar + `listCharacterProfiles` / `getCharacterProfile` / `voicePerformanceM410` / `scriptwriter` / `library` / `promote` / `setupStatus` | Already wired or one call away |
| `character/types.ts` | Approved identity/sheet/hero — do not fork |
| `CharacterReferenceAssetPicker.tsx` / `CoDirectorAssetPicker.tsx` | Still / video / background plate |
| `AvatarRuntimeInstallPanel.tsx` + `buildAiGuidedSetupPath` | Setup, already linked |
| `GeneratorSourceSelector.tsx` | Optional eligibility UI pattern (Character Creator) |
| `LibraryPanel.tsx` session list | Same store; do not add a second list model |
| `ProjectEditor.tsx` `tab === "avatar"` | Routing already correct |

**CONFIRMED — do not treat as Avatar SOT**
- `DirectorTracks.tsx`, `director_timeline_w46/*`, Timeline Master, `magi/timeline_handoff.py` — out of scope unless an existing write API is used (none writes today).

---

## READY TO IMPLEMENT | BLOCKED

### Callouts (required)

| Question | Verdict | Class |
| --- | --- | --- |
| Is Long-Form Presenter implemented or marketing copy? | **Both.** Heading is copy. Section-job orchestrator is implemented. Live section video is **not** certified (honest fail). | CONFIRMED |
| Is Existing Video Dubbing a real path or a dead card? | **Real path, plan-only.** Wires video pick + MuseTalk job (`startImmediately: false`) + repair plan. Does not execute dubbing. | CONFIRMED |
| Is generator eligibility capability-driven? | **No.** Hardcoded provider ids + mode heuristics + experimental health. Specs (`creative_role`, VRAM, OS) unused. | CONFIRMED |
| Is approved character identity used? | **No. Silent text-only fallback** (`character_name` / id string). Hero/sheet/approved look unused. | CONFIRMED |
| Timeline handoff without shipping Timeline WIP? | **Yes.** `timeline/prepare` + Co-Director tool store a proposal (`timelineWritten: false`). Legacy `promote` → `scene_new`. **Do not edit Timeline / DirectorTracks / director_timeline_w46.** | CONFIRMED |
| Vercel-safe routing? | **Yes.** `?workspace=avatar` already mounts the workspace. **No new App.tsx route.** | CONFIRMED |
| Second session store? | **No.** One `avatar_sessions` blob + child jobs. sessionStorage is character handoff only. **Do not add another.** | CONFIRMED |

### Smallest reuse map (Phase 1 — edit, don’t create)

**Edit**
1. `studio-web/src/components/AvatarStudioWorkspace.tsx` — contrast/selection, bind approved still, Library picker reuse, persist messaging, `canGenerate` = validate + runtime badge, Open Setup vs session wording, hide/collapse Plan+Duration+Advanced.
2. `studio-web/src/styles.css` (Avatar Studio block ~3814–4035) — selected vs unselected contrast.
3. `studio-web/src/avatar/types.ts` — validation aligned with Script vs Approved Voice; optional identity asset fields on the existing session (no new store).
4. `studio-api/app/avatar_studio.py` — `_validate` / job identity: attach approved still if provided; keep certify gate; do not fake video assets.
5. `studio-web/src/api.ts` — only if a thin helper is required; `getCharacterProfile` already exists.

**Reuse as-is (no new files required)**
- Character Creator profile/reference APIs and `character/types.ts`
- Voice Studio M4.10 + readiness
- Scriptwriter document/scene + `prepareTimeline`
- `api.library` + existing asset pickers
- `avatar_runtimes.inspect_runtime` + Setup path
- `prepareAvatarTimeline` / `avatar.prepare_timeline` / `promote`
- Co-Director avatar tools

**New files: none required.** Optional extract later (`avatar/characterBind.ts`, `avatar/providerMatch.ts`) only if the monolith split is needed. Not Phase 1.

### Phase 2+ must NOT create
- No second avatar registry / character store / session store / `data_json` twin.
- No new App.tsx route; no new workspace id.
- No Timeline / DirectorTracks / `director_timeline_w46` edits unless a write API already exists (it does not write today).
- No second provider catalog (use `avatar_runtimes`).
- No fake composite / live-gen success while `_execute_section_generation` is uncertified.
- No TTS execution inside Avatar Studio (Voice Studio remains SOT).

### Verdict

READY TO IMPLEMENT — existing workspace, one session store, and handoff APIs are enough for cleanup, identity/library/eligibility wiring, and honest E2E of the current contract; live provider certification is an existing runtime gate, not an audit block.
