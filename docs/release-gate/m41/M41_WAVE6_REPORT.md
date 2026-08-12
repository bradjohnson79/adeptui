# M41 Phase 4.1 — Wave 6 Report

| Field | Value |
|---|---|
| **Phase** | 4.1 — Co-Director Production Completion |
| **Wave** | 6 — Media Generation Execution |
| **Date** | 2026-07-29 |
| **Product** | Adept UI Studio / Co-Director / Adept FilmWorks |
| **Branch** | `phase2/video-runtime-m41-41b-certified-workflows` |
| **Baseline** | [`M41_CODIRECTOR_AUDIT.md`](./M41_CODIRECTOR_AUDIT.md) |
| **Engine prerequisites** | [`M41_41A_REPORT.md`](./M41_41A_REPORT.md) · [`M41_41B_REPORT.md`](./M41_41B_REPORT.md) · [`M41_41BL_FINAL_GO_REPORT.md`](./M41_41BL_FINAL_GO_REPORT.md) |
| **Consumer contract** | [`M41_41BL_WAVE6_CONSUMER_CONTRACT.md`](./M41_41BL_WAVE6_CONSUMER_CONTRACT.md) |
| **Verdict** | **GO — Wave 6 production activation unlocked; Wave 6P product/beta certified (see M41_W6P_FINAL_CERTIFICATION.md)** |

---

## 1. Objective

Wave 6 connects Co-Director and product tools to the **Certified Workflow Library** so image/video/voice/music/SFX/lipsync/editor place/subtitle actions execute through a trustworthy runtime — not ad-hoc builders or silent mocks.

This report records the **production-activation entry gate** after M41 4.1B-L live certification and L-10B consumer-contract certification. It does **not** replace a dedicated Wave 6 end-to-end product and beta-certification campaign.

---

## 2. Division of responsibility

| Layer | Owns | Status |
|---|---|---|
| **4.1A Video Runtime** | Queue, cancel, VRAM, output gate, progress honesty | CONDITIONAL GO → wiring unlocked |
| **4.1B / 4.1B-L Certified Library** | Versioned workflows, resolver, fingerprints, live smoke/cancel/VRAM/output | **GO** |
| **L-10B Consumer Contract** | Wave 6 surfaces resolve only via public contracts | **PASS** |
| **Wave 6 product / beta** | Intelligent Co-Director + tool UX end-to-end on the certified engine | **Not yet certified** (separate prompt) |

```text
4.1A (wiring) ──► 4.1B-L (engine GO) ──► L-10B (consumer contract)
                                              │
                                              ▼
                              wave6ProductionActivationUnlocked = true
                                              │
                                              ▼
                         Wave 6 product implementation + beta cert
```

---

## 3. Gate status (live)

From `GET /api/video-runtime/gate` / `evaluate_gate()` (`artifacts/m41/41bl/workflow_gate_results.json`):

| Field | Value |
|---|---|
| `phase` | `M41-4.1B-L` |
| `localGateSatisfied` | `true` |
| `phase41bGo` | `true` |
| `wave6ConsumerContractPassed` | `true` |
| `wave6ProductionActivationUnlocked` | `true` |
| `wave6MediaExecutionUnlocked` | `true` |
| `enabledCloudProductionWorkflowKeys` | `[]` (cloud optional; fal remains Blocked) |
| `missingRequiredLocalKeys` | `[]` |

**Unlock rule:**

```text
localGateSatisfied
  ∧ phase41bGo
  ∧ wave6ConsumerContractPassed
→ wave6ProductionActivationUnlocked
```

---

## 4. Certified local production workflows (Wave 6 may execute)

`requiredLocalProductionWorkflowKeys ⊆ certifiedWorkflowKeys`:

| Workflow key | Role |
|---|---|
| `ltx.simple_i2v` | Local I2V leaf |
| `ltx.scene` | LTX Director keyframe scene |
| `ltx.ingredients_ic_lora` | Ingredients IC-LoRA reference path |
| `wan.first_last_frame` | WAN first/last-frame |
| `wan.three_frame` | Dual-segment first→middle / middle→last + stitch |
| `director.shot_render` | Shot orchestration (inherits certified leaves) |
| `director.scene_render` | Scene orchestration |
| `director.timeline_render` | Timeline orchestration |
| `director.batch_timeline` | Batch timeline orchestration |
| `video.extend` | Last-frame → local I2V extend |
| `lipsync.latentsync` | LatentSync lipsync |

