# Revision B Live Closure

**HISTORICAL / ABSORBED.** The unified review report is [REVISION-B-UNIFIED-REVIEW.md](./REVISION-B-UNIFIED-REVIEW.md). Do not cite this file as current truth.

**Governing:** [00-GOVERNING.md](./00-GOVERNING.md)  
**Law 30:** Superseded as the current report. [01-CERTIFICATION.md](./01-CERTIFICATION.md) is also historical.  
**Branch:** `feat/codirector-temporal-continuity`  
**HEAD:** `9a349b4`  
**Remote:** `origin/feat/codirector-temporal-continuity`  
**Beta topology:** `http://127.0.0.1:8760/` → `http://127.0.0.1:8758/`  
**API identity (live):** `apiRevision=f51838a` · `apiStartedAt=2026-08-20T16:27:33Z` · `routeContract=["perception.capability"]`  
**Project reused:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278` (no `POST /api/projects`)  
**Map:** `6bc36d92-d21a-4c2f-b85f-71d1f6aa9081`

Isolated `:5174` → `:8742` is not this certification topology.

## Verdict

```text
NO-GO — REVISION B CREATION INTELLIGENCE NOT CERTIFIED
```

Governing equivalent:

```text
NO-GO — FULL-STACK E2E NOT VERIFIED
```

This is not `CERTIFIED COMPLETE — FULL-STACK E2E VERIFIED`. Independent verifiers returned `READY FOR PRIMARY REVIEW` only.

## Why

Live GPU Character CRS, Schnick blocking still, and `zimage.inpaint` leak measurement did **not** run on pixels. ImageProduct jobs stayed `queued` while Comfy’s queue was empty and the RTX 5090 was idle. After a zombie Korri job (`657d1665`, “running in ComfyUI” / sampling, prompt gone) was cancelled, the in-process JobQueue consumer did not start the next job. Official Character Creator retry created `3dde1cb7` and it also stayed queued.

Leftover Character Creator tabs had already enqueued a Korri multi-view CRS. Recycling `:8758` would `recover_interrupted` those Korri jobs and overwrite production Korri. That recycle was refused.

## Layer status

| Layer | Result |
|---|---|
| SOURCE | IMPLEMENTED — Architecture A, sibling SpatialDraft, no `zones[]`, route contract + adoption probe, CD Scene Review hardening |
| UNIT | TESTED — API perception / identity / single-CRS / spatial regression **131 passed**; frontend Rev B **48 passed** (re-run after repairs; do not reuse older counts) |
| SMOKE | LIVE API — `GET /api/health` 200 + `GET /api/perception/capability` `sceneReview=available`, `chatRequired=false` on **8758** |
| PLAYWRIGHT | TESTED — `revision-b-creation-intelligence.spec.ts` against **8760/8758** (`ADEPT_BETA_TARGET=1`): **8 passed, 1 flaky** (case A timed out once on `[data-testid=spatial-map-panel]`, retry passed; B–H + NL passed) |
| LIVE API | PARTIAL — Review / correction persist / NL parse on Schnick are in `live-gates.json`. First Accept in that file is `FILL_NOT_FOUND`. A later Accept is evidenced by live map GET, not by the runner JSON. |
| LIVE GPU | NOT VERIFIED — CRS and stills never left `queued` |
| PIXEL | NOT VERIFIED — no `character-crs.png` / `schnick-still.png` / `edit-inpaint.png` |
| VISUALLY VERIFIED | NOT VERIFIED |

## Live API measurements (8760→8758)

Evidence: [evidence/live-gates.json](./evidence/live-gates.json), [evidence/queue-block.json](./evidence/queue-block.json), [8758-STALE-AUDIT.md](./8758-STALE-AUDIT.md)

| Check | Result |
|---|---|
| Review does not write slots | PASS — characters/props/cameras unchanged; `zones` absent |
| Geometry | `unavailable` (installer not required; no CPU-torch greenwash) |
| Correction persists | PASS (weak) — `userCorrections` rows for `fill:korri` and `fill:coffee cup` remain on GET draft. The runner renamed both to the same phrase; this is persistence, not a clean unique-label proof. |
| Accept writes `place_*` | MIXED — `live-gates.json` Accept is `FILL_NOT_FOUND` / `documentWritten=false`. A later Accept on current-draft `fill_46484b9f3077` returned `documentWritten=true`. Follow-up GET ([evidence/map-after-accept.json](./evidence/map-after-accept.json)): 2/2/4 slots, no `zones[]`, Korri still slot 0. Slot 1 id is Anadriya `284411ea-…` with label `CRS Single 1787198703328`. Playwright B proved Accept on a disposable temp project, not this Schnick Accept body. |
| NL parse compile facts | PASS — behind / beside / facing / customer / employee / Korri / Anadriya present in parse-shots JSON |
| Disposable character | Created `3b73a488-06be-4407-a21d-284e60ed8bfc` (`RevB Live 1787244404`), not Korri |
| CRS start | PASS — `POST .../visual-sheet/generate` 200, Qwen `qwen2512.txt2img`, provenance label `LOCAL — Qwen Image 2512`, `candidateCount` coerced to 1 |
| CRS runtime | FAIL — job `d1abe4af` / retry `3dde1cb7` remained `queued` |
| Character still / Schnick still / inpaint leak | NOT RUN |

## E2E TRACE — Character

| Stage | Verdict |
|---|---|
| User action | FAIL — no approved sheet or `@Name` still |
| Frontend | N/A for this live runner (API path) |
| API | PASS — generate accepted, Qwen locked |
| Backend | PASS — pack `GENERATING`, no silent model swap |
| Persistence | FAIL — no sheet asset |
| Runtime | FAIL — JobQueue did not execute |
| Result | FAIL |
| Reload | FAIL |
| Downstream | FAIL |

## E2E TRACE — Spatial (Schnick)

| Stage | Verdict |
|---|---|
| User action | PASS — Review / correct / Accept / NL parse |
| Frontend | PASS (Playwright A–H on 8760) |
| API | PASS — `/api/perception/*` on 8758 |
| Backend | PASS — draft sibling; Accept uses `place_*`; no `zones[]` |
| Persistence | PASS — draft + `userCorrections` survive GET. Extra character slot survives GET (`map-after-accept.json`). First Accept in `live-gates.json` did not write. |
| Runtime | FAIL — Schnick blocking still never generated |
| Result | FAIL — no still pixels |
| Reload | PASS for draft/slots; FAIL for still |
| Downstream | FAIL — no compile-to-pixels job `creativeContext.spatial_language` |

## E2E TRACE — Edit

| Stage | Verdict |
|---|---|
| User action | FAIL — no approved still to paint |
| Frontend | PASS (Playwright E — Smart Select does not fake a mask) |
| API / Backend | N/A — region-edit not invoked on live pixels |
| Persistence / Runtime / Result / Reload / Downstream | FAIL / N/A |

## Adoption hole

Source now refuses SHA-alone adoption (`should_adopt_studio_api` requires perception). Supervisor log `2026-08-20T16:13:29Z` recycled a healthy-but-not-current listener. This live process is **owned** (`adopted=false`), exposes perception, and reports `f51838a` + `routeContract=["perception.capability"]`.

Live `apiRevision=f51838a` ≠ cert HEAD `9a349b4` (later commits were supervisor / Playwright-runner only). A new preflight would treat SHA as not current even though perception is present. Remaining failure is JobQueue drain, not missing `/api/perception`.

Windows Beta API uses `--workers 1`.

## Tests (measured this closure)

| Suite | Result |
|---|---|
| `test_creation_perception` + identity + single-CRS + spatial / engine / attach / grounding / placement | **131 passed** |
| Frontend vitest (requestPolicy, CdSceneReview, Smart Select, CC copy) | **48 passed** |
| Playwright A–H on 8760→8758 | **8 passed, 1 flaky** (A retried green) |

## Independent verifiers

All returned `READY FOR PRIMARY REVIEW` only (Law 27: `inherit` — `gpt-5.4-medium` is not in the available Task model list).

| Role | Agent |
|---|---|
| Runtime ownership | [Runtime ownership](c772e946-7046-4e3c-a339-9bb6f4e3cdf6) |
| Backend / perception | [Backend perception](788bf6b9-ef75-4587-8f42-0a6e8cddde08) |
| Character / CRS | [CRS conditioning](d6acf1c0-36c0-4bef-a628-c60723c730b8) |
| Spatial draft → compile | [Spatial compile](b3095dbe-750c-4f01-a885-801c2cbd16a2) |
| Edit + leak | [Edit leak](169a9d04-0d02-4e19-b4f2-b4a8cda83ddf) |
| Frontend / Playwright 8760 | [Playwright 8760](d9308c4f-6111-4204-a009-6df0c911afc2) |
| Visual pixels | [Pixel inspector](5b0363ab-737b-43e5-88d1-2fcd3cb72520) — **PIXEL NOT VERIFIED** |
| Architecture + evidence | [Architecture review](08aa6dd7-504d-45e8-84c6-f5bd1ec9bd00) |

Architecture review punch list applied above: do not treat `live-gates.json` Accept as PASS; do not call LIVE API fully verified; do not claim `gpu_lease.py` is clean in the working tree; record HEAD vs `apiRevision` drift.

## Limitations (honest)

- Geometry worker not installed; Review used Visual Canon / glossary. Allowed.
- DeepSeek CRS spinner / queue-watchdog repair was not taken.
- This closure did not edit `gpu_lease.py`. The working tree may still contain unrelated dirty `gpu_lease.py` / `SpatialMapDocument` movement fields / `web_server.py` timeout from other work. Those are not Revision B cert evidence.
- Leftover Adept UI tabs on Korri flooded `:8758` with `/visual-sheet/advance` and enqueued a Korri CRS. Those queued Korri jobs were left in place to avoid overwriting production Korri.
- Live gates runner died during CRS poll; `live-gates.json` stops at `crsStart`. Follow-up GETs confirm jobs still queued.
- Unit / Playwright counts (131 / 48 / 8 passed + 1 flaky) were measured in this closure session before GPU gates; they are not checked into `evidence/` as a raw log artifact.
- `02-LIVE-CLOSURE.md`, `run_live_gates.py`, and `evidence/` were written after HEAD `9a349b4` and may still be untracked.

## Manual review

Beta left running:

- Creator UI: `http://127.0.0.1:8760/`
- Studio API: `http://127.0.0.1:8758/`

Do not certify on `:8742`.

## Binary certification

```text
NO-GO — REVISION B CREATION INTELLIGENCE NOT CERTIFIED
```

```text
NO-GO — FULL-STACK E2E NOT VERIFIED
```
