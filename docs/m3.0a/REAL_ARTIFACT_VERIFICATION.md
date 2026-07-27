# M3.0a Phase 3 - Real Artifact Verification

| Field | Value |
|-------|-------|
| Tip SHA | `e2f3ae8a9750d44ec37b64361cbede6a95351d3c` |
| Date | 2026-07-26 |
| Question | Which artifacts in this system have actually been produced by a real provider, and which have only ever been produced by a fixture? |
| Short answer | **No generative artifact was produced during M3.0a - not locally and not on fal.** Non-generative artifacts (database rows, director-timeline mutations, reference sets, scripts) are verified. |

---

## 1. What "verified" means here

| Code | Meaning |
|------|---------|
| VERIFIED | An artifact of this kind was produced during M3.0a, or is produced by an automated test that runs on the non-fixture path. |
| FIXTURE_ONLY | The only artifacts of this kind that exist were produced by an env-gated fixture. |
| NOT_RUN | No attempt was made in M3.0a. The path exists and fails closed. |
| REFUSED | The path deliberately refuses to produce an artifact outside a fixture run, as of Phase 1 / Phase 3 remediation. |

A FIXTURE_ONLY or REFUSED row is not a bug. It is the correct behaviour for a provider that
is not wired, and it is the whole point of the Phase 0 audit. What would be a bug - and what
Phase 1 and Phase 3 removed - is a fixture artifact reported as a real one.

---

## 2. Environment at the time of this report

| Fact | Value | How it was established |
|------|-------|------------------------|
| ComfyUI | Reachable at `http://127.0.0.1:8188` (HTTP 200 from `/system_stats`) | Direct probe |
| ComfyUI driven by Adept during M3.0a | No | No imagegen, render or lipsync job was submitted |
| fal.ai key in the environment | Not set (`FAL_KEY` and `ADEPT_M30A_FAL_KEY` both unset) | Direct probe |
| `ADEPT_M30A_FAL_LIVE` | Unset | Direct probe |
| Playwright stack | Fixture stack via `scripts/e2e-start.mjs` (`STUDIO_E2E=1`, M2.8/M2.9 fixture modes on, mock Co-Director provider) | `scripts/e2e-start.mjs` |

The important line is the second one. A reachable ComfyUI means a local artifact proof is
*possible* on this machine; it is not evidence that one happened. It did not.

---

## 3. Local (ComfyUI / ffmpeg / on-disk) artifacts

| Artifact | Producer | Status | Evidence |
|----------|----------|--------|----------|
| Generated still image | `queue_worker._imagegen` via ComfyUI | NOT_RUN | Path refuses without Comfy; `imagegen_adapter.poll_imagegen_job(allow_mock=False)` raises rather than fabricating |
| Character sheet / multi-angle | `queue_worker._image_tool` | NOT_RUN | |
| Scene render (video) | `queue_worker._build_and_run_scene` | NOT_RUN | |
| Timeline render | `queue_worker._render_timeline` | NOT_RUN | |
| Lipsync output | `queue_worker._lipsync` / `_dual_lipsync` | NOT_RUN | |
| Txt2Vid output | `queue_worker._txt2vid` | NOT_RUN | |
| Project / pack export | `queue_worker._export` | NOT_RUN | |
| Processed audio (loudnorm) | `m29/providers.py::process_audio_ffmpeg` | NOT_RUN | Real ffmpeg path, refuses without ffmpeg on PATH |
| Kokoro TTS WAV | `m210b/adapters/kokoro.py` | NOT_RUN | Refuses when Kokoro is not installed |
| Deterministic CI WAV | `m210b/adapters/fixture_ci.py` | FIXTURE_ONLY | Env-gated; never claims production readiness |
| Mouth-tracking keyframes | `m29/providers.py::run_mouth_track` (MediaPipe) | NOT_RUN | Requires an existing video asset |

## 4. Non-generative artifacts (verified)

