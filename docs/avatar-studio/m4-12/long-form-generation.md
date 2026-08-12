# M4.12 Long-Form Avatar Generation

Status: implementation-aligned architecture and contract notes for the first persistent long-form Avatar Studio engine.

## What this pass adds

- Persistent `AvatarProjectJob` records per presenter session
- Deterministic script-to-section planning with overlap windows
- Section-level status, retry, pause, resume, cancel, approve, and retake hooks
- Honest provider dispatch that never fakes successful long-form generation
- Assembly gating that refuses completion until transition validation is recorded
- Workspace wiring for the `Sections` and `Progress` tabs against real job state

## Data model

Primary persisted record:

```ts
type AvatarProjectJob = {
  id: string;
  projectId: string;
  sessionId: string;
  avatarId: string;
  providerId: string;
  scriptSourceId?: string;
  audioAssetId: string;
  sections: AvatarGenerationSection[];
  assemblyState: string;
  requestedDurationMs: number;
  completedDurationMs: number;
  status: "planning"|"queued"|"generating"|"paused"|"assembling"|"completed"|"failed"|"cancelled";
  createdAt: string;
  updatedAt: string;
};
```

Each section stores the required M4.12 fields plus a few operational helpers:

- `attempt`
- `retryCount`
- `errorMessage`
- `updatedAt`
- `retakeNote`

Those helpers support section-only retries without replacing the rest of the job.

## Section planning

Planning starts from the saved Avatar Studio session:

- `dialogue_spoken` or `dialogue_original`
- approved/fallback audio attachment metadata
- presentation style, framing, background, and continuity lock
- selected provider or best-match fallback

The planner:

1. Chooses a target section size from `duration_class`
2. Splits script text into sentence-aware chunks
3. Estimates timing windows per chunk
4. Assigns `overlapBeforeMs` / `overlapAfterMs`
5. Writes continuity and transition-validation hooks into `presentationPlan`

If there is approved/fallback audio but no script text, the planner still creates a persistent section shell rather than pretending the pass is complete.

## Continuity contract

Each section references a shared style profile and identity lock:

- `sharedStyleProfileId`
- `identityProfileRef`
- `continuity.previousSectionId`
- `continuity.requiresContinuationFrame`
- `transitionValidation.required`

This keeps all sections bound to one presenter session instead of spawning per-section projects or independent visual identities.

## Provider dispatch honesty

The live section executor is intentionally conservative in this pass.

- If the runtime is not installed, section dispatch fails with `AVATAR_SECTION_PROVIDER_NOT_INSTALLED`
- If the runtime is installed but unavailable, it fails with `AVATAR_SECTION_RUNTIME_UNAVAILABLE`
- If the runtime is installed and experimental, it still fails honestly with `AVATAR_SECTION_PROVIDER_NOT_CERTIFIED`

This means Avatar Studio can plan and enqueue real long-form jobs today without pretending the experimental avatar runtimes are production-ready.

Tests monkeypatch the executor seam to simulate successful section outputs, but production code does not fabricate success.

## Job controls

Session-scoped endpoints:

- `GET /api/projects/:projectId/avatar-sessions/:sessionId/jobs`
- `POST /api/projects/:projectId/avatar-sessions/:sessionId/jobs`

Job-scoped endpoints:

- `GET /api/projects/:projectId/avatar-jobs/:jobId`
- `POST /api/projects/:projectId/avatar-jobs/:jobId/pause`
- `POST /api/projects/:projectId/avatar-jobs/:jobId/resume`
- `POST /api/projects/:projectId/avatar-jobs/:jobId/cancel`
- `POST /api/projects/:projectId/avatar-jobs/:jobId/transition-validation`
- `POST /api/projects/:projectId/avatar-jobs/:jobId/assemble`
- `POST /api/projects/:projectId/avatar-jobs/:jobId/sections/:sectionId/retry`
- `POST /api/projects/:projectId/avatar-jobs/:jobId/sections/:sectionId/retake`
- `POST /api/projects/:projectId/avatar-jobs/:jobId/sections/:sectionId/approve`

## UI mapping

`AvatarStudioWorkspace.tsx` keeps the creator-first layout and now maps the lower workspace to real job state:

- `Sections`
  - lists persistent sections in order
  - shows duration, overlap, continuity hook status, and section errors
  - exposes `Retry Section`, `Request Retake`, and `Approve Section`
- `Takes`
  - reflects section attempt/retry state for long-form jobs
- `Progress`
  - shows real job status, completed-vs-total sections, assembly state, and last honest error
  - exposes `Pause`, `Resume`, `Cancel`, `Validate Transitions`, and `Assemble`
- `Completed Videos`
  - reports honest assembly-stub completion state
  - does not claim a composite video asset when none exists

## Assembly rules

Assembly is intentionally a stubbed control-plane step in this pass.

- It will not run if any section is incomplete or failed
- It will not mark the job complete until transition validation is explicitly recorded
- When all sections are complete and transition validation exists, it marks the job `completed` with `assemblyState="assembled_stub"`
- It still reports `compositeVideoAssetId: null`

This preserves the long-form lifecycle contract without faking a final rendered video.

## Typed errors

Creator-facing typed errors added in this pass:

- `AVATAR_SECTION_INPUT_REQUIRED`
- `AVATAR_SECTION_NOT_RETRIABLE`
- `AVATAR_SECTION_PROVIDER_NOT_INSTALLED`
- `AVATAR_SECTION_RUNTIME_UNAVAILABLE`
- `AVATAR_SECTION_PROVIDER_NOT_CERTIFIED`
- `AVATAR_SECTION_CANCELLED`
- `AVATAR_JOB_NOT_PAUSABLE`
- `AVATAR_JOB_NOT_RESUMABLE`
- `AVATAR_JOB_NOT_CANCELLABLE`
- `AVATAR_ASSEMBLY_EMPTY`
- `AVATAR_ASSEMBLY_SECTIONS_INCOMPLETE`
- `AVATAR_ASSEMBLY_TRANSITION_VALIDATION_REQUIRED`

Each returns plain-language `message` and `recovery` guidance.

## Tests in this pass

Focused API coverage:

- section planning persistence
- overlap and continuity hooks
- failed-section retry independence
- job persistence reload
- pause / resume / cancel controls

## Honest limitations

- No provider in this pass is marked Ready or Certified for live long-form generation
- Section execution defaults to honest failure until a provider-specific live engine is approved
- Final composite rendering is still a stub
- Timeline placement for long-form assembled avatar jobs is not part of this pass

**READY FOR PRIMARY REVIEW**
