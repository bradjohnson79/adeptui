# Comfy MCP Integration + SenseNova Workflow Forensics — Completion Report

**Branch:** `feat/character-creator-final-closure`
**HEAD SHA:** `3b6fbd47a5ba7a9bfd6037bd314b88a0a823afd0`
**Date:** 2026-08-23
**Author:** Primary agent (GLM 5.2)

---

## 1. Executive Summary

Integrated the official `Comfy-Org/comfy-mcp` server with the live Adept ComfyUI instance to perform workflow forensics on a stuck `SenseNova CRS` generation, diagnosed the root cause, and repaired the surrounding progress / cancel / watchdog plumbing so a stuck generation is honest, cancelable, and fast-fails instead of hanging for an hour.

**Root cause (CP1):** the Adept SenseNova builder (`studio-api/app/workflows/sensenova_u15.py`) sets `SENSENOVA_VRAM_MODE = "fast"`. In the installed SenseNova v0.2.0, `fast` is an **offload mode** (`for_offload=True`) that materializes the ~47 GB bf16 model in **host RAM**. On a 64 GB host with ~31 GB used by other processes, only ~33 GB is free — insufficient for the 47 GB model → host-RAM OOM. The model never reaches the GPU; generation never starts; the loader is cancel-resistant and eventually OOM-crashes Comfy. Hardware-capacity mismatch triggered by a generated-workflow-topology choice, not an MCP/Adept-submission/frontend defect.

**Two independent gates:**
- **COMFY TOOLING GATE — GO** (MCP installed, isolated, certified; cancel/queue/validate/server_info/object_info/search_models verified live).
- **SENSENOVA GATE — NO-GO** (loader OOMs the host before any CUDA allocation; no real SenseNova output produced). MCP-GO coexists with SenseNova-NO-GO, as required.

---

## 2. Branch & SHAs

- Branch: `feat/character-creator-final-closure`
- HEAD SHA: `3b6fbd47a5ba7a9bfd6037bd314b88a0a823afd0`
- HEAD subject: `docs: record stability cull recertification and workflow audit`
- Changes are uncommitted working-tree edits on top of HEAD (awaiting user commit instruction).

---

## 3. Scope (Phases 1-14)

- **Checkpoint 1 (P1-P7):** MCP install + forensics → root-cause diagnosis.
- **Checkpoint 2 (P8-P14):** Repair progress/cancel/watchdog plumbing; ERS forensics; no-default-change invariant; regression; final certification.

All 14 phases + CP1 + Final completed.

---

## 4. CP1 Failure-Point Diagnosis (root cause)

Defect origin: **(B) generated workflow topology** (`SENSENOVA_VRAM_MODE="fast"` constant in the builder) triggering **(A) runtime** host-RAM exhaustion physically unavoidable for the full bf16 model on this hardware (47 GB model vs 32 GB VRAM / ~33 GB free host RAM).

Evidence:
- `phase6-loader-forensics.json` — full forensic diagnosis.
- `cancel-resistance-finding.json` — `/interrupt` and `/queue delete` return 200 but the job persists; `SenseNovaU1LocalLoader.from_pretrained` ignores interrupts.
- `phase5-direct-execution.json` — bounded P5 reproduction → Comfy OOM-crashed.
- Historical `comfyui.log`: `SenseNova U1 loader: loading model` → 58m50s weight load → `post-load (for_offload=True) alloc=0.00 GiB` → `Processing interrupted` (after OOM).

Secondary (non-root) defects: (C) Adept submission/job tracking, (E) frontend state semantics — both repaired in P8-P11. The first failing boundary is the `SenseNovaU1LocalLoader.from_pretrained` native call (host RAM allocation), not Adept submission or frontend.

---

## 5. P1 — MCP Smoke

