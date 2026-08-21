# PHASE — PoseCraft Full Overhaul + Co-Director Integration

**Law 30 governing document** for this milestone.

Supersedes [PHASE-POSECRAFT-V4-VISUAL-INTERACTION.md](./PHASE-POSECRAFT-V4-VISUAL-INTERACTION.md) (historical; that pass stopped at untracked assets and T-pose rest).

Completion report: [POSECRAFT_FULL_OVERHAUL_COMPLETION_REPORT.md](./POSECRAFT_FULL_OVERHAUL_COMPLETION_REPORT.md)

## Status

Implemented and certified on `feat/posecraft-v4-human-replacement` against live Beta (`http://127.0.0.1:8760/` + `http://127.0.0.1:8758/`).

Cert project: Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`.

Hosted Vercel deploy is **out of scope** for this milestone.

## Architecture (frozen)

- Visible humans are Fable v4 GLB region meshes with static arm-chain bind rotations.
- Semantic rig is the certified **hanging-arm** 17-joint rest (zero pose = arms at sides).
- Pose catalog and Pose Intelligence are **not** rebaked.
- Invisible pick colliders sit on region meshes; two-pass pick prefers exact body hits.
- Co-Director `posecraft.apply_pose` writes real, limit-clamped joint rotations into the persisted scene.

## POSECRAFT VISUAL TRUTH LAW

An action is not certified because JSON, Euler values, or an API receipt are correct.

```text
COMMAND / USER ACTION → INTERNAL STATE CHANGES → VISIBLE GLB GEOMETRY CHANGES
→ SAVE → RELOAD → VISIBLE GEOMETRY RECONSTRUCTS THE SAME RESULT
```

Both structured PoseCraft state **and** rendered geometry must change (and reconstruct). Either alone is a fail.

## Binding law (this milestone)

- Clear `rotationQuaternion` on clones so Euler bind/pose writes are live.
- Compensate lost glTF `__root__` handedness with `backFaceCulling = false`.
- Keep Fable segment lengths; hang elbow/wrist along −Y.
- Apply `V4_REGION_BIND_ROTATION_Z` so T-pose arm geometry lies on the hanging skeleton.

## Interaction law

- CSS-space pick coordinates (no DPR² pre-scale).
- Pose Body is the default after add/select.
- All 17 joint markers visible on the selected READY figure in Pose Body; selected joint emphasized; `renderingGroupId = 1`.
- Pointer observer registered first (`insertFirst`); drag cleared on up / cancel / leave / mode / selection change.
- Camera mode never activates figure gizmos. Camera commits after inertia settles.

## Co-Director law

- `posecraft.apply_pose` resolves `posePresetId` from the canonical catalog mirror (or an explicit `joints` map / project custom pose) and persists the full 17-joint pose.
- Unknown figure or pose is a hard error — never a fake success.
- TypeScript `POSE_CATALOG` remains the source of truth; `studio-api/app/posecraft/pose_catalog.json` is the generated mirror, guarded by `poseCatalogExport.test.ts`.

## Certification project (Section 42)

Schnick Coffee, two figures, opposing martial-arts presets:

| Figure | Pose | Evidence |
|---|---|---|
| Adult Female 1 | Strike (`action-strike`) | rightElbow.x persisted; viewport geometry moved |
| Adult Male 1 | Block (`action-block`) | CD proposal + approve wrote joints; semantic summary Strike vs Block |

Manual left-elbow isolation, save/reload reconstruct, and CD apply_pose viewport change are gated by `tests/e2e/posecraft/posecraft-visual-truth-law.spec.ts`.
