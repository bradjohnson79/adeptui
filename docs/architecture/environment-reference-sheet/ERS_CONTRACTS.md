# Environment Reference Sheet Contracts

This document freezes the foundation contracts for `studio-api/app/environment_reference_sheet/`.

## Standing laws

1. Co-Director is the only canonical ERS creation path.
2. ERS reuses existing `spatial_map`, `image_pipeline`, Library, and Production Bible systems.
3. North lock is required before primary directional view planning.
4. No silent approval, no silent canon mutation, and no silent paid generation.
5. Optional 3D labels must stay truthful: `illustrative`, `isometric`, `derived`, or `true`.
6. Continuity findings in this foundation pass are metadata-based unless a later capability explicitly adds pixel-level review.

## Frozen record

- `EnvironmentReferenceSheet`
  - Canonical project-owned ERS record with `sheetId`, `projectId`, profile, linked Spatial Map, directional views, continuity, composition, registration, exports, provenance, and revision law.
- `EnvironmentProfile`
  - Environment description, visual DNA, atmosphere, scale, architecture, palette, lighting, and continuity locks.
- `SpatialMapReference`
  - Bound Spatial Map id/version, north lock, reference bundle summary, warnings, and directional prompts.
- `DirectionalViewRecord`
  - One of `north|east|south|west`, with source spatial direction, Image Pipeline plan/group ids, approved asset, status, and warnings.
- `OptionalThreeDRecord`
  - Truth label plus optional asset link. Never implies a mesh if one does not exist.
- `ContinuityValidationReport`
  - Cross-view findings, preserved directions, repair strategy, summary, and evaluation timestamp.
- `ERSCompositionRecord`
  - Creator-facing rendered-sheet metadata and produced asset ids/files.
- `ERSProjectRegistration`
  - Production Bible location link, library path, linked scenes, and project-memory notes.
- `ERSExportRecord`
  - Export kind, status, asset id, file path, archive name, and disclosure message.
- `ERSCreationPlan`
  - Creator preview, readiness, reasons, stages, and approval requirements.
- `ERSRevisionLaw`
  - Preserve approved directions, require north lock, and require approval for mutations.

## Direction mapping

ERS locks the four creator-facing directions to Spatial Map capture references:

- `north` -> `front`
- `east` -> `right`
- `south` -> `rear`
- `west` -> `left`

The environment stays constant while the camera rotates. The world does not redesign itself per direction.

## Revision law

- Approved directions are protected during repair by default.
- Repairs should target only missing or blocked directions unless the creator explicitly asks for a broader rebuild.
- Registration and export never backfill fake success; each export record is explicit about what was created.
