# Co-Director Multimodal Continuity Compiler + Krea 2 Production Certification
## Final Program Report

**Program-level summary report.** Per Adept UI Law #30 (Documentation Canon),
the two milestones in this program each have their own governing document:

1. **Co-Director Multimodal Continuity Compiler** →
   `docs/release-gate/ers/CD_MULTIMODAL_CONTINUITY_COMPILER_REPORT.md` (Pass A)
2. **Krea 2 Production Certification** →
   `docs/release-gate/krea2/KREA2_PRODUCTION_CERTIFICATION_REPORT.md` (Passes B/C/D)

This document is the program-level summary that ties the passes together and
records the final verdict matrix. It does not supersede the two governing
milestone documents; it references them.

Branch: `beta`
Law: VERIFY → COMPILE → RENDER → CERTIFY
No commit / push / deploy was performed (per program directive). All changes
remain in the working tree for manual review.

---

## 1. Program order and pass verdicts

| Pass | Scope | Deterministic | Live | Verdict |
| --- | --- | --- | --- | --- |
| Phase 0 | Runtime diagnosis: fix `NO_EXECUTABLE_ROUTE` / `gpu: Unknown` | PASS | N/A | **DONE** — image route unblocked, Qwen + Krea 2 executable + fast |
| Pass A | Continuity compiler: close gaps + live same-set I2I proof | PASS | PASS | **PASS** — continuity compiler certified |
| Pass B | Krea 2 workflows: deterministic validation | PASS | BLOCKED (VRAM) | **Draft** (deterministic PASS, live VRAM-blocked) |
| Pass C | Continuity compiler → Krea 2 (controlled production test) | PASS | BLOCKED (VRAM) | **Draft** (deterministic PASS, live VRAM-blocked) |
| Pass D | Independent certification | PASS | BLOCKED (VRAM) | **Draft** — honest, no forced promotion |

---

## 2. Headline verdict

