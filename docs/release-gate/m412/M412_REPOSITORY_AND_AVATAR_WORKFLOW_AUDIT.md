# M4.12 Repository And Avatar Workflow Audit

## Audit Gate

| Field | Value |
| --- | --- |
| Mission | M4.12 Long-Form Avatar Studio |
| Repository | `C:\AdeptFilmWorks\AIVideoStudio` |
| Starting branch | `feature/m4-11-spatial-map-360-consistency` |
| Starting SHA | `fa09c99d6395` |
| Audit branch | `feature/m4-12-long-form-avatar-studio` |
| Audit mode | Repository and workflow audit only |
| Scope lock | No provider install, no broad UX rebuild, no implementation beyond audit docs |
| Status | **READY FOR PRIMARY REVIEW** |

---

## 1. Starting identity

- Audit branched from the current tip at `fa09c99d6395`.
- The working tree already carried substantial unrelated in-progress changes before this audit branch was created.
- This pass stayed audit-only and wrote documentation only.

---

## 2. Exact files inspected

### Avatar Studio and route wiring

- `studio-web/src/pages/ProjectEditor.tsx`
- `studio-web/src/components/AvatarStudioWorkspace.tsx`
- `studio-web/src/avatar/types.ts`
- `studio-api/app/avatar_studio.py`
- `studio-web/src/api.ts`

### Character Creator / identity / approved look

- `studio-web/src/components/CharacterProfileWorkspace.tsx`
- `studio-api/app/character_identity/api.py`

### Voice Studio / approved voice performance

- `studio-web/src/components/voiceStudio/VoicePerformanceStudio.tsx`
- `studio-api/app/voice_performance/router.py`
- `studio-api/app/voice_performance/m410_service.py`
- `studio-api/app/voice_performance/runtime/index_tts2.py`
- `docs/voice-studio/m4-10-voice-performance/timeline-and-lipsync-integration.md`

### Timeline / retake / repair

- `studio-api/app/director_timeline_w46/router.py`
- `studio-web/src/components/timeline-master/TimelineInpaintWorkspace.tsx`

### Scriptwriter / Bible / Co-Director / Library

- `studio-api/app/scriptwriter/api.py`
- `studio-web/src/components/ProductionBibleWorkspace.tsx`
- `studio-api/app/codirector/bible/domain/schemas.py`
- `studio-web/src/components/CoDirector/CoDirectorAssetPicker.tsx`
- `studio-api/app/project_library/service.py`
- `studio-api/app/routers/extra.py`

### Setup / Source Manager / runtime registry / providers

- `studio-api/app/setup/catalog.py`
- `studio-api/app/production_control/router.py`
- `studio-api/app/production_control/model_registry.py`
- `studio-api/app/model_registry/__init__.py`
- `studio-api/app/video_runtime/workflow_resolver.py`
- `studio-api/app/video_runtime/hunyuan_providers.py`
- `studio-api/app/hosted_providers/discovery.py`

### Existing tests

- `tests/e2e/m42/m42-production-menu.spec.ts`
- `studio-api/tests/test_install_jobs_m412.py`
- repository-wide test searches for `avatar`, `scriptwriter`, `director-timeline`, `project_library`, and `voicePerformanceM410`

---

## 3. What exists today

### Avatar Studio UI/API

- `Avatar Studio` is already routed as a first-class workspace from `ProjectEditor`.
- `studio-web/src/components/AvatarStudioWorkspace.tsx` is a real persisted workspace, not a placeholder.
- `studio-api/app/avatar_studio.py` provides CRUD, validation, and take registration over `avatar_sessions`.
- The current product shape is clip/session oriented:
  - character selection
  - look metadata
  - voice metadata
  - dialogue text
  - generic still/video generation
  - take registration
  - promote-to-scene handoff

### Session persistence

- Server persistence exists through `avatar_sessions.data_json`.
- Local bridge persistence also exists through `sessionStorage` keys:
  - `adept_selected_character`
  - `adept_avatar_profile`
- This is enough for reopening a selected character, but it is not a full long-form avatar production state model.

### Character Creator integration

- Character bootstrap is real:
  - `CharacterProfileWorkspace` writes selected character into session storage.
  - `AvatarStudioWorkspace` consumes that state and can auto-create a session for the selected character.
