# Revision C Phase 2 — PoseCraft + JEPA Integration

**Status:** GOVERNING for Revision C Phase 2  
**Law 30:** This is the single governing document for PoseCraft + JEPA world-state integration. Phase 1 remains governed by [00-GOVERNING.md](./00-GOVERNING.md). Authoritative A+B+C naming is [REVISION-ABC-FINAL-CLOSURE.md](../REVISION-ABC-FINAL-CLOSURE.md).

```text
Revision A = Temporal Continuity (VideoChat3 / InternVideo3 / Timeline continuation)
Revision B = Creation Intelligence (Scene Review / SpatialDraft / CRS / Scene Creator)
Revision C = World Intelligence (V-JEPA / world-state-v1)
```

PoseCraft remains the pose engine. This phase adds kinematic pose intelligence and reuses the existing V-JEPA worker for visual comparison only.

## Environment

| Item | Value |
|---|---|
| Branch | `feat/codirector-temporal-continuity` |
| Starting / tracked HEAD | `9b8d5a9cdae8c88266e6fd253551450611c1e4d9` |
| Cert project | Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278` |
| Creator UI | http://127.0.0.1:8760/ |
| Studio API | http://127.0.0.1:8758/ |
| Live evidence | [evidence/phase2-live-gates.json](./evidence/phase2-live-gates.json) |

Phase 2 source is implemented on this working tree. It is **not yet in the tracked HEAD**. A clean clone of `9b8d5a9` will not include `pose_intelligence/` until this work is committed.

## Product law

```text
PoseCraft  →  where the body goes
JEPA / World Intelligence  →  visual world-state comparison
Kinematic pose analysis  →  balance, support, contact, stance
Co-Director  →  meaning, continuity, next-batch guidance
Adapters  →  provider-specific prompt/conditioning only
```

- Do not create a second JEPA system.
- Do not replace the 17-joint rig, gizmos, or snapshots.
- Analysis never overwrites a creator pose.
- Do not invent a successful packet when JEPA is down.
- JEPA embeddings never become “left foot planted.”

## Architecture

Kinematic / contact analysis is always available (no GPU). V-JEPA is called only when a snapshot/image exists and a visual compare is meaningful. `WorldStatePacket` (`world-state-v1`) is referenced, not forked.

Packets: `PoseWorldStatePacket`, `ContactGraph`, `PoseSequenceState`, `PoseMotionConditioningPacket`, `PoseContinuityReview`.

## Files

### Backend

- `studio-api/app/codirector/pose_intelligence/` — contracts, analyze, persist, compile, compare, service, router
- `studio-api/app/posecraft/router.py` — mounts intelligence routes
- `studio-api/app/codirector/tools/definitions.py` + `handlers/posecraft.py` + `registry.py` — read tools
- `studio-api/app/scene_creator/service.py` — `_attach_pose_intelligence`
- `studio-api/app/director_timeline_w46/generation/request_builder.py` — `poseMotionConditioning`
- `studio-api/app/codirector/video_intelligence/compare.py` + `service.py` — intended vs observed + observed world after JEPA augment
- `studio-api/tests/test_pose_intelligence.py`

### Frontend / figures

- `studio-web/src/components/GenerationTools/PoseCraftWorkspace.tsx`
- `studio-web/src/posecraft/posecraftApi.ts`
- `studio-web/src/posecraft/humanMeshBuilder.ts` — v3 faceted anatomical hulls, 17-joint parented rig
- `studio-web/public/posecraft/figures/*-lowpoly-v3.glb` + `.json` — 2528 tris each
- `scripts/generate_posecraft_figure_glbs.py`

### Tests / evidence

- `tests/e2e/posecraft/posecraft-pose-intelligence.spec.ts`
- `studio-web/src/posecraft/humanMeshBuilder.test.ts`
- `studio-web/src/posecraft/poseIntelligenceUi.test.ts`
- `docs/release-gate/codirector-world-intelligence/run_phase2_live_gates.py`

## Test counts (measured)

| Suite | Result |
|---|---|
| `tests/test_pose_intelligence.py` + world + temporal + creation perception | **101 passed** (closure rerun) |
| Frontend vitest (`humanMeshBuilder`, `poseIntelligenceUi`) | **3 passed** (2 files) |
| Playwright A + B + C1 + Pose Intelligence | **20 passed** (5 A + 9 B + 5 C1 + 1 Phase 2) |
| Playwright Revision B H isolated | **1 passed** |
| Live Schnick A–F + JEPA evaluate | **PASS** — [phase2-live-gates.json](./evidence/phase2-live-gates.json) |

## Live A–F (Schnick Coffee, one project)

| Gate | Result | Notes |
|---|---|---|
| A static pose | PASS | Korri standing, `availability=available`, support both, creator intent honored |
| B pose A→B | PASS | Structured changes (support, translation, foot release) |
| C contact | PASS | Hands → service counter; feet planted; pelvis is `contact` not false `seated` |
| D Scene Creator | PASS | `poseWorldStatePacketId` hydrates on workspace |
| E Timeline | PASS | `poseMotionConditioning.applied=true`, prompt prefix compiled |
| F intended vs observed | PASS | New LTX 2.5 draft clip `84bbbff3-0155-4968-914a-ae6f589ac549` (`scene_0_6686546d.mp4`). Generate saved `poseMotionConditioning.applied=true`, `sourcePosePacketId=pws_c2990d8e80ea`. VideoChat3 observed the new file. `extras.worldReview.availability=available`. `extras.poseContinuityReview` id `pcr_014112b150f1`. No silent generator fallback. |
| JEPA evaluate | PASS | Existing Schnick image → `world-intelligence/evaluate` `availability=available` |
| Pose snapshot image → JEPA | PASS (honest) | After cache fix, snapshot image reaches `evaluate_project_assets`. Result: `insufficient_reference` / “No approved world references available for comparison.” That is correct for a lone snapshot with no pose reference pair. Two-image `evaluate` on Schnick is `available`. |

World intelligence worker: `available=true`, `workerOk=true`. Pose packets with no snapshot image correctly report `world.availability=insufficient_reference`.

## E2E TRACE

| Stage | Result |
|---|---|
| User action | PASS — Analyze Pose / Check Motion Continuity / Send to Scene Creator / Send to Timeline |
| Frontend | PASS — accordion, no JEPA jargon, persist hydrate on reload |
| API | PASS — `/api/posecraft/projects/{id}/intelligence/*` |
| Backend | PASS — kinematic analyzer + optional V-JEPA reuse |
| Persistence | PASS — `ProjectTraitRow` category `pose_intelligence`; reload returns same packet |
| Runtime | PASS — V-JEPA worker reused; evaluate available on Schnick images |
| Result | PASS — creator-facing summary + contacts + conditioning prefix |
| Reload | PASS — Playwright reload keeps workspace + analyze control; API GET latest |
| Downstream | PASS — Scene Creator production_context; Timeline `providerOptions.poseMotionConditioning` |

## Peer review

| Reviewer | Verdict | Action taken |
|---|---|---|
| GLM 5.2 (`glm-5.2-max`) [Review](61558c0f-f2b7-42b5-a6b5-73db14ef4e8c) | READY FOR PRIMARY REVIEW | Cache tautology, snapshot mislabel, Playwright reload, degraded UI |
| Kimi K3 (`kimi-k3-max`) [Review](011c62f1-93f1-4587-bb46-588afad418ab) | GAPS FOUND | Persist key collision fixed; seated false-positive fixed; `observedWorld` attached after JEPA augment; JEPA evaluate proven; snapshot-cache fallback fixed |

## Closure diagnosis (Playwright H)

H was not Accept deleting cameras. Serial Playwright (`workers=1`) plus a 30–180s `/auto-mask` GPU/Comfy `/free` hang in test E restarted the worker. `beforeAll` then created a new empty map and H read `cameras.length === 0`. Repair: auto-mask is cache-or-honest-paint (no GPU spawn on that request). H now proves existing camera → Review → Accept → persist → reload → same camera id from `:8758` and keeps `cameras.length > 0` plus `camera-slot-0`. Isolated H and the full Revision B file both passed.

## Limitations

- Hosted Vercel frontend cannot invent a local JEPA pass.
- Sequence intelligence uses existing snapshots/revisions. No new pose-timeline editor.
- Auto-mask no longer starts the SAM worker on the request thread. Scene Creator Smart Select stays honest (`Paint the region` / Essentials Pack) unless a cached mask exists.
- Timeline generate prompt also includes movement UNCHANGED FACTS before the pose-continuity prefix. Conditioning `applied=true` and the prefix are present in the saved generate response.

## Binary matrix

| Gate | Verdict |
|---|---|
| Revision A Temporal Continuity regression | **GO** — Playwright **5 passed** |
| Revision B Creation Intelligence regression | **GO** — full file **9 passed**; isolated H **1 passed** |
| Revision C Phase 1 World Intelligence regression | **GO** — Playwright **5 passed** |
| Revision C Phase 2 PoseCraft + JEPA | **GO** — units, Playwright, live A–F with a new posed LTX clip |

```text
GO — REVISION A TEMPORAL CONTINUITY REGRESSION PASS
GO — REVISION B CREATION INTELLIGENCE REGRESSION PASS
GO — REVISION C PHASE 1 WORLD INTELLIGENCE REGRESSION PASS
GO — REVISION C PHASE 2 POSECRAFT + JEPA
```

Deploy frontend only from the committed Phase 2 SHA after clean-clone and peer review. Hosted frontend must not be used as JEPA proof.
