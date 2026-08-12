# Adept UI Runtime Recovery & Workflow Zero-Block Audit

**RUN_ID:** `runtime-zero-block-2026-08-05T18-16-27Z`  
**Branch:** `feature/ai-guided-setup`  
**HEAD (start):** `fa09c99d6395c29461cdec4555055faad116c435`  
**Coordinator:** Primary agent + specialized subagents  
**Updated:** 2026-08-06T02:23:00Z

## 1. Executive summary

Control-plane recovery is complete for the live Beta stack. After ComfyUI restart, capability blockers returned to **0** and Production Assurance reaches **Operational / 100** with a bound project. Live DEFAULT_WORKFLOW_REGISTRY certification for the **active** release catalog is **9/9 GO**. Hunyuan workflows are **EXCLUDED** by product-owner direction (not used in Adept UI) and do not gate `WORKFLOW_CATALOG_GREEN`. MiniMax H3 33B Route A private T2VA completed with artifact + library import (`ltxUsed=false`). Playwright zero-block Stages **1–8 passed**. A prior soak recorded `NO-GO - SOAK UNSTABLE`; a clean 30-minute soak was restarted after stabilization. Human Beta review remains open. **Final verdict remains NO-GO until soak is stable, independent verifier returns VERIFIED, and human review is GO.**

## 2. Branch and HEAD

| Field | Value |
|-------|-------|
| Branch | feature/ai-guided-setup |
| Starting HEAD | fa09c99d6395c29461cdec4555055faad116c435 |

## 3–6. Timeout / blocker recovery

- Root cause repaired: flat 1.5s `wait_for` + duplicate Comfy/capability work → shared probe warm + per-check budgets + BUSY vs TIMED_OUT.
- Library persistence write probe live; timeout budget raised to **15s** after load-induced 6s partial timeouts.
- Capability active blockers: **0** (after `POST /api/capabilities/refresh` when Comfy healthy).
- SceneCraft remains `PLANNED_FUTURE_MODULE` / not in release.

## 7. Hunyuan product exclusion (user)

**2026-08-05/06 user direction:** Hunyuan will not be used in Adept UI — skip Hunyuan live certification.

| Workflow | Matrix verdict |
|----------|----------------|
| hunyuan15.t2v / hunyuan15.i2v | **EXCLUDED** |
| hunyuan13b.t2v / hunyuan13b.i2v | **EXCLUDED** |

- Frozen manifest annotated with `releaseExclusion` / `hunyuanReleaseExclusion`.
- HyVideo nodes may still be present in Comfy; they are not required for release catalog GO.
- `WORKFLOW_CATALOG_GREEN` is computed over non-`EXCLUDED` rows only.

## 8–18. Workflow matrix (active catalog)

Artifact: `artifacts/.../workflows/matrix.json`

| Workflow | Live artifact | Verdict |
|----------|---------------|---------|
| image.txt2img | API imagegen | GO |
| image.img2img_edit | Comfy PNG | GO |
| image.zimage_reference | Comfy PNG | GO |
| ltx.scene | Comfy MP4 | GO |
| ltx.simple_i2v | Comfy MP4 | GO |
| ltx.ingredients_ic_lora | Comfy MP4 | GO |
| lipsync.latentsync | `latentsync_nkbhn_out.mp4` (PreviewAny text path) | GO |
| wan.first_last_frame | Comfy MP4 | GO |
| wan.three_frame | Comfy MP4 | GO |
| hunyuan* (4) | — | **EXCLUDED** |

`WORKFLOW_CATALOG_GREEN = true` (active rows only)

### Lipsync harness fix

`ComfyClient.find_output_files` now accepts absolute paths returned under PreviewAny `text` outputs (LatentSync).

## MiniMax H3 33B (separate from builder registry)

