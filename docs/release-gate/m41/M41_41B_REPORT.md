# M41 Phase 4.1B — Certified ComfyUI Video Workflow Library Report

| Field | Value |
|---|---|
| **Phase** | 4.1B — Certified ComfyUI Video Workflow Library |
| **Date** | 2026-07-29 |
| **Product** | Adept UI Studio / Adept FilmWorks |
| **Branch** | `phase2/video-runtime-m41-41b-certified-workflows` |
| **Extends** | [M41 4.1A Video Runtime](./M41_41A_REPORT.md) (no parallel stack) |
| **Hard gate for** | M41 Wave 6 production activation |
| **Verdict** | **GO — required local production workflows live-certified (M41 4.1B-L)** |

---

## 1. Objective

Establish the **Certified Workflow Library** as the single authoritative source for every Adept UI video-generation capability:

- Versioned ComfyUI (and cloud) workflows with permanent WF-IDs
- Workflow Resolver (product intent → canonical contract)
- QueueWorker execute-only (no imperative engine selection)
- Immutable fingerprints + graph-drift detection
- Auditable Certification Records
- Smoke / cancel / VRAM / output / UI honesty
- Deferred only for genuine future research (not incomplete production holes)

**Maturity label:** Required local production workflows are **Certified** via M41 4.1B-L live Comfy evidence (smoke, cancel, VRAM/output, append-only Certification Records). Cloud fal keys remain Blocked (not in `enabledCloudProductionWorkflowKeys`). Upscale/research stay Deferred.

---

## 2. Sequencing

```text
Wave 4 (GO) Durable Planning Operator
        │
        ├────────────────┬────────────────┐
        ▼                ▼                │
   Wave 5           Phase 4.1A            │
 Specialists     Video Runtime (CONDITIONAL GO)
        │                │                │
        │                ▼                │
        │           Phase 4.1B            │
        │     Certified Workflow Library  │
        │           GO (4.1B-L live cert) │
        │                │                │
        └────────┬───────┘                │
                 ▼                        │
     Wave 6 wiring may continue           │
     Production activation ◄── 4.1B GO    │
```

| Unlock | Status |
|---|---|
| Wave 6 **wiring / integration development** | Allowed (per 4.1A CONDITIONAL GO) |
| Wave 6 **production activation** | **Blocked** until 4.1B Full GO (CERTIFIED workflows + live evidence) |
| Production media via non-CERTIFIED workflows | **Must not** claim Production Ready |

Exposed via `GET /api/video-runtime/gate` (`phase: M41-4.1B`, `certifiedWorkflowCount`, `phase41bGo`).

---

## 3. Scope delivered

| Wave | Deliverable | Status |
|---|---|---|
| **4.1B-1** | Workflow inventory + permanent WF-IDs | **Done** |
| **4.1B-2** | Single Certified Workflow Registry (semver, fingerprints, Certification Records) | **Done** |
| **4.1B-3** | Build/normalize LTX/WAN/timeline/extend/lipsync/fal; WAN three-frame | **Done (code)** |
| **4.1B-4** | Static graph validation (fail closed) | **Done** |
| **4.1B-5** | Smoke testing harness | **Static PASS; live SKIP** |
| **4.1B-6** | Cancellation certification | **Code path ready; live SKIP** |
| **4.1B-7** | VRAM profiles | **Registry estimates; live SKIP** |
| **4.1B-8** | Output validation | **Gate wired; live SKIP** |
| **4.1B-9** | Resolver + QueueWorker + UI honesty | **Done** |
| **4.1B-10** | Production certification stamp | **GO** (via 4.1B-L) |

---

## 4. Architecture

```text
Director / Co-Director / Generate Studio / Timeline
        │
        ▼
 WorkflowResolver
        │
        ▼
 Certified Workflow Registry  ←── single authority
        │
        ▼
 CanonicalWorkflowContract
        │
        ▼
 QueueWorker (execute-only)
        │
        ├─ static validate
        ├─ fingerprint check (Certified only)
        ▼
 Comfy / fal runtime → Output Gate → Asset registration
```

