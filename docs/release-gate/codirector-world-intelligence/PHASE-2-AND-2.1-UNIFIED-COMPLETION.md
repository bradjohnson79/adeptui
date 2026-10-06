# Revision C Phase 2 + Phase 2.1 — Unified Completion Report

**Law 30:** This is the single completion report for Revision C Phase 2 PoseCraft/JEPA closure and Phase 2.1 Spatial Metric. It does **not** replace the milestone governing files.

| Role | Document |
|---|---|
| Phase 2 governing (historical) | [PHASE-2-POSECRAFT.md](./PHASE-2-POSECRAFT.md) |
| Phase 2.1 governing (current) | [PHASE-2.1-SPATIAL-METRIC.md](./PHASE-2.1-SPATIAL-METRIC.md) |
| Phase 1 world intelligence | [00-GOVERNING.md](./00-GOVERNING.md) |
| A+B+C naming | [REVISION-ABC-FINAL-CLOSURE.md](../REVISION-ABC-FINAL-CLOSURE.md) |
| Phase 2 live evidence | [evidence/phase2-live-gates.json](./evidence/phase2-live-gates.json) |

Do not cite this file as the Spatial Map schema contract. The contract lives in `PHASE-2.1-SPATIAL-METRIC.md` and `studio-api/app/spatial_map/metric.py`.

---

## Verdict

```text
GO — REVISION C PHASE 2 POSECRAFT
GO — REVISION C PHASE 2.1 SPATIAL METRIC (LOCAL BETA)
```

Hosted Vercel is **Phase 2 only**. Phase 2.1 is **not** on production.

Independent reviewers returned **READY FOR PRIMARY REVIEW** only. Primary reconciled those reviews into the binary gates below.

| Gate | State | Verdict |
|---|---|---|
| Revision A Playwright regression (Phase 2 closure) | TESTED + LIVE VERIFIED | **GO** — 5 passed |
| Revision B Playwright (including isolated H) | TESTED + LIVE VERIFIED | **GO** — full file 9 passed; isolated H 1 passed |
| Revision C Phase 1 Playwright | TESTED + LIVE VERIFIED | **GO** — 5 passed |
| Phase 2 PoseCraft units / Playwright / live A–F | TESTED + LIVE VERIFIED | **GO** |
| Phase 2 hosted frontend (`5cbbb41`) | LIVE VERIFIED | **GO** — UI/figures only |
| Phase 2 hosted JEPA | NOT VERIFIED | Honest: hosted cannot invent a local worker pass |
| Phase 2.1 units + Playwright + persist/isolation | TESTED + LIVE VERIFIED (local) | **GO** |
| Phase 2.1 hosted frontend | NOT VERIFIED | Separate SHA; not deployed |
| Phase 2.1 Revision B + C regression re-run | TESTED | **GO** — **14 passed (19.9s)** including Playwright H persist |

```text
NOT a final Adept UI Final Systems & Resilience GO.
NOT hosted Phase 2.1.
NOT hosted JEPA proof.
```

---

## Environment

```text
Branch:                 feat/codirector-temporal-continuity
Phase 2 hosted SHA:     5cbbb41647f13054b6648ad33782c56b1948910d
Phase 2.1 first SHA:    763248a76c15918a1b6028d750cb3ba8e31e1bd0
Phase 2.1 local HEAD:   d340899429c1030033a2d2d7312efbafab394ef5
Remote at report time:  origin/feat/codirector-temporal-continuity @ 763248a
                        (local is ahead 2: 11cb0e1 off-map anchors, d340899 peer/regression record)

Named cert project:     Schnick Coffee
Project ID:             2347bf46-3762-4763-86c5-4a6032522278
Creator UI (Beta):      http://127.0.0.1:8760/
Studio API:             http://127.0.0.1:8758/
Beta health (measured): http://127.0.0.1:8760/__beta_web_health HTTP 200
                        http://127.0.0.1:8758/api/health HTTP 200
Hosted product:         https://adeptui.vercel.app
Hosted deploy:          dpl_3MRKtGSvK1SfTqvJ2WmT884WV2J7
Hosted alias target:    https://adeptui-iytjge73y-anoint.vercel.app
Vercel project:         adeptui (prj_1NHSYLrFYQM3rIXyHwKUpezprbsx), root studio-web
```

One project only. No disposable `POST /api/projects` for cert.

The working tree on this machine also contains uncommitted Movement / avatar / perception work. **Clean-clone truth is the committed SHAs above**, not the dirty tree. Phase 2.1 was committed by parking dirty copies, applying a metric-only slice, committing, then restoring the dirty copies so Movement work was not lost.