| Field | Value |
|-------|-------|
| Readiness | ready (`cuda:0` RTX 5090, isolated `:8192`) |
| Plan | `ef6a0570-eda0-4abb-a471-e9d73c7c0757` |
| Job | `4fe776f6-3f0c-4a19-b713-14b343468a66` **completed** |
| Output | `...\Adept_H3_Private_4fe776f6_00001_.mp4` (22 187 bytes) |
| Library asset | `d07a0a00-c4b3-4094-b5b8-eb3f5caf6822` |
| Provenance | `ltxUsed=false`, `apiUsed=false`, `minimax-h3-route-a-local` |
| Evidence | `artifacts/.../minimax-h3/H3_CERT_SUMMARY.json` |

## 19–23. Deferred / UI / persistence

- Optional image cloud blockers remain optional (not required-release).
- SceneCraft excluded.
- Library write probe: pass (PA).
- H3 library import: pass for cert project `ae57714e-d43e-4cec-9bd9-0af2780fa185`.

## 24. Unit / integration

`studio-api/tests/test_codirector_status_cross_check.py` — **9 passed** (earlier in RUN).

## 25. Live Playwright

`tests/e2e/system/adept-ui-runtime-workflow-zero-block-cert.spec.ts` — **8 passed** (2026-08-06T02:22Z class).

Stage 7 aggregates (authoritative for dual-green file):

```json
{
  "SYSTEM_RUNTIME_GREEN": true,
  "WORKFLOW_CATALOG_GREEN": true,
  "FINAL_ACTIVE_BLOCKERS": 0,
  "FINAL_UNEXPLAINED_TIMEOUTS": 0,
  "statusIndicator": "Operational",
  "score": 100,
  "hunyuanExcluded": true
}
```

## 26. Independent verification

```text
BLOCKED
```

Reasons: post-stabilization soak not yet completed with `GO - POST-CERTIFICATION SOAK STABLE`; human Beta review pending; prior soak archived as unstable.

## 27. Human Beta review

Checklist: `HUMAN_BETA_REVIEW_CHECKLIST.md` — **pending product owner**.

Beta URLs (leave running):

- UI: http://127.0.0.1:8760/
- API: http://127.0.0.1:8758/
- Comfy: http://127.0.0.1:8188
- H3 Route A: http://127.0.0.1:8192

## 28. Remaining risks

- Intermittent PA `Degraded` / library partial timeouts under GPU+disk load — mitigated with 15s library budget; soak must prove stability.
- Imagegen may disclose `qwen2512` when zimage preferred — must remain disclosed (no silent MiniMax/Hunyuan substitution).
- Co-Director non-stream `/chat` can time out under heavy local LLM load; provider health + PA remain the Wave 4 evidence path.
- Prior soak `NO-GO - SOAK UNSTABLE` archived; clean soak in progress.

## 29. Final active blocker count

- Capability readiness active blockers: **0**
- PA blocked checks (project bound, healthy window): **0**
- Active workflow catalog rows not GO: **0 / 9**
- Hunyuan excluded: **4**
- Unexplained PA timeouts (Playwright Stage 7 window): **0**

## Aggregates

| Gate | Value |
|------|-------|
| SYSTEM_RUNTIME_GREEN | **true** (Stage 7 file) |
| WORKFLOW_CATALOG_GREEN | **true** (active rows; Hunyuan EXCLUDED) |
| POST_CERTIFICATION_SOAK | **in progress** (clean restart; prior = unstable) |
| INDEPENDENT_VERIFIER | **BLOCKED** |
| HUMAN_BETA_REVIEW | pending |
| FINAL_ACTIVE_BLOCKERS | **0** |
| FINAL_UNEXPLAINED_TIMEOUTS | **0** (Stage 7 window) |

## 30. Final verdict

```text
NO-GO — ADEPT UI RUNTIME OR SUPPORTED WORKFLOWS REMAIN DEGRADED, BLOCKED OR INCOMPLETE
```

Dual-green Stage 7 aggregates are true and Playwright is green, but final GO is refused until the clean soak reports stable, independent verification returns VERIFIED, and human Beta review is GO.
