# Adept UI — Timeline Certified Update: Commit + Git + Vercel Release

**Law 30:** This is the single governing document for the Timeline certified-state **commit / push / Vercel deploy** milestone.  
**E2E certification remains:** [TIMELINE_MASTER_PRODUCTION_CONTROL_COMFY_MCP_CERTIFICATION.md](./TIMELINE_MASTER_PRODUCTION_CONTROL_COMFY_MCP_CERTIFICATION.md)  
**Do not cite as current E2E truth:** [TIMELINE_MASTER_FULL_STACK_SNAP_ZOOM_COMFY_CERTIFICATION.md](./TIMELINE_MASTER_FULL_STACK_SNAP_ZOOM_COMFY_CERTIFICATION.md) (HISTORICAL)

**Date:** 2026-08-29  
**Mission:** Preserve the certified Timeline state exactly — audit → test → commit → push → deploy → smoke → report.  
**No new Timeline / ERS / Footer Dock / generator features were added.**

---

## Verdict

`GO — ADEPT UI TIMELINE CERTIFIED UPDATE COMMITTED + PUSHED + VERCEL DEPLOYED`

---

## Environment

```text
Release branch:      release/timeline-fullstack-comfy-mcp
Release worktree:    C:\AdeptFilmWorks\AIVideoStudio-timeline-release
Remote:              origin  https://github.com/bradjohnson79/adeptui.git
Milestone commit:    b57572e115ec10230c47324f30b5c7cb0710e166
Vercel tsc repair:   6c1a369913c4cc5b479d36eadfcf7f67d63c8944   ← remote HEAD
Parent SHA:          b6156455e643d5fa430784b3130756f2d8038651
                     (feat/character-creator-final-closure at isolation time)

Vercel project:      adeptui  (prj_1NHSYLrFYQM3rIXyHwKUpezprbsx)
Production URL:      https://adeptui.vercel.app
Production deploy:   dpl_6DikNgG7d8pRLyJ9qyN3ve5Gkqwx
                     https://adeptui-9yhvu8uhe-anoint.vercel.app  READY
Production bundle:   /assets/index-C-qQwIBw.js
Preview URL:         https://adeptui-rkxdayyxb-anoint.vercel.app  READY
Preview deploy:      dpl_5kYBieFgc5SRZDV6HB2Rrc9urXYc
Branch alias:        https://adeptui-git-release-timeline-fullstack-comfy-mcp-anoint.vercel.app
Failed preview:      https://adeptui-73nd2t88p-anoint.vercel.app  ERROR (b57572e tsc)

Local creator UI:    http://127.0.0.1:5173/
Studio API:          http://127.0.0.1:8758/
Comfy:               http://127.0.0.1:8188/

Cert project:        SenseNova Integration Lab  0ffe56e2-0d58-4926-91bf-0f947898d02e
Scene 1:             f0b97b96-3456-4ceb-96ce-56bbece7e5b7
Jacob:               10303eba-ed95-49fe-a86b-e5493b7a1c75
Hero still:          90e8c04a-c9c0-4016-85e6-95dc7d1a967e
                     → studio/imagegen_edit_97271e7a.png
Hosted smoke project: 2347bf46-3762-4763-86c5-4a6032522278  (shell / Timeline route only)
```

Git tags were **not** created. Current practice is `checkpoint/*`; a one-off `timeline-fullstack-comfy-cert-2026-08-29` tag was not invented.

---

## What this release preserves

Certified E2E verdict (unchanged):

`GO — ADEPT UI TIMELINE FULL-STACK + PRODUCTION CONTROL + COMFY MCP E2E CERTIFIED`

Preserved behavior (not weakened for deploy convenience):

- Timeline Video Generator inventory is Production Control (`GET /api/production-control/models?modality=video`)
- LTX 2.3 Local (`ltx-local`) is truthfully I2V-only; LTX T2V stays disabled; silent `ltx.scene` T2V fallback stays removed
- Legal LTX size is **1280×704** through capability → compile → worker → Comfy MCP → executed graph → MP4
- MiniMax Route A remains honestly **not ready** (no Route B substitution)
- Scene Prompt, Timed Prompt, and Camera reach live generation / CLIP conditioning
- Jacob approved hero reaches the correct Comfy image input
- Stop cancels a live Comfy job; Resume re-queues batches (does not pretend to resume cancelled inference)
- Retake creates a new candidate without replacing the approved take
- Snap, Zoom, and Video Generator selector remain repaired
- `requestCache` modality / query-string isolation remains intact
- Temperature replaces Weight in the creator chrome
- Library / References persistence remains intact
- Raw traceback UX stays cleaned; cancellation is terminal

