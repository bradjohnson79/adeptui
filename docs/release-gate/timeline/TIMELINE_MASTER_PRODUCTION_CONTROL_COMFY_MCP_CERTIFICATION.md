# Timeline Master — Production Control + Comfy MCP Closure

**Status:** Governing document for this milestone (Law 30).  
**Date:** 2026-08-29  
**Branch:** `feat/character-creator-final-closure`  
**HEAD (repo):** `b6156455e643d5fa430784b3130756f2d8038651`  
**Working tree:** this closure is implemented on the dirty tree above that SHA (not a separate commit).  
**Cert project (reuse only):** SenseNova Integration Lab `0ffe56e2-0d58-4926-91bf-0f947898d02e`  
**Scene 1:** `f0b97b96-3456-4ceb-96ce-56bbece7e5b7`  
**Jacob:** `10303eba-ed95-49fe-a86b-e5493b7a1c75`  
**Hero start still:** `90e8c04a-c9c0-4016-85e6-95dc7d1a967e` → `studio/imagegen_edit_97271e7a.png`  
**Local review URLs:** creator UI `http://127.0.0.1:5173/` · Studio API `http://127.0.0.1:8758/` · Comfy `:8188`  
**Runtime after last force restart:** Studio API PID 20404 · Comfy PID 67896

Supersedes `TIMELINE_MASTER_FULL_STACK_SNAP_ZOOM_COMFY_CERTIFICATION.md` (now HISTORICAL). Grok Bot API-side job `23888b26` / `scene_0_a2fa5849.mp4` at 1920×1056 is **not** this certification.

---

## Verdict

`GO — ADEPT UI TIMELINE FULL-STACK + PRODUCTION CONTROL + COMFY MCP E2E CERTIFIED`

---

## ROOT CAUSES

1. **Two video inventories.** Footer Dock used Production Control. Timeline Video Generator used `/api/director-timeline/generators` + adapter IDs. Labels drifted (`LTX 2.5` vs PC `LTX 2.3`).
2. **Three resolution authorities.** Compile invented draft `512×288` via `PRODUCTION_PIXELS`. Worker ignored compile and used `resolve_scene_dims` (1280×720 or project 1920 → 1920×1056). LTX then silently snapped height `/32`.
3. **LTX T2V advertised, I2V required.** Adapter `supportsTextToVideo=True` while `ltx.simple_i2v` needs `LoadImage`. Silent `ltx.scene` T2V fallback had already been removed; capability still lied.
4. **Duration clocks.** Header used scene `duration_sec` (5s) while the board is two 5s batches (10s) and the generator max is 20s.
5. **MiniMax executable guess.** Timeline adapters hardcoded `executable=True` while Production Control and Route A `:8192` said Requires Setup.
6. **720 claimed, 704 delivered.** First live Timeline generate sent `LTXVImgToVideo` height 720; ffprobe of `batch_bb_0b021_00002.mp4` is **1280×704**. LTX 2.5 builder already documented this (`1280x720` → latent height 45, not divisible by patch 2).

---

## PRODUCTION CONTROL AUTHORITY

Canonical identity, display name, modality, installed, local/API, and executable come from:

`model_registry.list_models(modality)` → `GET /api/production-control/models?modality=video`

Footer Dock and Timeline Video Generator are two consumers of that list. Grok Bot’s `api.productionControlModels` + `sectionsFromProductionControlModels` + `requestCache` query-string keys were **consumed, not forked**.

---

## OLD TIMELINE GENERATOR AUTHORITY

`GET /api/director-timeline/generators` + `director_timeline_w46/capabilities.py` + adapter registry.

**A — moved to Production Control:** id, label, modality, installed, executable.  
**B — kept, keyed by PC id:** duration max, T2V/I2V, start-frame, FPS, resolutions, references, camera/prompt, Comfy leaf.  
**C — not deleted:** adapters, preflight, compile, watcher. The old list is no longer the picker inventory.