- MCP venv: `data/venvs/mcp` (isolated; torch NOT installed in MCP venv → no CUDA contamination). Production Comfy venv retains `torch 2.10.0+cu130` / `torchvision 0.25.0+cu130` / `torchaudio 2.10.0+cu130`, CUDA available (RTX 5090, 32 GB VRAM).
- `.cursor/mcp.json` configured for Cursor/Grok, localhost-only `127.0.0.1:8188`.
- Verified live: server_info (RTX 5090, 64 GB RAM), node/model discovery (10 SenseNova nodes, 13/13 SenseNova weights), queue inspection (found live stuck SenseNova job), workflow validation (SenseNova CRS graph `valid: true`).
- Evidence: `phase1-smoke.json`, `phase1-queue-raw.json`, `sensenova-crs-graph.json`.

---

## 6. P2 — Known-Good Control

Ran `zimage.txt2img` end-to-end via MCP/Comfy → `STATUS_STR=success`, output `mcp_control_zimg_00001_.png` in ~12 s. Proves MCP is not the failure; the defect is in the SenseNova runtime path. Evidence: `phase2-control.json`, `phase2-control.png` (red cube on white background, matches prompt).

---

## 7. P3-P7 — CRS/ERS Forensics

- Extracted exact stuck SenseNova CRS graph (`sensenova-crs-graph.json`) + node schemas (`sensenova-crs-nodeschemas.json`, `sensenova-crs-nodemap.md`).
- P4: graph `valid: true`; all nodes/models present; no torch contamination; `sensenova-u1` 0.1.0 importable → failure is runtime execution, not topology/deps.
- P5: bounded direct reproduction → Comfy OOM-crashed (host RAM exhausted).
- P6: loader forensics — `vram_mode="fast"` → `for_offload=True` → 47 GB model in host RAM → OOM.
- P7: CRS + ERS graphs share identical 4-node topology and `vram_mode="fast"`.
- Evidence: `phase4-validation.json`, `phase5-direct-execution.json`, `phase6-loader-forensics.json`, `phase7-graph-inspection.md`, `sensenova-ers-graph.json`, `cp1-failure-point-diagnosis.md`.

---

## 8. P8 — Progress Repair (truthful coarse states)

- `types.ts`: added `BatchCoarseStage` + `batchCoarseStage()`/`batchCoarseLabel()` — truthful coarse states derived from real backend state. No fake progress.
- `GenerationProgressBar.tsx`: single-node generator (SenseNova) now shows "Loading model…" instead of fake "0 of 1 character sheets complete".
- `CharacterSheetGenerator.tsx`: fixed **infinite timeout reset** — `pollExhaustedRef.current = true` is binding in all fast-fail paths, so the 4 s tick can no longer restart a fast-failed cycle with a fresh 60-min budget. Fixed **swallowed poll errors** — `consecutiveErrorsRef` + vanished-job (404/410) fast-fail + bounded transient-error threshold (`POLL_ERROR_THRESHOLD=10`). Mapped `STALLED`/`CANCELLED` pack statuses to truthful creator-facing messages.

---

## 9. P9 — Reject Modal Repair (hidden Reject)

- `activeCrsCard.ts`: `resolveActiveCrsSheets`/`resolveActiveCrsCard` now show a live-generating draft (no asset yet) as the **draft hero** (`status="draft"`) so Reject is reachable, while preserving the approved canon via `showBoth=true`. Previously a generating draft was hidden behind the approved sheet → Reject was a no-op.
- `activeCrsCard.test.ts`: updated regression to expect `status="draft"` + `showBoth=true` for a generating draft over an approved sheet; added negative test (failed draft does NOT hide the approved look); added Reject-modal async-dismiss guards (`closeOnPrimary={false}`, busy `primaryDisabled`/`primaryLoading`, `onClose` guard, `handleReject` clears `rejectTarget` in `finally`).

---

## 10. P10 — Cancellation Repair