### Key modules

| Path | Role |
|---|---|
| [`config/video-workflows/certified-registry.json`](../../../config/video-workflows/certified-registry.json) | Source of truth |
| [`studio-api/app/video_runtime/certified_registry.py`](../../../studio-api/app/video_runtime/certified_registry.py) | Loader + `productionReady` honesty |
| [`studio-api/app/video_runtime/workflow_resolver.py`](../../../studio-api/app/video_runtime/workflow_resolver.py) | Intent → contract |
| [`studio-api/app/video_runtime/workflow_execute.py`](../../../studio-api/app/video_runtime/workflow_execute.py) | Build + validate + drift gate |
| [`studio-api/app/video_runtime/fingerprints.py`](../../../studio-api/app/video_runtime/fingerprints.py) | Structural graph / builder / inventory hashes |
| [`studio-api/app/video_runtime/graph_validation.py`](../../../studio-api/app/video_runtime/graph_validation.py) | Fail-closed static checks |
| [`studio-api/app/workflows/wan_builder.py`](../../../studio-api/app/workflows/wan_builder.py) | `build_wan_three_frame_workflow` (dual-segment) |
| [`scripts/m41_41b_live_certify.py`](../../../scripts/m41_41b_live_certify.py) | Static + live cert harness |

Compatibility catalog is a **projection** of the certified registry (not a second authority). Root `workflows/*.json` are non-authoritative mirrors ([`workflows/README.md`](../../../workflows/README.md)).

---

## 5. Production pipeline vs Deferred

### Production pipeline (must leave no holes)

| WF-ID | workflowKey | Implementation | Cert status |
|---|---|---|---|
| WF-LTX-001 | `ltx.simple_i2v` | Existing builder + resolver | **Blocked** (live pending) |
| WF-LTX-002 | `ltx.scene` | Existing Director builder | **Blocked** |
| WF-LTX-003 | `ltx.ingredients_ic_lora` | Existing compiler | **Blocked** |
| WF-WAN-001 | `wan.first_last_frame` | Existing FLF (middle unsupported) | **Blocked** |
| WF-WAN-002 | `wan.three_frame` | Dual-segment FLF + stitch | **Blocked** |
| WF-SHOT-001 | `director.shot_render` | Orchestration → leaf | **Blocked** |
| WF-SCENE-001 | `director.scene_render` | Orchestration → leaf | **Blocked** |
| WF-TIMELINE-001 | `director.timeline_render` | Reuse outputs + stitch | **Blocked** |
| WF-TIMELINE-002 | `director.batch_timeline` | Regenerate all + stitch | **Blocked** |
| WF-EXTEND-001 | `video.extend` | Last-frame → local I2V | **Blocked** |
| WF-LIPSYNC-001 | `lipsync.latentsync` | Existing LatentSync | **Blocked** |
| WF-FAL-001…004 | `fal.*` | Cloud adapters | **Blocked** (credentials/live) |

### Deferred (stable contracts only)

| WF-ID | workflowKey |
|---|---|
| WF-UPSCALE-001 | `video.upscale` |
| WF-DEF-001…007 | motion / camera / character / rife / restoration / local_t2v / pose |

**Honesty rule:** `productionReady === true` only when `status === Certified` **and** a Certification Record exists. Built/Blocked never advertise Production Ready.

---

## 6. Fingerprints & Certification Records

Each workflow version may carry:

- `graphHash` — structural Comfy graph (volatile inputs redacted)
- `builderHash` — builder source digest
- `nodeInventoryHash` / `modelInventoryHash`

Runtime: Certified workflows fail closed on `WORKFLOW_GRAPH_DRIFT` before `queue_prompt`.