Aliases (not a third product inventory): `ltx` / `ltx-2.5-*` → `ltx-local`; `minimax-h3` → `minimax-h3-t2v-local`. WAN / Hunyuan / Veo appear in PC but have no Timeline adapter, so the picker filters them.

---

## CODE REMOVED

- Timeline picker calls to `api.directorTimelineGenerators()` in Video Generator dock, Inspector, toolbar, Director tracks, Timed Prompt modal, Inpaint workspace.
- LTX advertised T2V and `:8188 refused` stale notes.
- Compile draft `512×288` invention for LTX.
- Worker `resolve_scene_dims` override when `timelineGeneration=True`.
- MiniMax adapter hardcoded `executable=True`.

Not removed: adapter/preflight/compile stack; `requestCache` query keys; navy Idle monitor; Temperature-not-Weight; silent `ltx.scene` T2V fallback stays gone.

---

## NEW SHARED AUTHORITY

- Frontend: `joinProductionControlVideoOptions()` + `useTimelineVideoGenerators`.
- Backend compile: adapter `finalResolution` / `supportedResolutions`.
- Worker: `params.width/height` or `params.resolution` for Timeline jobs.
- LTX builder: `_snap_ltx_25_spatial` so 720 cannot re-enter the graph.

---

## TIMELINE CAPABILITY CONTRACT

| Field | LTX 2.3 (Local) `ltx-local` | MiniMax H3 |
|---|---|---|
| PC label | LTX 2.3 (Local) | MiniMax H3 |
| T2V | False (no Adept T2V leaf) | True if Route A up |
| I2V | True, start image required | adapter-specific |
| Resolution | **1280×704** only | 480×256 when executable |
| Duration | 5 / 8 / 10 / 15 / 20s max | adapter |
| Executable | Comfy `:8188` probe | `route_a_executable()` — **False** today |

---

## COMFY MCP BEFORE

`COMFY MCP LIVE: PASS` against Desktop 0.32.0, RTX 5090, PyTorch `2.10.0+cu130`, ~1997 nodes.

Installed checkpoints include `ltx-2.3-22b-dev-fp8.safetensors` and `ltx-2.3-22b-distilled-fp8.safetensors`. Canonical Adept leaf is `ltx.simple_i2v` (`LTXVImgToVideo` + `LoadImage` + `CLIPTextEncode`). No certified Adept LTX T2V path. Route A `:8192` down. Supervisor does not own `:8192`.

---

## REPAIRS

- Timeline Video Generator consumes PC `modality=video`.
- LTX capability I2V-only, label **LTX 2.3 (Local)**, proven size **1280×704**.
- Compile + worker + `build_ltx_simple_i2v` snap `/32`.
- Header duration = board sum (`timelineBoardDurationSec`).
- MiniMax executable from Route A readiness.
- Preflight blocks `empty_required_start_frame` even in `warnings_only`.
- Resume copy: re-queue Cancelled/Failed batches — not Comfy mid-prompt resume.
- Inspector **Approve this take** → `POST .../approve` (same lock as activate-take).

---

## COMFY MCP AFTER

Stdio `data/venvs/mcp/Scripts/comfy-mcp.exe` against live `:8188`.

Retake prompt `06ef7737-08b9-4ea7-9d19-98971b9a3f7c`:

- MCP `job` status **completed**
- MCP `validate_workflow` **valid**, 0 errors
- MCP `system_stats`: Comfy 0.32.0, RTX 5090, `2.10.0+cu130`
- Evidence: `docs/release-gate/timeline/evidence/mcp_06ef7737.json`

First Timeline generate `cb204ad3-72b0-4a91-bec5-9d63748fb3f2` was inspected over `/history` before `--force` restarted Comfy (history evicted). Capture: `docs/release-gate/timeline/evidence/http_cb204ad3_first_generate.json`.

---

## LIVE LTX E2E