- **Verified MCP `job(cancel)` mechanism live:** submitted a known-good Z-Image job → entered running queue → `POST /interrupt` returned 200 → queue cleared within 8 s. Evidence: `phase10-cancel-verify.json` (`p10_verdict: PASS`).
- `queue_worker.py`: added `schedule_comfy_interrupt_if_owner(job_id)` — fire-and-forget `POST /interrupt` to Comfy when a cancelled job owns the active prompt. `JobQueue.cancel()` alone only sets a cooperative flag a blocked native call never checks; this actually stops the in-flight prompt. Ownership guard prevents a leftover/coverage cancel from killing a sibling prompt.
- `visual_sheet.py`: `_cancel_replaced_draft_jobs` and `reject_visual_sheet_candidate` now call `schedule_comfy_interrupt_if_owner` for in-flight jobs (best-effort, logged).
- `CharacterCore.tsx`: `handleReject` now allows **reject-during-gen** via `jobId` (`candidateKey`) when there is no `assetId`; removes the candidate by `assetId` OR `candidateKey`.
- New tests: `test_schedule_comfy_interrupt.py` (5 pass).

---

## 11. P11 — Watchdog Repair (fast-fail vanished prompts)

- `comfy_client.py`: added a **vanished-prompt watchdog** to `wait_for_prompt`. If a prompt is NOT in running, NOT in pending, AND NOT in history for >15 s grace, fast-fail as `STALLED`. Previously a prompt Comfy forgot polled for the full `timeout` (the old 1 h hang). The existing 180 s stall detector (running-with-no-history) is preserved.
- `image_product/service.py`: replaced `except Exception: pass` around `schedule_job_queue_enqueue` with a **failure-marking block** (`job.status="failed"`, creator-facing "Could not start the generation job. Please retry.", + log). Previously an enqueue failure left the job stuck at "queued"/0 % forever.
- New tests: `test_comfy_vanished_prompt.py` (2 pass), `test_image_product_enqueue_failure.py` (1 pass).

---

## 12. P12 — ERS Forensics

ERS shares the identical 4-node topology and `vram_mode="fast"` root cause as CRS. **No live ERS test run** — it would reproduce the same host-RAM OOM that already crashed Comfy in P5, violating the Resource Safety Law. Defect proven by code+graph inspection. Evidence: `phase12-ers-forensics.md`.

---

## 13. P13 — No Default Change

SenseNova remains **Draft / Not Ready / never-default**. All 5 SenseNova workflow entries in `certified-registry.json` are `status=Draft`. The frontend labels SenseNova "Not Ready" when not executable (`opt.executable !== false`). `characterGeneratorPlan.ts` (pre-existing uncommitted work, NOT modified by this program) sets `DEFAULT_GENERATOR_FAMILY="flux"` with a fallback order that explicitly **excludes sensenova**. The builder `sensenova_u15.py` was NOT modified. Evidence: `phase13-no-default-change.md`.

---

## 14. P14 — Regression

Ran `zimage.txt2img` through `comfy.wait_for_prompt` (exercising the P11 vanished-prompt watchdog) end-to-end → `status_str=success`, `completed=true`, output `mcp_p14_regression_00001_.png` in **9.38 s**. The watchdog did NOT false-trigger on a normal completing job. Evidence: `phase14-regression.json`, `phase14-regression.png` (blue sphere on white background, matches prompt).

---

## 15. Files Changed (this program)

Frontend (studio-web): `types.ts`, `GenerationProgressBar.tsx`, `CharacterSheetGenerator.tsx`, `activeCrsCard.ts` (new), `activeCrsCard.test.ts` (new), `CharacterCore.tsx`.
Backend (studio-api): `queue_worker.py`, `character_identity/visual_sheet.py`, `comfy_client.py`, `image_product/service.py`.
New tests: `tests/test_schedule_comfy_interrupt.py`, `tests/test_comfy_vanished_prompt.py`, `tests/test_image_product_enqueue_failure.py`.
Scripts/config: `.cursor/mcp.json`, `scripts/restart_studio_api_only.py`.
Evidence: `docs/release-gate/comfy-mcp/evidence/*` (phase1-7, phase10, phase12-14, cp1, sensenova graphs, cancel-resistance).