Hosted Vercel smoke is **deployment integrity**, not a second Comfy generation cert.

---

## Isolation method

The main checkout on `feat/character-creator-final-closure` was a mixed dirty tree (~1900 changed files). **`git add -A` was not used.**

Certified files were copied into a clean worktree from `b6156455` and committed there only:

```text
Worktree:  C:\AdeptFilmWorks\AIVideoStudio-timeline-release
Branch:    release/timeline-fullstack-comfy-mcp
```

The main working tree was not overwritten. Other agents' Korri CRS, GPT Image 2 ERS, Occupied, Scene Creator, website, and Adept Bots work remains in that dirty tree.

Surgical slices (not the mixed main-tree files):

- `studio-web/src/api.ts` — `directorTimelineApproveBatch` in commit 1; `directorTimelinePutMaster` in commit 2
- `studio-api/app/queue_worker.py` — Timeline compile width/height pass-through when `timelineGeneration=True`; silent LTX T2V fallback remains removed

---

## Working tree audit

| Class | Decision | Examples |
|---|---|---|
| **A. Certified Timeline** | Keep | Timeline Master UI, cinematography, `director_timeline_w46`, LTX capability/resolution, Stop/Resume/Retake, snap/zoom, Video Generator, Playwright, governing E2E report + MCP evidence |
| **B. Required shared infrastructure** | Keep | Production Control join / `filterByModality`, `requestCache`, `projectJobsStore`, preview-failure copy, scene-scoped reference remapping, track control state, library asset filter |
| **C. Unrelated concurrent work** | Exclude | Korri CRS Rev 3, GPT Image 2 ERS, Occupied, Scene Creator extras, website, Adept Bots, full mixed `api.ts` / `queue_worker.py` from the main tree |
| **D. Temporary / debug / generated** | Exclude | `.runtime` pids, tmp/bak scripts, worktree `ai-video-studio: file:..` npm link, `scripts/_timeline_ltx_mcp_inspect.py` (gitignored) |

---

## Files committed (by subsystem)

### Commit 1 — `b57572e` (74 files, +7752 / −482)

```text
feat(timeline): certify full-stack Production Control and Comfy MCP workflow
```

- **Docs / evidence:** governing E2E report; superseded snap/zoom report marked HISTORICAL; `evidence/mcp_06ef7737.json`; `graph_06ef7737.json`; `http_cb204ad3_first_generate.json`
- **API:** `cinematography/*`; `director_timeline_w46` capability / adapters / request_builder / orchestrator / router / reconcile; LTX builder 1280×704 + I2V truth; Timeline tests
- **Web:** Timeline Master (Video Generator dock, Inspector Approve, Temperature, timed prompt, camera, snap/zoom); Production Control `filterByModality`; `requestCache`; `useTimelineVideoGenerators`
- **E2E:** `tests/e2e/timeline/timeline-master-snap-zoom-generator.spec.ts`

### Commit 2 — `6c1a369` (16 files, +1000 / −79)

```text
fix(timeline): include sibling contracts required for Vercel TypeScript build
```

Release-blocker repair only. Git preview of `b57572e` failed `tsc -b` because isolation omitted siblings the certified UI already imported.

- `directorTimelinePutMaster`
- Job optional error fields (`jobId`, `reasonCode`, `errorCode`, `errorMessage`, `internalJobId`)
- `TimelineTrackLabel` control state
- `AssetTray` `libraryAssetIds`
- `projectJobsStore` + tests
- `livePreviewFailure` + tests
- `remapBindingIdsToSceneScope` / `siblingBindings`
- Type-only Character Creator unused/narrowing fixes so a clean clone can `tsc -b`
- Unreachable Video Generator `else` removed (no runtime change)

---

## Tests

| Gate | When | Result |
|---|---|---|
| API Timeline resolution / camera / temperature | Before commit 1 | **24 passed** |
| Frontend certified Vitest set | Before commit 1 | **46 passed** |
| Playwright live Timeline (`:5173` / `:8758`) | Before commit 1 | **6 passed** (~1.2m) |
| Focused Vitest after sibling commit | After commit 2 | **50 passed** (added jobs-store, preview-failure, sibling-scope reference cases) |

Playwright was not re-run after commit 2. Those sibling files were already in the certified working tree Playwright used. No generation contract changed after MCP evidence.

Local worktree production build after commit 2: `tsc -b && vite build` **succeeded** (bundle `index-DyEJqfaa.js`).

---

## Runtime health