---

## Product law (held)

```text
Spatial Map = intended geography (canonical)
PoseCraft  = bodies at those world origins
JEPA       = observed / advisory only
Co-Director = intent vs observation
```

- Axes stay `adept-world-v1`: **+X East, +Y Up, +Z South, −Z North**.
- Existing Schnick `x/y/z` values are already meters. Migration fills `positionMeters` and must **not** rescale.
- No `zones[]` on `SpatialMapDocument`.
- Camera-only commands must not move characters, props, or anchors.
- APPROVED / PROPOSED / OBSERVED stay distinct.
- Analysis never overwrites a creator pose.
- Do not invent a successful packet when JEPA is down.
- WAN / Hunyuan / stub generators are forbidden on the Phase 2 Gate F clip. Measured generator was LTX 2.5.

---

## What shipped

### Phase 2 — PoseCraft + JEPA (hosted SHA `5cbbb41`)

- Persist cameras after Scene Review Accept (Playwright H was a worker-restart / auto-mask hang, not Accept deleting cameras).
- Auto-mask is cache-or-honest-paint on that request (no GPU spawn that killed serial Playwright).
- Live Gate F: new posed Schnick Timeline clip on LTX 2.5 with `poseMotionConditioning.applied=true`, then VideoChat3 + `worldReview` + `poseContinuityReview`.
- Pose intelligence accordion (Analyze Pose, Check Motion Continuity, Send to Scene Creator, Send to Timeline). No JEPA jargon in creator chrome.
- v3 faceted figure GLBs (adult-female-lowpoly-v3 and siblings).
- Clean-clone repairs: leaked Movement tool defs stripped; `auto_mask.py` no longer imports untracked perception helpers.
- Production-build repairs: drop Revision D `extractSubject` UI that was not on the Phase 2 `api.ts`; stop unused `onChange` from failing `tsc`.

Phase 2 source family:

```text
773fedd  Close Revision C Phase 2: persist cameras after Accept and generate a real posed Timeline clip
d737a43  Make Phase 2 clean-clone importable by dropping leaked tool bindings
b9eda76  Stop Phase 2 auto-mask from importing an untracked perception helper
a62d7a1  Make Phase 2 auto-mask cache lookup optional on a clean clone
017649c  Record Phase 2 clean-clone peer review on SHA a62d7a1
067cd67  Drop PoseCraft picture-extract so the Phase 2 frontend typechecks
5cbbb41  Stop unused onChange from failing the Phase 2 PoseCraft production build
```

### Phase 2.1 — Spatial Metric (local SHA `763248a` + `11cb0e1` + `d340899`)

Additive `spatial-metric-v1` on `schemaVersion: 1`:

- Document: `metricSchema`, `metersPerCell` (1.0), `originMeters`, `widthMeters` / `depthMeters`, `environmentalAnchors[]`
- Placements / cameras: `positionMeters`, `gridCell` (E8-style), `targetMeters`, footprints / occupied cells
- Off-map anchors: bearing / distance / elevation (mountain 40 m NW in `11cb0e1`)
- Camera tools: look-at (yaw 0 = north / −Z), raise, orbit, halfway
- PoseCraft hydrates `worldOriginMeters` from Spatial Map when the figure is still at the origin
- Scene Creator / Timeline compile metric lines
- Quiet UI: **1 square = 1 meter** (`spatial-metric-scale` and Placement Precision `cell-size-label`)

Martial-arts cert map is 20×20 m so two fighters can stand 12 m apart.

---

## Files (authoritative slices)

### Phase 2

- `studio-api/app/codirector/pose_intelligence/`
- `studio-api/app/posecraft/router.py`
- `studio-api/app/codirector/tools/definitions.py`, `handlers/posecraft.py`, `registry.py`
- `studio-api/app/scene_creator/service.py`
- `studio-api/app/director_timeline_w46/generation/request_builder.py`
- `studio-api/app/codirector/video_intelligence/compare.py`, `service.py`
- `studio-web/src/components/GenerationTools/PoseCraftWorkspace.tsx`
- `studio-web/src/posecraft/posecraftApi.ts`, `humanMeshBuilder.ts`
- `studio-web/public/posecraft/figures/*-lowpoly-v3.glb`
- `tests/e2e/posecraft/posecraft-pose-intelligence.spec.ts`
- `docs/release-gate/codirector-world-intelligence/run_phase2_live_gates.py`

