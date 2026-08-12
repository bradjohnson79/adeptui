# M42 W45 — Shared Contracts (Frozen)

| Field | Value |
|---|---|
| **Status** | FROZEN for Phase 4.5 build |
| **Change policy** | change request → impact analysis → primary approval → update → notify subagents |
| **Branch** | `phase2/m42-audio-studio-completion` |

Code mirrors: `studio-api/app/audio_studio/contracts.py`, `studio-web/src/audioStudio/contracts.ts`.

## Pipeline

```text
Brief → Intent → Provider Resolution → Generation Queue → Candidate Batch
→ Approval → Project Library → Timeline → Mixing → Preview → Render Plan → Provenance
```

## Core contracts

### AudioCreativeBrief
- project_id, scene_id?, shot_id?, category, prompt, duration_seconds?, mood[], intensity?, tempo?, instrumentation[], loop_required, start_behavior?, end_behavior?, reference_asset_ids[], notes?

### MusicIntent / SoundEffectIntent / AmbienceIntent
- Compiled from brief; category-specific fields; provider-neutral.

### AudioGenerationJob
- id, project_id, intent_id, provider, runtime, status, attempt_index, error?, output_asset_id?, created_at, completed_at?

### AudioCandidateBatch / AudioCandidate
- Batch: id, project_id, method (design|similar|ambience|sfx), brief_snapshot, candidate_ids[], parent_candidate_id?, created_at
- Candidate: id, batch_id, name, asset_id?, status (ready|failed|selected|approved|archived), summary?, provider?, runtime?, parent_candidate_id?, error?

### AudioApprovalDecision
- candidate_id, approved: bool, approved_by, approved_at — distinct from select-for-preview

### AudioVersionLineage
- version_id, parent_version_id?, asset_id, stems?: MusicStemSet, attempts[], provenance

### MusicStem / MusicStemSet
- Stem roles: Drums, Bass, Vocals, Pads, FX, Lead, Strings, Percussion, Custom
- Never fabricate stems when provider returns mixdown only (`stemsSupported: false`)

### AudioAssetMetadata
- roles: music_track, music_loop, music_stem, ambience, foley, reaction, sound_effect, transition, room_tone

### TimelineAudioClip / AudioPlacementIntent
- assetId, assetVersionId, category, provider, runtime, sourceIntentId, startTime, duration, gain, pan, mute, solo, loop, fadeIn, fadeOut, crossfadeToClipId?, approvalStatus, provenanceId

### AudioMixClipState / AudioMasterOutput
- gain, pan, mute, solo, normalize, fades, crossfade, trackRoute, peak/LUFS snapshots; master gain + meters

### HostedAudioProviderMapping / LocalAudioRuntimeMapping
- Preference: Kie.ai → WaveSpeed.ai → fal.ai (recommendation only; no silent switch)
- Local: ACE-Step (music), MMAudio (sfx/ambience)

### CoDirectorAudioProposal
- propose → preview → explicit approval → execute → persist → UI refresh

## Provider honesty labels

Certified | Testing | Available but uncertified | Unsupported | Unavailable | Requires setup
