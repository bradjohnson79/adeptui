# Co-Director Sanitation Phase 1 — Unified Completion

**Law 30:** this is the completion report for `docs/release-gate/codirector-sanitation-phase1/00-GOVERNING.md`.

**Date:** 2026-08-21  
**Branch:** `feat/codirector-sanitation-phase1`  
**HEAD (committed):** `475153206d8d4df16591d73df18afcef379fcf29`  
**Created from:** `feat/codirector-temporal-continuity` @ `d340899`  
**Working tree:** Phase 1 product changes after the cherry-pick are **uncommitted**. Do not deploy. Do not treat HEAD as the full sanitation tree.

## PoseCraft integration record

```text
PoseCraft source SHA:     412542bb855aa02deaad99dadb245639f821c932
Sanitation integration SHA: 475153206d8d4df16591d73df18afcef379fcf29
merge/cherry-pick method: cherry-pick (clean; no dirty-tree merge)
files integrated:         45 files (+9614 / −227)
```

Certified baseline kept: `GO — POSECRAFT FULL OVERHAUL + CO-DIRECTOR APPLY_POSE`. No v5. No 17-joint semantic-rig change.

## One project

Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`.  
Korri `c49371ed-ba6b-4c16-ba98-a8b28b72118b`.  
Approved CRS `b6ab91dd-9d0a-4e4b-98b4-b26d268950dc` (revision 3, RGB PNG 1254×1254, 2,187,397 bytes).

Isolation Playwright for Working Context used disposable projects. Generation stayed on Schnick Coffee.

## What was implemented

- Persisted `CoDirectorWorkingContext` (`working-context-v1`) under existing `production_state`. No `memory2/`.
- Confidence compiler: HIGH / MEDIUM / LOW + reasons. No theater floats.
- Confirmation memory; PATCH cannot forge confidence / approvals / confirmations.
- PoseCraft reference slice (ids, preset, x/z). Canonical scene remains SoT.
- `posecraft.apply_pose` adjust-joint path; CRS ↔ figure bind; Timeline compile `applied=true`.
- Concurrent `/tools/proposals` sanitation: local `project`/`library` tools skip GPU snapshot; snapshot timeout is proposal-only.
- CRS card: failed/empty visual-sheet draft no longer hides the approved look; checkerboard matte; `?rev=` cache-bust; Preview modal; approved copy.

## Measured tests

| Suite | Result |
| --- | --- |
| `studio-api` pytest `test_working_context.py` + `test_crs_sanitation.py` + `test_posecraft_contracts.py` | **34 passed** |
| `studio-web` vitest `activeCrsCard.test.ts` | **4 passed** |
| Playwright CRS + Working Context (`ADEPT_BETA_TARGET=1`) | **5 passed** (1 CRS, 4 WC) |

PoseCraft Visual Truth Playwright was **not** re-run on this branch after integration.

## Peer review (review-only)

- GLM 5.2 [CRS review](3abc0ab0-c93c-479d-a177-b3eca4ea56b3): READY FOR PRIMARY REVIEW. No must-fix.
- Kimi K3 [CRS review](5704c5ac-3c61-43b5-92d9-b5de1ff6fc9b): READY FOR PRIMARY REVIEW. Residual: live Korri Regenerate not run; commit before deploy.

## Live Beta

Refreshed after the CRS card rebuild.

- Creator UI: http://127.0.0.1:8760/ (HTTP 200)
- Studio API: http://127.0.0.1:8758/ (`/api/health` ok, `apiRevision` `4751532`, started `2026-08-21T15:27:43Z`)

No Vercel deploy.

## Track C — live generates

Z-Image was chosen **explicitly**. Qwen is blocked for this shot because character/prop pictures require a pixel slot. That is not a silent substitute.

| Run | Shot | Job | Asset | Family |
| --- | --- | --- | --- | --- |
| 1 | `38146179-4a3e-4055-8136-ff407bddf789` (existing two-shot) | `74dedea3-a4a2-46b1-ae2f-b9b06d5ae0d5` | `c862b1bb-3104-47e5-b5a0-f209c881b4e4` | `zimage.ref_edit` of CRS |
| 2 | `bbd12a61-3680-45ed-ba4e-e351028365f0` (Korri-only authoritative intent) | `81c5eebd-4764-4fd7-9162-7b624032913b` | `498b13d9-8c8a-4e65-8aba-f9934b74d66d` | `zimage.ref_edit` of CRS |

Both jobs consumed approved CRS `b6ab91dd-…` as `sourceAssetId`. Spatial Map was not rewritten.

### Pixel review (human / vision path dimensions)

Generate 1 (`korri-schnick-generate.png`):

| Dimension | Verdict |
| --- | --- |
| IDENTITY | FAIL — photoreal woman, not approved elf Korri |
| PLACEMENT | PASS — behind a service counter |
| ENVIRONMENT | FAIL — coffee shop, Schnick signage garbled |
| PERFORMANCE | PASS — standing, not sitting / in front / back-turned |
| CAMERA | PASS — medium-wide counter readable |

Generate 2 (`korri-schnick-generate2.png`):

| Dimension | Verdict |
| --- | --- |
| IDENTITY | FAIL — different person; no elf ears, twin tails, purple circuitry arm, or wrap/skirt |
| PLACEMENT | PASS — barista panel behind the counter |
| ENVIRONMENT | PASS — readable “Schnick Coffee” signs |
| PERFORMANCE | PASS — standing at the counter |
| CAMERA | FAIL — 4-panel sheet layout, not one customer-side medium-wide frame |

Root cause (observed): certified Z-Image path is `zimage.ref_edit` with one pixel slot. The consumed slot is the **4-view CRS sheet**, so the runtime edits the sheet instead of rendering a single production frame of Korri in Schnick. Identity does not survive.

## Three-turn contract (non-pixel)

LIVE VERIFIED on Schnick:

1. Authoritative command → confidence **HIGH**, no question.
2. `POST .../working-context/approvals` stored `what=image` / asset `c862b1bb-…`.
3. “Give me a full close-up on Korri. High angle, 20 degrees.” → **HIGH**, asked=false, locked scene/identity/geography/performance, changing camera only.
4. “Raise her right hand slightly.” → `apply_pose` `adjusted=true`, changed joints `rightElbow` + `rightWrist` only. Male figure pose `action-block` unchanged.

## API restart recovery

LIVE VERIFIED. Working Context approvals, active scene/shot, Korri PoseCraft bind, and `neutral-relaxed` recovered after two Beta/API restarts **without** the chat transcript.

## Gate table

| Gate | State |
| --- | --- |
| GO — CRS SANITATION | **GO** — approved thumb + Preview + reload. Live Korri **Regenerate job** not run (approved rev 3 protected). |
| GO — CO-DIRECTOR WORKING CONTEXT | **GO** |
| GO — CONFIDENCE / CLARIFICATION BEHAVIOR | **GO** |
| GO — POSECRAFT + CO-DIRECTOR OPERATIONAL INTEGRATION | **GO** (operational). Hand picking residual: **PASS WITH DOCUMENTED LIMIT** (handles + two-pass body pick; hanging-rest hand bbox can still hit hip). Visual Truth Playwright not re-run here. |
| GO — KORRI IDENTITY GROUNDING | **NO-GO** |
| GO — SCHNICK SPATIAL GROUNDING | **NO-GO** as a unified claim (run 2 environment pass; run 1 fail; identity still failed) |
| GO — POSE / PERFORMANCE GROUNDING | **GO** semantic (standing) + PoseCraft joint update. Mannequin limb angles not pixel-certified. |
| GO — VISUAL TRUTH | **NO-GO** for pose-to-image (generated pixels are not Korri). PoseCraft JSON→geometry path not re-certified this session. |
| GO — SCENE CREATOR HANDOFF | **IMPLEMENTED / LIVE** enqueue+asset. Identity fail blocks product GO. |
| GO — TIMELINE HANDOFF | **GO** compile `poseMotionConditioning.applied = true`. No new Timeline video render in this window. |
| GO — RELOAD / API-RESTART RECOVERY | **GO** |

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | PASS — Character Creator + Scene Creator + Working Context APIs on Schnick |
| Frontend | PASS — CRS card shows approved sheet after sanitation |
| API | PASS — generate, working-context, apply_pose, CRS GET |
| Backend | PASS — jobs, persist, confidence |
| Persistence | PASS — WC + PoseCraft survive API restart |
| Runtime | PASS — Comfy ready, RTX 5090, Z-Image models present, jobs completed |
| Result | **FAIL** — pixels are not approved Korri |
| Reload | PASS — CRS thumb + WC |
| Downstream | PARTIAL — Timeline compile applied; no live Timeline render |

## Limitations

- Phase 1 product files after `4751532` are uncommitted.
- Korri CRS **Regenerate** was not live-run.
- PoseCraft Visual Truth Playwright not re-run on this branch.
- No Timeline video render this window.
- No Vercel. No commit (not requested).
- Hand picking: documented overhaul limit remains.

## FINAL

```text
NO-GO — CO-DIRECTOR SANITATION PHASE 1 INCOMPLETE
```

**Exact blocker:** Korri identity is not grounded in the generated Scene Creator image. Z-Image `ref_edit` consumed the 4-view CRS as the edit source. Two live jobs completed; both fail IDENTITY. Isolated subsystem greens (CRS card, Working Context, confidence, PoseCraft operate, Timeline compile, restart recovery) do not satisfy the unified chain.