- Approved character identity is stronger in Character Creator than in Avatar Studio.
- Avatar Studio references character profiles, but it does not consume the richer approved-look / canonical identity contract as its primary execution source.

### Avatar reference images

- Character Creator already has reference-role and gallery concepts.
- Avatar Studio can select a `source_still_asset_id` from the project library.
- The current avatar flow does not define a dedicated avatar identity package made from approved portrait, approved talk-head framing, fallback refs, and provider-specific reference bundles.

### Dialogue input

- Avatar Studio stores:
  - `dialogue_original`
  - `dialogue_spoken`
  - `dialogue_adaptation_accepted`
- The UI explicitly says original dialogue is never silently changed.
- This is creator-friendly intent, but the data is still local to the avatar session and is not deeply linked to Scriptwriter scene/line identity.

### Voice Studio assets / IndexTTS2 approved takes

- Real approved voice identity and approved take workflows already exist in M4.10 Voice Studio.
- `m410_service.create_record()` requires an approved voice identity.
- `m410_service.approve_take()` persists a single approved take.
- `m410_service.place_timeline_dialogue()` and `prepare_lipsync()` both guard replacement with explicit confirmation.
- **Critical current-state finding:** Avatar Studio does not consume those approved takes. Its own UI still says the execute path is uploaded audio this pass, and the workspace writes `provider: "upload"` when attaching dialogue audio.

### Lip-sync paths

- Voice Studio has a real lip-sync preparation path through `m410_service.prepare_lipsync()`.
- Director Timeline has repair/retake infrastructure.
- Avatar Studio itself only tracks `mouth_mask.placed` and tells the creator to go to Director for lip sync.
- There is no avatar-native, end-to-end lip-sync orchestration for long-form presenters.

### Timeline handoff

- Avatar Studio handoff is currently `POST /api/projects/{project_id}/promote` with target `scene_new`.
- That creates a new scene from the chosen video asset.
- This is a valid asset handoff, but it is weaker than the M4.12 mission:
  - no section lineage
  - no shot/segment structure
  - no approved voice provenance on the resulting avatar clip
  - no final-assembly model

### Scriptwriter linkage

- Scriptwriter has real scene linking and timeline prep endpoints.
- Avatar session schema includes `links.script_segment_id`, `links.storyboard_panel_id`, `links.master_sheet_id`, `links.scene_id`.
- **Gap:** those links are not actually driven as the canonical source of avatar line production.

### Project Library

- Project Library is real and project-scoped.
- Avatar Studio can already browse/select audio, video, and image assets from the project library.
- Co-Director also reads from the library through `CoDirectorAssetPicker`.
- Library taxonomy is richer than Avatar Studio’s current usage.

### Production Bible

- Production Bible character schema already includes:
  - `avatarSessionId`
  - `characterProfileId`
  - `activeVoiceProfileId`
- That means the repo already anticipates avatar-related canon references.
- **Gap:** Avatar Studio is not currently driven by the Bible as the authoritative identity/performance memory for long-form avatar work.

### Co-Director tools

- Co-Director has strong surrounding systems for Bible, voice planning, and timeline tools.
- I found only a schema-level avatar hook, not a dedicated avatar-generation toolset with approved-voice / section-retake / final-assembly semantics.

### Generation queue

- Avatar Studio uses the generic job queue:
  - `imagegen`
  - `txt2vid`
- The workspace polls `api.getJob()` directly and tells the user to check the Jobs panel when polling times out.
- The queue exists and is real, but it is not specialized for long-form avatar shots, sections, retries, or assembly state.

### Setup / Source Manager / runtime manager / model registry

- Setup catalog and install-job plumbing exist for:
  - `IndexTTS2`
  - `WAN 2.2`
  - `HunyuanVideo 1.5`
  - `HunyuanVideo 13B`
  - image runtimes and extensions
- Production Control / model registry / hosted-provider discovery already expose current video model inventory.
- **Gap:** no setup/catalog/runtime entry exists yet for the M4.12 target avatar providers:
  - `LongCat-Video-Avatar 1.5`
  - `InfiniteTalk`
  - `MuseTalk 1.5`
  - `EchoMimicV2`

### Current avatar providers

