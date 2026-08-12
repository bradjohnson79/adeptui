# Image Pipeline Contracts

This document freezes the foundation contracts for `studio-api/app/image_pipeline/`.

## Purpose

The Image Pipeline foundation is the orchestration layer that prepares creator-safe image plans on top of the existing `image_product`, `image_runtime`, `spatial_map`, and character systems. It does not replace those systems.

## Core contracts

- `ProductionImageRequest`
  - Creator request payload with `purpose`, `qualityProfile`, and `deploymentPreference`.
- `ImageShotIntent`
  - Deterministic shot interpretation with subject count, complexity, motion, staging signals, and one optional clarification question.
- `CreativeDirectionPacket`
  - Storytelling packet with `scenePurpose`, `audienceFocus`, composition, lens, camera height, mood, lighting, color, movement, visual priority, stance, lighting emotion, purpose class, symmetry, and optional `visualLanguageProfileId`.
- `ImageReferenceAssignment`
  - Semantic reference binding for character, continuity, style, and visual-reference roles.
- `ImageContinuityPackage`
  - Lock level, protected elements, locked reference ids, and figure color map.
- `ImageControlPackage`
  - High-level staging choice plus optional `PoseCraftControlPackage` and `SpatialEnvironmentPackage`.
- `ImageModelRoute`
  - Capability-aware model route with explicit local or approval-gated API routing.
- `ImagePipelineStage`
  - Stage metadata for plan, pose, spatial, generation, evaluation, repair, mastering, approval, and selection.
- `ImageApprovalRequirement`
  - Explicit approval envelope for creator confirmation and paid-route consent.
- `ImageGenerationPlan`
  - Durable orchestration artifact containing request, shot intent, creative direction, controls, route, readiness, and provenance.
- `ImageCandidateEvaluation`
  - Honest pass, warning, fail, or not-evaluated result.
- `ImageCandidate` / `ImageCandidateGroup`
  - Draft, queued, ready, selected, rejected, and mastered candidate records that are never auto-deleted.
- `ImageMasteringRequest` / `ImageMasteringResult`
  - Controlled mastering record that never claims an upscale when only resize metadata exists.
- `StageReceipt`
  - Immutable per-stage provenance receipt.

## Foundation guarantees

- No silent API spend. API deployment requires explicit approval.
- No false success. Candidate generation can create draft slots without pretending finished assets exist.
- Creator-safe language. Preview text and recommendation explanations stay human readable.
- Honest staging. Spatial stubs disclose that a collage or reference is not true 3D scene data.
- Existing runtime ownership is preserved. The pipeline prepares and delegates; it does not rewrite lower layers.