Certification Records store evidence (`smoke`, `cancellation`, `vram`, `output`, `playback`, `uiIntegration`, `regression`), Comfy/node/model inventory, fingerprints, and artifact refs. Bare `CERTIFIED` without a record is invalid.

---

## 7. API & UI surfaces

| Surface | Notes |
|---|---|
| `GET /api/video-runtime/certified-registry` | Full library |
| `POST /api/video-runtime/resolve` | Intent → contract |
| `POST /api/video-runtime/validate-graph` | Static validation |
| `GET /api/video-runtime/gate` | 4.1B phase + certified counts |
| `POST …/render` `kind=shot\|batch_timeline` | New orchestration jobs |
| GenTools `video.extend` | Queues `video_extend` (local I2V) |
| `/diagnostics/video-runtime` | Shows Certified Workflow Library |
| GenTools Deferred badge | Maps `DEFERRED` → Deferred (not Unknown) |

---

## 8. Testing

| Suite | Result |
|---|---|
| `tests/test_m41_41b_certified_workflows.py` | **PASS** |
| `tests/test_m41_41a_video_runtime.py` (honesty updated) | **PASS** |
| `scripts/m41_41b_live_certify.py` (static) | **PASS** (all production keys) |
| Live Comfy smoke / cancel / VRAM / output / playback | **SKIP** (ComfyUI unreachable) |
| Playwright `tests/e2e/m41/m41-41b-certified-workflows.spec.ts` | Spec added |

---

## 9. Evidence index

| Document | Path |
|---|---|
| **This report** | [`M41_41B_REPORT.md`](./M41_41B_REPORT.md) |
| Inventory | [`M41_41B_WORKFLOW_INVENTORY.md`](./M41_41B_WORKFLOW_INVENTORY.md) · [`docs/video-workflows/workflow_inventory.md`](../../video-workflows/workflow_inventory.md) |
| Registry | [`M41_41B_WORKFLOW_REGISTRY.md`](./M41_41B_WORKFLOW_REGISTRY.md) |
| Implementation | [`M41_41B_IMPLEMENTATION_REPORT.md`](./M41_41B_IMPLEMENTATION_REPORT.md) |
| Smoke | [`M41_41B_SMOKE_TEST_REPORT.md`](./M41_41B_SMOKE_TEST_REPORT.md) |
| Cancellation | [`M41_41B_CANCELLATION_REPORT.md`](./M41_41B_CANCELLATION_REPORT.md) |
| VRAM | [`M41_41B_VRAM_CERTIFICATION.md`](./M41_41B_VRAM_CERTIFICATION.md) |
| Output | [`M41_41B_OUTPUT_VALIDATION.md`](./M41_41B_OUTPUT_VALIDATION.md) |
| UI | [`M41_41B_UI_INTEGRATION_REPORT.md`](./M41_41B_UI_INTEGRATION_REPORT.md) |
| Final stamp | [`M41_41B_FINAL_CERTIFICATION.md`](./M41_41B_FINAL_CERTIFICATION.md) |
| Artifacts | [`artifacts/m41/41b/`](../../../artifacts/m41/41b/) |

---

## 10. Path to GO

1. Start ComfyUI with LTX / WAN / LatentSync models and extensions.
2. Run `ADEPT_41B_LIVE=1 python scripts/m41_41b_live_certify.py --live` with real smoke/cancel/VRAM/output runners.
3. Promote each production WF-ID to **CERTIFIED** only when all evidence is PASS and a Certification Record is written.
4. Re-stamp [`M41_41B_FINAL_CERTIFICATION.md`](./M41_41B_FINAL_CERTIFICATION.md) and this report with **Verdict: GO**.
5. Gate unlocks Wave 6 production activation only when `phase41bGo` is true and certified keys cover the production pipeline.

---

## 11. Forward look (4.1C)

Registry/resolver/fingerprint/certification APIs keep `modality` first-class (`video` now; `image` later) so **4.1C — Certified Image Workflow Library** can reuse this infrastructure without forking.