- Current practical avatar generation rides on generic video paths:
  - local `ltx-local`
  - local `wan-local`
  - optional local `hunyuan-video-1.5-local`
  - optional local `hunyuan-video-13b-local`
  - hosted `seedance-fal`
  - hosted `kling-fal`
  - hosted `veo-fal`
  - non-executable discovery entries under Kie / WaveSpeed
- These are video providers, not dedicated long-form talking-avatar providers.

### Existing tests

- I found only one direct Avatar Studio end-user check:
  - `tests/e2e/m42/m42-production-menu.spec.ts` verifies gating when no character is selected.
- Voice Studio, Project Library, Scriptwriter, and Timeline have materially stronger test coverage than Avatar Studio.
- There is no focused test suite today for:
  - approved voice -> avatar generation binding
  - long-form avatar persistence
  - section retake
  - final assembly
  - avatar timeline provenance

---

## 4. Workflow trace findings

## Current repository trace

```text
Character Creator
  -> CharacterProfileWorkspace / character_identity API
  -> approved visual identity and references exist

Avatar Session Bootstrap
  -> sessionStorage selected character
  -> avatar_sessions row created / loaded

Voice Studio (separate stronger path)
  -> approved voice identity required
  -> IndexTTS2 performance takes generated
  -> one take explicitly approved
  -> timeline/lipsync replacement guarded

Avatar Studio (current actual path)
  -> optional voice profile metadata
  -> uploaded audio asset or selected library audio
  -> generic imagegen / txt2vid job
  -> take registered inside avatar session
  -> promote asset to new scene

Director Timeline
  -> retake / repair ranges / immutable snapshot lineage exist

Breaks for M4.12
  -> Avatar Studio does not require approved voice performance
  -> no avatar-native section model
  -> no final assembly object
  -> no canonical handoff from approved voice take into avatar generation provenance
  -> no dedicated long-form avatar provider/runtime layer
```

## End-to-end mission trace vs current reality

### Character -> Avatar Identity

- Partially exists.
- Character identity and approved look systems are real.
- Avatar Studio can attach a character, but it does not yet elevate a creator-approved avatar identity bundle as the canonical execution artifact.

### Avatar Identity -> Approved Voice Performance

- Break.
- Voice Studio owns the stronger approved-take flow.
- Avatar Studio still accepts any library/uploaded audio and does not enforce use of an approved IndexTTS2 take.

### Approved Voice Performance -> Avatar Generation

- Break.
- No audited code path binds an approved `m410` take directly into avatar generation as the mandatory source.

### Avatar Generation -> Section Retake

- Partial but indirect.
- Director Timeline already supports repair ranges and retake lineage.
- Avatar Studio itself has no section-aware retake model for presenter clips.

### Section Retake -> Final Assembly

- Break.
- I found no dedicated long-form avatar final-assembly record or workspace contract.

### Final Assembly -> Timeline

- Weak partial.
- Current handoff is scene creation from a promoted video asset, not a sectioned long-form avatar assembly with provenance.

---

## 5. Gaps vs the M4.12 mission

1. **Avatar Studio is clip-oriented, not long-form.** The session model is built around a single generated clip plus takes, not a presenter performance broken into sections with durable assembly state.

2. **Voice Studio ownership is not actually enforced in Avatar Studio.** M4.12 says Voice Studio owns voice and Avatar must consume approved voice assets, but current Avatar Studio still works from uploaded/selectable audio.

3. **No dedicated avatar identity contract exists.** Character refs and approved looks exist, but there is no explicit Avatar Identity object for talk-head production across providers.

4. **Timeline semantics are too thin.** Promote-to-scene is a useful asset bridge, but not the long-form Timeline handoff needed for section retakes and final assembly lineage.

5. **Scriptwriter linkage is present in schema but not in execution.** The session link fields exist, but they are not the canonical driver of avatar line generation.

6. **Provider/runtime infrastructure does not yet include the target avatar providers.** The repo is ready for model/runtime plumbing in general, but not for the locked M4.12 provider list.

7. **Co-Director and Production Bible are adjacent, not central.** Schema hooks exist, but there is not yet a creator-facing avatar workflow where Co-Director and Bible memory actively guide avatar identity, performance, retakes, and approvals.

8. **Test coverage is too shallow for a release gate.** Avatar workflow certification would currently depend on surrounding systems, not on dedicated avatar tests.

---

## 6. Creator-first UX audit notes

Current Avatar Studio violates creator-first principles in several ways:

