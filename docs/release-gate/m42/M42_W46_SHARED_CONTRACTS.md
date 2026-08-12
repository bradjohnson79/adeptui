# M42 W46 — Shared Contracts (Frozen)

Python: `studio-api/app/director_timeline_w46/contracts.py`  
TypeScript: `studio-web/src/timelineMaster/contracts.ts`

## Locked decisions

1. **BatchBlock** = stable production container (ID never changes when approved media changes).
2. **DurationState** = `plannedDuration` | `generatedDuration` | `timelineVisibleDuration` | `sourceMediaDuration`.
3. **ExecutionSnapshot** = immutable; jobs/candidates store `executionSnapshotId` only.
4. **CancelAction** enum with hosted cancel labelled `unsupported` when not real.
5. **BatchStatus** includes `ApprovedConfigurationChanged` / `RegenerationRecommended`.
6. **RepairOverlapPolicy** = `block` (default) | `merge` | `stack_advanced`.
7. **InPaintStrategy** never claims `native` unless certified (currently disclosed fallback).

## Gate flags (directorTimelineGo)

Includes: executionSnapshotPassed, batchInvalidationPassed, durationStateSeparationPassed, repairOverlapPolicyPassed, sceneCancelResumePassed, immutableProvenancePassed, plus migration/UX/playwright/attribution flags.

Dock geometry flags are prerequisites only and do not alter `productionDockGo`.

## Contract change process

Impact analysis → primary approval → dual-language update → notify dependents → update tests.
