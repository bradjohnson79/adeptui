# Revision B — Unified Review Report

**SUPERSEDED.** This file is the historical NO-GO snapshot. Current Law 30 completion report: [../REVISION-ABC-FINAL-CLOSURE.md](../REVISION-ABC-FINAL-CLOSURE.md).

**Governing product law:** [00-GOVERNING.md](./00-GOVERNING.md)  
**Absorbed / historical:** [01-CERTIFICATION.md](./01-CERTIFICATION.md), [02-LIVE-CLOSURE.md](./02-LIVE-CLOSURE.md). Do not cite those as current truth.

**Branch:** `feat/codirector-temporal-continuity`  
**Revision B commits:** `ae6988b` → `9a349b4`  
**Current git HEAD (may include later unrelated work):** see `git rev-parse --short HEAD`  
**Live Studio API at measurement:** `apiRevision=f51838a` · `apiStartedAt=2026-08-20T16:27:33Z` · `routeContract=["perception.capability"]`  
**SHA drift:** live API `f51838a` ≠ later HEAD. Perception is already on that process. Later commits in the Rev B range after `f51838a` are supervisor boot-grace / Playwright-runner only.

**Named project (reused, no `POST /api/projects`):** Schnick Coffee  
**Project ID:** `2347bf46-3762-4763-86c5-4a6032522278`  
**Spatial map:** `6bc36d92-d21a-4c2f-b85f-71d1f6aa9081`  
**Scene:** `e4550745-f0ef-44c8-99a5-ef9e20bd47d2`  
**Korri (do not overwrite):** `c49371ed-ba6b-4c16-ba98-a8b28b72118b`  
**Disposable CRS character:** `3b73a488-06be-4407-a21d-284e60ed8bfc` (`RevB Live 1787244404`)

**Cert topology only:**

```text
http://127.0.0.1:8760/  →  http://127.0.0.1:8758/
```

Isolated `:5174` → `:8742` is evidence-only. Do not certify on it.

**Beta (left running at handoff):** creator UI http://127.0.0.1:8760/ · Studio API http://127.0.0.1:8758/

---

## Verdict

```text
NO-GO — REVISION B CREATION INTELLIGENCE NOT CERTIFIED
```

Governing equivalent:

```text
NO-GO — FULL-STACK E2E NOT VERIFIED
```

This is not `CERTIFIED COMPLETE — FULL-STACK E2E VERIFIED`.  
Independent verifiers returned `READY FOR PRIMARY REVIEW` only.  
This closure does **not** use `E2E BLOCKED` as a final program result.

---

## Why (one paragraph)

Source, adoption, CD Scene Review, unit tests, and Playwright A–H on **8760→8758** are in. Live GPU Character CRS, Schnick blocking still, and measured `zimage.inpaint` leak are **not**. ImageProduct jobs stayed `queued` while Comfy’s queue was empty and the RTX 5090 was idle. After zombie Korri job `657d1665` was cancelled, the in-process JobQueue did not start the next row. Recycling `:8758` would `recover_interrupted` leftover Korri CRS jobs from abandoned Character Creator tabs. That recycle was refused so production Korri would not be overwritten.

---

## Reviewer path (10 minutes)

1. Read this file. Verdict is **NO-GO**. Do not upgrade it from units or Playwright.
2. Confirm Beta: http://127.0.0.1:8760/ and `GET http://127.0.0.1:8758/api/health` + `GET http://127.0.0.1:8758/api/perception/capability`.
3. Open Schnick Coffee → Spatial Map. Confirm **CD Scene Review** (not “Auto Map”), visible 4+4+4 slots, no `zones[]` chrome.
4. Skim [evidence/live-gates.json](./evidence/live-gates.json) (stops at `crsStart`), [evidence/queue-block.json](./evidence/queue-block.json), [evidence/map-after-accept.json](./evidence/map-after-accept.json).
5. Confirm `evidence/` has **no** `character-crs.png`, `schnick-still.png`, or `edit-inpaint.png`.
6. Do not treat `:8742` or a Vercel preview as this cert.

---

## Scope

Architecture **A** only. Sibling `SpatialDraft`. Do **not** add `zones[]` to `SpatialMapDocument`.

```text
CD Scene Review
      ↓
  SpatialDraft (no slot write)
      ↓
  filmmaker correction
      ↓
  Accept → place_character / place_prop / create_camera
      ↓
  NL compile (behind / beside / facing / customer side)
      ↓
  Scene Creator still
      ↓
  region paint → zimage.inpaint
      ↓
  measure unmasked_mean_delta
```

Chat is not required. Accept is the only write from perception into slots. Hard 4 / 4 / 4 stay visible.

