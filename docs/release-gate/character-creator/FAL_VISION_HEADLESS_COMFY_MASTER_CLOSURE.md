# Master Closure — fal.ai Vision + Adept Headless Comfy

**Governing document for this milestone (Law 30).**  
Does not recertify hosted Vercel Express / Illustrious, Timeline, Scene Creator, or MiniMax Route A.  
Does not supersede `docs/release-gate/character-creator-4view-json/CHARACTER_CREATOR_4VIEW_JSON_CLOSURE.md` except for the Vision provider and `:8188` spawn owner described here.

**Date:** 2026-08-30  
**Branch:** `feat/character-creator-final-closure`  
**HEAD (committed):** `b6156455e643d5fa430784b3130756f2d8038651`  
**Working tree:** dirty. Do not commit unless asked.

**Creator UI:** Vite `http://127.0.0.1:5173/` (PID 62868)  
**Studio API:** `http://127.0.0.1:8758/` (listener PID 62532 after API-only recycle)  
**Retired:** do not use `:8760`

**Owner lock (one project, one library):**

| Lock | Id |
|---|---|
| Project | `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` |
| Character Anadriya | `4c1c0bc8-a771-4998-b652-5d549b2a2b8d` |
| Front asset (not regenerated) | `0c7d967f-eb3b-4003-a4d6-a4a562a38ee0` |

---

## Verdicts (binary, independent)

```text
GO — CO-DIRECTOR FAL.AI VISION E2E CERTIFIED
GO — ADEPT HEADLESS COMFY RUNTIME E2E CERTIFIED
GO — CHARACTER CREATOR FRONT VISION + QWEN MULTIVIEW E2E CERTIFIED
```

Independent verifier language for this slice:

```text
VERIFIED — FULL-STACK E2E PASSED
```

Law 27 GPT 5.4 specialized subagents were not launched: that slug is not in the current Task allowlist. Primary observed the live traces below. Do not treat this as a hosted Vercel / Illustrious recert.

---

## Track A — Co-Director Vision = fal.ai only

Canonical `chat_vision` uses `fal_api_key` + `upload_file_to_fal` + `run_fal_model("fal-ai/any-llm/vision")`. Nested model actually used:

**`google/gemini-2.5-flash-lite`**

No `kie_api_key` on this path. No fal → Kie fallback. Spatial Map `mini_validation` uses the same `chat_vision`. Kie remains for GPT Image 2 and other generators.

### Persisted facts (reload + SQLite `character_traits.cc_v2`)

| Field | Value |
|---|---|
| `visualLock.status` | `ok` |
| `provider` | `fal` |
| `model` | `google/gemini-2.5-flash-lite` |
| face | humanoid, female, blue eyes, blonde hair |
| hair | long, blonde, wavy |
| skin | fair |
| wardrobe | full body suit, metallic, armored, high collar, gloves, boots |
| colors | silver, gold |
| distinctive | metallic suit with gold trim, geometric patterns on suit |
| build_as_seen | slender, athletic |
| style_as_seen | futuristic, armored, warrior |
| notes | (empty) |

Refresh: lock still `ok`; FAILED banner gone (Playwright). Generate stayed gated on `front.approved && visualLock.status === "ok" && engine.available`.

### Isolation

| Request | HTTP |
|---|---|
| Scoped Front file | **200** |
| Unscoped `/api/assets/{id}/file` | **403** |
| Wrong project `2bc632b8-…` + same Front id | **403** |

---

## Track B — Adept Headless Comfy Service

`:8188` is spawned only by `studio-api/runtime_supervisor/headless_comfy/`. Supervisor `start_comfy` is a thin request. Desktop YAML is not selected. Healthy unknown `:8188` is a conflict, not adopt.

| Record | Value |
|---|---|
| PID | **50236** |
| `owned` | **true** |
| YAML | `C:\Users\bradj\AppData\Roaming\Adept\Comfy\extra_model_paths.yaml` |
| Engine python | Comfy-Desktop *install tree* `.venv\Scripts\python.exe` (on-disk engine, not a running Desktop process) |
| Listen | `127.0.0.1:8188` |
| Parent | PID 9568 — same Adept Comfy `main.py` + Adept YAML (not PowerShell / Cursor) |
| Grandparent 53124 | gone (detached) |
| Logs | `logs/runtime/headless-comfy/` |
| `GET /system_stats` | **200** before and after `/free` |
| GPU | `cuda:0 NVIDIA GeForce RTX 5090` |

Qwen Edit 2509 after soak + `/free` (live `cc-v2.engine`):

- `available === true`
- `status === "READY"`
- `engine === qwen_image_edit_2509`
- `gpuDetail === cuda:0 NVIDIA GeForce RTX 5090 : cudaMallocAsync`
- `reason === Runtime Ready`

### Soak (same PID 50236)

| Step | Result |
|---|---|
| Authorized Track B start (port was free) | PID 50236 |
| Vite `:5173` HMR | 200; Vite PID 62868 unchanged |
| Studio API recycles only (never `start_all`) | Comfy stayed 50236 |
| Qwen angle jobs | completed on this PID |
| `POST http://127.0.0.1:8188/free` | **200**; not a restart |
| After `/free` | Listen PID **50236**; `system_stats` **200**; Qwen **READY** |

Comfy MCP is configured in `.cursor/mcp.json` but was not in this session’s MCP catalog. Probe used Comfy CLI against `http://127.0.0.1:8188` (`nodes show UNETLoader` listed `qwen_image_edit_2509_fp8_e4m3fn.safetensors`).

---

## Combined — Anadriya angles

Front was **not** regenerated. After Track A lock `ok` and Track B Qwen Ready:

| Angle | status | approved | assetId | jobId |
|---|---|---|---|---|
| side | approved | true | `98da27bf-e38b-4696-8371-2beb87a30509` | `8515e13d-d349-480a-853a-42d22c74640a` |
| three_quarter | approved | true | `480cca40-af47-49f1-88bc-697b6aa55bf9` | `17e20586-c539-4f6d-8889-3d180787614e` |
| back | approved | true | `0f24d610-339b-4c83-9b69-c71bd5092ea3` | `96c2de26-5363-4bd7-a7bc-8fe254f2c3d7` |

`sheetGate.ready === true`, `missing: []`. Compose Character Sheet control enabled. **No new sheet was composed or saved** (`sheetAssetId` remains null).

Reload (Playwright + second `GET cc-v2` + SQLite): lock `ok` / fal; three approved angles persist; no Create Back View; angle cards have no file inputs; no new 5xx.

---

## E2E TRACE

| Stage | Track A Vision | Track B Headless | Combined Angles |
|---|---|---|---|
| User action | Retry Co-Director Vision | Headless start (authorized) | Generate Character Angles → Approve Side / 3/4 / Back |
| Frontend | `CharacterV2Studio` / Playwright | N/A (runtime) | Same studio; Generate / Approve / Compose gate |
| API | `POST …/canon/retry-vision` | thin `start_comfy` → headless service | `generate-multiview` + `…/angles/{side,three_quarter,back}/approve` |
| Backend | `chat_vision` → fal only | Adept YAML + detached spawn | `cc_v3_multiview` + queue worker + Qwen 2509 graph |
| Persistence | `visualLock` on `cc_v2` | `owned.json` PID 50236 | angle `assetId`s + `approved` on `cc_v2` |
| Runtime | `fal-ai/any-llm/vision` + `google/gemini-2.5-flash-lite` | `:8188` owned | same Comfy PID; Qwen Edit 2509 on RTX 5090 |
| Result | `visualLock.status=ok` + structured facts | `system_stats` 200; engine READY | three Library assets |
| Reload | lock still `ok` | same PID after API recycle + `/free` | angles + approvals + `sheetGate.ready` |
| Downstream | Generate gated honestly | angle jobs could run | compose enabled; sheet not written |

All applicable stages: **PASS**.

---

## Tests (measured)

| Suite | Count |
|---|---|
| Playwright `anadriya-front-vision` + `anadriya-angles-persist` (`ADEPT_BETA_TARGET=1`) | **2 passed** |
| `test_headless_comfy` + `test_runtime_supervisor_lifecycle` | **31 passed** |
| `test_apply_job_four_view_prompt` | **3 passed** |
| `test_angle_enqueue_accepts_qwen_edit_sampler_kwargs` | **1 passed** |
| Qwen 2509 registry normalize + Draft-not-Certified | **passed** |
| Readiness catalog fallback | **1 passed** |

Pre-existing (not this gate): `test_queue_worker_crs_four_view_pin` collection (`prompt_purpose_for_expand`); some `test_qwen_edit_2509` / family-route API mismatches.

---

## Product bugs repaired so the combined path could run

Necessary for completion, not a CC redesign:

1. `_enqueue_txt2img` accepts Qwen sampler kwargs used by angle enqueue.
2. Family `qwen_edit_2509` is not collapsed to t2i-only `qwen`; Draft registry entries `qwen_edit_2509.edit` / `qwen_edit_2509.crs_single_view`.
3. `apply_job_four_view_prompt` implemented; CC v3 angles are not four-panel-strengthened.
4. `is_default_four_view_pack_tile` implemented so CRS gate import succeeds.
5. Readiness falls back to `discover_qwen_edit_2509()` when setup catalog lacks the component.
6. Comfy stall window `min(900, timeout)` so first UNET+CLIP load is not marked dead at 180s.
7. Supervisor `_spawn` now includes `CREATE_NEW_PROCESS_GROUP` so API recycle does not die with the launcher job (observed after `/free` when the hung API was recycled).

---

## COMFY BEFORE / AFTER / RESTARTED?

| | |
|---|---|
| **COMFY BEFORE** (this closing pass) | PID **50236** / `system_stats` 200 / `owned:true` |
| **COMFY AFTER** | PID **50236** / `system_stats` 200 / `owned:true` |
| **COMFY RESTARTED?** | **NO** for Vision retry, angle generate/approve, Playwright, `/free`, and API recycle |
| **WHY?** | Ordinary work. `/free` only. API recycle only. |
| Earlier Track B start (port was free) | **YES** once — Adept Headless Comfy Service authorized by this plan |

MiniMax `:8192` was not started, stopped, or used.

---

## Limitations (honest)

- Working tree is dirty; this report is not a commit or deploy.
- Character Sheet was not composed (gate proven available only).
- MiniMax Route A was out of scope; `:8192` was not listening at close and was left alone.
- First API recycle after `/free` left `:8758` hung, then a `start_studio_api` child exited with the launcher; Studio API was restarted detached (PID 62532). Comfy PID did not change.
- Hosted Vercel Express / Illustrious addendum path was not re-run.
- `comfy-mcp` tools were not in this Cursor session catalog.

---

## Manual review

1. Open `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=characters&characterId=4c1c0bc8-a771-4998-b652-5d549b2a2b8d`
2. Confirm Front is the existing approved asset; Co-Director Vision is ok (no FAILED banner).
3. Confirm Side / 3/4 / Back images are present and approved.
4. Confirm Compose Character Sheet is enabled. Do not compose unless you intend to write a sheet.
5. Do not regenerate Front. Do not bounce `:8188`.

---

## Binary close

```text
GO
```

Three independent GOs above all hold on the measured Anadriya + owned `:8188` evidence.