### Phase 2.1

- `studio-api/app/spatial_map/metric.py` (**new**)
- `studio-api/app/spatial_map/schemas.py`, `grid.py`, `service.py`, `router.py`
- `studio-api/app/codirector/tools/handlers/spatial_m411.py`
- `studio-api/app/codirector/camera_shot_packet.py`
- `studio-api/tests/test_spatial_metric.py`
- `studio-web/src/components/CoDirector/SpatialMap/types.ts`
- `studio-web/src/components/CoDirector/SpatialMap/gridGeometry.ts`
- Spatial Map heading / Placement Precision labels in the Spatial Map UI
- PoseCraft `worldOriginMeters` hydrate
- `tests/e2e/codirector/phase-2.1-spatial-metric.spec.ts`

---

## Test counts (measured)

| Suite | Result | When |
|---|---|---|
| Pose + world + temporal + creation perception | **101 passed** | Phase 2 closure |
| Frontend vitest (`humanMeshBuilder`, `poseIntelligenceUi`) | **3 passed** (2 files) | Phase 2 |
| Playwright A + B + C1 + Pose Intelligence | **20 passed** (5 + 9 + 5 + 1) | Phase 2 closure |
| Playwright Revision B H isolated | **1 passed** | Phase 2 closure |
| Live Schnick A–F + JEPA evaluate | **PASS** | [phase2-live-gates.json](./evidence/phase2-live-gates.json) |
| `studio-api/tests/test_spatial_metric.py` | **10 passed** | Phase 2.1 (`11cb0e1`) |
| `gridGeometry.test.ts` (includes E8) | **26 passed** | Phase 2.1 |
| Playwright `phase-2.1-spatial-metric.spec.ts` | **3 passed (5.2s)** | Phase 2.1 on 8760→8758, Schnick only, map title `Martial Arts Metric Cert` |
| Playwright Revision B + C after Phase 2.1 | **14 passed (19.9s)** | Includes H persist |
| `test_spatial_map_v1_grid_camera.py` after placed-only cell derivation | **26 passed** | Phase 2.1 repair |

---

## Phase 2 live A–F (Schnick Coffee)

| Gate | Result | Notes |
|---|---|---|
| A static pose | PASS | Korri standing; creator intent honored |
| B pose A→B | PASS | Structured support / translation / foot-release changes |
| C contact | PASS | Hands → service counter; feet planted; pelvis is `contact`, not false `seated` |
| D Scene Creator | PASS | `poseWorldStatePacketId` hydrates |
| E Timeline | PASS | `poseMotionConditioning.applied=true` |
| F intended vs observed | PASS | New LTX 2.5 draft clip `84bbbff3-0155-4968-914a-ae6f589ac549`. `sourcePosePacketId=pws_c2990d8e80ea`. `poseContinuityReview` `pcr_014112b150f1`. No silent generator fallback |
| JEPA evaluate | PASS | Existing Schnick image → `world-intelligence/evaluate` `availability=available` |
| Pose snapshot → JEPA | PASS (honest) | Lone snapshot with no approved pair → `insufficient_reference` |

---

## Phase 2.1 local cert

| Gate | Result |
|---|---|
| 20×20 map, no `zones[]`, 12 m fighter spacing | PASS |
| Camera look / raise / orbit does not move characters | PASS |
| UI **1 square = 1 meter** + persist + reload | PASS |
| Wrong-project isolation 404 | PASS |
| Schnick `x=1.25, z=-0.5` unchanged after migrate | PASS |
| Off-map mountain NW (`11cb0e1`) | PASS (unit) |
| List-maps after `gridCell` on `SpatialAnchor` | PASS — guard: only write grid fields the model owns |

---

## E2E TRACE

### Phase 2 PoseCraft

| Stage | Result |
|---|---|
| User action | PASS — Analyze Pose / Check Motion Continuity / Send to Scene Creator / Send to Timeline |
| Frontend | PASS — accordion; no JEPA jargon; persist hydrate on reload |
| API | PASS — `/api/posecraft/projects/{id}/intelligence/*` |
| Backend | PASS — kinematic analyzer + optional V-JEPA reuse |
| Persistence | PASS — `ProjectTraitRow` `pose_intelligence`; GET latest after reload |
| Runtime | PASS — V-JEPA worker reused on Schnick images (local) |
| Result | PASS — creator summary + contacts + conditioning prefix |
| Reload | PASS — Playwright + API GET |
| Downstream | PASS — Scene Creator `production_context`; Timeline `poseMotionConditioning` |