**Not in this revision:** Architecture B ERS zones, MAGI, Revision A worker moves, JEPA, SceneCraft, FreqEdit, identity embeddings, Qwen-Image-Edit-2511, DeepSeek CRS spinner/queue-watchdog, `gpu_lease.py` API changes (stills use sibling `preflight_for_stills`).

---

## Layer status

| Layer | Result |
|---|---|
| SOURCE | IMPLEMENTED |
| UNIT | TESTED — **131** API passed, **48** frontend passed |
| SMOKE | LIVE API — health + perception on **8758** |
| PLAYWRIGHT | TESTED — **8 passed, 1 flaky** (case A retry passed) on 8760→8758 |
| LIVE API | PARTIAL — Review / correction persist / NL parse in `live-gates.json`. First Accept in that file failed. Later Accept is a follow-up map GET. |
| LIVE GPU | NOT VERIFIED |
| PIXEL | NOT VERIFIED |
| VISUALLY VERIFIED | NOT VERIFIED |

---

## What shipped (source)

### Runtime identity and adoption

- `HealthOut.routeContract` includes `perception.capability`.
- Supervisor adopts only if health 200 **and** SHA current **and** `GET /api/perception/capability` has `sceneReview` in `{available,testing,unavailable}` and `chatRequired=false`.
- SHA match + missing perception ⇒ recycle Adept-owned listeners, including multiprocessing orphans when the listen PID is already gone.
- Windows Beta API starts with `--workers 1`.
- Unit: healthy SHA + missing perception ⇒ do not adopt.

Historical stale listener: [8758-STALE-AUDIT.md](./8758-STALE-AUDIT.md) — adopted `c8c5133` from `2026-08-20T06:45:22Z` with `/api/perception` **404**.

### CD Scene Review / Smart Select

- Authoritative busy only while the request is open.
- Shared timeout / creator copy: “Scene review couldn't start.” + Retry.
- Single-flight Review and Smart Select.
- Review does not `place_*`. Accept remains the only write.
- Smart Select does not invent a mask when geometry is unavailable.

### Creation intelligence (Architecture A)

- Sibling `SpatialDraft` (`spatial_draft` trait). No `zones[]` on the map document.
- Optional stills geometry worker (GDINO-T / SAM 2.1 / DA-V2 Small), installer `stills_perception_hf`, `required=False`. Not installed for this live pass (`geometry=unavailable`). Allowed.
- Scene NL: behind / beside / facing / customer-side via `entity_resolver` + `spatial_language.py`.
- Character Creator: single-CRS coerce (Qwen default or explicit GPT Image 2). No embeddings. Approve registers `@Name`.
- Inpaint leak detector exists (`LEAK_THRESHOLD = 2.0`). Not run on live pixels. No FLUX composite added.

### Revision B commit range

| SHA | Change |
|---|---|
| `ae6988b` | Perception package, CD Scene Review, stills installer, health route contract, adoption hole |
| `5f9c9ce` | Recycle when listen PID is already gone |
| `c5a7108` | Windows `--workers 1` |
| `ac0d353` | Respawn when adopted `:8758` dies |
| `f51838a` | 120s boot grace before hung-restart (this is the live API revision) |
| `9a349b4` | Force Beta Playwright onto 8760→8758 |

---

## Files (review surface)

| Area | Paths |
|---|---|
| Perception | `studio-api/app/codirector/perception/` |
| Health / identity | `studio-api/app/routers/api.py`, `studio-api/app/schemas.py` |
| Supervisor | `scripts/beta_runtime/supervisor.py`, `scripts/beta_runtime/api_identity.py` |
| Scene NL | `studio-api/app/codirector/entity_resolver.py`, `perception/spatial_language.py` |
| Single CRS | `studio-api/app/character_identity/visual_sheet.py` (`_coerce_single_crs_sources`) |
| Setup stills | `studio-api/app/setup/` catalog + `executors/stills_perception.py` |
| CD Scene Review | `studio-web/src/components/CoDirector/SpatialMap/CdSceneReview.tsx` |
| Request policy | `studio-web/src/codirector/perception/requestPolicy.ts` |
| Smart Select | `studio-web` RegionEditPanel + perception `auto-mask` |
| Playwright | `tests/e2e/codirector/revision-b-creation-intelligence.spec.ts` |
| Beta runner | `scripts/run-playwright-beta.mjs` (forces 8760/8758) |
| Live runner | `docs/release-gate/codirector-creation-intelligence/run_live_gates.py` |

Do not treat unrelated dirty tree files (`gpu_lease.py`, `web_server.py` timeout, `SpatialMapDocument` movement fields) as Revision B evidence.

---

## Tests (measured this closure)

