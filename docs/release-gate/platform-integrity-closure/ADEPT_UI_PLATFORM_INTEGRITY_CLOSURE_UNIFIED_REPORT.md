# Adept UI Platform Integrity Closure — Unified Report

**Governing completion report** for this mission (Law 2 / Law 30).  
Per-gate evidence lives beside this file (`00`–`18`). Binary cert extract: [`FINAL_CERTIFICATION.md`](FINAL_CERTIFICATION.md).  
Audit that authorized the work: [`../platform-audit/ADEPT_UI_PLATFORM_WIDE_INTEGRITY_AND_EVOLUTION_AUDIT.md`](../platform-audit/ADEPT_UI_PLATFORM_WIDE_INTEGRITY_AND_EVOLUTION_AUDIT.md).

| Field | Value |
|---|---|
| Date | 2026-08-30 |
| Builder | Cursor + Grok 4.6 |
| Peers (review-only) | Kimi K3, GLM 5.2 |
| Branch | `feat/character-creator-final-closure` |
| HEAD | `b6156455e643d5fa430784b3130756f2d8038651` |
| Remote / deploy | Not pushed. Not deployed. |
| Surface | CURRENT DEVELOPMENT — dirty worktree (~1500+ porcelain). Do not `git add -A`. |
| Named project (reuse) | SenseNova Integration Lab `0ffe56e2-0d58-4926-91bf-0f947898d02e` · Scene `f0b97b96-3456-4ceb-96ce-56bbece7e5b7` |
| Timed Prompt E2E project | Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278` |

---

## Verdict

```text
GO — ADEPT UI PLATFORM INTEGRITY CLOSURE + OWNER-TESTING READINESS E2E CERTIFIED
```

Both final peers: **PASS WITH NON-BLOCKING**. No FAIL. No open BLOCKING finding.  
No commit, push, merge, tag, or deploy.

---

## What this mission was

The 2026-08-29/30 platform audit concluded **CONDITIONAL / HIGH-PRIORITY REPAIRS REQUIRED**. This was a root-cause repair and owner-testing readiness pass — not a rewrite and not a second audit.

Work stayed on the dirty `feat/character-creator-final-closure` tree. Unrelated Character Creator / ERS / Timeline dirt was not mixed into a commit (no commit was authorized).

Creator UI is Vite `:5173`. Studio API is `:8758`. Retired `:8760` is not the product UI and was not killed (Law 14).

---

## Gate matrix

| Gate | Subject | Result | Evidence |
|---|---|---|---|
| Freeze | Branch, ports, GPU, PC snapshot | Done | [`00_FREEZE.md`](00_FREEZE.md) |
| A | Project-scoped asset file/thumb; unscoped **403** | **CLOSED** | [`01_SECURITY.md`](01_SECURITY.md) |
| B | One generator join (not a fourth catalog) | **CLOSED** | [`02_GENERATOR_AUTHORITY.md`](02_GENERATOR_AUTHORITY.md) |
| C | Same supervisor owns Route A adopt; GPU admission; no `:8760` start | **CLOSED** | [`03_RUNTIME_GPU.md`](03_RUNTIME_GPU.md) |
| D | `timelineMaster` authority; `auto_approve=False`; spatial projection | **CLOSED** | [`04_STATE.md`](04_STATE.md) |
| E | Home hydration; Comfy status; disabled reasons; Resume=requeue | **CLOSED** | [`05_CREATOR_TRUTH.md`](05_CREATOR_TRUTH.md) |
| F | `compile_for_generator` on W46; MiniMax subjects only if wired | **CLOSED** | [`06_KNOWLEDGE.md`](06_KNOWLEDGE.md) |
| G | MiniMax honest max **5/24 ≈ 0.21s** (not 15s) | **CLOSED** | [`07_MINIMAX_DURATION.md`](07_MINIMAX_DURATION.md) |
| H | Comfy MCP **stdio** vs live `:8188` | **CLOSED** | [`08_COMFY_MCP.md`](08_COMFY_MCP.md) · [`08_COMFY_MCP.json`](08_COMFY_MCP.json) |
| I | Hygiene — no new event bus; unused workspaces not deleted | Done | [`09_HYGIENE.md`](09_HYGIENE.md) · [`13_CODE_REMOVED.md`](13_CODE_REMOVED.md) |
| J / L | Playwright Home + Timed Prompt X | **2 passed** | [`10_PLAYWRIGHT.md`](10_PLAYWRIGHT.md) |
| K | Live LTX 2.3 I2V + measured media | **LIVE VERIFIED** | [`11_LIVE_GENERATION.md`](11_LIVE_GENERATION.md) |
| M | Reload / persist | Proven on X + LTX approve | [`12_RELOAD_PERSISTENCE.md`](12_RELOAD_PERSISTENCE.md) |
| N | Unbiased finals | Both PASS WITH NON-BLOCKING | [`14_KIMI_K3_REVIEW.md`](14_KIMI_K3_REVIEW.md) · [`15_GLM_5_2_REVIEW.md`](15_GLM_5_2_REVIEW.md) |
| O–R | Owner check, hygiene, matrix, pack | Done | [`16_REVIEW_FINDING_CLOSURE.md`](16_REVIEW_FINDING_CLOSURE.md) · [`17_FINAL_AUTHORITY_MATRIX.md`](17_FINAL_AUTHORITY_MATRIX.md) · [`18_REMAINING_NON_BLOCKING_ITEMS.md`](18_REMAINING_NON_BLOCKING_ITEMS.md) |

Per-gate peer loop: implement → test → Kimi → GLM → disposition. One BLOCKING finding from either peer would have kept the gate open. None remained.

---

## Repairs (what changed)

### Security (A)

Canonical byte routes:

- `GET /api/projects/{projectId}/assets/{assetId}/file`
- `GET /api/projects/{projectId}/assets/{assetId}/thumb`

Chain: project exists → asset exists → `asset.project_id` match → `resolve_data_file_path` → reject traversal / escape / ambiguous scope.  
Unscoped `/api/assets/{id}/file` and `/thumb` raise **403** `ASSET_SCOPE_REQUIRED`. First-party URL builders emit the scoped path.

Authority: `studio-api/app/project_security/asset_file.py`

### Generator authority (B)

`studio-api/app/production_control/generator_authority.py` is a **join**, not a fourth catalog.

- Identity: Production Control + hosted discovery  
- Execution proof: Timeline adapter registry  
- Timeline `list_generators()` is a view of that join  
- WAN / Hunyuan: `executable=False`, Unsupported  
- LTX 2.5: `executable=False`, Testing  
- Frontend `joinProductionControlVideoOptions` is a presenter; fossil dropdowns use `EngineAuthoritySelect`

Live join (end of mission): `ltx-local` Ready/exec max 20; MiniMax Testing/exec **max 0.2083**; WAN/Hunyuan/LTX 2.5 not executable.

### Runtime / GPU (C)

Same Python supervisor. Route A is `minimax_h3_route_a`. Normal `start_all` **adopts** healthy `:8192` and does not spawn Route A. Adopt never claims Adept-owned Ready. GPU admission blocks spawning a second Comfy. Product start refuses `:8760`.

**Operator trap:** `scripts/run_runtime_supervisor.py restart` often **reuses** a healthy uvicorn and does not load new Python. To pick up API edits, stop the `:8758` Adept uvicorn and start a new owned process. Do not casually `--force` (stops Comfy / Route A).

### State (D)

`timelineMaster` in `scenes.director_json` remains write authority. PUT `/director` merges. Watcher `auto_approve=False` (Generate → CandidateReady → Approve). Spatial write authority is `spatial_scenes`; `project.spatial_map_json` is a projection.

### Creator truth (E)

Home: Loading / failed / first-use / filtered — “No Projects Yet” does not show while the list is loading.  
Comfy reachable + catalog loading = **Ready · Loading Nodes**, not “Starting…”.  
Resume help = **requeue**, not mid-diffusion resume.

### Knowledge (F)

W46 `build_timeline_generation_request` calls `compile_for_generator`. Authored prompt kept in `providerOptions.authoredPrompt`. MiniMax `<subject N>` only from entity + asset + **wired** Route A slot. Current Route A `ref_images` is EXIST UNWIRED → production emits **no** subject tags. LTX/WAN/Hunyuan strip MiniMax syntax.

### MiniMax duration (G)

Route A `length` is **frame count 5** at **24 fps** → `EXPERIMENTAL_DURATION_SEC = 5/24 ≈ 0.208s`. Not 5s. Not 15s. Planned 5s batches are refused (`DURATION_EXCEEDS_GENERATOR`). Collect-result uses probed duration. No frame-loop / stretch / metadata lie.

### Timed Prompt X (J / M)

X now goes through shell `mutateTimeline` + `dropPromptIdsFromMaster` + batch PATCH. Undo/Redo use the same history (director + master prompts). GET overlay will not resurrect a tombstoned prompt.

---

## Tests (measured)

Run from `studio-api` (repo-root `pytest` fails: `ModuleNotFoundError: app`).

| Bundle | Result |
|---|---|
| A–G + LoRA kwargs (`test_project_lock_media`, `test_generator_authority`, `test_runtime_supervisor_lifecycle`, `test_timeline_auto_approve_gate`, `test_spatial_document_authority`, `test_timeline_knowledge_compile`, `test_minimax_duration_truth`, `test_ltx_leaf_graph_lora_kwargs`, `test_generator_knowledge`) | **78 passed**, 0 failed, 8.34s |
| `test_timeline_generation_adapters` + `test_production_dock` | **41 passed**, 0 failed, 28.41s |
| `node --test src/timelineMaster/draftCapabilities.test.ts` | **4 passed** |
| Playwright chromium, live `:5173` / `:8758`, `ADEPT_ALLOW_KORRI_MUTATION=1` | **2 passed**, 18.5s |

Playwright specs:

- `tests/e2e/home/home-library-hydration.spec.ts` — library hydrates; no first-use empty while projects exist  
- `tests/e2e/timeline/timeline-timed-prompt-x-canonical-delete.spec.ts` — X removes both lanes; Inspector Scene; Undo/Redo; reload persists delete  

Not run: full Vitest, full backend pytest tree. Collection-broken WIP tests were not weakened.

---

## Live generation (Gate K)

**Project reused.** No `POST /api/projects`.

| Field | Value |
|---|---|
| Batch | `bb_c1eb5212d68b` Platform Integrity LTX I2V |
| Generator | `ltx-local` |
| Runtime | `ltx-2.3-22b-distilled-fp8.safetensors` · workflow `ltx.simple_i2v` |
| Path | Generate → CandidateReady → Approve (`candidateId` required) |
| After approve | **Approved** · `approvedClip.assetId` `ffd1e38a-ccad-4d5b-9688-c5b485cb652d` |
| File | `data/projects/0ffe56e2-…/renders/scene_0_98400655.mp4` |
| Scoped file | **200** `video/mp4` 688043 bytes |
| Unscoped file | **403** |
| **ffprobe** | 1280×704 · 24 fps · **113 frames** · **4.708s** |

Do not certify take-state `512x288`. Measured media is 1280×704.

The first walk script set `"ok": true` after a **Failed** poll. That flag is a lie. Authoritative result is the Approved batch + ffprobe. See [`10_E2E.md`](10_E2E.md).

MiniMax: no 15s claim, no new generate this closure. Honest advertised max **0.208s**.

---

## E2E TRACE

| Stage | Result |
|---|---|
| User action | Home library + Timeline X + SenseNova LTX Generate / Approve |
| Frontend | Vite `:5173` 200; SenseNova / Schnick cards after load; Timed Prompt X |
| API | `:8758/api/healthz` 200; scoped file 200; unscoped 403 |
| Backend | W46 `ltx-local`; `auto_approve=False`; approve needs `candidateId` |
| Persistence | `timelineMaster` + director; batch Approved |
| Runtime | Comfy Desktop `:8188`; distilled LTX 2.3 |
| Result | MP4 688043 bytes; ffprobe 4.708s |
| Reload | X stays gone; Approved batch still Approved |
| Downstream | Library row present; scoped playback 200 |

---

## Peer supervision

| Gate | Kimi K3 | GLM 5.2 |
|---|---|---|
| A | PASS WITH NON-BLOCKING (`bfc64016`) | PASS WITH NON-BLOCKING (`5980f759`) |
| B | PASS WITH NON-BLOCKING (`b9c442a5`) | PASS WITH NON-BLOCKING (`f9fb54a7`) |
| C | PASS WITH NON-BLOCKING (`21301c27`) | PASS WITH NON-BLOCKING (`8eb5c359`) |
| D | PASS WITH NON-BLOCKING (`898c6442`) | PASS WITH NON-BLOCKING (`7650bdce`) |
| E | PASS WITH NON-BLOCKING (`159c851a`) | PASS WITH NON-BLOCKING (`784c2ec3`) |
| F | PASS WITH NON-BLOCKING (`bee0819a`) | **PASS** (`ac605263`) |
| G | PASS WITH NON-BLOCKING (`47921dfb`) | PASS WITH NON-BLOCKING (`8bb07cc7`) |
| H | **PASS** (`f5cca296`) | **PASS** (`7b99191e`) |
| Final (N) | PASS WITH NON-BLOCKING (`eda327f4`) | PASS WITH NON-BLOCKING (`a8130809`) |

Every material finding: **FIXED / DISPROVEN / ACCEPTED NON-BLOCKING**. Ledger: [`16_REVIEW_FINDING_CLOSURE.md`](16_REVIEW_FINDING_CLOSURE.md).

---

## Authority (short)

| Domain | Write authority | Must not |
|---|---|---|
| Asset bytes | Scoped file/thumb + `resolve_data_file_path` | Unscoped UUID fetch |
| Generator identity | PC + hosted via the join | Second Timeline catalog |
| Executable | Adapter **and** install/runtime | Certified ⇒ Ready |
| Timeline | `timelineMaster` | Auto-approve; X that leaves master |
| Spatial scene | `spatial_scenes` | Two write authorities |
| MiniMax duration | Route A frames/fps `5/24` | 15s without measured media |
| Prompt compile | `compile_for_generator` on W46 | Decorative `<subject N>` |
| Runtime | Same supervisor | Second supervisor as product start |

Full matrix: [`17_FINAL_AUTHORITY_MATRIX.md`](17_FINAL_AUTHORITY_MATRIX.md).

---

## High-signal files

**Backend:** `project_security/asset_file.py`, `production_control/generator_authority.py`, `runtime_supervisor/services.py` + `gpu_admission.py`, `director_timeline_w46/generation/watcher.py`, `orchestrator.py`, `spatial_scene.py`, `generation/request_builder.py`, `codirector/generator_knowledge/compiler.py`, `minimax_h3/route_a_adapter.py`, `video_runtime/workflow_execute.py` (`lora_name` / `lora_strength` on `build_leaf_graph`).

**Frontend:** `Home.tsx`, `helpCatalog.ts`, `contracts/minimaxH3.ts`, `DirectorTracks.tsx`, `timeline-master/TimelineEditorShell.tsx`, `TimelineInspector.tsx`, `timelineMutateBridge.ts`, `EngineAuthoritySelect` / `draftCapabilities.ts`.

**Tests / scripts:** `test_project_lock_media.py`, `test_generator_authority.py`, `test_runtime_supervisor_lifecycle.py`, `test_timeline_auto_approve_gate.py`, `test_spatial_document_authority.py`, `test_timeline_knowledge_compile.py`, `test_minimax_duration_truth.py`, `test_ltx_leaf_graph_lora_kwargs.py`, `tests/e2e/home/home-library-hydration.spec.ts`, `tests/e2e/timeline/timeline-timed-prompt-x-canonical-delete.spec.ts`, `scripts/_platform_integrity_comfy_mcp.py`.

---

## Live URLs (left running)

| Surface | URL |
|---|---|
| Creator UI | `http://127.0.0.1:5173/` |
| Studio API | `http://127.0.0.1:8758/` |
| Comfy (implementation) | `http://127.0.0.1:8188/` — do not send creators here |
| MiniMax Route A | `http://127.0.0.1:8192/` — external / adopted |

