# M41 Phase 4.1A — Video Runtime Capability Audit

| Field | Value |
|---|---|
| **Phase** | 4.1A — Video Runtime & Generation Infrastructure |
| **Wave** | 4.1A-1 Audit |
| **Date** | 2026-07-29 |
| **Machine matrix** | [`artifacts/m41/41a/video-capability-matrix.json`](../../../artifacts/m41/41a/video-capability-matrix.json) |
| **Baseline** | [`docs/audit/generate-workflow-audit.md`](../../audit/generate-workflow-audit.md), M32A matrices, M30h/M32g certs |

---

## 1. Positioning

```text
Wave 4 (GO) Planning
   ├─ Wave 5 Specialists (no media execution)
   └─ Phase 4.1A Video Runtime certification
            │
            ▼ HARD GATE
         Wave 6 Media Execution
```

Wave 5 may proceed. **Wave 6 media generation execution is hard-blocked until 4.1A certification is GO.**

---

## 2. Architecture (current → target)

**Current:** UI → `txt2vid` / `render_*` / gen-tools → in-process `JobQueue` → ComfyUI (HTTP poll) or fal.ai → Asset file serve.

**Target:** Same Job rows + Model Compatibility Registry + preflight/VRAM gate + immediate Comfy cancel + normalized progress + output validation gate + diagnostics dashboard.

---

## 3. Production paths (must leave 4.1A Ready or Blocked-with-remediation)

| Mode | FE | Route | Workflow / Provider | Disposition |
|---|---|---|---|---|
| LTX simple I2V | Txt2Vid / Director / AssetTray | `POST …/render` | `ltx.simple_i2v` / Comfy | Repair + certify |
| LTX Director | Director | `render_scene` | `ltx.scene` (+ simple fallback) | Repair + certify |
| WAN FLF | Director / scene | `render_scene` | `wan.first_last_frame` | Repair + certify |
| LTX IC-LoRA | scene + refs | `render_scene` | `ltx.ingredients_ic_lora` | Ready when weights; else Blocked |
| fal Seedance/Kling/Veo/Runway | Txt2Vid | `POST …/txt2vid` | fal catalog | Repair + certify (paid gate) |
| Lip-sync | Director / lipsync | `lipsync` job | `lipsync.latentsync` | Repair + certify |
| Timeline stitch | Generate Timeline | `render_timeline` | multi-scene | Repair + certify |
| Video extend | GenTools | `video.extend` | last-frame → I2V | Repair + certify |
| Video upscale | GenTools | `video.upscale` | SeedVR2 intent | **Deferred** (no worker) |

---

## 4. Explicitly Deferred (stable contracts, no fake COMPLETE)

| Capability ID | Label |
|---|---|
| `video.motion_transfer` | Motion transfer |
| `video.camera_motion` | Camera motion synthesis |
| `video.character_consistent` | Character-consistent video |
| `video.rife_interpolation` | RIFE interpolation |
| `video.frame_restoration` | Frame restoration |
| `video.pose_transfer` | Advanced pose transfer |
| `video.multi_character_temporal` | Multi-character temporal consistency |
| `video.local_t2v` | True local text-to-video |
| `video.upscale` | Unfinished AI upscaling pipeline |

Each Deferred entry has a Model Compatibility Registry row with `capabilityState: deferred`, UI honesty, and no invented success.

---

## 5. Broken connections → disposition

See machine matrix `brokenConnectionsDisposition`. Critical 4.1A repairs: Avatar start/polling, local T2V honesty, WAN middle-frame honesty, **immediate Comfy cancel halt**, extend last-frame wiring, ensure_queueable preflight.

---

## 6. Gaps driving 4.1A implementation

1. `ensure_queueable` unused; missing models can reach Comfy.
2. Cancel marks Studio job cancelled but may leave Comfy sampling.
3. Progress is coarse 0.2/0.55/1.0; no WS / normalized stages.
4. VRAM tiers clamp settings; no live `VRAM_*` safety states.
5. No output gate before `completed` / playback.
6. No Model Compatibility Registry or diagnostics dashboard.
7. `video_upscale` queues jobs the worker cannot run.

---

## 7. Audit verdict

| Question | Answer |
|---|---|
| Is video runtime production-ready? | **No** — Partially Working product paths; infra gaps above |
| May Wave 6 media execution start? | **No** — hard gate until 4.1A GO |
| May Wave 5 specialists proceed? | **Yes** — no media execution |

**Proceed to 4.1A-2…8 implementation.**