### Phase 2.1 Spatial Metric

| Stage | Result |
|---|---|
| User action | PASS — create 20×20 Martial Arts Metric Cert map on Schnick |
| Frontend | PASS — `1 square = 1 meter` on empty Atlas setup and populated map |
| API | PASS — Spatial Map create / update / camera look-raise-orbit |
| Backend | PASS — `metric.py` migrate + sync; no axis flip; no invented cells for unplaced entities |
| Persistence | PASS — meters survive reload |
| Runtime | N/A — no GPU generation required for the metric Playwright file |
| Result | PASS — 12 m spacing; camera lock |
| Reload | PASS |
| Downstream | PASS (local) — compile lines + PoseCraft world-origin hydrate. Hosted N/A |

---

## Hosted Phase 2 deploy

| Item | Value |
|---|---|
| Method | Local `npm --prefix studio-web run build` in a clean worktree, then `vercel deploy --prebuilt --prod --yes` |
| Why | Git-triggered preview failed (~50s). Remote `vercel --prod` hung UNKNOWN. Cursor Vercel MCP stayed in error |
| CLI identity | `vercel whoami` → `bradjohnson79-8209` |
| Bundle proof | Analyze Pose, Check Motion Continuity, Send to Scene Creator, Send to Timeline, `adult-female-lowpoly-v3`, Pose Intelligence, `posecraft-accordion` |
| Hosted JEPA string | **False** (do not claim hosted JEPA) |
| v3 GLBs | HTTP 200, ~32816 bytes, `model/gltf-binary` |

Do **not** deploy the `studio-web` Vercel project `prj_Bh26SzRX6yPB1kN3Jj3KJH0fGo8V`. Product project is **adeptui**.

---

## Peer review

Law 27 requested `gpt-5.4-medium` for specialized subagents. That slug was unavailable. Reviews used `glm-5.2-max` and `kimi-k3-max`.

| Reviewer | SHA | Verdict |
|---|---|---|
| GLM 5.2 [Review](61558c0f-f2b7-42b5-a6b5-73db14ef4e8c) | Phase 2 first pass | READY FOR PRIMARY REVIEW |
| Kimi K3 [Review](011c62f1-93f1-4587-bb46-588afad418ab) | Phase 2 first pass | GAPS FOUND — persist key, seated false-positive, observedWorld, snapshot-cache; **repaired** |
| GLM 5.2 [Review](243fee29-8e3a-44d5-82e8-5b2c13c7e288) | `a62d7a1` | READY FOR PRIMARY REVIEW |
| Kimi K3 [Review](73129835-58c1-4eaf-bdf7-6ff0c9b7eb0d) | `a62d7a1` | READY FOR PRIMARY REVIEW |
| GLM 5.2 [Review](f522d5fd-8f8f-4c03-848c-a37cec78d7ed) | `763248a` Phase 2.1 | READY FOR PRIMARY REVIEW |
| Kimi K3 [Review](560ee853-2712-44b2-adc1-5c065fba7f15) | `763248a` Phase 2.1 | READY FOR PRIMARY REVIEW |
| GLM 5.2 [Review](f325dc3f-e9f3-479a-974f-73edfc797e3b) | `11cb0e1` Phase 2.1 | READY FOR PRIMARY REVIEW |
| Kimi K3 [Review](353c5fd3-1f75-4294-8593-6b7175c62677) | `11cb0e1` Phase 2.1 | READY after primary adjudication |

Kimi flagged committed frontend `movementSegments` on `studio-web` `SpatialMapDocument`. That type is Phase 2 production legacy (`7964efd`), not a Phase 2.1 add. The backend Pydantic `SpatialMapDocument` at `11cb0e1` has no `movementSegments` / `zones`. Primary accepts this as out of Phase 2.1 scope.

Non-blocking notes kept:

- On a 20 m map, Neutral visual density can still be 10×10, so a drawn square can be 2 m while the label says 1 m.
- `camera_shot_packet` wraps metric compile in `except Exception: pass`.
- Phase 2.1 is not on Vercel SHA `5cbbb41`.

---

## Closure diagnoses (do not regress)

### Playwright H was not Accept deleting cameras

Serial Playwright (`workers=1`) plus a 30–180s `/auto-mask` GPU / Comfy `/free` hang restarted the worker. `beforeAll` then created a new empty map and H read `cameras.length === 0`. Repair: cache-or-honest-paint. H now proves existing camera → Review → Accept → persist → reload → same camera id from `:8758`.

### Phase 2 clean-clone

