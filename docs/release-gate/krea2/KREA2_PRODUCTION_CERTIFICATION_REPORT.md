# Krea 2 Production Certification Report

**Governing document for the Krea 2 Production Certification milestone.**

Per Adept UI Law #30 (Documentation Canon), this is the single governing document
for this milestone. The Phase 1 capability-unblock report
(`KREA2_PHASE1_CAPABILITY_UNBLOCK_REPORT.md`) is historical and superseded for
production-certification purposes; it remains the authority for Phase 1
capability readiness only.

Branch: `beta`
Program: Co-Director Multimodal Continuity Compiler + Krea 2 Production Certification
Law: VERIFY → COMPILE → RENDER → CERTIFY

---

## 0. Scope and locked decisions

In scope:
- Validate Krea 2 (Turbo + RAW) workflows independently (Pass B).
- Feed the certified continuity compiler into Krea 2 in one controlled
  production test (Pass C).
- Decide Certified / Draft / Rejected status independently per workflow (Pass D).

Locked decisions (user, honored here):
1. **Turbo and RAW stay completely independent.** Turbo could become Certified
   while RAW remains Draft. Successful Krea T2I does NOT automatically certify
   Krea ERS.
2. **No automatic default-model promotion.** A Certified Krea engine becomes an
   *available* Certified engine — it does not replace Qwen, Z-Image, FLUX, etc.
3. **`providers/krea2.py` stays tiny.** It only translates the canonical
   continuity packet into the prompt representation Krea needs. No second
   continuity compiler, no Krea-specific truth model, no duplicated production
   context.
4. **Semantic continuity ≠ identity conditioning.** If Krea receives the correct
   description and spatial facts but not Korri's character pixels, the report
   cannot claim visual identity preservation.
5. **Simplicity law.** A certification failure resolved by correcting
   configuration, stale tests, runtime state, a provider renderer, or an
   existing contract is preferred over any new subsystem. A truthful
   DRAFT/PARTIAL result is preferable to expanding architecture to force a PASS.

---

## 1. Initial state (entering Pass B)

| Item | Value |
| --- | --- |
| Phase 1 verdict | PASS — capability unblocked, runtime verified (one local Turbo GPU smoke) |
| `models.image.krea2.ready` | Ready |
| `krea2.turbo_txt2img` workflow | Draft |
| `krea2.raw_txt2img` workflow | Draft |
| `krea2-turbo-local` static `capability` (model_registry) | "Certified" (stale — contradicted Draft workflow) |
| Live runs budget | Constrained (avoid unnecessary GPU cycles) |

---

## 2. Pass B — deterministic findings

### 2.1 Krea-specific test failures (fixed)

| Test | Root cause | Fix |
| --- | --- | --- |
| `test_installed_krea2_files_map_to_static_readiness` | Expected `readiness == "ready"` but Krea 2 is a Draft workflow not present in the `certifications.json` store, so `_map_local_readiness` correctly returns `"draft"`. | Updated expectation to `"draft"` with an explanatory comment. Honest non-Certified readiness. |
| `test_krea2_fingerprints_match_registry` | `graphHash` for `krea2.turbo_txt2img` and `krea2.raw_txt2img` drifted in `certified-registry.json` after a change in how volatile inputs are fingerprinted (`fingerprints.py`, commit `5f6554e`). Builders are deterministic. | Recomputed deterministic `graphHash` for both workflows and updated `certified-registry.json`. `builderHash` unchanged. |

Krea 2 test suite: **77 passed, 0 failed** after fixes.

### 2.2 Registry reconciliation

`krea2-turbo-local` static `capability` changed from `"Certified"` to `"Available"`
in `studio-api/app/production_control/model_registry.py` to honestly reflect its
Draft workflow status and align with the runtime override path
(`_apply_setup_status` downgrades a non-certified workflow's static "Certified"
claim to "Available"). `_map_local_readiness` then maps "Available" → `"draft"`.

This is a Simplicity-Law fix: correcting a stale static claim, not introducing a
new readiness subsystem.

### 2.3 ComfyUI `/object_info` probe (cfg + node semantics)

