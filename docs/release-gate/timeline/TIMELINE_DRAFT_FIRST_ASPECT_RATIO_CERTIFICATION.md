# Timeline Draft-First Generation + Aspect Ratio System — Certification

**Status:** Governing document for this milestone.  
**Date:** 2026-08-16  
**Verdict:** `GO — TIMELINE DRAFT-FIRST GENERATION + ASPECT RATIO SYSTEM CERTIFIED END TO END`

Older Timeline reports remain historical and must not be cited as current truth for Draft Mode, production aspect ratios, or Video Reference:

- `TIMELINE_GENERATOR_ARCHITECTURE_AUDIT.md` (2026-08-05 architecture audit)
- `TIMELINE_TWO_BATCH_FINAL_CERTIFICATION_REPORT.md`
- `TIMELINE_TWO_BATCH_MINIMAX_I2V_FINAL_CERTIFICATION_REPORT.md`
- `TIMELINE_MINIMAX_I2V_PATH_AUDIT.md`

## Product

Scene Creator defines the shot and ratio → Timeline binds image and motion references → Adept selects the cheapest truthful draft path → creator evaluates it → Final only happens after promotion → lineage preserves everything.

## Capability truth

| Provider | draftPathway | Cancel queued/running | Video reference | 21:9 |
| --- | --- | --- | --- | --- |
| LTX local | `local_live` | Yes / Yes (`cancel_and_halt`) | Refuse if attached | Adept pixels (672×288 / 1344×576) |
| MiniMax H3 | `none` (Final-only) | Yes / Yes | Refuse if attached | Warn; do not fake ultrawide |
| Seedance | `cheap_preview` (480p → 720p) | No / No | R2V only when a clip is attached | `aspect_ratio=21:9` + 480p/720p |
| Kling | `none` | No / No | Refuse if attached | Provider-native |

No provider currently exposes a native draft-task API. `native_api_draft` stays unused.

`BatchStatus: "Draft"` remains “unconfigured batch”. Draft takes use `CandidateVersion.takeState.quality = "draft"`.

Local LTX Timeline generation is **I2V only**. Text-to-video without a start frame is refused by the runtime (`Local LTX requires a start frame`).

## Live environment

- Creator UI: `http://127.0.0.1:8760/` (production `studio-web/dist`, bundle `index-CQ23iWUh.js`)
- Studio API: `http://127.0.0.1:8758/` (`/api/health` 200)
- ComfyUI: reachable, RTX 5090, LTX checkpoint present
- Project reused: `Timeline Draft Aspect Cert` (`70c789ff-952e-47d9-a630-be522c9651da`)

## Certification evidence

### Playwright (mocked generate)

`tests/e2e/timeline/timeline-draft-aspect-videoref.spec.ts`  
**1 passed** (13.9s) with `ADEPT_BETA_TARGET=1`.

Covered: Timeline open, LTX Draft Mode default ON, four Picture Shape values, Video Reference track visible, Seedance cheap-preview copy, Kling Draft unavailable, 21:9 survives reload.

### Live gates (one each)

| Gate | Result | Evidence |
| --- | --- | --- |
| LTX Stop while running | **PASS** | Job `96a8b7c9-…` had `comfy_prompt_id`; Timeline `cancel_active_local_job` → `cancel_and_halt`; `confirmedStopped=true`, prompt `deleted`, Comfy presence `active=false`. Artifact: `artifacts-draft-aspect/ltx_stop_running.json` |
| LTX draft result + Promote | **PASS** | Job `082777d3-…` `done`, `draftMode=true`, `672×288`, `fast_mode`; Library asset `0bef05e4-…` tag `ltx-draft` `prompt_meta_json.quality=draft`; candidate `cand_3ff8622d0da1` quality `draft` 21:9 survives re-GET; Promote submitted **new** job `02446114-…` `draftMode=false` `1344×576` 21:9. Artifact: `artifacts-draft-aspect/ltx_draft_candidate_final.json` |
| Seedance 21:9 Draft→Final | **PASS** | Draft job `seedance_9294e7b1300c` candidate `cand_318964783b8c` quality `draft` `480p` `21:9`; Final job `seedance_32692a8605d5` candidate `cand_cdc087a5b864` quality `final` `720p` `21:9`. No Video Reference attached → T2V/I2V, not R2V. |
| Kling / LTX video-ref refuse | **PASS** | Live generate with `sourceAnchors.kind=video` returned `CAPABILITY_VALIDATION_FAILED` and did not drop the reference. |
| Aspect 1:1 / 4:3 / 16:9 / 21:9 | **PASS** | Playwright selectors; live scene `21:9` on LTX pixels and Seedance `aspect_ratio=21:9` (not a 16:9 crop labeled 21:9). |

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | PASS (Generate Draft / Final / Stop / Promote / Picture Shape / Video Reference) |
| Frontend | PASS (capability-driven; no silent drop) |
| API | PASS (`draftMode`, refuse unsupported video refs) |
| Backend | PASS (W46 adapters + request builder; LTX enqueue on `job_queue`; draft assets labeled) |
| Persistence | PASS (candidates, Library `quality=draft`, `scene.aspect_ratio`) |
| Runtime | PASS (Comfy halt + LTX draft render; Seedance fal 480p/720p) |
| Result | PASS |
| Reload | PASS (21:9 UI; LTX draft candidate re-GET) |
| Downstream | PASS (handoff writes aspect; Timeline contain-fit) |

## Limitations (honest, not blockers for this gate)

- Seedance **reference-to-video** was not live-run; no Video Reference clip was attached. Without a clip, Seedance stays I2V/T2V as specified. R2V wiring is covered by adapter code + unit tests.
- LTX Timeline path is I2V-only. A start image is required.
- One LTX run logged `WORKFLOW_GRAPH_DRIFT` and fell back to simple I2V; Stop still halted the Comfy prompt.
- Playwright UI cert used mocked generate. Live Stop/Promote/Seedance were proven on the same Timeline generate/cancel APIs the Inspector buttons call.
- Commit / Vercel SHA alignment was not performed in this pass (no git commit requested).
- A stale process on port **8761** still 500s Timeline generate; Beta UI on **8760** is proxied to **8758**, which is the certified API.

## Binary verdict

`GO — TIMELINE DRAFT-FIRST GENERATION + ASPECT RATIO SYSTEM CERTIFIED END TO END`