| Suite | Result |
|---|---|
| Perception / identity / single-CRS / spatial / engine / attach / grounding / placement | **131 passed** |
| Frontend vitest (requestPolicy, CdSceneReview, Smart Select, CC copy) | **48 passed** |
| Playwright A–H + NL on 8760→8758 (`ADEPT_BETA_TARGET=1`) | **8 passed, 1 flaky** |

Playwright cases:

| Case | Intent | Result |
|---|---|---|
| A | Review drafts; slots unchanged | Flaky then PASS |
| B | Accept writes `place_*` | PASS (disposable temp project) |
| C | Correction survives reload | PASS |
| D | Geometry unavailable; manual map works | PASS |
| E | Smart Select does not fake a mask | PASS |
| F | Forced review failure stops spinner; creator copy | PASS |
| G | Duplicate Review does not double-submit | PASS |
| H | Browser 8760 persists through 8758 after reload | PASS |
| NL | parse-shots keeps spatial language | PASS |

These counts were measured in the closure session. They are not checked in as a raw log under `evidence/`.

---

## Live API measurements (Schnick, 8760→8758)

| Check | Result | Evidence |
|---|---|---|
| Health + perception | PASS | `sceneReview=available`, `chatRequired=false` |
| Review does not write slots | PASS | `live-gates.json` before/after 1/2/4; `zones` absent |
| Geometry | `unavailable` | No CPU-torch greenwash |
| Correction persists | PASS (weak) | `userCorrections` for `fill:korri` and `fill:coffee cup` (both renamed to the same phrase) |
| Accept | MIXED | JSON Accept = `FILL_NOT_FOUND`. Later Accept `fill_46484b9f3077` wrote. GET now 2/2/4, Korri slot 0, slot 1 id Anadriya `284411ea-…` labeled `CRS Single 1787198703328`. No `zones[]`. |
| NL parse facts | PASS | behind / beside / facing / customer / employee / Korri / Anadriya |
| Disposable CRS enqueue | PASS | Qwen `qwen2512.txt2img`, `LOCAL — Qwen Image 2512`, `candidateCount=1`, not Korri |
| CRS runtime | FAIL | `d1abe4af` and retry `3dde1cb7` stayed `queued` |
| Character still / Schnick still / leak | NOT RUN | No PNGs |

---

## E2E TRACE — Character

| Stage | Verdict |
|---|---|
| User action | FAIL — no approved sheet or `@Name` still |
| Frontend | N/A for the live API runner |
| API | PASS — generate accepted, Qwen locked, no silent swap |
| Backend | PASS — pack `GENERATING` |
| Persistence | FAIL — no sheet asset |
| Runtime | FAIL — JobQueue did not execute |
| Result | FAIL |
| Reload | FAIL |
| Downstream | FAIL |

## E2E TRACE — Spatial (Schnick)

| Stage | Verdict |
|---|---|
| User action | PASS — Review / correct / Accept attempt / NL parse |
| Frontend | PASS — Playwright A–H on 8760 |
| API | PASS — `/api/perception/*` on 8758 |
| Backend | PASS — sibling draft; Accept uses `place_*`; no `zones[]` |
| Persistence | PASS — draft + corrections survive GET; extra slot on follow-up GET |
| Runtime | FAIL — no blocking still |
| Result | FAIL — no still pixels |
| Reload | PASS for draft/slots; FAIL for still |
| Downstream | FAIL — no generate-job `creativeContext.spatial_language` |

## E2E TRACE — Edit

| Stage | Verdict |
|---|---|
| User action | FAIL — no approved still to paint |
| Frontend | PASS — Playwright E (Smart Select honesty) |
| API / Backend | N/A — region-edit not invoked on live pixels |
| Runtime / Result / Reload / Downstream | FAIL / N/A |

---

## JobQueue blocker (why GPU never started)

| Item | Observation |
|---|---|
| Comfy | `queue_running=[]`, `queue_pending=[]` |
| GPU | ~30842 MiB free on RTX 5090 |
| Zombie | `657d1665` (`korri_four_view`) status=running / sampling ~20 min with prompt gone; cancelled |
| Disposable jobs | `d1abe4af`, `3dde1cb7` remained `queued` |
| Leftover Korri jobs | seven `korri_*` rows still queued from abandoned UI tabs |
| Recycle | Refused — `recover_interrupted` would start those Korri CRS jobs |

See [evidence/queue-block.json](./evidence/queue-block.json).

---

## Independent verifiers

All `READY FOR PRIMARY REVIEW` only. Model: `inherit` (`gpt-5.4-medium` was not in the available Task list).