Observed at release time:

| Surface | Result |
|---|---|
| `http://127.0.0.1:8758/api/healthz` | **200** |
| `http://127.0.0.1:5173/` | **200** |
| `http://127.0.0.1:8188` | Down during commit/deploy (supervisor restart failed: Comfy not healthy within 45s). Later probe **200**. |

No expensive LTX generation was re-run. Prior MCP / live-generation evidence remains the E2E record.

---

## Diff hygiene and secrets

**Secrets audit: PASS**

Scanned the release diffs for API keys, tokens, auth headers, signed URLs, passwords, provider credentials, and machine-specific `C:\Users\...` paths.

- MCP evidence local argv paths were redacted to `[REDACTED_LOCAL_PATH]` before commit
- Worktree `package.json` `ai-video-studio: file:..` link was **not** committed
- Vercel-downloaded `.env.production.local` was **not** committed
- Production JS scan: `127.0.0.1:8188` = 0, `localhost:8188` = 0, `C:\Users\bradj` = 0
- Production JS contains `productionControlModels` (3), `directorTimelinePutMaster` (2), `requestCache` (1)

---

## Push

```text
Normal push only. No --force. Not detached HEAD.

b57572e1..6c1a3699  HEAD -> release/timeline-fullstack-comfy-mcp

Local HEAD:   6c1a369913c4cc5b479d36eadfcf7f67d63c8944
Remote HEAD:  6c1a369913c4cc5b479d36eadfcf7f67d63c8944
```

GitHub: https://github.com/bradjohnson79/adeptui/tree/release/timeline-fullstack-comfy-mcp

---

## Vercel

Canonical workflow: existing project **adeptui** (not `studio-web` / `prj_7a3WAZPPdj6Yjp1lRHgcsfh3EjhW`). Git push creates a preview; production was assigned to the same SHA.

| Deployment | SHA | Env | Status | Duration |
|---|---|---|---|---|
| `adeptui-73nd2t88p-anoint.vercel.app` | `b57572e` | Preview | **Error** | 39s — `tsc -b` missing siblings |
| `adeptui-rkxdayyxb-anoint.vercel.app` | `6c1a369` | Preview | **Ready** | 56s |
| `adeptui-9yhvu8uhe-anoint.vercel.app` | `6c1a369` | Production | **Ready** | 44s — aliases `adeptui.vercel.app` |

GitHub deployment records:

```text
Preview     6160377026  sha 6c1a369913c4cc5b479d36eadfcf7f67d63c8944  2026-08-29T21:36:42Z
Production  6160384459  sha 6c1a369913c4cc5b479d36eadfcf7f67d63c8944  2026-08-29T21:37:40Z
```

The deployed frontend does not bake local Comfy `:8188` or machine paths. Local runtimes remain Desktop / Studio API concerns. Hosted status copy may still report Comfy unavailability from the live API — that is runtime status, not a baked generation target.

---

## Live smoke

**PASS** — deployment integrity, not hosted Comfy generation.

| Check | Result |
|---|---|
| App loads | Adept UI Studio home, `#root`, Co-Director dock, Production menu |
| `vercel curl https://adeptui.vercel.app/` | Title Adept UI Studio, `#root`, `/assets/index-C-qQwIBw.js` |
| Timeline route | `https://adeptui.vercel.app/project/2347bf46-3762-4763-86c5-4a6032522278?workspace=timeline` |
| Timeline shell | `timeline-editor-shell`, Generate, Resume, snap, zoom |
| Video Generator | `timeline-video-generator-select` |
| Production Control dock | `production-control-dock` |
| Hydration / missing chunks | None observed |
| Console on Timeline route | No blocking errors in the smoke collector |

Unauthenticated raw HTTP to `*.vercel.app` can hit the Vercel Authentication wall. Authenticated `vercel curl` and the in-IDE browser returned the real Adept UI document.

---

## Certification docs

| Path | Role |
|---|---|
| [TIMELINE_MASTER_PRODUCTION_CONTROL_COMFY_MCP_CERTIFICATION.md](./TIMELINE_MASTER_PRODUCTION_CONTROL_COMFY_MCP_CERTIFICATION.md) | Governing **E2E** document |
| [evidence/mcp_06ef7737.json](./evidence/mcp_06ef7737.json) | Comfy MCP evidence (retake `06ef7737-…`) |
| [evidence/graph_06ef7737.json](./evidence/graph_06ef7737.json) | Executed graph |
| [evidence/http_cb204ad3_first_generate.json](./evidence/http_cb204ad3_first_generate.json) | First generate HTTP capture |
| [TIMELINE_MASTER_FULL_STACK_SNAP_ZOOM_COMFY_CERTIFICATION.md](./TIMELINE_MASTER_FULL_STACK_SNAP_ZOOM_COMFY_CERTIFICATION.md) | HISTORICAL — superseded |

