# Adept Audio-Visual Media Intelligence — Governing Architecture

**Milestone:** Adept Audio-Visual Media Intelligence (Qwen2.5-Omni + VideoChat3)
**Status:** IN PROGRESS — Phase A (audit) COMPLETE, Phase B (contract) IN PROGRESS
**Authority:** Primary agent. Subagents return `READY FOR PRIMARY REVIEW`.
**Supersedes:** none (new milestone). Historical fidelity reports stay historical (Law 30).

## Mission (condensed)

Build one canonical Adept Media Intelligence Service that inspects finished video
with both vision and audio awareness, produces a structured timestamped
**Media Intelligence Packet**, and exposes it to:

- **Timeline + Co-Director** — event detection, dialogue, footstep/contact timing,
  ambience/SFX placement, scene analysis.
- **CREATE Diagnostics** — 1 Frame / 3 Frame / Text to Video — inspect generated
  clips for visual defects, audio distortion, temporal problems, A/V sync,
  color shifts, identity drift, broken frames.

Not a chatbot feature. A shared production perception service.

## EXISTING VIDEO INTELLIGENCE AUDIT (Chapter 1) — COMPLETE

Three parallel subagents audited `C:\AdeptFilmWorks\AIVideoStudio`. Classification:
EXISTS / DISCONNECTED / MISSING / LEGACY.

### EXISTS — reuse, do not rebuild

| Capability | Location | Notes |
|---|---|---|
| VideoChat3 4B | `codirector/video_intelligence/` | Full module: worker subprocess, GPU lease, hardware profile, certify, health, observability. Produces `TemporalContinuityPacket` (`temporal-continuity-v1`) with timestamped `ImportantEvent`s. `required=True` in Setup. **Weights NOT on disk.** |
| V-JEPA 2 (world) | `codirector/world_intelligence/` | Router live. **Weights on disk** (1.3GB). Used by video + pose. |
| InternVideo3 8B | `codirector/video_intelligence/worker.py` | Optional deep-review, same worker, `--model-id` routed. Weights not on disk. |
| Stills perception | `codirector/perception/` | DINO/SAM 2.1/Depth. Optional. |
| Pose intelligence | `codirector/pose_intelligence/` | Reuses V-JEPA. |
| Co-Director fal vision | `codirector/vision/vision_review.py` | Canonical **image** vision (fal-ai/any-llm/vision). Image-only. |
| Timeline cue model | `director_timeline_w46/contracts.py` | `BatchClip(kind="sfx")` on `BatchBlock.sfxClips`. |
| SFX placement API | `AudioService.place_cue()` | Live placement path. |
| `timeline.add_audio` handler | `codirector/capabilities/handlers/timeline_add_audio.py` | Uses `plan_walk_footsteps()` — **inferred 0.55s cadence** (the gap). |
| Capability/Tool/Deliberation registries | `codirector/capabilities/registry.py`, `tools/registry.py`, `deliberation/service.py` | Frozen, extensible. `_FOOTSTEP_PLACE_RE` is the routing template. |
| Asset DB + project scoping | `db.py`, `project_security/asset_file.py` | `resolve_project_asset_path()` → 403 `ASSET_PROJECT_MISMATCH`. |
| Project-scoped packet store | `ProjectTraitRow` (+ `spatial_map/ers_persistence._upsert_trait/_load_trait_value`) | Used by pose + world intelligence. Reuse for MI packet. |
| Audio Studio / SFX library | `audio_studio/` | `service._library_audio()` — **per-project only** (aligns with Ch 41). |
| Colorspace query | `minimax_h3/route_a_adapter._stream_colorspace` | Reusable ffprobe query. `finalize_h3_colorspace` stays H3-specific. |

### DISCONNECTED / MISSING / LEGACY — build or promote

| Gap | Class | Action |
|---|---|---|
| M2.5 Vision Validation Engine | DISCONNECTED (flag off, validators are stubs) | Revive for CREATE diagnostics (has schemas/sessions/approvals/corrections). |
| Audio perception (`-an` strip) | MISSING | Remove `-an` from `clip_extract.py`; add audio ingestion for Qwen-Omni. |
| Qwen2.5-Omni | MISSING | Add as new `model_id` in worker + Setup catalog + Source Manager. |
| `analyze.video` capability | MISSING | Add to capability registry + handler. |
| ASR/transcription | MISSING (whisper is lip-sync-only) | Build or wrap whisper-tiny. |
| A/V sync measurement | MISSING | Build new (deterministic). |
| Comprehensive audio amplitude scan | LEGACY (`.runtime/_fidelity_analyze.py`, not in codebase) | Promote + generalize into `studio-api/app`. |
| Canonical ffprobe helper | FRAGMENTED (5+ variants) | Consolidate into one reusable probe. |
| Footstep contact detection (real) | MISSING | Replace inferred cadence with detected timestamps. |

