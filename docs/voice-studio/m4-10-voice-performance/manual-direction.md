# Manual Direction

## Purpose

Manual Direction is the creator-led alternative to `Co-Director Recommended`.

In `VoicePerformanceStudio.tsx`, switching to `Manual Direction` keeps the same line-focused workspace but lets the creator author the active performance plan directly.

## Editable fields

The manual plan is persisted as freeform structured direction, including:

- `emotionLabel`
- `intensity`
- `delivery`
- `pacing`
- `breath`
- `emphasis`
- `subtext`
- `performanceReference`
- `notes`
- `presetId`
- `emotionVector`

These values are serialized from the UI and saved through:

- `POST /api/voice-performance/m410/records`
- `PATCH /api/voice-performance/m410/records/{recordId}/performance-plan`
- `POST /api/voice-performance/m410/records/{recordId}/direction-mode`

## Persistence rules

`m410_service.set_direction_mode()` preserves both stored plans:

- `manualPlan`
- `codirectorPlan`

Switching modes changes which plan is active in `performancePlan`; it does not erase the inactive mode.

## What manual mode does not do

Manual Direction only updates direction metadata.

It does **not**:

- auto-generate takes
- auto-approve a take
- auto-place dialogue on the Timeline
- auto-prepare Lip Sync

Generation remains a separate creator action in the Takes panel.
