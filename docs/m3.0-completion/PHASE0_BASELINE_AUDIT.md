# M3.0 Completion — Phase 0 Baseline Audit

| Field | Value |
|-------|-------|
| Date | 2026-07-26 |
| Branch | `phase2/codirector-m2-9-production-suite` |
| `git rev-parse HEAD` | `e2f3ae8a9750d44ec37b64361cbede6a95351d3c` |
| Working tree | **Dirty** — large uncommitted M2.9–M3.0b / M3.0a working tree on top of tip (source, tests, docs, scripts, artifacts). No commit made in this phase. |
| Provider Manifest sha256 | `cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc` (39,547 bytes) — **UNCHANGED** (`cf99d7e5…`) |
| Plan file | Not edited |

---

## 1. High-level changed areas

Inventory is by area, not every path. Tip remains `e2f3ae8a9750d44ec37b64361cbede6a95351d3c`; changes below are uncommitted working-tree deltas and untracked milestone docs/artifacts.

| Area | What is present in the dirty tree |
|------|-----------------------------------|
| **m29** | Production suite API/services (image, video, audio, editing), providers helpers, honesty fixes for generate responses (B1), mix-revise ops contract (B3), related tests |
| **m213** | Virtual environment studio API, camera spin, concepts, flags, persistence, reconstruction, UI/e2e wiring patches |
| **m214** | Unified experience API/contracts/DB, attachments, conflicts, idea-first, media, meetings, messaging, sound producer, storyteller, honesty helpers; ProviderHealth flag serialization (B2) |
| **fal** | `fal_client.py`, `fal_catalog.py` (incl. Seedance T2V fallback), credential routes/tests, budgeted live-proof script, `docs/m3.0a` fal matrices |
| **queue recovery** | `JobQueue.recover_interrupted()` in `queue_worker.py`, lifespan hook in `main.py`, `tests/test_job_queue_recovery.py` (R1 closed in M3.0b docs) |
| **docs/m3.0a** | Full M3.0a audit pack (Playwright, fal, Co-Director coverage, wiring matrix, native inventory, mock/scaffold audit) |
| **docs/m3.0b** | Situation beta plan/matrix, Playwright/Co-Director findings, `FINAL_BETA_BLOCKERS.md` |
| **artifacts/m30a-fal** | Live Seedance T2V proof MP4 + `live_proof_summary.json` (script-level C2) |

Also present but out of Phase 0 scope detail: m28 capability patches, vision/provider health, e2e harness (`playwright.config.ts`, `scripts/e2e-start.mjs`), many `_emit_*` / `_patch_*` helper scripts, functional-audit traces under `artifacts/functional-audit/`.

**Staging forever exclude:** `.env`, secrets, media binaries, Playwright traces/videos, local DBs — do not stage in later phases.

---

## 2. fal.ai

| Check | Result |
|-------|--------|
| `.env` key | `FAL_API_KEY` **present** (redacted: `99cc…16e6`, length 69). Value never logged or committed. |
| Script-level C2 | **VERIFIED** — `scripts/m30a_fal_budgeted_live_proof.py` |
| `request_id` | `019fa1fc-e05f-7d80-9908-e6d0c3e8d4fc` |
| Artifact | `artifacts/m30a-fal/seedance_t2v_4s_480p.mp4` **exists** (667,974 bytes) |
| Endpoint proven | `bytedance/seedance-2.0/text-to-video` via Seedance T2V fallback (not I2V) |
| API secrets bridge | **Still missing** — queue/API paths read encrypted `fal_api_key` via `secrets_store`; `config.py` does not bind `FAL_*` from `.env` into that store on startup. Script proof loaded `.env` directly; production API path remains unbridged. |

Do **not** resubmit a paid fal job unless Asset/queue/browser proof cannot reuse the existing MP4 (hard session cap $5; one submit already spent).

---

## 3. ComfyUI (probe only — no downloads)

