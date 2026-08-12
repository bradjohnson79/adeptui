# M4.12 Retakes

Avatar Studio retakes are now localized, traceable, and non-destructive by default.

## Creator actions

- `Re-perform Sentence`
- `Re-sync Paragraph`
- `Regenerate Gesture`
- `Correct Pronunciation`
- `Replace Voice Performance`
- `Replace Background`
- `Regenerate Section`
- `Repair Lip-Sync`

## Persistence model

Each section can now retain:

- `retakeRequest`
- `retakeHistory[]`
- `versionHistory[]`
- `retakeActionType`
- `retakeReason`

Each preserved version snapshot records:

- prior output video asset
- prior continuation frame
- prior presentation notes
- attempt number
- timestamp

## Continuity rule

Localized retakes must not erase completed neighboring sections.

This pass enforces that by:

- preserving the current section output as a saved version
- storing neighboring context with the retake request
- leaving other completed sections untouched

## Honest limitation

Retakes are recorded and proposal-gated in this pass. The system does not claim automatic repaired media output unless a real runtime later produces it.
