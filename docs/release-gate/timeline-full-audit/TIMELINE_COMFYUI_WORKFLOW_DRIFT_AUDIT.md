# Timeline ComfyUI Workflow Drift Audit

**Date:** 2026-08-07
**Auditor:** Primary agent (read-only empirical investigation)
**Scope:** `WORKFLOW_GRAPH_DRIFT` release-blocker — where the certified fingerprint is created, where the runtime fingerprint is created, why they diverge on the Timeline path, and the canonical fingerprint contract repair.
**Status:** ROOT CAUSE CONFIRMED WITH RUNTIME EVIDENCE (Cause class A — legitimate dynamic substitution incorrectly included in the fingerprint)

## 1. Observed failure

Live Timeline generation surfaces:

```
WORKFLOW_GRAPH_DRIFT: <workflowKey>@<version> graphHash mismatch
  (certified=sha256:…, actual=sha256:…)
```

The error is raised **before** `queue_prompt` — generation is blocked (fail-closed). This audit does not suppress the error and does not weaken drift detection.

## 2. Where the certified fingerprint is created

- Registry: `config/video-workflows/certified-registry.json`
  - `ltx.simple_i2v` @ 1.0.0 — status **Certified**, `fingerprints.graphHash = sha256:6e35b92dc996a91861f8bed6baca663fb3075a965aba5613ca5f59fbd3310767`
  - `ltx.scene` @ 1.0.0 — status **Certified**, `fingerprints.graphHash = sha256:5818dfcffb4f15ae146bacf0d06c05e88e00f44d2714eeb5caaaec128d23cf52`
  - Both certified 2026-07-29 (`CERT-WF-LTX-001/002-20260729-003`). The certification record stores **only the hash** — no reference build parameters.
- Hash algorithm: `studio-api/app/video_runtime/fingerprints.py`
  - `canonicalize_graph()` (lines 61–75): sorts nodes, keeps `class_type` + `inputs`, redacts only `_VOLATILE_INPUT_KEYS` (lines 24–41: `image`, `text`, `filename_prefix`, `noise_seed`, `seed`, `video`, `audio`, `video_path`, `audio_path`, `ckpt_name`, `unet_name`, `vae_name`, `clip_name`, `model_name`).
  - **All other scalar inputs are hashed verbatim** — including geometry and quality scalars.
  - `graph_hash()` = sha256 of the canonical JSON.

## 3. Where the runtime fingerprint is created

- `studio-api/app/video_runtime/workflow_execute.py` → `prepare_executable_graph()` (lines 209–231): for **Certified** workflows, calls `assert_no_graph_drift(built_graph, expected_graph_hash)` — recomputes `graph_hash` over the just-built runtime graph and compares to the registry value.
- Timeline call path: `queue_worker.py::_build_and_run_scene` → `resolve_from_scene_params` → `build_leaf_graph` (line ~920, with **per-batch** `width/height/length/fps/steps`) → `_run_graph` → `prepare_executable_graph(..., enforce_certified_fingerprint=True)` (line 856) → drift gate.
- Timeline per-batch params come from the W46 batch: `timelineGeneration` job params override prompt, duration→frames (`length`), seed (queue_worker.py lines 731–744, `TIMELINE_BATCH_LTX`).

## 4. Empirical field-level diff (the decisive evidence)

Two legitimate `build_ltx_simple_i2v` builds differing only in per-job params
(768×512/121f/24fps/8 steps vs 832×480/65f/30fps/12 steps, different prompt/seed/image/prefix) produce canonicalized graphs differing in **exactly six inputs**:

| Node (class) | Input | Build 1 | Build 2 | Nature |
|---|---|---|---|---|
| 5 (`LTXVImgToVideo`) | `width` | 768 | 832 | per-job geometry |
| 5 (`LTXVImgToVideo`) | `height` | 512 | 480 | per-job geometry |
| 5 (`LTXVImgToVideo`) | `length` | 121 | 65 | per-job frames (duration × fps) |
| 3b (`LTXVConditioning`) | `frame_rate` | 24.0 | 30.0 | per-job fps |
| 12 (`VHS_VideoCombine`) | `frame_rate` | 24 | 30 | per-job fps |
| 8 (`BasicScheduler`) | `steps` | 8 | 12 | per-job quality plan |

