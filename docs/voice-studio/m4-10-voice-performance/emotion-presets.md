# Emotion Presets

## Backend source of truth

M4.10 preset definitions live in:

- `studio-api/app/voice_performance/emotion_presets.py`

The preset API is:

- `GET /api/voice-performance/m410/emotion-presets`

## Supported emotion vectors

Preset vectors are limited to the IndexTTS2-compatible keys:

- `joy`
- `sadness`
- `anger`
- `fear`
- `surprise`
- `disgust`
- `contempt`

`normalize_mix()` removes unsupported keys, clamps negatives away, and normalizes the remaining weights to total `1.0`.

Alias support is intentionally small:

- `hate` maps to `contempt`

## Current presets

The shipped preset set is:

- `quiet-grief`
- `contained-anger`
- `warm-reassurance`
- `fear-beneath-calm`
- `embarrassed-sincerity`
- `defensive-humor`
- `soft-pleading`
- `growing-panic`
- `cold-authority`
- `tender-vulnerability`
- `joyful-relief`
- `exhausted-determination`

Each preset carries:

- `name`
- `emotionVector`
- `intensity`
- `delivery`
- `pacing`
- `breath`
- `notes`
- `summary`

## UI behavior

When the creator selects `Emotion Preset` in `VoicePerformanceStudio.tsx`, the UI:

- sets `emotionSource` to `preset`
- loads the preset's `emotionVector`
- copies its direction fields into the active plan

That keeps the frontend and backend preset language aligned.

## Co-Director interplay

`build_codirector_performance_plan()` accepts `presetId` in its context. When present, the preset vector and direction fields become the basis of the proposed Co-Director plan instead of the keyword-based fallback mix.