| Check | Result |
| --- | --- |
| 9 core Krea 2 nodes present | PASS — `Krea2CheckpointLoader`, `Krea2TextEncoder`, `Krea2VAELoader`, `ModelSamplingAuraFlow`, `Krea2ImageEncode`, `Krea2Denoise`, `Krea2Sampler`, `Krea2Decode`, `Krea2ImageSave` |
| `cfg = 0.0` allowed | PASS — Turbo uses `cfg=0.0` (flow-matching distilled checkpoint) |
| `ModelSamplingAuraFlow.shift` (mu) present | PASS — resolution-aware mu shift via `krea2_resolution_shift` |
| IPAdapter (reference images) | **MISSING** — reference-conditioning via IPAdapter is not installed; LoRA path is present |
| Resolution support | PASS — arbitrary resolutions padded to a multiple of 16; resolution-aware mu shift |

Known limitation (recorded, not a regression): **reference-image conditioning
(IPAdapter) is not installed in this ComfyUI.** Krea 2 can do text-to-image and
LoRA, but reference-conditioned I2I via IPAdapter is not currently available.
This is material to the semantic-vs-identity distinction in §3.3.

### 2.4 Existing-provider regression (pre-existing, Pass D)

5 pre-existing stale tests in the existing-provider regression are NOT new
regressions caused by Phase 0 or Pass B. They are Pass D's responsibility to
fix/justify:

1. `test_qwen_2512_registry_entries_present` — expects `qwen2512.txt2img` "Draft", actual "Certified"
2. `test_qwen_2512_resolve_txt2img_family` — expects `qwen2512.txt2img` "Draft", actual "Certified"
3. `test_identity_registry_draft_not_enforced` — expects enforced=False, actual True
4. `test_recommend_why_and_cost` — expects photo recommendedFamily "flux", actual "qwen2512"
5. `test_compile_no_workflow_preference` — expects workflowKey "zimage.txt2img" (flux Deferred), actual "flux.txt2img"

Root cause: the system advanced (workflows Certified, identity enforced,
recommender logic changed) and these tests were not updated. Pass D will
fix/justify each.

### 2.5 Pass B live runs — VRAM-BLOCKED

| Live run | Status | Blocker |
| --- | --- | --- |
| Turbo cold load measurement | BLOCKED | VRAM |
| Turbo warm generation measurement | BLOCKED | VRAM |
| Turbo quality (2 prompts) | BLOCKED | VRAM |
| RAW one smoke | BLOCKED | VRAM |

VRAM state after the Pass A live Qwen I2I proof: ~25.6 GB used, ~6.5 GB free.
Krea 2 needs ~24 GB. ComfyUI holds a stuck Qwen model that the `/free` API does
not release. Restarting the external Comfy-Desktop process to reclaim VRAM is a
manual, out-of-process action and was not performed.

**Pass B deterministic verdict: PASS.** Tests, fingerprints, registry
reconciliation, `/object_info` semantics, and resolution support are complete
and honest. **Pass B live verdict: BLOCKED (VRAM).** Live cold/warm/quality/RAW
runs remain pending and are carried into the final program report as a runtime
blocker, not a certification failure.

---

## 3. Pass C — continuity compiler → Krea 2 (controlled production test)

### 3.1 `providers/krea2.py` — tiny packet translator

Added `studio-api/app/codirector/knowledgebase/multimodal_continuity/providers/krea2.py`
and wired the `krea2` branch into `packet.py`'s provider dispatch. The renderer
is ~30 lines: it re-views the **same** `InstructionPacket` the Qwen/GPT
renderers consume (no second compiler, no Krea-specific truth model, no
duplicated production context). Krea 2 is Qwen-Image-based, so the prompt is
Chinese-first (like Qwen) with a Krea-specific view phrase
(`KREA2_VIEW_WHOLE = "生成同一锁定环境的统一环境参考表（krea2 production_ers）。"`).
Krea 2 sampling specifics (cfg 0.0, mu 1.15, 8-step turbo / 52-step raw) are
handled by the workflow builder, not the renderer.

Terminology additions (`terminology.py`): `KREA2_KEEP` (reuses `QWEN_KEEP`) and
`KREA2_VIEW_WHOLE`.

### 3.2 Same-packet test (Qwen + GPT + Krea)

