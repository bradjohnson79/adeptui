# PHASE — PoseCraft v4 Visual + Interaction

**SUPERSEDED.** Historical Law 30 document for the first v4 attach pass. Current governing document: [PHASE-POSECRAFT-FULL-OVERHAUL.md](./PHASE-POSECRAFT-FULL-OVERHAUL.md).

**Law 30 governing document** for replacing the default PoseCraft procedural humans with the approved Fable v4 GLBs and closing body-click / handle / mode-sync.

Asset-only history (not product GO): [POSECRAFT_V4_LOWPOLY_HUMAN_GLB_ASSET_COMPLETION_REPORT.md](./POSECRAFT_V4_LOWPOLY_HUMAN_GLB_ASSET_COMPLETION_REPORT.md)

## Status

Implementation and local Beta Playwright are done on `feat/posecraft-v4-human-replacement`.

Governing verdict: **NO-GO** until the eight v4 runtime files are committed. See [POSECRAFT_V4_VISUAL_INTERACTION_COMPLETION_REPORT.md](./POSECRAFT_V4_VISUAL_INTERACTION_COMPLETION_REPORT.md).

Cert project: Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`.

Hosted deploy is **out of scope** until binary GO. Do not mix this into Phase 2 SHA `5cbbb41`.

## Asset promotion

Quarantine copies were validated (`glTF` magic) and promoted **without overwriting v3**.

| modelId | Source | Runtime | SHA-256 |
|---|---|---|---|
| adult-male-lowpoly-v4 | `assets/posecraft/v4/adult-male-lowpoly-v4.glb` | `studio-web/public/posecraft/figures/adult-male-lowpoly-v4.glb` | `88333899BE91ED659632C8A8914E336EFDCB77458C60FFBC5EDE6A03ED27F01C` |
| adult-female-lowpoly-v4 | `assets/posecraft/v4/adult-female-lowpoly-v4.glb` | `studio-web/public/posecraft/figures/adult-female-lowpoly-v4.glb` | `54F600160166790E9F23691A6021F33C7A927D71B69A3F6036B1F9A99C8427D1` |
| child-boy-lowpoly-v4 | `assets/posecraft/v4/child-boy-lowpoly-v4.glb` | `studio-web/public/posecraft/figures/child-boy-lowpoly-v4.glb` | `761D0524F30F3D41A35A4DA66EED43416934C5847609C542496BB52532747204` |
| child-girl-lowpoly-v4 | `assets/posecraft/v4/child-girl-lowpoly-v4.glb` | `studio-web/public/posecraft/figures/child-girl-lowpoly-v4.glb` | `F84E181FD4EC2D9966F67E0C9F5DAC2A207D4BFA24EB4CC59A9CA27AA506D848` |

Source and runtime hashes match. Companion JSON files were copied beside the GLBs.

Child Boy / Child Girl binaries were repaired in place: the glTF JSON chunk was padded with `0x00`, which Babylon `JSON.parse` rejects. Padding was replaced with `0x20` (spec). Mesh/bin payloads were not regenerated. The generator now uses space padding for JSON chunks.

## V4 PIVOT BINDING LAW

Tolerance: **≤ 1 cm (0.01 m)** in figure-root space.

The previous ArchetypeSpec rest pose hangs the arms along −Y. Fable v4 is a true T-pose (arms along ±X). Measured hand deltas reach **0.80 m**. Those pivots do **not** coincide.

Action taken: correct each v4 archetype's **REST JOINT POSITIONS** from the Fable authored Figure-root translations. After correction, region meshes parent to the matching joint with local position 0 / rotation 0 / scale 1. Pose Euler math is unchanged.

Measured 17 × 4 deltas versus the old hanging-arm spec rest (all `correct-rest`):

| Archetype | Region | Fable root (m) | Spec rest delta (m) | Bind |
|---|---|---|---|---|
| adult-male | head | (0.000,1.621,0.000) | 0.0878 | correct-rest |
| adult-male | neck | (0.000,1.546,0.000) | 0.0405 | correct-rest |
| adult-male | chest | (0.000,1.359,0.000) | 0.1267 | correct-rest |
| adult-male | spine | (0.000,1.161,0.000) | 0.0517 | correct-rest |
| adult-male | pelvis | (0.000,0.962,0.000) | 0.0520 | correct-rest |
| adult-male | leftUpperArm | (-0.240,1.475,0.000) | 0.0683 | correct-rest |
| adult-male | leftLowerArm | (-0.550,1.475,0.000) | 0.3931 | correct-rest |
| adult-male | leftHand | (-0.840,1.475,0.000) | 0.8017 | correct-rest |
| adult-male | rightUpperArm | (0.240,1.475,0.000) | 0.0683 | correct-rest |
| adult-male | rightLowerArm | (0.550,1.475,0.000) | 0.3931 | correct-rest |
| adult-male | rightHand | (0.840,1.475,0.000) | 0.8017 | correct-rest |
| adult-male | leftUpperLeg | (-0.130,0.962,0.000) | 0.0520 | correct-rest |
| adult-male | leftLowerLeg | (-0.130,0.502,0.000) | 0.0520 | correct-rest |
| adult-male | leftFoot | (-0.130,0.052,0.000) | 0.0520 | correct-rest |
| adult-male | rightUpperLeg | (0.130,0.962,0.000) | 0.0520 | correct-rest |
| adult-male | rightLowerLeg | (0.130,0.502,0.000) | 0.0520 | correct-rest |
| adult-male | rightFoot | (0.130,0.052,0.000) | 0.0520 | correct-rest |
| adult-female | head | (0.000,1.504,0.000) | 0.0793 | correct-rest |
| adult-female | neck | (0.000,1.438,0.000) | 0.0327 | correct-rest |
| adult-female | chest | (0.000,1.265,0.000) | 0.1130 | correct-rest |
| adult-female | spine | (0.000,1.082,0.000) | 0.0457 | correct-rest |
| adult-female | pelvis | (0.000,0.898,0.000) | 0.0480 | correct-rest |
| adult-female | leftUpperArm | (-0.170,1.372,0.000) | 0.0587 | correct-rest |
| adult-female | leftLowerArm | (-0.440,1.372,0.000) | 0.3428 | correct-rest |
| adult-female | leftHand | (-0.690,1.372,0.000) | 0.6951 | correct-rest |
| adult-female | rightUpperArm | (0.170,1.372,0.000) | 0.0587 | correct-rest |
| adult-female | rightLowerArm | (0.440,1.372,0.000) | 0.3428 | correct-rest |
| adult-female | rightHand | (0.690,1.372,0.000) | 0.6951 | correct-rest |
| adult-female | leftUpperLeg | (-0.160,0.898,0.000) | 0.0480 | correct-rest |
| adult-female | leftLowerLeg | (-0.160,0.468,0.000) | 0.0480 | correct-rest |
| adult-female | leftFoot | (-0.160,0.048,0.000) | 0.0480 | correct-rest |
| adult-female | rightUpperLeg | (0.160,0.898,0.000) | 0.0480 | correct-rest |
| adult-female | rightLowerLeg | (0.160,0.468,0.000) | 0.0480 | correct-rest |
| adult-female | rightFoot | (0.160,0.048,0.000) | 0.0480 | correct-rest |
| child-boy | head | (0.000,1.076,0.000) | 0.0525 | correct-rest |
| child-boy | neck | (0.000,1.018,0.000) | 0.0231 | correct-rest |
| child-boy | chest | (0.000,0.894,0.000) | 0.0799 | correct-rest |
| child-boy | spine | (0.000,0.762,0.000) | 0.0292 | correct-rest |
| child-boy | pelvis | (0.000,0.631,0.000) | 0.0406 | correct-rest |
| child-boy | leftUpperArm | (-0.145,0.971,0.000) | 0.0414 | correct-rest |
| child-boy | leftLowerArm | (-0.355,0.971,0.000) | 0.2693 | correct-rest |
| child-boy | leftHand | (-0.555,0.971,0.000) | 0.5513 | correct-rest |
| child-boy | rightUpperArm | (0.145,0.971,0.000) | 0.0414 | correct-rest |
| child-boy | rightLowerArm | (0.355,0.971,0.000) | 0.2693 | correct-rest |
| child-boy | rightHand | (0.555,0.971,0.000) | 0.5513 | correct-rest |
| child-boy | leftUpperLeg | (-0.100,0.631,0.000) | 0.0406 | correct-rest |
| child-boy | leftLowerLeg | (-0.100,0.331,0.000) | 0.0406 | correct-rest |
| child-boy | leftFoot | (-0.100,0.041,0.000) | 0.0406 | correct-rest |
| child-boy | rightUpperLeg | (0.100,0.631,0.000) | 0.0406 | correct-rest |
| child-boy | rightLowerLeg | (0.100,0.331,0.000) | 0.0406 | correct-rest |
| child-boy | rightFoot | (0.100,0.041,0.000) | 0.0406 | correct-rest |
| child-girl | head | (0.000,1.038,0.000) | 0.0588 | correct-rest |
| child-girl | neck | (0.000,0.984,0.000) | 0.0281 | correct-rest |
| child-girl | chest | (0.000,0.864,0.000) | 0.0821 | correct-rest |
| child-girl | spine | (0.000,0.737,0.000) | 0.0308 | correct-rest |
| child-girl | pelvis | (0.000,0.609,0.000) | 0.0394 | correct-rest |
| child-girl | leftUpperArm | (-0.135,0.938,0.000) | 0.0454 | correct-rest |
| child-girl | leftLowerArm | (-0.335,0.938,0.000) | 0.2528 | correct-rest |
| child-girl | leftHand | (-0.525,0.938,0.000) | 0.5204 | correct-rest |
| child-girl | rightUpperArm | (0.135,0.938,0.000) | 0.0454 | correct-rest |
| child-girl | rightLowerArm | (0.335,0.938,0.000) | 0.2528 | correct-rest |
| child-girl | rightHand | (0.525,0.938,0.000) | 0.5204 | correct-rest |
| child-girl | leftUpperLeg | (-0.100,0.609,0.000) | 0.0394 | correct-rest |
| child-girl | leftLowerLeg | (-0.100,0.319,0.000) | 0.0394 | correct-rest |
| child-girl | leftFoot | (-0.100,0.039,0.000) | 0.0394 | correct-rest |
| child-girl | rightUpperLeg | (0.100,0.609,0.000) | 0.0394 | correct-rest |
| child-girl | rightLowerLeg | (0.100,0.319,0.000) | 0.0394 | correct-rest |
| child-girl | rightFoot | (0.100,0.039,0.000) | 0.0394 | correct-rest |

Unit fixture: `studio-web/src/posecraft/v4RestJoints.test.ts`.

## V4 ASSET LIFECYCLE LAW

States: `LOADING | READY | ERROR | DISPOSED`.

- 17-joint rig is created immediately with Fable rest locals.
- GLB attaches only when the load token still matches the same figure instance.
- Delete before complete increments the token and sets `DISPOSED`; completed loads do not attach.
- Validated `AssetContainer` is cached per `modelId`. React `sync()` does not re-download.
- Manipulation (body pick, handles, pose ring, highlight) is gated until `READY`.
- Asset error is honest. There is **no** `buildHumanBody` fallback.
- Custom import remains a separate path.

## Interaction

- Select events carry `joint` and `region`. React persists `selectedJoint`.
- `sync()` does not overwrite `selectedJoint` or live rotations during an active drag.
- Highlight is an emissive overlay on the selected region only.
- Only the selected joint handle is visible, offset slightly from the coincident pivot.
- Move/rotate gizmo scale is derived from figure height.
- Camera mode is a real `GizmoMode` (`"camera"`). It does not call Move.

## Tests

- Unit: `v4RestJoints.test.ts`, `v4InteractionContracts.test.ts`, `humanMeshBuilder.test.ts`
- Playwright: `tests/e2e/posecraft/posecraft-v4-visual-interaction.spec.ts` (Schnick)
- Final GO D1–D3 updated from v3 → v4 and wait for `visualState === READY`