| Role | Result | Link |
|---|---|---|
| Runtime ownership | Adoption requires perception; live 8758 owned + perception present | [Runtime ownership](c772e946-7046-4e3c-a339-9bb6f4e3cdf6) |
| Backend / perception | Architecture A holds; no `zones[]` | [Backend perception](788bf6b9-ef75-4587-8f42-0a6e8cddde08) |
| Character / CRS | Qwen enqueue proven; no asset; Korri not overwritten | [CRS conditioning](d6acf1c0-36c0-4bef-a628-c60723c730b8) |
| Spatial draft → compile | Review/NL hold; compile-to-pixels missing | [Spatial compile](b3095dbe-750c-4f01-a885-801c2cbd16a2) |
| Edit + leak | Leak not measured; no FLUX composite added | [Edit leak](169a9d04-0d02-4e19-b4f2-b4a8cda83ddf) |
| Frontend / Playwright | Spec pinned to 8760→8758 | [Playwright 8760](d9308c4f-6111-4204-a009-6df0c911afc2) |
| Visual pixels | **PIXEL NOT VERIFIED** | [Pixel inspector](5b0363ab-737b-43e5-88d1-2fcd3cb72520) |
| Architecture + evidence | Punch list applied (do not overclaim Accept / LIVE API / clean `gpu_lease.py`) | [Architecture review](08aa6dd7-504d-45e8-84c6-f5bd1ec9bd00) |

---

## Automatic NO-GO checklist

| Condition | Result |
|---|---|
| Dead `/api/perception` on cert `:8758` | **PASS** — route present on this process |
| SHA-alone adoption still possible | **PASS** (source) — probe required |
| Review writes slots | **PASS** — slots unchanged on review |
| `zones[]` added to map document | **PASS** — absent |
| Silent model swap on CRS | **PASS** — Qwen locked, `fallbackApplied=false` |
| Korri CRS overwritten | **PASS** — disposable character used; leftover Korri jobs not started |
| Success without pixels | **NO-GO** — this is the cert failure |
| Request without runtime job | **NO-GO** — jobs queued, never ran |
| Mock / fixture completion | **PASS** — not used as GO |
| Certifying on `:8742` | **PASS** — refused |

---

## Limitations (honest)

- Geometry worker not installed. Review used Visual Canon / glossary. Allowed.
- First Accept in `live-gates.json` failed (`FILL_NOT_FOUND` after re-review changed fill ids). Follow-up Accept is not in that JSON.
- Correction proof is persistence of `userCorrections` rows, not a unique-label visual.
- Live runner died during CRS poll; JSON stops at `crsStart`.
- Unit / Playwright counts have no raw log artifact under `evidence/`.
- Working tree may contain unrelated dirty files from other milestones.
- This unified file and `evidence/` may still be untracked at review time.

---

## Manual review

1. Open http://127.0.0.1:8760/ → **Schnick Coffee**.
2. Spatial Map → **CD Scene Review** → confirm slots stay put until Accept.
3. Scene Creator → confirm Smart Select does not invent a mask if geometry is unavailable.
4. Do not start a new Korri CRS.
5. Do not certify a still that was not generated in this closure.

---

## Mandatory completion checklist

```text
[x] Branch + Rev B SHA range verified (ae6988b..9a349b4)
[x] Contracts preserved (Architecture A, SpatialDraft sibling, 4/4/4, no zones[])
[x] Implementation completed (source)
[ ] Full-stack live GPU completed
[x] Visible CD Scene Review / Smart Select wired
[ ] Real CRS / still / inpaint runtime on pixels
[x] Draft / correction persistence after GET
[x] Error/retry UX for Scene Review (Playwright F)
[x] Project isolation: Schnick reused; Korri not overwritten
[x] Unit/API/regression: 131 passed
[x] Frontend vitest: 48 passed
[x] Playwright A–H on 8760/8758: 8 passed, 1 flaky
[x] Failures documented (adoption hole, JobQueue drain, Accept FILL_NOT_FOUND)
[x] Independent verifiers second-pass (READY FOR PRIMARY REVIEW only)
[x] Beta left running; URLs reported
[x] Manual review path documented
[x] Evidence saved (JSON + audit; no PNGs)
[x] Unified Markdown review report created (this file)
[x] Limitations honest
[x] Verdict: NO-GO
[ ] GPU-designated CRS / still / inpaint executed on GPU
[x] No silent CPU fallback / no CPU-torch greenwash
[x] Creator workflows inside Adept UI (Law 29)
[x] One governing doc; superseded reports marked (Law 30)
```

---

## Final language

```text
NO-GO — REVISION B CREATION INTELLIGENCE NOT CERTIFIED
```

```text
NO-GO — FULL-STACK E2E NOT VERIFIED
```