`test_same_packet_drives_qwen_gpt_krea2` (new, passing): the SAME canonical
continuity packet drives all three renderers. Same `fingerprint`, same
`syncOk=True`, same `hardInvariants`, same actors. Krea's prompt is
Chinese-first with the Krea view phrase; Qwen and Krea share the Chinese-first
shape but differ in the view phrase; GPT is English-primary.

### 3.3 Semantic continuity ≠ identity conditioning

`test_semantic_continuity_not_identity_conditioning` (new, passing): the
packet's `referenceImage` is the **environment plate**
(`type == "original_environment"`, `assetId == ORIGINAL_ID`), not Korri's
character pixels. Korri is carried as a placed actor (semantic placement,
`factStatus == "creator_confirmed"`), and the packet carries **no character
identity image** for any actor. Therefore a Krea ERS image generated from this
packet receives the correct description and spatial facts (semantic continuity)
but NOT Korri's visual identity — so it cannot claim identity preservation for
Korri from this packet alone. This is reinforced by the missing IPAdapter
reference-conditioning path (§2.3): even if a character identity image were
supplied, the installed ComfyUI cannot currently consume it for Krea 2.

### 3.4 ERS promotion rule (policy — not a subsystem)

This rule governs when a Krea 2 ERS workflow may be promoted from Draft to
Certified. It is a contract, recorded here; the actual promotion (if any) is
performed by Pass D in `certified-registry.json`.

1. **Independent per workflow.** `krea2.turbo_txt2img` Certified does NOT
   certify `krea2.raw_txt2img`, and neither T2I workflow certifies a Krea ERS
   workflow. ERS is a separate capability and must pass its own live E2E proof.
2. **Live E2E required for ERS.** A Krea ERS workflow may be promoted to
   Certified only after a live end-to-end ERS run: continuity packet → Krea
   renderer → Krea workflow → generated ERS image → Library asset → provenance
   stamped → survives reload. Local-only or deterministic-only evidence is
   insufficient.
3. **No default-model switch.** Promoting any Krea workflow to Certified makes
   it an *available* Certified engine. It does NOT change the default model,
   does NOT replace Qwen / Z-Image / FLUX, and does NOT alter the recommender's
   default family selection. A creator may explicitly select a Certified Krea
   engine; nothing is auto-switched.
4. **Identity honesty.** A Krea ERS image may not be labeled as preserving a
   character's visual identity unless that character's pixels were actually
   supplied to and consumed by the Krea run (reference conditioning). Semantic
   continuity (correct description + spatial facts) is not identity
   conditioning.
5. **Simplicity.** If promotion is blocked by configuration, stale tests,
   runtime state, or an existing contract, fix that — do not introduce a new
   subsystem to force a PASS. A truthful Draft/Partial result is acceptable.

### 3.5 Optional ERS comparison (no default switch)

If a live Krea ERS run becomes possible (VRAM permitting), an optional
side-by-side comparison of a Qwen ERS image and a Krea ERS image for the same
continuity packet may be recorded as evidence. This comparison is informational
only and does NOT switch the default ERS engine, does NOT auto-promote Krea ERS,
and does NOT demote Qwen ERS. It is captured as artifacts + prose in this report.

### 3.6 Pass C live run — VRAM-BLOCKED

The controlled production test (Schnick Krea production image from the same
continuity packet used in Pass A) is VRAM-blocked for the same reason as §2.5.
The deterministic parts of Pass C (tiny translator, same-packet test,
semantic-vs-identity distinction, ERS promotion rule) are complete and passing.

**Pass C deterministic verdict: PASS.** **Pass C live verdict: BLOCKED (VRAM).**

---

## 4. Pass D — independent certification

Pass D was performed by the primary agent. Note on independence: Adept UI
Law #27 specifies GPT 5.4 for the independent certification subagent, but
`gpt-5.4-medium` is not in the available model list for this session (only
`inherit`, `composer-2.5-fast`, `cursor-grok-4.6-high-fast`, `glm-5.2-max`).
Per the Task-tool model constraint, no substitute model was launched; the
primary agent performed Pass D (Law #25: primary owns final integration and
certification; Law #27: the parent agent may use the active model for
certification). This constraint is recorded honestly.

### 4.1 Stale-test fixes (5/5)