1. It exposes too many low-level controls at once in a single inspector rather than a guided long-form presenter flow.
2. It surfaces implementation language like `provider`, `mode`, `lip_sync_method`, and direct prompt fields instead of defaulting to creator language.
3. It asks creators to manually bridge between Avatar Studio and Director for mouth mask/lip sync rather than carrying them through a single guided workflow.
4. It separates the strongest approval path, Voice Studio approved takes, from the Avatar workspace that should consume it.
5. It treats long-form presenter work like generic txt2vid generation instead of a simple story: pick presenter identity, choose approved voice performance, generate section, retake section, assemble, send to Timeline.

This does not mean the current workspace should be discarded. It means the power is present, but the M4.12 presentation and orchestration layer does not yet exist.

---

## 7. Blocking risks

1. **State split across too many systems.** Avatar session state, character identity state, voice performance records, timeline settings, scene fields, and library assets all persist independently today.

2. **Approved voice could be bypassed accidentally.** Without a hard contract, long-form avatar work could silently drift back to arbitrary uploaded audio.

3. **Provider work started too early would cement the wrong contract.** Installing or wiring target avatar providers before defining the avatar identity + approved voice + section assembly model would create rework.

4. **Timeline provenance is currently too weak for long-form certification.** Promoted scene assets do not carry the richer lineage M4.12 will need.

5. **Tests would not currently catch core regressions.** The direct Avatar Studio test footprint is minimal.

6. **Branch hygiene risk exists.** This branch inherits a heavily modified working tree; broad implementation will need discipline to avoid mixing unrelated work.

---

## 8. Recommended implementation order after audit

1. **Freeze the M4.12 contracts first.**
   Define:
   - Avatar Identity
   - Approved Voice Asset handoff from Voice Studio
   - Long-form section record
   - Final Assembly record
   - Timeline provenance fields

2. **Make Avatar consume approved voice performance, not arbitrary audio.**
   Keep Voice Studio as owner of voice identity and IndexTTS2 performance.
   Avatar should reference approved voice takes/assets, not duplicate voice generation logic.

3. **Refactor Avatar Studio from single-clip session to sectioned long-form workflow.**
   Add section list, per-section generation state, retake lineage, and assembly state before adding new providers.

4. **Define avatar identity inputs from approved character assets.**
   Use Character Creator / approved look / library references to build the canonical avatar identity package.

5. **Add dedicated provider/runtime plumbing for the target avatar providers.**
   Only after the contracts are fixed:
   - setup catalog / source manager entries
   - runtime/model registry entries
   - honest readiness states
   - no silent fallback behavior

6. **Wire Timeline retake/repair semantics into Avatar-native UX.**
   Reuse existing Director Timeline lineage infrastructure instead of inventing a second retake system.

7. **Integrate Scriptwriter, Production Bible, and Co-Director around the new contracts.**
   Script lines, canon facts, and performance notes should reference the same avatar identity and approved voice assets.

8. **Add focused tests only after the new workflow is real.**
   Minimum expected:
   - unit/API coverage for avatar contracts
   - end-to-end approved voice -> avatar -> retake -> assembly -> timeline flow
   - persistence across reload
   - replacement/overwrite guard coverage

---

## 9. Primary implementation guidance

### Extend, do not replace

- Extend the stronger existing systems:
  - Character Creator for identity
  - Voice Studio for approved voice performance
  - Project Library for asset scope
  - Director Timeline for retake lineage
  - Setup / Production Control for runtime registry

### Avoid as first moves

- Do not start with provider installation.
- Do not start with a full Avatar Studio visual rewrite.
- Do not create a second voice-performance system inside Avatar Studio.
- Do not bypass approved voice by treating uploaded audio as equivalent to an approved Voice Studio asset.

---

## 10. Audit conclusion

The repository already contains many of the right building blocks for M4.12: real character identity, real approved voice performance, real library persistence, real timeline retake lineage, and real runtime/setup infrastructure. What is missing is the contract and orchestration layer that turns those separate systems into one creator-first long-form Avatar Studio.

The current Avatar Studio should be treated as an existing persisted prototype surface, not as the finished foundation for M4.12. It is useful because it already owns avatar-session persistence and generation hooks, but it is not yet the authoritative long-form presenter workflow described in the mission.

**READY FOR PRIMARY REVIEW**