These are real artifacts in the sense that matters for the wiring matrix: they are produced by
the production code path, persisted, and covered by a test that does not run in fixture mode.

| Artifact | Producer | Status | Evidence |
|----------|----------|--------|----------|
| Director timeline mutation (trim / insert / ripple / undo / redo) | `m29/editing/service.py::execute_job` | VERIFIED | `tests/test_m29_production_suite.py::test_edit_apply_trim_and_undo` deletes `ADEPT_M29_FIXTURE_MODE` before running |
| Project / scene / asset rows | `routers/api.py` | VERIFIED | `tests/e2e/projects/project-crud.spec.ts` |
| Reference sets and timeline bindings | `references/api.py` | VERIFIED | `tests/e2e/projects/references.spec.ts`, `tests/e2e/director/timeline-references.spec.ts` |
| Production Bible versions, canon records, proposals | `codirector/bible/*` | VERIFIED | `tests/e2e/codirector/production-bible*.spec.ts` |
| Script segments and panels | Script/storyboard API | VERIFIED | Covered by workspace CRUD tests |
| M2.13 environment records, blocking, scene state, approvals | `m213/*` | VERIFIED (records) / FIXTURE_ONLY (their content) | `tests/test_m213_virtual_environment_studio.py` - the rows and approval history are real, the environments they describe are fixtures |
| Encrypted fal credential + verification record | `secrets_store.py` | VERIFIED | `tests/test_fal_credentials.py` |

## 5. fal.ai artifacts

| Artifact | Status | Note |
|----------|--------|------|
| fal video render (Seedance / Kling / Veo / Runway) | NOT_RUN | Gated on `ADEPT_M30A_FAL_LIVE=1` plus a real key; neither is present |
| fal image render | N/A | `FAL_IMAGE_MODELS` is empty - there is no fal image endpoint in this repository to run |
| fal queue `request_id` on a real job | NOT_RUN | The persistence path is unit-tested (`tests/test_fal_credentials.py::test_queue_worker_records_the_fal_request_id`) but has never seen a real fal request id |
| fal credential accepted by fal | NOT_RUN | The rejection path is verified; the acceptance path is not |
| fal usage / billing read | NOT_RUN | Requires an admin-scoped key |

Detail in `FAL_AI_REAL_JOB_RESULTS.md`.

## 6. Artifacts that are now refused rather than faked

Phase 1 and Phase 3 turned five fabricated artifacts into honest refusals. Each row is an
artifact that used to exist on the production path and no longer does.

| Former artifact | Now | Remediation |
|-----------------|-----|-------------|
| `installed.fixture` marker reported as an installed model | REFUSED outside `ADEPT_M28_FIXTURE_MODE` / `STUDIO_E2E` | M28-03 (Phase 1) |
| `runtime: fixture-sandbox` reported as a validated sandbox | REFUSED | M28-04 (Phase 1) |
| `fixture-spin-*` frames reported as location coverage | REFUSED | M28-06 (Phase 3) |
| `fixture-asset-*` reported as a completed recipe stage | REFUSED, executive reports Blocked | M28-08 / EXEC-04 (Phase 3) |
| `fixture-spin-*` frames reported as a camera-spin environment | REFUSED | M213-04 (Phase 3) |
| `m29_fixture` edit proposal returned outside fixture mode | Replaced by an honest echo of the caller's own ops | M29-08 (Phase 3) |

## 7. What is still needed for a real artifact proof

Neither of these is difficult; both are simply out of scope for an audit milestone.

**Local:** a project with a checkpoint installed, one `POST /api/projects/{id}/imagegen`, and
the resulting `Asset` row plus file on disk. ComfyUI is already reachable on this machine, so
the only missing piece is a model and a deliberate run.

**fal:** a real key, `ADEPT_M30A_FAL_LIVE=1`, and one image-to-video job against
`fal_seedance` or `fal_kling`. This spends credits, which is why it is gated.

Until both exist, M3.0a cannot claim a green generative path, and this report does not.