**Deferred (not Wave 6 production):** upscale, motion/camera/character-consistent research modes, local T2V, etc.

**Cloud (release-required set exists; not enabled):** `fal.seedance`, `fal.kling`, `fal.veo`, `fal.runway` — Blocked / UI-disabled while `enabledCloudProductionWorkflowKeys` is empty.

---

## 5. Consumer contract (L-10B) summary

Wave 6 surfaces must consume the library only through:

```text
product intent → WorkflowResolver → CanonicalWorkflowContract → QueueWorker execute path
```

Verified:

- Co-Director generation intent resolves to a Certified contract  
- Director shot / scene intents resolve correctly  
- Generate Studio modes (LTX/WAN/txt2vid I2V/extend/lipsync) resolve correctly  
- Timeline and batch-timeline intents resolve correctly  
- Every contract carries workflow ID, version, provider, required inputs, cancellation policy, concurrency class, output contract  
- Blocked and Deferred rejected before queue (`assert_executable`)  
- No Wave 6 consumer imports Comfy builders directly  
- No Wave 6 consumer performs imperative engine→builder selection  
- No consumer bypasses static validation / VRAM preflight / QueueWorker / Output Gate / asset registration via direct `queue_prompt`  
- Registry status consistent across registry, projection, and gate  

Artifact: `artifacts/m41/41bl/wave6_consumer_contract_results.json`

---

## 6. Public contracts Wave 6 must use

| Surface | Contract |
|---|---|
| Resolve | `POST /api/video-runtime/resolve` → `CanonicalWorkflowContract` |
| Registry | `GET /api/video-runtime/certified-registry` |
| Gate | `GET /api/video-runtime/gate` |
| Execute | Studio jobs → QueueWorker (resolver at execute time) |
| Validate | `POST /api/video-runtime/validate-graph` + Output Gate on completion |

Product UI may select **engine** and **present inputs** as intent parameters. It must not select leaf Comfy graphs or import builders.

---

## 7. What Wave 6 product/beta still must prove

Production activation is unlocked; the following remain **out of scope for this report** and belong to a dedicated Wave 6 campaign:

1. Co-Director tool registry wiring for image/video/voice/music/SFX/lipsync/editor place/subtitle IDs  
2. End-to-end filmmaker scenarios (propose → approve → job → asset → timeline)  
3. Specialist handoffs that enqueue media jobs through the closed registry  
4. Honesty under degraded runtime (Comfy down, VRAM tight, cancel mid-job) from Co-Director UX  
5. Beta-entry checklist and Wave 8 cert overlap (M41-CD media items)  
6. Optional cloud enablement only after fal keys are Certified and added to `enabledCloudProductionWorkflowKeys`

---

## 8. Evidence index

| Artifact / report | Role |
|---|---|
| `M41_41BL_FINAL_GO_REPORT.md` | 4.1B-L engine GO |
| `M41_41BL_SMOKE_REPORT.md` / `CANCELLATION` / `VRAM` / `OUTPUT` | Live Comfy suites |
| `M41_41BL_CERTIFICATION_RECORDS.md` | Append-only cert ledger pointer |
| `M41_41BL_WAVE6_CONSUMER_CONTRACT.md` | L-10B consumer contract |
| `artifacts/m41/41bl/workflow_gate_results.json` | Gate snapshot |
| `artifacts/m41/41bl/wave6_consumer_contract_results.json` | Consumer contract results |
| `artifacts/m41/41bl/workflow_certification_records.json` | Certification Records |

---

## 9. Final verdict

| Question | Answer |
|---|---|
| May Wave 6 **wiring** continue? | **Yes** (since 4.1A) |
| May Wave 6 **production activation** proceed? | **Yes** |
| Is the Certified Library live-certified for required local keys? | **Yes** |
| Do Wave 6 consumers use public contracts only? | **Yes** (L-10B PASS) |
| Is Wave 6 product/beta end-to-end certified? | **No — separate campaign** |

**GO — Wave 6 production activation unlocked on the Certified Workflow Library and L-10B consumer contract. Proceed to Wave 6 product implementation and beta certification without redesigning the video runtime.**
