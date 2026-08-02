# Emotional Reference Audio

## Current implemented scope

M4.10 supports emotional reference audio as a **creator intent and persistence feature**.

In `VoicePerformanceStudio.tsx`, choosing `Emotional Reference Audio` lets the creator:

- upload an audio file into the current project library
- store `emotionalReferenceAssetId`
- adjust `emotionalReferenceStrength`
- save `emotionSource = "emotional_reference_audio"`

## Stored on the record

These fields persist on `voice_performance_records`:

- `emotionSource`
- `emotionalReferenceAssetId`
- `emotionalReferenceStrength`

They are returned on every M4.10 record read and survive reload.

## What is wired today

The upload path is real:

- the frontend calls `api.uploadAsset(projectId, file, "voice_emotional_reference", "audio")`
- the resulting project asset id is stored on the M4.10 record

Take generation resolves the asset path and passes it into IndexTTS2 separately from Voice Identity:

- `m410_service.create_takes` → `emotion_audio_path`
- runtime `generate_take` → `emotionAudioPath` / worker `emo_audio_prompt`
- Voice Identity reference remains `referenceAudioPath` / `spk_audio_prompt`

Emotional reference guides **how** the line is performed; it must not replace who is speaking.