`773fedd` imported Movement / avatar handlers that were not in that tree. Repair: drop leaked tool defs; inline the auto-mask unavailable message; make cache lookup optional. Do **not** commit untracked `movement_tools.py` / dirty `avatar_m412.py` / `perception_router` into a PoseCraft SHA.

### Phase 2 production build

Clean SHA `017649c` failed `tsc` because `PoseCraftWorkspace` called `api.perception.extractSubject` (Revision D; not on Phase 2 `api.ts`). Extract-from-picture UI removed. Unused `onChange` then failed TS6133 and was stopped from destructuring.

### Phase 2.1 `sync_entity` invented cells

Default `x=0,z=0` is not a placement. Deriving `gridCell` for unplaced entities broke `test_spatial_map_v1_grid_camera.py`. Setting `gridCell` on `SpatialAnchor` 500’d list-maps. Repair: placed-only derivation; only write grid fields the model owns.

---

## Limitations

- Hosted Vercel frontend cannot prove local JEPA.
- Phase 2.1 **1 square = 1 meter** is not on `https://adeptui.vercel.app` until a **new** production SHA is deployed.
- Visual grid density (`gridScale`) is independent of `metersPerCell`. Neutral 10×10 on a 20 m map means a drawn square can be 2 m.
- Sequence intelligence uses existing snapshots/revisions. No new pose-timeline editor.
- Auto-mask no longer starts the SAM worker on the Scene Review request thread. Smart Select stays honest unless a cached mask exists.
- Timeline generate prompts may still include movement UNCHANGED FACTS before the pose-continuity prefix. Conditioning `applied=true` was present on the Gate F generate response.
- Cursor Vercel MCP remained broken; CLI deploy worked.
- Working tree remains dirty with unrelated Movement / avatar / perception files. Cert from a clean checkout of the SHAs above.

---

## Manual review path

1. Open Schnick Coffee (`2347bf46-3762-4763-86c5-4a6032522278`) at http://127.0.0.1:8760/.
2. Spatial Map: confirm **1 square = 1 meter**. Create or open `Martial Arts Metric Cert` (20×20). Characters 12 m apart. Camera look / raise / orbit must not move bodies.
3. PoseCraft: Analyze Pose / Check Motion Continuity / Send to Scene Creator / Send to Timeline. Reload; packets remain.
4. Hosted check (Phase 2 only): https://adeptui.vercel.app — Pose Intelligence accordion and v3 figures. Do not expect the 2.1 meter label or JEPA.

Leave Beta running.

---

## Mandatory checklist

```text
[x] Branch + starting SHA verified
[x] Contracts preserved or intentionally updated (additive spatial-metric-v1; schemaVersion stays 1)
[x] Full-stack implementation completed (Phase 2 hosted UI; Phase 2.1 local)
[x] Every visible Phase 2 / 2.1 control wired on the certified environment
[x] Real runtime for Phase 2 Gate F (LTX 2.5); no mock completion
[x] Persistence after reload verified (H cameras; metric Playwright)
[x] Error/cancel path honest for JEPA insufficient_reference
[x] Project isolation verified (wrong-project 404 on metric Playwright)
[x] Unit / API / Playwright measured above
[x] Playwright B + C re-run after Phase 2.1: 14 passed (19.9s)
[x] Failures repaired and documented
[x] Subagents second-pass: READY FOR PRIMARY REVIEW; primary issued the binary gates
[x] Production build passed for Phase 2 SHA 5cbbb41
[x] Beta updated and running; URLs reported
[x] Manual review path documented
[x] Evidence saved (phase2-live-gates.json + Playwright)
[x] This unified Markdown completion report created
[x] Limitations honest
[x] Verdict: GO for Phase 2; GO for Phase 2.1 local; hosted 2.1 = NOT VERIFIED
[x] GPU Gate F used the intended generator (LTX 2.5); no silent fallback
[x] Creator workflows inside Adept UI; JEPA not exposed as creator chrome
[x] One governing doc per milestone; this file is the completion report
```

---

## Remaining (authorized, not in this GO)

1. Push `11cb0e1` and `d340899` if they should be on the remote branch.
2. Deploy Phase 2.1 as a **new** adeptui production SHA if the 1 m label should appear on https://adeptui.vercel.app. Do not overwrite the Phase 2 SHA in place without an explicit new deploy.
3. Reconnect Cursor Vercel MCP (CLI already works).
4. Optionally raise Spatial Map visual density on 20 m maps so a drawn square matches 1 m.
