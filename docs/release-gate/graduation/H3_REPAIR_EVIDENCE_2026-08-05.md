# H3 Route A T2VA Repair — Graduation RED → GREEN Evidence

> Durable repair record for the Adept UI Graduation RED blocker: MiniMax H3 private Route A T2VA failing on Windows + RTX 5090.
> The auto-generated `ADEPT_UI_DRAMATIC_SCENE_GRADUATION.md` is regenerated each run; this document is the persistent repair evidence.
> Date: 2026-08-04/05. Final verdict: **GREEN (GO)**.

## 1. Original blocker (RED)

- Run: `ADEPT-GRADUATION-COFFEE-2026-08-04T23-41-10-832Z`
- Symptom: Comfy `SamplerCustomAdvanced` → `OSError [Errno 22] Invalid argument` after ~60s.
- Route A log surfaced `ImportError: No module named 'triton'` (Linux-only) — suspected root.
- H3 readiness was otherwise green (`cuda:0` RTX 5090).
- Graduation verdict: **RED** because the final scene video could not be produced.

## 2. Root cause

`triton` was a **red herring**. ComfyUI logs showed `res_multistep` running successfully via `eager/cuda` backends on Windows; `triton` is Linux-only and not required by the H3 Route A sampler on this stack.

The real root cause was **multi-process resource contention** on the H3 Route A ComfyUI runtime (:8192):

- Multiple stale `python.exe` ComfyUI processes were bound to port 8192 simultaneously.
- SQLite DB lock contention — log: `Failed to initialize database. Could not acquire lock on database 'comfyui.db'. Another ComfyUI process may already be using it.`
- VRAM + `comfy-aimdo` host-buffer contention — log: `!!! Exception during processing !!! HostBuffer.read_file_slice failed`.
- The corrupted host-buffer access surfaced inside the model kernel run as `OSError [Errno 22] Invalid argument at SamplerCustomAdvanced` — a memory/IO symptom, not a sampler or triton defect.

A prior live full-stack E2E (`docs/release-gate/minimax-h3/H3_PRIVATE_OWNER_ADEPT_UI_SMOKE.md`) had already proven `SamplerCustomAdvanced` works on this same Windows/RTX 5090 stack with the same graph when the runtime is clean and singular.

## 3. H3 fix (no silent LTX, no mock, GPU-first Law 26)

| File | Change |
| --- | --- |
| `C:\AdeptFilmWorks\AIVideoStudio-h3\runtime\minimax-h3\scripts\start_isolated_comfy_route_a.ps1` | Enforce single instance: kill any stale H3 Route A python process on port 8192 before launch; launch with a dedicated SQLite DB URL (`--database-url sqlite:///.../route_a_single.db`) so concurrent processes can no longer corrupt the shared DB. |
| `C:\AdeptFilmWorks\AIVideoStudio\scripts\Start-AdeptUI-H3-RouteA.ps1` | New canonical operator entrypoint: idempotent single-instance launch, log rotation, waits for `/system_stats` + `/object_info` + Adept H3 readiness. |
| `C:\AdeptFilmWorks\AIVideoStudio\scripts\Stop-AdeptUI-H3-RouteA.ps1` | Canonical stop: kills all H3 Route A processes and confirms port 8192 is free. |

GPU preflight confirmed `cuda:0` (RTX 5090); H3 executes on GPU; no silent CPU fallback; provenance records `apiUsed: false`, `ltxUsed: false`, `nativeAudio: true`.

## 4. Focused H3 T2VA proof (Adept API path, not creator→:8192)

- Artifact directory: `docs/release-gate/graduation/artifacts/dramatic-scene/ADEPT-H3-REPAIR-20260804T165945Z`
- `4-job-final.json` — job `3556dd09-b664-496f-b723-89c52bd344cd`, status `completed`, real MP4 `Adept_H3_Private_3556dd09_00001_.mp4`, `videoCodec: h264`, `audioCodec: aac`, `audioNonSilent: true`, `decodePass: true`, library import `assetId b0bf13ff-809f-4335-b2f3-01538b69c952`.
- `6-verdict.json` — `{ "pass": true, "realH3T2VA": true }`.
- Provenance: `modelId: minimax-h3-route-a-local`, `runtime: route-a`, `runtimeUrlIdentity: isolated-comfyui-8192`, `workflowId: route-a-experimental-private-t2va`, `nativeAudio: true`, `apiUsed: false`, `ltxUsed: false`.