| Check | Result |
|-------|--------|
| Endpoint | `http://127.0.0.1:8188` |
| TCP / HTTP | **Reachable** — `/system_stats` OK (ComfyUI `0.28.2`, win32) |
| CheckpointLoaderSimple `ckpt_name` | `ltx-2.3-22b-dev-fp8.safetensors`, `ltx-2.3-22b-distilled-fp8.safetensors`, `ltx-video-2b-v0.9.5.safetensors` (3) |
| UNETLoader `unet_name` | Present (7), including Wan 2.2 I2V/T2V weights, LTX transformer-only, AceStep, and **`z_image_turbo_bf16.safetensors`** |

No model downloads were performed. Local proof in later phases must use already-installed paths (Z-Image ImageGen if wired; otherwise LTX/Wan video already on disk).

---

## 4. Blocker status (from `docs/m3.0b/FINAL_BETA_BLOCKERS.md`)

| ID | Severity | Status at Phase 0 |
|----|----------|-------------------|
| **B4** | BLOCKER (sound path) | **OPEN** — generated audio cues stay `assetId: null` / draft; never reach `director_json` without a separate place-cue that requires an asset id |
| **B10** | MAJOR | **OPEN** — Bible-apply approval path still failing in Playwright (`production-bible*`); mock field-name root cause to re-verify in Phase 2 |
| **B5** | BLOCKER | **OPEN** — no generative provider path proven end-to-end through API Asset/queue for beta (local engines installed but not yet Adept-path proven; fal key on disk but secrets bridge missing) |
| **B6** | MAJOR | **PARTIALLY MITIGATED** — Seedance **T2V** fallback live-verified at script level; I2V engines still need a start image; `FAL_IMAGE_MODELS` still empty; API bridge still missing |
| **B7** | MAJOR | **OPEN** — orchestration still runs specialists with `use_provider=False` / heuristic path; emotional profile constant across briefs |

**Already fixed in working tree (not this phase):** B1 (phantom asset ids), B2 (unified-experience flag serialization), B3 (mix revise ops). Gate verdict remains **NOT READY FOR MANUAL USER BETA** until B4/B10 and real-media proofs close.

---

## 5. Playwright — prior 5 fails + skips (`docs/m3.0a/PLAYWRIGHT_RESULTS.md`)

Headline of that run: 89 passed, **6 failed**, 9 skipped (104 tests). One failure (`tools.spec.ts` catalog allowlist) was fixed in M3.0a. **Five remain** (pre-existing / not caused by M3.0a):

| Spec | Failure summary |
|------|-----------------|
| `intelligence-storyboard.spec.ts:47` | Honesty caveat text matches naive "render completed" guard |
| `production-bible.spec.ts:90` | Approve proposal → Bible apply fails (no Version 2) |
| `production-bible-m23.spec.ts:29` | Same Bible-apply / FK or validation defect from character lifecycle angle |
| `streaming-cancel.spec.ts:40` | Expects `[mock]` prefix; E2E scenario provider reply has none |
| `vision-storyboard-validation.spec.ts:9` | Strict-mode: multiple `Co-Director` buttons |

**Skips (9)** — all stated reasons:

| Spec | Skips | Reason |
|------|------:|--------|
| `production-suite-m29.spec.ts` | 3 | `codirector_production_suite_v1` off by default |
| `production-executive-m27.spec.ts` | 2 | One flag-off, one restart-recovery stub |
| `m214-unified-experience.spec.ts` | 2 | `codirector_unified_experience_v1` off by default |
| `capability-intelligence-m28.spec.ts` | 1 | Flag-gated case |
| `m30a-fal-ai-provider.spec.ts` | 1 | `ADEPT_M30A_FAL_LIVE` unset |

---

## 6. Manifest hash

Provider Manifest path: `config/capabilities/adept-ui-v1.0-provider-manifest.json`

```
sha256: cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc
size:   39547 bytes
```

Matches the frozen prefix **`cf99d7e5…`**. Phase 0 did not modify the manifest. Later completion phases must keep it unchanged.

---

## 7. Phase 0 outputs

| Path | Purpose |
|------|---------|
| `docs/m3.0-completion/PHASE0_BASELINE_AUDIT.md` | This baseline |
| `docs/m3.0-completion/REMEDIATION_PLAN.md` | Ordered phases 1–13 |

No commit. No plan-file edits.
