# M4.12 Voice, Timeline, and Retake Integration

Status: implementation-aligned integration notes for Avatar Studio creative handoff, approved voice usage, localized retakes, and timeline provenance.

## What this pass adds

- Approved Voice mode now requires a real approved Voice Studio take
- Scriptwriter document and scene linkage can be saved into Avatar Studio session provenance
- Section retakes now preserve prior section versions, retake reasons, and neighboring context
- MuseTalk 1.5 is treated as a Lip-Sync Repair path, not a full avatar generation path
- Timeline handoff packages now carry script, voice, retake, and section-map provenance
- Audio Mix access is exposed without overwriting the Voice Studio master by default

## Approved voice contract

Avatar Studio now follows the Voice Studio source-of-truth rule more strictly.

- `input_mode="approved_voice"` requires:
  - `voice.audio_asset_id`
  - `voice.approved_record_id`
  - `voice.approved_take_id`
- Job creation fails with `AVATAR_APPROVED_VOICE_REQUIRED` if that linkage is incomplete
- Fallback audio now lives separately at `voice.fallback_audio_asset_id`
- Choosing fallback audio no longer clears approved take linkage silently

That preserves the creator expectation that an approved performance came from Voice Studio and was not regenerated inside Avatar Studio.

## Scriptwriter source linkage

Avatar Studio now saves Scriptwriter provenance in the session `links` payload:

- `script_document_id`
- `script_scene_heading_id`
- `script_scene_id`
- `script_source_label`
- `script_revision_version`

The workspace can:

1. Select a script document
2. Select a scene
3. Pull scene dialogue into the presenter script
4. Keep the source linkage attached to the session and downstream job

Job-level provenance mirrors that linkage under:

- `job.scriptSource`
- `job.scriptSourceId`

## Retake system

Localized retakes are now treated as lineage-preserving requests instead of destructive overwrites.

Each retake request stores:

- `retakeActionType`
- `retakeReason`
- `retakeRequest`
- `retakeHistory[]`
- `versionHistory[]`
- neighboring section context

The preserved version snapshot captures:

- prior output video asset id
- prior continuation frame id
- prior presentation plan
- attempt number
- captured timestamp

The current section remains in place with its existing output asset while the retake request is recorded. Other completed sections are left untouched.

Creator-facing actions wired in the workspace:

- `Re-perform Sentence`
- `Re-sync Paragraph`
- `Regenerate Gesture`
- `Correct Pronunciation`
- `Replace Voice Performance`
- `Replace Background`
- `Regenerate Section`
- `Repair Lip-Sync`

## MuseTalk repair path

MuseTalk integration is intentionally narrow in this pass.

- Role: `Lip-Sync Repair`
- Provider id: `musetalk-1-5-local`
- UI behavior: dubbing / repair planning, not full avatar generation claims
- Honest failure: `AVATAR_LIPSYNC_REPAIR_PROVIDER_REQUIRED` when MuseTalk is not installed

`avatar.repair_lipsync` stores a repair plan and runtime evidence only. It does not fabricate a repaired video output.

## Timeline handoff

The existing Co-Director `avatar.prepare_timeline` proposal path now persists a richer handoff package.

Placement modes:

- `full_presentation`
- `selected_section`
- `replace_section`
- `create_alternate_take`

Stored payload includes:

- job id
- session id
- placement mode
- selected section ids
- ready section ids
- generated timeline clip payloads
- script provenance
- voice provenance
- section map
- retake history per section
- audio mix linkage

Key provenance fields:

- `avatarId`
- `providerId`
- `script.documentId`
- `script.sceneHeadingId`
- `voice.approvedRecordId`
- `voice.approvedTakeId`
- `voice.audioAssetId`
- `sectionMap[]`
- `retakeHistory`
- `assemblyVersion`

Timeline packages remain proposal-gated and keep `timelineWritten=false` in this pass.

## Audio Mix access

Avatar timeline proposals now attach an `audioMix` block that points Audio Studio at the dialogue stem without destructive overwrite:

- `dialogueStemAssetId`
- `voiceStudioMasterAssetId`
- `openWorkspace="audiostudio"`
- `destructiveOverwriteAllowed=false`

The Avatar Studio workspace also exposes `Open Audio Mix` as a direct creator action.

## Workspace changes

`AvatarStudioWorkspace.tsx` now includes:

- Script document + scene selection in Script mode
- `Use Scene Dialogue`
- stronger Approved Voice gating copy
- separated fallback audio selection
- `Prepare Lip-Sync Repair` CTA for existing-video mode
- creator-facing retake action list per completed section
- Timeline handoff hooks for full presentation, selected section, replace section, and alternate take
- `Open Audio Mix`

## API and tool changes

Backend:

- `POST /api/projects/:projectId/avatar-jobs/:jobId/timeline/prepare`
- stricter job creation gate for Approved Voice mode
- richer retake persistence on `POST /sections/:sectionId/retake`

Co-Director:

- `avatar.request_retake` now supports action-specific retake reasons
- `avatar.repair_lipsync` now checks MuseTalk installation honestly
- `avatar.replace_voice` now requires approved take linkage
- `avatar.prepare_timeline` now stores full provenance

## Tests

Focused coverage added for:

- approved voice gate
- retake version preservation
- MuseTalk repair provider requirement
- timeline handoff provenance

Verified with:

- `python -m pytest studio-api/tests/test_m412_avatar_long_form.py studio-api/tests/test_m412_codirector_avatar_tools.py`
- `npm run build` in `studio-web`

## Honest limitations

- Avatar timeline handoff is still proposal-first; this pass does not claim automatic final clip insertion into a certified timeline path
- MuseTalk repair is recorded as a repair plan only; no live repaired media is fabricated
- Approved Voice mode enforces approved take linkage, but the workspace still allows pure script mode for planning before voice approval

**READY FOR PRIMARY REVIEW**
