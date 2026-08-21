# PoseCraft v4 Visual + Interaction — Completion Report

**SUPERSEDED.** Historical report. Current governing document: [PHASE-POSECRAFT-FULL-OVERHAUL.md](./PHASE-POSECRAFT-FULL-OVERHAUL.md). Current completion report: [POSECRAFT_FULL_OVERHAUL_COMPLETION_REPORT.md](./POSECRAFT_FULL_OVERHAUL_COMPLETION_REPORT.md).

Governing doc: [PHASE-POSECRAFT-V4-VISUAL-INTERACTION.md](./PHASE-POSECRAFT-V4-VISUAL-INTERACTION.md)

Asset-only history (not this verdict): [POSECRAFT_V4_LOWPOLY_HUMAN_GLB_ASSET_COMPLETION_REPORT.md](./POSECRAFT_V4_LOWPOLY_HUMAN_GLB_ASSET_COMPLETION_REPORT.md)

## Verdict

**NO-GO**

Local Beta full-stack interaction is implemented and Playwright-verified. Release / clean-clone / hosted remain blocked until the eight v4 runtime files under `studio-web/public/posecraft/figures/*-lowpoly-v4.{glb,json}` are committed to Git.

Do not deploy to Vercel from this tree. Do not mix into Phase 2 SHA `5cbbb41`.

## Branch

- Branch: `feat/posecraft-v4-human-replacement`
- Started from: `d340899` on `feat/codirector-temporal-continuity`
- Cert project: Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`

## What shipped

- Fable v4 GLBs promoted beside (not over) v3.
- Default archetypes load `/posecraft/figures/*-lowpoly-v4.glb` through `v4FigureLoader`.
- Rest joints corrected from Fable T-pose pivots (17×4 table in the governing doc). No `buildHumanBody` fallback.
- Lifecycle: `LOADING | READY | ERROR | DISPOSED`, per-`modelId` cache, stale loads discarded.
- Select events carry `joint` / `region`; `sync()` does not stomp selection or live rotations during drag.
- Camera is a real `GizmoMode` and does not call Move.
- Selected-joint handle only; gizmos scale from figure height.
- Child Boy / Child Girl JSON chunks repaired from NUL padding to `0x20` so Babylon can parse them.

## Tests

| Suite | Result |
|---|---|
| `v4RestJoints.test.ts`, `v4InteractionContracts.test.ts`, `v4GlbAssets.test.ts`, `humanMeshBuilder.test.ts` | 15 passed |
| `posecraft-v4-visual-interaction.spec.ts` (Beta, Schnick) | 3 passed |
| Final GO D1–D3 | Updated v3 → v4 and wait for `visualState === READY` (not re-run this session; that spec creates a disposable project) |

Playwright on live Beta (`http://127.0.0.1:8760/` + `http://127.0.0.1:8758/api/health`):

1. Adult Female `modelId` v4 + `READY` → Pose body → canvas pick selects a joint → Thinking pose `head.x = -10` → reload keeps the pose.
2. Adult Male / Child Boy / Child Girl reach v4 `READY`.
3. Camera mode is `"camera"`, not Move.

## Reviews

- [GLM 5.2](84fa1933-2ce3-400b-88bf-dc2af6a350f6): READY FOR PRIMARY REVIEW (source laws pass; live was pending at review time).
- [Kimi K3](b64afb4d-fd39-4160-a668-15cbccbdeda4): all 10 hunted defects absent; **INVALIDATED** on untracked v4 runtime assets (Clean-Clone Law). That blocker still holds until commit.

## Beta

- Web: http://127.0.0.1:8760/ (200)
- API: http://127.0.0.1:8758/api/health (200)
- GLB: http://127.0.0.1:8760/posecraft/figures/adult-female-lowpoly-v4.glb (200, 289548 bytes)

Left running for manual review.

## E2E TRACE

| Stage | Result |
|---|---|
| User action | PASS — Cast add, Pose body, canvas pick, pose card, Camera |
| Frontend | PASS — v4 loader, select/sync, Camera mode |
| API | PASS — Schnick scene GET after pose |
| Backend | N/A — static GLB + existing PoseCraft scene API |
| Persistence | PASS — reload kept `head.x = -10` |
| Runtime | PASS — Babylon loaded repaired v4 GLBs |
| Result | PASS — `visualState === READY`, `modelId` ends `-v4` |
| Reload | PASS |
| Downstream | N/A — JEPA / Spatial Map / Timeline not in scope |

## Limitations

- v4 GLB/JSON copies are on disk and served by local Beta; they are **not in Git**.
- Schnick already contains multiple figures; canvas pick can hit a neighboring silhouette.
- Custom import path is unchanged and still silent on load failure.
- Hosted deploy was not attempted.

## Clear the NO-GO

Commit, on this branch only, the v4 public runtime files (and the repaired quarantine copies if they should remain the source of truth). Then re-run `v4GlbAssets.test.ts` and the v4 Playwright spec on a clean checkout.