All 5 pre-existing stale tests were fixed by updating expectations to match the
current correct system behavior (the system advanced; the tests had not). No
production behavior was changed — only test assertions + explanatory comments.
One test was renamed to reflect reality.

| Test | File | Change |
| --- | --- | --- |
| `test_qwen_2512_registry_entries_present` | `test_qwen_2512_registry.py` | `qwen2512.txt2img` Draft → **Certified**; legacy `qwen.txt2img` Deferred → **Draft** |
| `test_qwen_2512_resolve_txt2img_family` | `test_qwen_2512_registry.py` | `contract.status` Draft → **Certified** |
| `test_identity_registry_draft_not_enforced` → `test_identity_registry_enforced_w5` | `test_m42_w1_image_runtime.py` | renamed; `enforced` False → **True** (continuity/service.py exists, M42-W5); added `authority` assertion |
| `test_recommend_why_and_cost` | `test_m42_w3_image_product.py` | photo recommendedFamily flux → **qwen2512**; anime qwen → **illustrious/qwen2512**; executionFamily zimage → **qwen2512** |
| `test_compile_no_workflow_preference` | `test_m42_w3_image_product.py` | workflowKey zimage.txt2img → **flux.txt2img** (flux now Certified, preference honored) |

Re-run: **5 passed**. Root cause for each was a real, intentional system advance
(Qwen-Image-2512 promoted to the canonical default; identity enforcement turned
on; FLUX promoted to Certified; Illustrious XL added for anime). These were
stale tests, not regressions.

### 4.2 Promotion decision (per ERS promotion rule §3.4)

- `krea2.turbo_txt2img`: stays **Draft**. Deterministic evidence PASS, but live
  E2E (cold/warm/quality) is VRAM-blocked. Per §3.4 rule 2 (live E2E required)
  and the Simplicity law, a VRAM-blocked live run keeps the workflow honestly at
  Draft — not Rejected, not Certified. No `certified-registry.json` status change.
- `krea2.raw_txt2img`: stays **Draft** (same reasoning; RAW smoke VRAM-blocked).
- Krea ERS: **not claimed**. No live ERS run; IPAdapter reference-conditioning
  not installed, so identity conditioning is not possible. No ERS workflow
  promoted.

No default-model switch. `krea2-turbo-local` / `krea2-raw-local` static
`capabilityLabel` is `"Available"` (Pass B fix), so a Certified Krea engine —
when live evidence eventually passes — becomes an *available* Certified engine,
not a default. Verified in the running Beta: `krea2_turbo_capabilityLabel =
Available`, `krea2_raw_capabilityLabel = Available`.

### 4.3 Rollback path

No destructive registry change was made. Pass B refreshed `graphHash` for the
two Krea 2 workflows (corrective, additive — `builderHash` unchanged) and
Pass A refreshed `qwen2512.ref` fingerprints. The previous `graphHash` values
are recoverable from git history. No workflow was deleted or demoted; no
status was flipped. Rollback path remains valid.

### 4.4 Existing-provider regression

Broad regression across 9 touched/existing-provider suites: **104 passed,
1 failed**. The single failure is `test_runtime_map_image_and_video`
(`NO_EXECUTABLE_ROUTE` for video `ltx-local`, `gpu: Unknown`) — the same
pre-existing video-route blocker tracked in Pass A. No NEW regressions were
introduced by Phase 0, Pass B, Pass C, or Pass D.

### 4.5 Krea Library / provenance (existing path)

Krea 2 uses the **existing shared asset persistence path** — no new persistence
model. `app/workflows/krea2_image.py` only builds the ComfyUI graph (with a
`Krea2ImageSave` node carrying `_meta.adeptRole`); asset persistence,
provenance, and Library registration are handled by the shared
`image_runtime` job layer after ComfyUI returns, identical to Qwen/FLUX/Z-Image.
Confirmed: `krea2_image.py` contains no bespoke persistence/provenance code
(only a comment referencing request-side provenance).

### 4.6 Beta refresh

Beta was refreshed to reflect the Pass B/C/D API changes (no studio-web build
needed — no UI changes). The adopted Studio API on :8758 (running old code,
not owned by the supervisor) was restarted with user approval, then
`Start-AdeptUI-Beta.ps1 -NoBrowser` relaunched the supervisor + Studio API +
web proxy.