Browser on `http://127.0.0.1:5173/project/0ffe56e2-0d58-4926-91bf-0f947898d02e?workspace=timeline`:

1. Video Generator = **LTX 2.3 — Local · 20s** (`ltx-local`).
2. Generate Scene clicked (header). Batch 1 job `job_144b6becb95e` / Comfy `cb204ad3-…` succeeded.
3. Batch 2 sequential-chain completed and auto-approved (watcher `auto_approve=not draft`).
4. Camera Inspector set Close Up / 35mm / Jacob / Dramatic; persisted on director clip `8dhmabeh`.
5. New take submitted; **Stop** cancelled `job_6ef69883415a`; Comfy queue empty; approved take **unchanged**.
6. Resume re-queued Batch 1 to **Ready** (Batch 2 stayed Approved).
7. Generate Scene submitted `job_4b17defa2e2b` / Comfy `06ef7737-…`.
8. Take C `e2aa3a76-f25b-4aaf-abd1-fd5a6d21f302` is a new candidate. Approved Take B asset **`6b9f9db1-15c4-4c72-9cf7-f9c0d8f74910` was not replaced**.

---

## RESOLUTION MATCH

| Stage | First generate | Camera retake (authority) |
|---|---|---|
| Capability / compile | 1280×720 (then repaired) | **1280×704** |
| `LTXVImgToVideo` | 1280×720 | **1280×704** |
| ffprobe MP4 | 1280×704 | **1280×704** |

Retake output: `batch_bb_0b021_00003.mp4` · 1280×704 · 113 frames · 24 fps · 4.708s.

---

## DURATION MATCH

- Generator max: 20s (picker label).
- Jacob board: Batch 1 5s + Batch 2 5s = **10.0s** header (`data-board-duration`).
- Graph: 5s × 24 fps → LTX `8n+1` = **113** frames → 4.708s media for a 5.0s planned batch.

---

## PROMPT MATCH

CLIP includes the Jacob Observatory scene prompt plus Co-Director continuity lines (`UNCHANGED FACTS` / M2 / M3). Negative CLIP: `blurry, low quality, watermark`.

---

## CAMERA MATCH

Retake CLIP (MCP + history):

`Camera: Close Up, 35mm, dolly in on dolly, lighting: Dramatic, focus on @SpecialAgentJacobBarnes`

First generate CLIP had only `Camera: dolly in on dolly` (shot/lens/focus/lighting were empty). Fields set in Inspector reached the executed graph on Retake.

---

## REFERENCE MATCH

`LoadImage.image` = `studio/imagegen_edit_97271e7a.png` (Jacob hero `90e8c04a-…`). Start anchor on Batch 1. Optional supporting-reference preflight warning only — did not block.

---

## SNAP

Playwright: Snap ON magnetizes to a Batch edge; Snap OFF allows free positioning. Magnetic, not a wall.

---

## ZOOM

Playwright: slider **0.20×**, **1.00×**, **5.00×**; clip times unchanged on API and DOM.

---

## BUTTON AUDIT

Exercised live or in Playwright: Video Generator, Add Scene (visible), Library, References, Fit, viewer size, aspect, Guides, Pause Viewer, Focus Timeline, Reset Layout, Image Planning, Video Finishing, Preflight, Generate, Stop, Resume, track hide/lock, Snap, Zoom, Timed Prompt, Camera, New take, Approve this take (wired; first finals auto-approve), Inspector take list, Preview (completed MP4 in monitor / Library `batch_bb_0b021-*`).

Full Screen / Temperature / Undo-Redo were not blocking this LTX path. MiniMax remains not-ready (control disabled in picker).

---

## PLAYWRIGHT

`npx playwright test tests/e2e/timeline/timeline-master-snap-zoom-generator.spec.ts` against live `:5173` / `:8758`:

**6 passed (58.4s)**