Do **not** open `:8760` as the product UI.

### Owner-testing path

1. Open `http://127.0.0.1:5173/`. Confirm Your library shows existing projects (SenseNova, Schnick) — not “No Projects Yet” while loading.  
2. Open **SenseNova Integration Lab** → Timeline. Generator list: LTX 2.3 Ready; LTX 2.5 / WAN / Hunyuan not executable; MiniMax Testing ~0.21s.  
3. Approved LTX batch `bb_c1eb5212d68b` should still be Approved; Library playback via the **project-scoped** file URL.  
4. On Schnick Coffee, Timed Prompt **X** should remove the clip from the track and Inspector; Undo restores; reload keeps the delete.  
5. Do not plan MiniMax at 5s or 15s — the API will refuse. Expect ~0.21s if you generate Route A.  
6. After API code edits, do not trust `supervisor restart` alone — confirm MiniMax `maxDurationSec` is `0.208…` before treating the live process as current.

---

## Limitations (non-blocking)

Full list: [`18_REMAINING_NON_BLOCKING_ITEMS.md`](18_REMAINING_NON_BLOCKING_ITEMS.md).

Highest-signal for the owner:

- Supervisor `restart` may reuse uvicorn and **not** load new Python.  
- `Start-AdeptUI-H3-RouteA.ps1` can spawn Route A without GPU admission.  
- Character / Prop / Spatial / ERS / Retake / Stop were not re-walked in Playwright this pass.  
- No MiniMax 15s media (honest — Route A is ~0.21s).  
- Library tag / `approvalState` can lag Timeline Approve.  
- Dirty tree not committed.  
- Tracked `library-refs-accordion.spec.ts` still hits the retired unscoped file route.

---

## Release safety

The owner decides commit / push / deploy. This mission did **not** commit.

If committing later: stage only Platform Integrity files. Do not `git add -A` (Character Creator / ERS / `.runtime` dirt is mixed in the tree).
