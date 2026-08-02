# Timeline And Lip Sync Integration

## Timeline preparation

M4.10 uses an approved take as the handoff point for dialogue placement.

The backend preparation method is:

- `m410_service.prepare_timeline_dialogue()`

It returns a proposed clip payload containing:

- `recordId`
- `takeId`
- `assetId`
- `characterId`
- `voiceIdentityId`
- `sceneId`
- `scriptDocumentId`
- `scriptElementId`
- `startMs`
- `durationMs`
- `label`

It also reports:

- target `trackId`
- whether placement `wouldReplace`
- `existingClipIds`

## Timeline placement

The write endpoint is:

- `POST /api/voice-performance/m410/records/{recordId}/timeline`

This calls `place_timeline_dialogue()` and persists the approved take into:

- `project.settings_json.timeline.dialogueTracks`
- `record.timelineLinkage`

Replacement is guarded. If matching dialogue clips already exist for the same record or scene/script binding, the caller must confirm replacement explicitly.

## Lip Sync preparation

The M4.10 endpoint is:

- `POST /api/voice-performance/m410/records/{recordId}/lipsync`

This calls `prepare_lipsync()` and, when allowed, updates:

- `scene.lipsync_audio_asset_id`
- `scene.lipsync_enabled`
- optionally `scene.audio_asset_id`
- `record.lipsyncLinkage`

The stored linkage includes:

- `sceneId`
- `recordId`
- `takeId`
- `audioAssetId`
- `setSceneAudioAsset`
- `updatedScene`
- `wouldReplace`

## Co-Director tool pairing

The Co-Director layer exposes the related non-mutating previews:

- `voice.prepare_timeline_dialogue`
- `voice.prepare_lipsync`

Those tools surface replacement risk before a creator-approved apply step runs.

## Frontend behavior

`VoicePerformanceStudio.tsx` wires both actions from the Takes panel:

- `Send to Timeline`
- `Prepare for Lip Sync`

Both flows use a second-click confirmation pattern when replacement would occur.
