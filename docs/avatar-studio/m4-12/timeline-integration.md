# M4.12 Timeline Integration

Avatar Studio timeline handoff now preserves creator-facing provenance instead of flattening a presenter pass into an untraceable clip.

## Handoff path

Proposal-gated Co-Director tool:

- `avatar.prepare_timeline`

Direct API helper:

- `POST /api/projects/:projectId/avatar-jobs/:jobId/timeline/prepare`

## Placement modes

- `full_presentation`
- `selected_section`
- `replace_section`
- `create_alternate_take`

## Stored provenance

Each timeline proposal now carries:

- `avatarId`
- `providerId`
- `script.documentId`
- `script.sceneHeadingId`
- `script.sceneId`
- `voice.approvedRecordId`
- `voice.approvedTakeId`
- `voice.audioAssetId`
- `sectionMap`
- `retakeHistory`
- `assemblyVersion`

## Audio handoff

Timeline proposals also include:

- `audioMix.dialogueStemAssetId`
- `audioMix.voiceStudioMasterAssetId`
- `audioMix.destructiveOverwriteAllowed=false`

That gives Audio Studio access to the dialogue stem for loudness and mix work without silently replacing the Voice Studio master.

## Honest limitation

This pass prepares and persists a traceable handoff package. It does not claim certified automatic final clip insertion.