## 5. Voice automation hardening (secondary)

The graduation spec referenced testids/flow that did not match the production Voice Studio UI (spec vs UI drift). These were automation fixes, not assertion relaxations:

- `tests/e2e/graduation/adept-ui-dramatic-scene-graduation.spec.ts`:
  - `voice-slider-tone` → `voice-slider-warmth` (the `tone` slider never existed; production sliders are `pitch/energy/warmth/playfulness/confidence/speakingSpeed`).
  - Removed stale `voice-design-preview` / `voice-design-preview-body` steps (preview consolidated into `voice-design-generate`).
  - Fixed candidate-player order: `voice-candidate-player` only renders AFTER "Select for Testing".
  - Fixed approve step: identity-approval is the selected card's "Approve Voice Identity" button (targeted by accessible name), since `voice-approve-candidate` only exists in the `phase === "approve"` section.
  - Hardened the Fine Tune `<details>` open-toggle (native `open` attribute, not `aria-expanded`).
- `tests/e2e/m42/m42-voice-voice-performance-smoke.spec.ts` — same `voice-slider-tone` → `voice-slider-warmth` fix. (Deeper m42 preview/candidate-player flow left for a separate m42 pass; out of scope for the graduation critical path.)

## 6. Co-Director conversation persistence fix (Phase 17 reload)

Phase 15–18 intermittently failed with `conversation messages >= 3, received 2`. Root cause: a frontend race in `studio-web/src/components/CoDirector/CoDirectorSession.tsx` — the send handler persisted `[...messages, userMsg]` using the React `messages` closure, which was still `[WELCOME_ASSISTANT]` if the send landed before the async conversation load completed, overwriting the real 5-message server conversation with a 2-message stub (data loss).

Fix:
- Added `conversationHydratedRef` tracking hydration state for the current project.
- `persistConversation` now merges incoming messages onto the latest server conversation (by id) when not yet hydrated, so a stale stub can never overwrite real history.
- The load effect now skips `setMessages(loaded)` when hydration already occurred (prevents the stale server snapshot fetched before the merge from reverting the merged state).

## 7. Graduation re-run history

| Run | Verdict | H3 | Voice | Phase 15-18 |
| --- | --- | --- | --- | --- |
| `2026-08-04T23-41-10-832Z` | RED | FAIL (EINVAL) | blocked | — |
| rerun2 | CONDITIONAL | PASS | blocked (slider `tone`) | PASS |
| rerun3 | — (failed P15-18) | PASS | PASS | FAIL (convo=2) |
| rerun4 | CONDITIONAL | PASS | blocked (preview testid) | PASS |
| rerun5 | CONDITIONAL | PASS | blocked (candidate-player order) | PASS |
| rerun6 | CONDITIONAL | PASS | blocked (approve button) | PASS |
| rerun7 | — (failed P15-18 flaky) | PASS | PASS | FAIL (convo=2) |
| **`2026-08-05T01-55-48-280Z`** | **GREEN** | **PASS** | **daniel+maya approved** | **PASS** |

Final GREEN run: 13/13 passed, no retries, 12.3m.

## 8. Final GREEN evidence

- Verdict artifact: `docs/release-gate/graduation/artifacts/dramatic-scene/ADEPT-GRADUATION-COFFEE-2026-08-05T01-55-48-280Z/22-verdict.json` → `verdict: GREEN`, `blockers: []`.
- H3: `11-h3-job-final.json` → job `69d458f7…` completed, real MP4, `nativeAudio: true`, `ltxUsed: false`, `apiUsed: false`, library import `assetId fe04cc8b…`.
- Voice: `10-voice-results.json` → daniel approved (`e6bd122e…`), maya approved (`75c6852c…`).
- Reload persistence + isolation: `17-reload-persistence.json`, `18-isolation.json` PASS.
- Protected project `77a4b96c-8e3f-4501-897c-51bab99bedb7` never mutated.

## 9. Beta verification

- Beta: http://127.0.0.1:8760/ (web) — 200
- API: http://127.0.0.1:8758/api/health — 200
- H3 Route A: http://127.0.0.1:8192/system_stats — 200; readiness http://127.0.0.1:8758/api/minimax-h3/readiness — 200
- Beta left running and ready for manual review.

## 10. Verdict

**GO** (GREEN). The original H3 RED blocker is fully repaired and proven; the full two-character dramatic scene graduation is GREEN.