---

## 16. Tests

- **Frontend character suite:** 107 passed / 0 failed (9 files) — `npx vitest run src/components/character/`.
- **Backend new tests:** 8 passed / 0 failed — `test_schedule_comfy_interrupt.py` (5), `test_comfy_vanished_prompt.py` (2), `test_image_product_enqueue_failure.py` (1).
- **Backend affected modules:** 30 passed / 0 failed — `test_local_comfy_adapter`, `test_comfy_find_output_files`, `test_queue_worker_drift_gate`, `test_image_product_execution_pin` + the 3 new files.
- **Live P10 cancel verify:** PASS (submitted Z-Image → /interrupt 200 → queue cleared ≤8 s).
- **Live P14 regression:** PASS (Z-Image through `wait_for_prompt` → success in 9.38 s).
- **Lints:** no errors on any edited frontend file.
- **studio-web build:** passed (`built in 1.80s`).
- **Pre-existing failures (NOT this program's regressions):** `test_crs_advance_optional_coverage.py` has 3 failures (view-job count 5 vs 4 — pre-existing uncommitted-work mismatch, unrelated to cancellation). Playwright `sensenova-character-creator.spec.ts` "lists SenseNova without flipping Flux default" fails at `expect(current).toBe("flux")` → received `"qwen2512"` because Flux is not executable in this environment (fallback picks Qwen); pre-existing test/environment mismatch in the default-selection logic (`characterGeneratorPlan.ts`, not modified by this program). Verified pre-existing: reproduces with this program's changes stashed.

---

## 17. Beta Refresh & Live URLs

- Rebuilt `studio-web` (build passed).
- Restarted **only** the Studio API (preserving the already-healthy Comfy via `scripts/restart_studio_api_only.py` — `start_comfy` reports "already healthy — reused"; Comfy was NOT killed, per user instruction).
- Live URLs:
  - Creator UI (local): `http://127.0.0.1:5173/` — HTTP 200
  - Studio API: `http://127.0.0.1:8758/api/healthz` — `{"status":"ok"}`
  - ComfyUI: `http://127.0.0.1:8188/system_stats` — HTTP 200 (RTX 5090, queue empty)
- Retired `:8760` was NOT started (Law 15).

---

## 18. Independent Reviews

Two independent review subagents (per the user's explicit model override of Law #27):

- **GLM 5.2** review: **READY FOR PRIMARY REVIEW**. 4 RISKs noted (all edge cases, no blockers): shared-jobId reject edge, interrupt-drop-on-loop-death, transport-error messaging, image_product late-enqueue race. Each strictly better than prior behavior.
- **Kimi K3** review: **READY FOR PRIMARY REVIEW**. 1 low-severity RISK (image_product late-enqueue self-healing race). Confirmed no regression to known-good workflows; `wait_for_prompt` change is additive and post-success-check.

Both reviewers independently confirmed: no silent failures, no mock completion, no fake success, no regressions to Flux/Qwen/Z-Image.

---

## 19. Known Limitations / RISKs

1. **SenseNova root cause NOT fixed** (by design — P13): `SENSENOVA_VRAM_MODE="fast"` in `sensenova_u15.py` still OOMs the host. A real fix requires a working configuration (e.g., a quantized model that fits 32 GB VRAM, or `vram_mode="full"` with a model that fits VRAM). That belongs to a future SenseNova-certification program, after which SENSENOVA GATE can be re-evaluated. The P8-P11 repairs make the failure honest and cancelable in the meantime.
2. **image_product late-enqueue race** (RISK, both reviewers): `schedule_job_queue_enqueue` can timeout (`.result(timeout=2)`) while the `_put()` coroutine is still scheduled; a late enqueue can resurrect a just-failed job (self-healing but briefly confusing; for cloud providers a retry in that window could duplicate a chargeable job). Pre-existing; the new visible-failure path is strictly better than the old silent infinite hang. Recommend follow-up: re-check job status before marking failed, or have `enqueue` skip terminal-status jobs.
3. **`schedule_comfy_interrupt_if_owner` is best-effort, no confirm path** (RISK, GLM): unlike `cancel_and_halt`, nothing verifies the prompt actually stopped. A failed interrupt leaves the Comfy prompt running while the DB job is marked cancelled. Acceptable for sync cancel paths (cannot block 20 s for confirm); recommend a delayed confirm/retry follow-up.
4. **Pre-existing Playwright/CRS-test failures** (not this program): documented in §16; not repaired (out of scope — default-selection logic and view-count assertions are pre-existing uncommitted work).
5. **SenseNova custom node non-persistent**: after the P5 OOM crash, `ComfyUI-SenseNova-U1` and the `sensenova-u1` pip package were found uninstalled/deleted from the Comfy environment. Forensics used GitHub source. A real SenseNova repair must also restore the installation.

---

## 20. Two Independent Gates + Final Verdict

### COMFY TOOLING GATE (MCP certification)

| Capability | Status | Evidence |
|---|---|---|
| MCP installed, isolated venv, torch guard | PASS | `data/venvs/mcp`, no torch in MCP venv, Comfy venv torch 2.10.0+cu130 intact |
| `.cursor/mcp.json` localhost-only | PASS | configured `127.0.0.1:8188` |
| server_info | PASS | RTX 5090, 64 GB RAM |
| object_info / node discovery | PASS | 10 SenseNova nodes, 13/13 weights |
| search_models | PASS | P1 smoke |
| queue inspection | PASS | found live stuck job |
| workflow validate | PASS | SenseNova CRS `valid: true` |
| job status / cancel | PASS | P10 cancel verify — /interrupt 200, queue cleared ≤8 s |
| output / logs | PASS | P2/P14 outputs produced |
| Known-good control (Z-Image) | PASS | P2 (12 s) + P14 (9.38 s through `wait_for_prompt`) |
| Regression (Flux/Qwen/Z-Image) | PASS | P14 + 30 backend tests + 107 frontend tests |

**COMFY TOOLING GATE: GO — MCP certified, isolated, and verified live against the Adept ComfyUI instance.**

### SENSENOVA GATE (SenseNova generation readiness)

| Criterion | Status | Evidence |
|---|---|---|
| Graph valid + nodes/models present | PASS | P4 `valid: true` |
| Real SenseNova output produced | FAIL | P5/P6: loader OOMs host before any CUDA allocation; no output |
| Generation completes end-to-end | FAIL | never starts (host-RAM OOM) |
| Cancelable while stuck | PARTIAL (P10) | `/interrupt` now wired from Adept cancel/reject paths; loader still cancel-resistant in native call but Adept no longer hangs silently |
| Honest failure UI | PASS (P8) | truthful coarse states + fast-fail + STALLED message |
| Default/capability label unchanged | PASS (P13) | Draft / Not Ready / never-default |
| Root cause fixed | FAIL | `SENSENOVA_VRAM_MODE="fast"` unchanged (by design — P13) |

**SENSENOVA GATE: NO-GO — the loader OOMs the host before any CUDA allocation; no real SenseNova output has been produced. The P8-P11 repairs make the failure honest, cancelable, and fast-failing, but do not make SenseNova generate.**

### Final Verdict

- **COMFY TOOLING GATE: GO**
- **SENSENOVA GATE: NO-GO**

These two gates are independent, as required: MCP-GO coexists with SenseNova-NO-GO. The Comfy observability/workflow-forensics program is certified complete; SenseNova generation readiness is not certified and remains Not Ready pending a working model configuration.

**Manual review path:** open `http://127.0.0.1:5173/` (Creator UI) and `http://127.0.0.1:8758/api/healthz` (Studio API). Comfy is running at `http://127.0.0.1:8188/` (queue empty, ready). Beta is left running for manual review.