- `http://127.0.0.1:8760/__beta_web_health` → **200**
- `http://127.0.0.1:8758/api/health` → **200**
- Runtime state: **HEALTHY**
- Smoke (venv = running Beta): `render_krea2` loads; `krea2_turbo_capabilityLabel
  = Available`; `krea2_raw_capabilityLabel = Available`.

Beta is left running and ready for manual review.

### 4.7 Verdict matrix (final)

| Workflow | Deterministic | Live E2E | Identity | Verdict |
| --- | --- | --- | --- | --- |
| `krea2.turbo_txt2img` | PASS | BLOCKED (VRAM) | N/A (T2I) | **Draft** |
| `krea2.raw_txt2img` | PASS | BLOCKED (VRAM) | N/A (T2I) | **Draft** |
| Krea ERS (if attempted) | N/A | BLOCKED (VRAM) | NOT CLAIMED (no IPAdapter) | **Draft** (capability not certified) |

Per-workflow verdicts are binary: **Certified** | **Draft** | **Rejected**.
A VRAM-blocked live run keeps a workflow honestly at **Draft** (capability
verified, production not certified) — not Rejected, not Certified. This is the
Simplicity-law outcome: a truthful Draft result is preferable to expanding
architecture to force a PASS.

### 4.8 No commit / deploy

Per the program directive, no commit, push, or deploy was performed. All
changes remain in the working tree on `beta` for manual review.

---

## 5. E2E trace (Pass C deterministic path)

| Stage | State | Evidence |
| --- | --- | --- |
| User action | N/A (deterministic) | Compile packet for Korri @ Schnick |
| Continuity compiler | PASS | `compile_packet(provider="krea2")` |
| Provider renderer | PASS | `render_krea2(packet)` — Chinese-first, Krea view phrase |
| Same packet → Qwen/GPT | PASS | `test_same_packet_drives_qwen_gpt_krea2` |
| Semantic vs identity | PASS | `test_semantic_continuity_not_identity_conditioning` |
| Krea workflow (live) | BLOCKED (VRAM) | §3.6 |
| Generated image (live) | BLOCKED (VRAM) | §3.6 |
| Library / provenance (live) | BLOCKED (VRAM) | §3.6 |
| Reload (live) | BLOCKED (VRAM) | §3.6 |

---

## 6. Files changed (Pass B + Pass C)

- `studio-api/app/production_control/model_registry.py` — `krea2-turbo-local` static `capability` "Certified" → "Available".
- `studio-api/config/image-workflows/certified-registry.json` — refreshed `graphHash` for `krea2.turbo_txt2img` and `krea2.raw_txt2img`.
- `studio-api/tests/test_krea2_provider_registration.py` — `test_installed_krea2_files_map_to_static_readiness` expects `"draft"`.
- `studio-api/app/codirector/knowledgebase/multimodal_continuity/terminology.py` — added `KREA2_KEEP`, `KREA2_VIEW_WHOLE`.
- `studio-api/app/codirector/knowledgebase/multimodal_continuity/providers/krea2.py` — new tiny translator.
- `studio-api/app/codirector/knowledgebase/multimodal_continuity/providers/__init__.py` — export `render_krea2`.
- `studio-api/app/codirector/knowledgebase/multimodal_continuity/packet.py` — `krea2` branch in provider dispatch.
- `studio-api/tests/test_multimodal_continuity_compiler.py` — `test_same_packet_drives_qwen_gpt_krea2`, `test_semantic_continuity_not_identity_conditioning`.
- `docs/release-gate/krea2/KREA2_PRODUCTION_CERTIFICATION_REPORT.md` — this report.

---

## 7. Limitations (honest)

- Live Krea runs (cold/warm/quality/RAW, and the controlled production test)
  are VRAM-blocked. Deterministic evidence is complete; live evidence is not.
- IPAdapter reference-conditioning is not installed; Krea 2 cannot currently
  consume a reference image for I2I identity conditioning. Semantic continuity
  is delivered; visual identity conditioning is not.
- 5 pre-existing stale tests in the existing-provider regression are deferred
  to Pass D.
- No commit / push / deploy performed (per program directive).