---

## Unrelated work left uncommitted

The main checkout `feat/character-creator-final-closure` remains dirty. Intentionally **not** part of this release:

- Character Creator / CRS / ERS / Occupied / Korri mixed edits
- Full mixed `studio-web/src/api.ts` and `studio-api/app/queue_worker.py`
- `.runtime` pids and supervisor state
- tmp / bak scripts
- Unrelated Scene Creator, website, and Adept Bots files
- Older docs under `timeline-continuity` / `timeline-final`

Do not call that working tree clean.

---

## E2E TRACE (this release mission)

This mission is Git + Vercel preservation, not a second Comfy generation cert.

| Stage | Verdict | Evidence |
|---|---|---|
| User action | PASS | Isolation → test → commit → push → deploy → hosted smoke |
| Frontend | PASS | Timeline / Production Control / requestCache in `6c1a369`; hosted Timeline route loads |
| API | N/A | Studio API is local/Desktop; Vercel ships the web frontend |
| Backend | N/A | No new API behavior after E2E evidence |
| Persistence | PASS | Certified code + docs + evidence are on `origin/release/timeline-fullstack-comfy-mcp` |
| Runtime | N/A | Hosted UI must not assume local Comfy; local Comfy evidence stays in the E2E report |
| Result | PASS | Production Ready on `adeptui.vercel.app` @ `6c1a369` |
| Reload | PASS | Hosted Timeline route hydrates and stays up |
| Downstream | N/A | No hosted Comfy generate attempted |

---

## Mandatory checklist

```text
[x] Branch + starting SHA verified (isolated from b6156455)
[x] Contracts preserved (PC authority, LTX I2V/1280×704, Stop/Resume, no MiniMax fake-ready)
[x] Certified Timeline state committed (not the mixed main tree)
[x] Visible Timeline controls not redesigned
[x] Real prior Comfy MCP evidence retained; no mock completion
[x] Hosted frontend loads after deploy
[x] Secrets not committed
[x] API 24 / Vitest 46 / Playwright 6 measured before commit 1
[x] Production tsc + Vite build succeeded after sibling repair
[x] Beta/local URLs reported; Vercel production URL reported
[x] Limitations honest (Comfy down during deploy window; Playwright not re-run after commit 2)
[x] Verdict binary: GO
[x] No localhost Comfy baked into the Vercel bundle
[x] One governing doc for this release milestone; E2E cert remains the E2E governing doc
[x] Creator workflows stay inside Adept UI (Law 29)
```

---

## Limitations

1. This report certifies **commit + push + Vercel frontend deploy**, not a new live LTX generation.
2. Comfy was down during the deploy window. Later local `:8188` returned 200. MCP evidence from the E2E cert is still the generation record.
3. Playwright 6 was measured on the certified dirty tree before isolation, not re-run on `6c1a369`.
4. Character Creator unused/narrowing edits in commit 2 are `tsc -b` unblockers only. They do not ship the uncommitted CRS/ERS work left on the main tree.
5. Production on `adeptui.vercel.app` is now this Timeline release SHA. It does **not** include uncommitted Character Creator / ERS work still sitting in the main working tree.
6. MiniMax Route A is still not operational.

---

## Manual review

1. Open https://adeptui.vercel.app — confirm Adept UI Studio home (Vercel SSO may apply to unauthenticated browsers).
2. Open Timeline: `https://adeptui.vercel.app/project/2347bf46-3762-4763-86c5-4a6032522278?workspace=timeline` — confirm Video Generator, snap, zoom, Production Control dock. Do **not** treat hosted Generate as local Comfy certification.
3. Local review: `http://127.0.0.1:5173/` + `http://127.0.0.1:8758/` + Comfy `:8188`.
4. Git recovery: `git fetch origin && git checkout release/timeline-fullstack-comfy-mcp` @ `6c1a369`.
5. E2E behavior detail: [TIMELINE_MASTER_PRODUCTION_CONTROL_COMFY_MCP_CERTIFICATION.md](./TIMELINE_MASTER_PRODUCTION_CONTROL_COMFY_MCP_CERTIFICATION.md).

---

## Final verdict

`GO — ADEPT UI TIMELINE CERTIFIED UPDATE COMMITTED + PUSHED + VERCEL DEPLOYED`
