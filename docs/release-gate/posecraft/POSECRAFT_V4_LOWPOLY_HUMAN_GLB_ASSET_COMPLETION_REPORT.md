# PoseCraft v4 Low-Poly Human GLB Assets — Completion Report

**Date:** 2026-08-20  
**Authority:** Fable 5 plan `fable_v4_glb_humans_75ea8703.plan.md`  
**Branch:** `feat/codirector-temporal-continuity`  
**HEAD SHA:** `d340899`  
**Scope of this report:** 3D asset creation only. This document does **not** certify PoseCraft product GO and does **not** supersede PoseCraft master / mandatory-GO reports.

## Verdict

```text
GO — FABLE V4 HUMAN GLB ASSET PASS COMPLETE (QUARANTINE / STOP)
```

```text
NOT STARTED — POSECRAFT INTEGRATION (GROK LATER)
```

This pass **STOPS** at `assets/posecraft/v4/`. No PoseCraft, Adept UI, Spatial Map, JEPA, Co-Director, Scene Creator, or Timeline source was modified. Existing v3 figure files were not overwritten.

## What was delivered

Four self-contained T-pose low-poly human GLBs plus companion JSON, written to the quarantine folder:

```text
assets/posecraft/v4/
  adult-male-lowpoly-v4.glb
  adult-female-lowpoly-v4.glb
  child-boy-lowpoly-v4.glb
  child-girl-lowpoly-v4.glb
  adult-male-lowpoly-v4.json
  adult-female-lowpoly-v4.json
  child-boy-lowpoly-v4.json
  child-girl-lowpoly-v4.json
  build/generate_v4_figures.py
  previews/*-preview.png
```

Rebuild aid only: `assets/posecraft/v4/build/generate_v4_figures.py`. It is not product code.

## Measured results

| Model | Target height | Measured Y max | Y min | Tris | GLB bytes |
|---|---:|---:|---:|---:|---:|
| Adult Male | 1.84 m | 1.8449 m | 0.000 | 3546 | 289,384 |
| Adult Female | 1.70 m | 1.7044 m | 0.000 | 3546 | 289,548 |
| Child Boy | 1.32 m | 1.3254 m | 0.000 | 3546 | 289,516 |
| Child Girl | 1.28 m | 1.2854 m | 0.000 | 3546 | 289,524 |

All four are within ~5–6 mm of target height (well inside the ~3 cm gate). Feet sit on Y = 0. Triangle counts are inside 2,000–5,000.

Triangle counts match because the four figures share topology and differ by authored proportion curves, not by uniform scale of one mesh.

## Scene convention (all four)

| Rule | Value |
|---|---|
| Units | meters |
| Up | +Y |
| Forward (face + toes) | +Z |
| Character left | −X |
| Floor | Y = 0 |
| Center | X = 0, Z = 0 |
| Pose | Neutral T-pose |
| Material | Matte gray PBR, baseColor ≈ `0.55, 0.55, 0.58`, roughness 0.92, metallic 0 |
| Textures | None |
| Skins / bones / animation | None |

## TRANSFORM LAW — verified

Each of the 17 body-region meshes is authored in local space with its origin at the intended PoseCraft pivot.

- Allowed and used: node translation to assemble the T-pose
- Rotation: 0 (no node `rotation` extras)
- Scale: identity (no node `scale`, therefore `1,1,1`)
- Forbidden items not present: negative scale, baked node rotations, skins, inverse bind matrices

A non-geometry identity root named `Figure` parents the 17 region nodes. That is permitted glTF scene structure.

## 17 geometry-bearing region nodes (exact names)

Each GLB contains exactly these geometry-bearing nodes and no additional body meshes:

```text
head
neck
chest
spine
pelvis
leftUpperArm
leftLowerArm
leftHand
rightUpperArm
rightLowerArm
rightHand
leftUpperLeg
leftLowerLeg
leftFoot
rightUpperLeg
rightLowerLeg
rightFoot
```

