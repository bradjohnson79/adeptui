# M410 Data And Persistence

## Scope

M4.10 adds durable Voice Performance persistence inside the existing `studio-api/app/voice_performance/` package.

- New SQLAlchemy tables: `voice_performance_records`, `voice_performance_takes`
- New API routes under `/api/voice-performance/m410/`
- New service flow for record creation, editable performance plans, take generation state, approved-take exclusivity, timeline placement, and lipsync linkage
- Creative emotion presets mapped to supported IndexTTS2 vectors only: `joy`, `sadness`, `anger`, `fear`, `surprise`, `disgust`, `contempt`

## Persistence Contract

`voice_performance_records` stores the durable creator-facing record:

- Project, scene, script, character, and voice identity linkage
- Active `directionMode`
- Current `performancePlan`
- Preserved `manualPlan` and `codirectorPlan`
- Emotion metadata, approved take pointer, consent snapshot
- Timeline and lipsync linkage snapshots for reload-safe UI state

`voice_performance_takes` stores independent generation attempts:

- Take numbering and labels
- Runtime job linkage
- Audio asset linkage
- Status lifecycle: `queued | running | completed | failed | cancelled | approved | rejected`
- Frozen direction snapshot for auditing and comparison

## Behavioral Rules

- Approved voice identity is required before M4.10 record creation or take generation.
- Switching `directionMode` preserves the other mode's saved plan.
- Applying a performance plan never auto-approves a take.
- Only one primary approved take may exist per record at a time.
- Timeline placement does not replace existing dialogue clips without explicit confirmation.
- Lipsync linkage updates the target scene audio references when a linked scene exists.
- Capability metadata is honest: live generation is only reported as available when the local runtime reports `ready=true`.

## Runtime Honesty

The local `index-tts2-local` runtime contract intentionally separates:

- `installed`
- `ready`
- `supportsLiveGeneration`

Scaffolding the runtime contract does not claim model readiness. Verification must still report the runtime as ready before generation is treated as available.

## Test Coverage

`studio-api/tests/test_m410_voice_performance.py` covers:

- emotion preset mapping
- emotion vector validation
- direction-mode switching persistence
- approved voice identity requirement
- approved take exclusivity
- timeline and lipsync payload shape
- capability metadata honesty
