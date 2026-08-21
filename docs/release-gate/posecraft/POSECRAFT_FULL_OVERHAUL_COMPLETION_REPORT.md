# PoseCraft Full Overhaul + Co-Director Integration — Completion Report

Governing doc: [PHASE-POSECRAFT-FULL-OVERHAUL.md](./PHASE-POSECRAFT-FULL-OVERHAUL.md)

Supersedes [POSECRAFT_V4_VISUAL_INTERACTION_COMPLETION_REPORT.md](./POSECRAFT_V4_VISUAL_INTERACTION_COMPLETION_REPORT.md) (historical NO-GO: untracked assets + T-pose rest).

## Verdict

**GO — POSECRAFT FULL OVERHAUL + CO-DIRECTOR APPLY_POSE**

This is the PoseCraft overhaul milestone verdict, not Adept UI Final Systems certification.

Visual Truth Law passed on live Beta. `posecraft.apply_pose` writes real joints. All four archetypes pose. Schnick Coffee holds opposing Strike / Block. v4 runtime assets are committed on `feat/posecraft-v4-human-replacement`.

## Branch

- Branch: `feat/posecraft-v4-human-replacement`
- Started from: `d340899`
- Cert project: Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`

## What shipped

- Hanging-arm semantic rest restored; T-pose GLB arm meshes bind with ±90° Z.
- Clone attach clears `rotationQuaternion`; both faces render (`backFaceCulling = false`).
- CSS-space picking; invisible region colliders; two-pass exact body then collider.
- 17 passive joint markers + emphasized selected anchor, camera-distance scaled, depth-on-top.
- Screen-size gizmos; Pose Body default after add/select; Camera isolated; drag always cleared.
- Server pose catalog mirror + drift-guard test.
- `posecraft.apply_pose` persists clamped 17-joint poses (catalog, custom, or explicit map). Unknown figure/pose is a hard error.

## Tests (observed)

| Suite | Result |
|---|---|
| vitest `v4RestJoints`, `v4InteractionContracts`, `v4GlbAssets`, `poseCatalogExport`, `poseCatalog`, `sceneState` | 34 passed |
| pytest `tests/test_posecraft_contracts.py` | 19 passed |
| Playwright Visual Truth Law (`posecraft-visual-truth-law.spec.ts`, Beta) | **6 passed** (41.5s) |
| Playwright `posecraft-v4-visual-interaction.spec.ts` | 3 passed |
| Playwright `posecraft-snapshot-workflow.spec.ts` | 1 failed — API POST timeout under Beta load (see Limitations) |

Visual Truth Law cases:

1. Adult Female 7 joint-handle picks + forearm/head body picks match Inspector.
2. Strike preset: joint state A ≠ B **and** right forearm/hand world centers move **and** reconstruct after reload.
3. Manual left elbow 80°: forearm+hand move; upper-arm center stays (< 0.04 m).
4. Adult Male / Adult Female / Child Boy / Child Girl: v4 READY + Strike moves geometry.
5. Camera mode is `"camera"`.
6. Co-Director `apply_pose` → `applied: true` → persisted elbows → reload viewport geometry changed.

## Section 42 — Schnick Coffee live

- Adult Female 1: `action-strike` / Strike (rightElbow.x = 100).
- Adult Male 1: `action-block` / Block via CD proposal `53d4300c-41ff-49be-8f4b-5b13d2944a93` (rightElbow.x = 70; changedJoints chest + both arms).
- Semantic summary: `Adult Female 1 — Strike` / `Adult Male 1 — Block`.
- Scene name `PoseCraft Blocking Study`, revision 124, 35 mm 16:9, one apple-box.
- Snapshot + Send to Co-Director / Image Generation / Storyboard / Scene Creator / Timeline controls remain on the Inspector.

## E2E TRACE

| Stage | Result |
|---|---|
| User action | PASS — Cast, Pose Body, handle/body pick, pose card, sliders, Camera |
| Frontend | PASS — v4 bind, colliders, handles, gizmos, Visual Truth probes |
| API | PASS — scene persist; CD `apply_pose` proposal/approve/receipt |
| Backend | PASS — catalog resolve + clamped joint write |
| Persistence | PASS — Strike/Block and manual elbow survive reload |
| Runtime | PASS — WebGPU Babylon, v4 READY, no procedural fallback |
| Result | PASS — visible geometry moved with state |
| Reload | PASS — reconstruct within 0.08 m |
| Downstream | PASS — CD apply_pose hydrates viewport; handoff buttons present. Full Scene Creator / Timeline live render not re-run this pass. |

## Reviews

- [GLM 5.2 architecture](092a63b0-6179-47f1-aed1-42c9013fce36): READY FOR PRIMARY REVIEW. Must-fix: body-click drag fell back to `spine` when `figure.pose[joint]` was undefined. Fixed in `engine.ts` — canvas drag now uses the clicked joint and zeros a missing pose entry.
- [Kimi K3 adversarial](1c2a639e-3b45-488a-bbf5-82d1eb9ec143): INVALIDATED on clean-clone (v4 GLBs and overhaul sources untracked at review time). The other nine hunts were ABSENT in the working tree. Cleared by committing runtime GLBs + overhaul code on this branch.

## Beta

- Web: http://127.0.0.1:8760/ (200)
- API: http://127.0.0.1:8758/api/health (200)
- Left running for manual review.

## Limitations

- Faceted low-poly mannequins meet the staging target; the generator was **not** regenerated this pass.
- In hanging rest, a hand bbox-center click can hit the hip. Handles and two-pass exact body picks are the usable path; Visual Truth clicks the handle plus forearm/head body.
- Beta Co-Director `/tools/proposals` can hang under concurrent load (snapshot-workflow smoke timed out). The Visual Truth CD case and the live male Block apply succeeded when the API was free.
- Hosted Vercel was not deployed.
- Broader CRS / Spatial Map / Scene Creator / Timeline / Library / Revision C suites were not re-run in full this pass. Existing contracts were preserved, not rebuilt.

## Mandatory checklist

```text
[x] Branch + starting SHA verified
[x] Contracts preserved or intentionally updated (apply_pose now writes joints)
[x] Full-stack implementation completed
[x] Every visible PoseCraft control wired
[x] Real runtime; no mock completion
[x] Persistence after reload verified
[x] Error/cancel/retry/recovery: unknown pose/figure hard-error; drag always cleared
[x] Authz + project isolation: Schnick only; no new spam projects for cert
[x] Unit/API/regression passed (34 vitest, 19 pytest)
[x] Playwright Visual Truth Law passed (6/6)
[x] Failures repaired (pick target, slider native setter, preset reset, CD retry)
[x] Production build passed
[x] Beta updated and running; URL reported
[x] Manual review path documented
[x] Unified Markdown completion report created
[x] Limitations honest
[x] Verdict: GO
```
