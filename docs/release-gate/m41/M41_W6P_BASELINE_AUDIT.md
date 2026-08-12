# M41 W6P-1 — Baseline Audit & Freeze

| Field | Value |
|---|---|
| **Phase** | M41 Wave 6P |
| **Date** | 2026-07-29 |
| **Baseline branch** | `phase2/video-runtime-m41-41b-certified-workflows` |
| **Target branch** | `phase2/wave6p-codirector-product-beta` |
| **Starting SHA** | `f758744168ec93f559d7fa0d9098ce47c39fe3ff` |
| **Prerequisites** | Met (`wave6ProductionActivationUnlocked=true`) |
| **Verdict** | **AUDIT COMPLETE — authoritative path map frozen; implementation may begin** |

---

## 1. Prerequisite gate snapshot

Recorded in `artifacts/m41/w6p/prerequisite_gate_snapshot.json`.

| Field | Value |
|---|---|
| `phase41bGo` | `true` |
| `wave6ConsumerContractPassed` | `true` |
| `wave6ProductionActivationUnlocked` | `true` |
| `wave6MediaExecutionUnlocked` | `true` |
| `missingRequiredLocalKeys` | `[]` |
| `enabledCloudProductionWorkflowKeys` | `[]` |

---

## 2. Product surface inventory

| Surface | Status at freeze |
|---|---|
| Co-Director compact / fullscreen | Partial UX (Waves 1–4); media tools incomplete |
| Director | Renders enqueue studio jobs; no ProductionIntent preflight |
| Generate Studio | Partial; modes do not compile shared intent |
| Timeline | `timeline/apply` + render kinds exist; editor.place not in registry |
| Asset Library | Working reads; provenance incomplete for scene renders |
| Production Bible | Working reads / proposals |
| Queue / JobPanel | Studio jobs + deep cancel |
| Video Runtime Diagnostics | Gate / resolve / registry |

---

## 3. Media tool inventory (closed registry)

| Tool | Status |
|---|---|
| Music / SFX generate | Partial (no place) |
| Video extend | Partial |
| Image upscale / bg / skin | Stub-success risk on failure |
| Shot / scene / I2V / three-frame / lipsync / voice / subtitle / editor.place / job.cancel|retry | **Missing** |

Full list: `artifacts/m41/w6p/baseline_inventory.json`.

---

## 4. Violations and honesty gaps

- No direct Comfy builder / `queue_prompt` imports under `codirector` or `studio-web` (L-10B PASS preserved).
- **Must remove:** `run_image_enhance_stub_copy` production fallbacks.
- **Must fix:** hardcoded `videoRuntime.workflow_key` in extend enqueue — resolve via WorkflowResolver.
- Plan readiness forces media steps to `deferred`.
- Specialists are advise-only (`may_execute_tools: false`).

---

## 5. Authoritative path map (frozen)

Every media action uses one path:

```text
Product intent
→ WorkflowResolver (video) or Approved Non-Video Tool Contract
→ Canonical Job Contract
→ QueueWorker / Certified Service Adapter
→ Output validation
→ Asset registration
→ Scene / Shot / Timeline / Project state
```

| Operation | Tool ID | Studio job / adapter | Resolver / workflow |
|---|---|---|---|
| `video.shot_render` | `propose_shot_generate` | `render_scene` | `shot_render` → `director.shot_render` |
| `video.scene_render` | `propose_scene_generate` | `render_scene` | `scene_render` → `director.scene_render` |
| `video.generate` | `propose_video_generate` | `render_scene` | `scene_i2v` → `ltx.simple_i2v` |
| `video.three_frame` | `propose_three_frame_generate` | `render_scene` | WAN three-frame → `wan.three_frame` |
| `video.timeline_render` | `propose_timeline_render` | `render_timeline` | `timeline_render` |
| `video.batch_timeline` | `propose_batch_timeline` | `batch_timeline` | `batch_timeline` |
| `video.extend` | `propose_video_extend` | `video_extend` | `extend` → `video.extend` |
| `video.lipsync` | `propose_lipsync` | `lipsync` | `lipsync` → `lipsync.latentsync` |
| `image.generate` | `propose_image_generate` | imagegen adapter | non-video contract |
| `voice/music/sfx` | propose_* | m210b / generation_tools | non-video |
| `subtitle.generate` | `propose_subtitle_generate` | subtitle adapter | non-video |
| `editor.place` | `editor.place_asset` | m29 / timeline | non-video |
| `job.cancel` / `job.retry` | `job.cancel` / `job.retry` | cancel_and_halt / re-enqueue | n/a |

---

## 6. Hard stop cleared

Implementation may proceed on `phase2/wave6p-codirector-product-beta` using only the paths above. No parallel media orchestration inside Co-Director, Director, or Timeline.
