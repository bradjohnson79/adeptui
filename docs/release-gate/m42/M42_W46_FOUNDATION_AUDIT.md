# M42 W46 — Foundation Audit

**Branch:** `phase2/m42-director-timeline-master`  
**Cut from:** `phase2/m42-production-dock` @ `f758744`  
**Wave:** W46

## Attribution

> Adept UI’s Director Timeline builds upon Director 2.0 created by WhatDreamsCost, extending its timeline-driven generation foundation with reference-aware Batch Blocks, multi-shot scene orchestration, local and hosted model routing, continuity management, Co-Director preflight, Re-Take, Timeline InPaint, background repair, Razor-based multi-range correction, nondestructive version lineage, and production-ready end-to-end workflows.

## Preserved Director 2.0 behaviors

- Prompt Timeline / `prompt_segments`
- `media_mode` image | video
- `image_clips` / `video_clips` / camera / audio / sfx
- LivePreviewMonitor, send-to-editor
- `director_references` COW bindings
- Continuity findings-only (no silent repair)

## Gaps closed by W46

| Gap | Resolution |
|-----|------------|
| No Batch Block | Stable production container in `timelineMaster` |
| Free-floating prompts | Timed Prompt Segments on Batch |
| No execution snapshot | Immutable `ExecutionSnapshot` on submit |
| Overloaded duration | planned / generated / visible / source |
| Cancel ambiguous | Explicit cancel/resume actions |
| Silent post-approval edits | Approved — Configuration Changed |
| Repair overlap | Block / Merge / Advanced stack |
| Fake native InPaint | Strategy disclosure |

## Out of scope (W47)

Docker installation, custom runtime import, custom-node isolation, safe uninstall.

## Dock prerequisite (not productionDockGo)

Stamped in `artifacts/m42/w46/prerequisites.json`:

- dockSingleRowPassed
- dockNoWrap1280Passed
- dockNoWrap1920Passed
- dockTimelineCollisionPassed