**No competing "Media Intelligence" authority by name.** Semantic overlap with
video_intelligence / world_intelligence / vision / perception — resolved by
**extending** video_intelligence (see decision below), not building beside it.

## Architecture Decision — EXTEND video_intelligence (owner-approved)

The existing `codirector/video_intelligence/` already runs models in an **isolated
subprocess worker** (not inside Studio API) with GPU lease + hardware profile +
certify + health — it IS a separate on-demand service. Per workspace law
("reconnect before rebuilding — do not introduce another video-understanding
authority if a usable part already exists") and the owner's selection, the
**Adept Media Intelligence Service = the extended `video_intelligence` authority**.

### Extension surface

1. **Worker** (`worker.py`) — add `qwen2-5-omni-7b` as a new `--model-id` branch.
   Qwen-Omni ingests video **+ audio** (`Qwen2_5OmniForConditionalGeneration`). VideoChat3
   stays the visual-temporal specialist; InternVideo3 stays optional deep-review.
2. **clip_extract** (`clip_extract.py`) — add audio-retaining variants (drop `-an`)
   for Qwen-Omni; keep the low-res 512px/2fps OOM-guard for VideoChat3.
3. **Service** (`service.py`) — decouple a general `analyze_asset(assetId, mode)`
   path from the batch-continuity gate (`review_completed_batch` stays for continuity).
4. **Packet** — new `MediaIntelligencePacket` (`media-intelligence-v1`) in
   `media_packet.py` (FROZEN). Asset-scoped, not batch-scoped. Persisted on
   `ProjectTraitRow` (category `media_intelligence_packet`).
5. **Capability** — add `analyze.video` to `capabilities/registry.py`; handler
   `capabilities/handlers/analyze_video.py`. Route in `deliberation/service.py`.
6. **Diagnostics** — consolidate ffprobe into one reusable probe; promote the
   `.runtime` amplitude scan; build A/V sync; revive M2.5 engine for CREATE diagnostics.
7. **Timeline** — feed detected `ContactEvent` timestamps into `timeline.add_audio` /
   `AudioService.place_cue` (replacing inferred cadence).

## Media Intelligence Packet — FROZEN CONTRACT

File: `studio-api/app/codirector/video_intelligence/media_packet.py`
Schema: `media-intelligence-v1`. Verified import + instantiate.

Top-level: `MediaIntelligencePacket` (projectId, assetId, analysisVersion, availability,
mode, media:MediaFacts, summary, visualEvents[], audioEvents[], speechSegments[],
characterActions[], motionEvents[], contactEvents[], environmentEvents[],
diagnostics:Diagnostics, createContext:CreateDiagnosticContext, modelEvidence:ModelEvidence,
fingerprint:AnalysisFingerprint, createdAt).

Every event extends `TimedEvent` (startTime, endTime, startFrame, endFrame, confidence) —
one time authority (Ch 5). `ContactEvent` carries foot/surface/intensity (Ch 10).
`AudioEvent` carries eventType/material/presentInAudio (Ch 11). `Diagnostics` carries
video/color/audio/avSync/distortions/report (Ch 24-29). `AnalysisFingerprint` for cache
invalidation (Ch 7). `CreateDiagnosticContext` for surface-specific framing (Ch 20-23).

## Model Installation / Source Authority (Chapter 2)

Add Qwen2.5-Omni through the canonical model/source architecture (no hardcoded paths):

1. `setup/catalog.py` — `ComponentDefinition(id="qwen2_5_omni_7b", required=False, ...)`.
2. `setup/diagnostics.py` — verifier branch + `_VERIFIER_TO_DEP_TYPE`.
3. `setup/orchestrator.py` — install-routing branch.
4. `source_manager/downloads/executors/` — reuse `huggingface_snapshot` (Qwen-Omni is on HF).
5. `capabilities/registry.py` — capability row.
6. `readiness/v11_policy.py` — `CAPABILITY_POLICY` entry.
7. `video_intelligence/install.py` + `paths.py` — add `qwen2_5_omni_7b` to `_SPECS`.

VideoChat3 weights: install via existing `videochat3_4b` component (weights currently
absent). Both visible in Source Manager with Not Installed / Installed / Ready / Updating /
Error states. Qwen-Omni tier: **Recommended Media Intelligence** (not a boot blocker —
core Adept stays usable if absent, per Ch 44).

## GPU Admission (Chapter 36)

Heavy local models — never permanently resident. Reuse existing Adept GPU admission
(request → residency → controlled unload). **Must not contend with MiniMax H3 `:8192` or
Comfy `:8188`** — queue/wait when generation is admitted. Do not kill active generation to
answer "what happens in this video?" unless user explicitly requests priority. The
`video_intelligence/gpu_lease.py` + `hardware_profile.py` already implement this — extend.

## Known pre-existing issues (OUT OF SCOPE — documented, not fixed here)

- **`tests/test_setup_refactor.py::test_status_reuses_short_cache_when_idle` FAILS** —
  pre-existing, NOT caused by Media Intelligence work. Root cause: an uncommitted prior
  `status.py` "ready-requires-filesystem-path" gate (38 insertions, predates this milestone)
  downgrades `path=None` → `error`; the test mocks `verify_component` to return `path=None`.
  Proven by the model-install subagent: reverting `status.py` to HEAD makes the test pass
  with all Qwen-Omni edits present. Left as-found (out of scope for this milestone). Owner
  may address separately.

## Integration Points

- **Co-Director** (Ch 14): `analyze.video` capability consumes the packet (not raw bytes
  through chat). Deliberation routes footstep/SFX/diagnostic intents (Ch 46).
- **Timeline** (Ch 15-18): detected `ContactEvent` → `timeline.add_audio` →
  `AudioService.place_cue`. Each cue preserves source event + packet ID/version +
  timestamp + SFX assetId + character + confidence (Ch 18). Human-editable (Ch 19).
- **CREATE Diagnostics** (Ch 20-23): post-generation `Analyze Result` route. 1F compares
  source still; 3F compares START/MIDDLE/END; T2V no reference. Surface-specific packets.
- **Cursor/Grok** (Ch 31): `diagnose asset <assetId>` returns structured evidence.
- **Creator vs Engineering UX** (Ch 32): creator sees concise status; engineering sees
  the full diagnostic packet in inspector/diagnostics.

## Phase Plan (A–M)

| Phase | Chapters | Status |
|---|---|---|
| A — Audit | 1 | COMPLETE |
| B — Architecture + contract | 2-7 | IN PROGRESS (packet frozen; doc this file) |
| C — Perception | 8-13 | pending |
| D — Co-Director + Timeline | 14-19 | pending |
| E — CREATE diagnostics | 20-23 | pending |
| F — Deterministic diagnostics | 24-30 | pending |
| G — Agent + UX | 31-32 | pending |
| H — Quality + governance | 33-36 | pending |
| I — Playwright E2E | 37-40 | pending |
| J — Isolation + persistence | 41-43 | pending |
| K — Setup + Source Manager + Deliberation | 44-46 | pending |
| L — Fallback + tests + review | 47-49 | pending |
| M — REQUIRED REPORT + verdict | — | pending |

## GPU / Runtime Before & After

- **Before:** `:8188` Comfy (protected), `:8192` MiniMax H3 (managed), Studio API `:8758`,
  Vite `:5173`. No Media Intelligence models loaded.
- **After (target):** same protected runtimes untouched. Qwen-Omni + VideoChat3 loaded
  on-demand in the isolated `videochat3-worker` subprocess under GPU admission, unloaded
  after analysis. No new persistent runtime. Comfy `:8188` RESTARTED?: NO.

## Final Verdict (pending)

Target: `GO — ADEPT AUDIO-VISUAL MEDIA INTELLIGENCE + CODIRECTOR TIMELINE SFX SYNC +
CREATE VIDEO DIAGNOSTICS E2E CERTIFIED`.

Issued only when Co-Director can genuinely watch+hear a real video, use timestamped
understanding to place Timeline audio/SFX, and the shared service diagnoses 1F/3F/T2V
defects using both perceptual and deterministic evidence. Otherwise NO-GO with the first
failing boundary.