Grok 1:1 map for the later integration pass:

```text
head→head  neck→neck  chest→chest  spine→spine  pelvis→pelvis
leftUpperArm→leftShoulder  leftLowerArm→leftElbow  leftHand→leftWrist
rightUpperArm→rightShoulder  rightLowerArm→rightElbow  rightHand→rightWrist
leftUpperLeg→leftHip  leftLowerLeg→leftKnee  leftFoot→leftAnkle
rightUpperLeg→rightHip  rightLowerLeg→rightKnee  rightFoot→rightAnkle
```

## Differentiation

The four figures are not one mesh scaled four ways.

- **Adult Male** — broader shoulders, narrower hips, stronger chest plane
- **Adult Female** — narrower shoulders, defined waist, wider pelvis; modest anatomical shelf, not sexualized
- **Child Boy** — larger head relative to torso, shorter limbs, slightly broader/squarer than the girl
- **Child Girl** — child proportions, slightly narrower shoulders than the boy

World AABB checks: child heads are wider than their chests; adult male chest span is wider than adult female; adult female pelvis is wider than adult male.

## Quality gate

| Check | Result |
|---|---|
| GLB magic `glTF` / self-contained | PASS |
| 17 exact geometry-bearing names | PASS |
| No skins / animation | PASS |
| TRANSFORM LAW | PASS |
| Height within ~3 cm | PASS |
| Feet on Y = 0 | PASS |
| Tris 2k–5k | PASS (3546) |
| No PoseCraft source edits | PASS |
| v3 files not overwritten | PASS |
| Visual: generic viewer reads male / female / boy / girl | PASS with limitations (see below) |

Front/side orthographic previews: `assets/posecraft/v4/previews/`.

## Limitations (honest)

- Geometry is **programmatically authored** (faceted anatomical lofts + skull/hand/foot features), not DCC-sculpted. Visible facets are intended.
- Preview images draw triangle edges, which exaggerates segmentation compared with a standard GLB viewer using only flat-shaded materials.
- Hands are simplified palm + finger silhouettes (no articulated fingers), as specified.
- Adjacent regions overlap slightly at joints so the assembled T-pose does not show large gaps. Grok should keep that overlap when parenting to the 17-joint rig.
- These files are **not** a runtime PoseCraft dependency. `HUMAN_MODEL_IDS` still points at v3. Live viewport figures remain the TypeScript builder until Grok wires v4.

## Out of scope (not done)

- PoseCraft engine / UI / picking / handles / highlighting
- Copy into `studio-web/public/posecraft/figures/`
- Overwrite of v3 assets
- Bones, skins, animation, anchors, gizmos
- Save/reload certification
- Playwright / Beta / hosted E2E

## Handoff to Grok

```text
FABLE
  → 4 v4 GLBs in assets/posecraft/v4/
  → STOP

GROK (next)
  → validate GLB structure in a standard viewer
  → map 17 regions → existing 17 joints
  → repair selectedJoint state
  → restore body clicking
  → restore/position joint handles
  → add limb highlighting
  → certify save/reload
  → PoseCraft GO
```

Do not promote a v4 GLB into `studio-web/public` until that validation pass has inspected each figure visually.

## Files touched

**New (quarantine assets):**

- `assets/posecraft/v4/adult-male-lowpoly-v4.glb` + `.json`
- `assets/posecraft/v4/adult-female-lowpoly-v4.glb` + `.json`
- `assets/posecraft/v4/child-boy-lowpoly-v4.glb` + `.json`
- `assets/posecraft/v4/child-girl-lowpoly-v4.glb` + `.json`
- `assets/posecraft/v4/build/generate_v4_figures.py`
- `assets/posecraft/v4/previews/*.png`

**Application source:** none.

## Rebuild

From repo root, with Python 3.11 + numpy + Pillow:

```text
python assets/posecraft/v4/build/generate_v4_figures.py
```