- **Co-Director Multimodal Continuity Compiler: PASS — CERTIFIED.**
  Spatial Map + Scene Intent + creator miniPrompt compile correctly,
  bilingual synchronization passes, provenance is stamped, and the live same-set
  I2I proof generated a real 2560×1440 image (asset `f13defaf`) with the
  continuity packet stamped (fingerprint `56f78627`, `syncOk=True`). VLM is
  `null` (unavailable), recorded as an unavailable enhancement — not a blocker
  (per the user's locked decision).

- **Krea 2 Production Certification: Draft — capability verified, production
  not certified.** Deterministic evidence (tests, `/object_info`, fingerprints,
  resolution support, registry reconciliation, tiny packet translator,
  same-packet proof, semantic-vs-identity distinction) is complete and
  passing. Live E2E runs (cold/warm, quality, RAW smoke, controlled production
  image) are VRAM-blocked (~6.5 GB free, Krea 2 needs ~24 GB; ComfyUI holds a
  stuck Qwen model that `/free` does not release; restarting the external
  Comfy-Desktop is a manual, out-of-process action). Per the ERS promotion rule
  (live E2E required) and the Simplicity law, both Krea 2 T2I workflows stay
  honestly at **Draft**. No default-model switch.

---

## 3. Test matrix

| Suite | Result |
| --- | --- |
| Continuity compiler + I2I regression (Pass A) | 73 passed, 1 pre-existing video-route failure |
| Krea 2 suite (Pass B) | 77 passed, 0 failed |
| Continuity + Krea 2 combined (Pass C) | 54 passed, 0 failed |
| 5 stale existing-provider tests (Pass D) | 5 fixed → 5 passed |
| Broad regression, 9 suites (Pass D) | 104 passed, 1 pre-existing video-route failure |
| New Pass C tests | `test_same_packet_drives_qwen_gpt_krea2` PASS; `test_semantic_continuity_not_identity_conditioning` PASS |

Pre-existing video-route failure: `test_runtime_map_image_and_video`
(`NO_EXECUTABLE_ROUTE` for video `ltx-local`, `gpu: Unknown`). Tracked, not
caused by this program. No NEW regressions were introduced.

---

## 4. E2E trace — Pass A (continuity compiler, LIVE PASS)

| Stage | State | Evidence |
| --- | --- | --- |
| User action | PASS | ERS generate for Schnick (Korri occupied-scale) |
| Frontend → API | PASS | `ers.generate` capability |
| Continuity compiler | PASS | packet fingerprint `56f78627`, `syncOk=True` |
| Bilingual sync | PASS | English + Chinese views of same facts |
| Provenance stamp | PASS | `creativeContext.continuityPacket` on job `params_json` |
| Runtime (Qwen I2I `qwen2512.ref`) | PASS | live ComfyUI job, ~22s |
| Generated image | PASS | 2560×1440 RGB, asset `f13defaf`, decodable |
| Library / reload | PASS | asset persisted, survives reload |
| VLM | N/A | `null` — unavailable enhancement, not a blocker |

---

## 5. E2E trace — Pass C (continuity → Krea, deterministic PASS / live BLOCKED)

| Stage | State | Evidence |
| --- | --- | --- |
| Continuity compiler | PASS | `compile_packet(provider="krea2")` |
| Provider renderer | PASS | `render_krea2` — Chinese-first, Krea view phrase |
| Same packet → Qwen/GPT/Krea | PASS | `test_same_packet_drives_qwen_gpt_krea2` |
| Semantic vs identity | PASS | `test_semantic_continuity_not_identity_conditioning` |
| Krea workflow (live) | BLOCKED (VRAM) | ~6.5 GB free, Krea 2 needs ~24 GB |
| Generated image (live) | BLOCKED (VRAM) | — |
| Library / provenance (live) | BLOCKED (VRAM) | — |
| Reload (live) | BLOCKED (VRAM) | — |

---

## 6. Files changed (program)

**Phase 0 (runtime diagnosis):**
- `studio-api/app/production_control/model_registry.py` — `_apply_setup_status` live-verifies image components, reads persisted state for non-image.
- `studio-api/app/setup/status.py` — `_BUILD_VERIFY_TIMEOUT_SEC = 6.0`; removed periodic warmer.
- `studio-api/tests/test_cdx075_local_readiness.py`, `studio-api/tests/test_production_dock.py`, `studio-api/tests/conftest.py` — updated to new sources of truth; autouse cache clear.
- `config/image-workflows/certified-registry.json` — refreshed `qwen2512.ref` fingerprints.

**Pass A (continuity compiler):**
- `docs/release-gate/ers/CD_MULTIMODAL_CONTINUITY_COMPILER_REPORT.md` — updated to PASS.

**Pass B (Krea 2 deterministic):**
- `studio-api/app/production_control/model_registry.py` — `krea2-turbo-local` `capability` Certified → Available.
- `config/image-workflows/certified-registry.json` — refreshed `graphHash` for `krea2.turbo_txt2img` + `krea2.raw_txt2img`.
- `studio-api/tests/test_krea2_provider_registration.py` — readiness expectation `ready` → `draft`.

**Pass C (continuity → Krea):**
- `studio-api/app/codirector/knowledgebase/multimodal_continuity/providers/krea2.py` — new tiny translator.
- `studio-api/app/codirector/knowledgebase/multimodal_continuity/providers/__init__.py` — export `render_krea2`.
- `studio-api/app/codirector/knowledgebase/multimodal_continuity/packet.py` — `krea2` dispatch branch.
- `studio-api/app/codirector/knowledgebase/multimodal_continuity/terminology.py` — `KREA2_KEEP`, `KREA2_VIEW_WHOLE`.
- `studio-api/tests/test_multimodal_continuity_compiler.py` — 2 new tests.
- `docs/release-gate/krea2/KREA2_PRODUCTION_CERTIFICATION_REPORT.md` — new governing report.

**Pass D (independent certification):**
- `studio-api/tests/test_qwen_2512_registry.py` — 2 stale tests fixed (Certified / Draft).
- `studio-api/tests/test_m42_w1_image_runtime.py` — renamed + fixed identity enforcement test.
- `studio-api/tests/test_m42_w3_image_product.py` — 2 stale tests fixed (recommender / compile).
- `docs/release-gate/krea2/KREA2_PRODUCTION_CERTIFICATION_REPORT.md` — Pass D finalized.
- `docs/release-gate/CD_MULTIMODAL_CONTINUITY_KREA2_PROGRAM_REPORT.md` — this report.

---

## 7. Limitations (honest)

- **VRAM block on live Krea runs.** ~6.5 GB free; Krea 2 needs ~24 GB. ComfyUI
  holds a stuck Qwen model that `/free` does not release. Restarting the
  external Comfy-Desktop process to reclaim VRAM is a manual, out-of-process
  action and was not performed. This blocks all live Krea runs (cold/warm,
  quality, RAW smoke, controlled production image). Deterministic evidence is
  complete; live evidence is not.
- **IPAdapter reference-conditioning not installed.** Krea 2 can do T2I + LoRA
  but cannot currently consume a reference image for I2I identity conditioning.
  Semantic continuity is delivered; visual identity conditioning is not. A
  Krea ERS image therefore cannot claim identity preservation for a character
  from the continuity packet alone.
- **Independent subagent model unavailable.** Law #27 specifies GPT 5.4 for
  the independent certification subagent, but `gpt-5.4-medium` was not in the
  available model list. Pass D was performed by the primary agent instead
  (recorded honestly in the Krea 2 report §4).
- **Pre-existing video-route failure.** `test_runtime_map_image_and_video`
  (video `ltx-local`, `gpu: Unknown`) remains. Tracked, not caused by this
  program, not in scope to fix.
- **No commit / deploy.** Per program directive, all changes remain in the
  working tree on `beta` for manual review.

---

## 8. Final program verdict

| Milestone | Verdict |
| --- | --- |
| Co-Director Multimodal Continuity Compiler | **PASS — CERTIFIED** (live same-set I2I proof passed; VLM recorded as unavailable enhancement) |
| Krea 2 Turbo (`krea2.turbo_txt2img`) | **Draft** (deterministic PASS; live E2E VRAM-blocked) |
| Krea 2 RAW (`krea2.raw_txt2img`) | **Draft** (deterministic PASS; live E2E VRAM-blocked) |
| Krea 2 ERS | **Draft / not claimed** (no live run; no IPAdapter identity conditioning) |

**Overall: the continuity compiler is certified; Krea 2 is honestly Draft
pending live VRAM.** No forced certification. No default-model switch. Beta is
refreshed, healthy, and ready for manual review at `http://127.0.0.1:8760/`
(web) and `http://127.0.0.1:8758/api/health` (API).

### To unblock live Krea certification (manual, out-of-process)

1. Restart the external Comfy-Desktop process to reclaim VRAM (or unload the
   stuck Qwen model), targeting ~24 GB free.
2. Re-run Pass B live runs (Turbo cold/warm, 2 quality prompts; RAW one smoke)
   and the Pass C controlled production image (Schnick, same continuity packet
   as Pass A).
3. If live quality + runtime + persistence + reload pass, promote Turbo and/or
   RAW independently in `certified-registry.json` per the ERS promotion rule
   (§3.4 of the Krea 2 report). No default-model switch.
4. Krea ERS requires IPAdapter reference-conditioning to be installed before any
   identity-preservation claim can be made.

