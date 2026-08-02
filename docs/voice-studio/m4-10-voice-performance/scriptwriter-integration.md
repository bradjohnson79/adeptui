# Scriptwriter Integration

## Record-level linkage

M4.10 records can bind voice performance to script structure with:

- `scriptDocumentId`
- `scriptElementId`
- `sceneId`

`m410_service.create_record()` validates that:

- the script document exists
- the script document belongs to the same project
- the referenced `scriptElementId` exists when provided

## `prepare_timeline` update

`studio-api/app/scriptwriter/service.py` now includes `elementId` for each dialogue proposal row returned by `prepare_timeline()`.

Each dialogue item also includes:

- `scriptDocumentId`
- `sceneHeadingId`
- `speaker`
- `text`
- `parenthetical`
- `previousLine`
- `nextLine`
- `revisionVersion`

That gives downstream tools a stable script-line handle instead of relying on speaker/text matching alone.

## Why this matters for M4.10

On the voice-performance side, timeline clip payloads and record data can now preserve `scriptElementId` alongside scene and character linkage. That improves continuity between:

- the original script line
- the saved performance record
- the approved take
- timeline dialogue placement

## Current frontend scope

The standalone `VoicePerformanceStudio.tsx` create-record path currently saves project, character, voice identity, dialogue text, plan, and emotion metadata directly. It does not itself populate script bindings unless a higher-level integration passes those values into the M4.10 record flow.