PC join + LTX persist, header 10.0s, zoom endpoints, snap ON/OFF, safe controls including New take, Resume re-queue copy.

Generate / Retake / Stop were **browser-driven on the same Jacob Timeline**, not Playwright clicks.

---

## REGRESSIONS

- Frontend Vitest: **46 passed** (`requestCache` query-key isolation, duration, control contract).
- API: `test_timeline_resolution_authority.py` + `test_timeline_prompt_temperature_camera.py` — **24 passed**.
- MiniMax validate now fail-closes when Route A is down (test updated; does not restore fake executable).
- Silent `ltx.scene` T2V fallback remains removed.
- `requestCache` still keys on the full query string.

---

## REMAINING BLOCKERS

None mandatory for this LTX + PC + MCP gate.

Disclosed, not blockers:

- MiniMax Route A `:8192` still down — picker shows not ready; no Route B.
- LTX T2V is not installed — capability False; no silent I2V fallback.
- First-final watcher auto-approve still exists; Retake does **not** auto-replace the locked take.
- Attention banner **Show it** navigates to `/project/:id` without `workspace=timeline` (out of this picker/compile scope).
- `GET /api/director-timeline/generators` remains a capability catalog, not a second picker.

---

## Comfy MCP contract matrix

| Control | Timeline | Compile | API | Adapter | MCP / executed graph | Result |
|---|---|---|---|---|---|---|
| Generator | PC `ltx-local` | `ltx-local` | `ltx-local` | LTX 2.3 I2V | `ltx-2.3-22b-distilled-fp8.safetensors` | PASS |
| Prompt | Scene prompt | request.prompt | job params | CLIP positive | Observatory + continuity lines | PASS |
| Timed Prompt | Board clips | compiled into prompt | same | CLIP | Continuity + scene text present | PASS |
| Camera | Inspector fields | `camera_nl_instruction` | request.camera | CLIP suffix | Close Up, 35mm, dolly, Dramatic, Jacob | PASS |
| Start image | Jacob hero | start asset | LoadImage | node 4 | `studio/imagegen_edit_97271e7a.png` | PASS |
| References | optional warning | not required | — | — | no extra ref nodes | PASS |
| Width | 1280 | 1280 | 1280 | 1280 | 1280 | PASS |
| Height | 704 | 704 | 704 | 704 | 704 | PASS |
| FPS | 24 | 24 | 24 | 24 | `frame_rate` 24 | PASS |
| Frames | 5s × 24 → 8n+1 | 113 | 113 | 113 | 113 | PASS |
| Duration | board 10s / batch 5s | 5.0 planned | 5.0 generated | 113/24=4.708s | ffprobe 4.708s | PASS |
| Output | Preview / Library | candidate Take C | asset `e2aa3a76-…` | VHS mp4 | `batch_bb_0b021_00003.mp4` | PASS |

---

## E2E TRACE

| Stage | Verdict |
|---|---|
| User action | PASS — Generate, Stop, Resume, New take, Camera, Approve path |
| Frontend | PASS — PC picker, header 10.0s, wired controls |
| API | PASS — generate / cancel / resume / retake / approve |
| Backend | PASS — compile 1280×704, I2V fail-closed |
| Persistence | PASS — approved Take B survives retake; camera persists |
| Runtime | PASS — Comfy MCP + GPU LTX 2.3 distilled |
| Result | PASS — MP4 1280×704, 113 frames |
| Reload | PASS — LTX selection + approved clip remain |
| Downstream | PASS — Take C selectable; locked take not replaced |

---

## Manual review

1. Open `http://127.0.0.1:5173/project/0ffe56e2-0d58-4926-91bf-0f947898d02e?workspace=timeline`
2. Confirm Video Generator is **LTX 2.3 — Local** (MiniMax disabled if Route A is still down).
3. Batch 1 approved take is Jacob I2V; Take C is the camera retake.
4. Header duration **10.0 sec**.

Do not start retired `:8760`.