Everything else — node IDs, `class_type`s, all links, and the already-redacted volatile keys (prompt text, seed, image filename, checkpoint names, filename_prefix) — is identical.

A probe of five plausible parameter combinations against the certified hash `sha256:6e35b92d…` produced **zero matches**, confirming the certified hash corresponds to one specific (unrecorded) reference parameter set from 2026-07-29.

## 5. Root cause

**Cause class A — legitimate dynamic substitution incorrectly included in the fingerprint.**

The certified `graphHash` conflates two different contracts:

1. **Topology** — node inventory, node classes, link structure. This is what drift detection must protect. It is stable across all legitimate per-job builds.
2. **Dynamic bindings** — prompt, seed, filenames (already redacted) **plus** `width`, `height`, `length` (frames), `frame_rate` (fps), and `steps` (NOT redacted — hashed).

Timeline batches legitimately vary duration (→ `length`), resolution (→ `width`/`height`), fps (→ `frame_rate`), and quality plan (→ `steps`). Every batch whose resolved bindings differ from the 2026-07-29 reference build fails the gate. Scene renders only ever passed when their resolved params happened to match the certification-time params.

Ruled out with evidence:
- **B (topology mutation):** no — node classes/links are identical across builds (§4).
- **C (stale certification artifact):** partially contributory (reference params unrecorded), but the artifact is "correct" for exactly one binding set — the contract itself is wrong, not just the artifact.
- **D/E (wrong template/route):** no — `resolve_from_scene_params` selects `ltx.simple_i2v`/`ltx.scene` correctly; the Timeline MiniMax H3 path uses its own adapter (`minimax_h3/route_a_adapter.py`) and never crosses this gate.
- **F (T2V/I2V mismatch):** no — I2V is enforced upstream (`ltx.* requires start_image`, queue_worker.py line 844).
- **G (serialization order):** no — canonicalization sorts nodes and keys.
- **H (runtime mutation):** no — the built graph is hashed before submission; nothing mutates it in between.

## 6. Canonical fingerprint contract (repair definition)

```text
CERTIFIED TOPOLOGY FINGERPRINT (topologyHash)
  = canonical form of: sorted node IDs → class_type + link inputs ONLY
  (all scalar inputs excluded — they are bindings, not topology)

RUNTIME INSTANCE VALIDATION (dynamic bindings)
  = per-build validation of: prompt non-empty, seed int, frames == snapped
    duration×fps, frame_rate == plan fps, width/height == plan dims,
    filename_prefix unique per batch, LoadImage reference present (I2V),
    model names ∈ runtime object_info lists

GATE RESULT
  TOPOLOGY MATCH: YES/NO      (NO → WorkflowGraphDriftError, BLOCK generation)
  DYNAMIC BINDINGS VALID: YES/NO + reasons
```

True topology changes (node added/removed, `class_type` changed, link changed,
required model node missing, I2V graph downgraded to T2V) still change
`topologyHash` and **block generation**. Binding variation no longer does.

## 7. Repair plan (implemented in t3-workflow)

1. `video_runtime/fingerprints.py`: add `canonicalize_topology` / `topology_hash` / `assert_no_topology_drift` / `validate_dynamic_bindings`. Legacy `graph_hash` retained for provenance.
2. `video_runtime/workflow_execute.py::prepare_executable_graph`: prefer `fingerprints.topologyHash`; legacy `graphHash` fallback only for unmigrated entries; attach `{topologyMatch, bindingsValid, bindingsReport}`.
3. Registry migration (additive): compute `fingerprints.topologyHash` for all video entries via reference builds; legacy `graphHash` values untouched.
4. `image_runtime` parallel module intentionally left unchanged (not implicated; Law 6) — revisited only if image runtime reports drift.
5. Phase 12 regression tests (7 mandatory) prove: prompt/seed/image/duration variation → no drift; class/link/model-node/I2V-downgrade changes → blocked.

## 8. Verdict

Defect understood end-to-end with runtime evidence. Repair proceeds under the contract in §6. Drift detection is preserved and strengthened (topology), not weakened.
