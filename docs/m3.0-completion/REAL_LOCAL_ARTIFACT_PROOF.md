# M3.0 Completion - Phase 5: Real Local Artifact Proof

**Verdict: VERIFIED.** One real image was produced by the locally installed ComfyUI through
the same Adept API path the web UI uses, landed on disk inside the project, and is backed by
an `Asset` row, an `AssetVersion` lineage row, and a matching `Job` row.

No model was downloaded. No fixture, mock, or fabricated completion was used at any point.

| Field | Value |
|-------|-------|
| Date | 2026-07-27 (UTC) |
| Verdict | **VERIFIED** |
| Endpoint used | `POST /api/projects/{projectId}/imagegen` |
| Provider | Local ComfyUI `0.28.2` at `http://127.0.0.1:8188` |
| Plan file | Not edited |
| Commit | None (Phase 5 does not commit) |

---

## 1. Preflight (no downloads)

`GET /system_stats` on ComfyUI and `GET /api/health` + `GET /api/capabilities` on the Adept API
were read before anything was submitted.

| Check | Result |
|-------|--------|
| ComfyUI version | `0.28.2` (Python 3.13.12, PyTorch `2.10.0+cu130`) |
| Device | `cuda:0 NVIDIA GeForce RTX 5090 : cudaMallocAsync`, 32 GiB VRAM |
| Adept `/api/health` | `ok: true`, `comfy_status: ready`, `comfy_reachable: true` |
| `models.image.ready` | `locally_verified` / available - "Required model components are verified on disk." |
| `workflows.image.ready` | `locally_verified` / available - "3 of 3 workflow(s) have all required nodes and models." |
| `generation.image.queue` | `locally_verified` / available - Comfy reachable and an image workflow with catalogued weights is ready to queue |
| `comfyui.queue` | `backend_only` (unchanged) - reachable only through job kinds today; not a Phase 5 blocker |

Readiness for still images resolves through the `zimage_models` component
(`zimage_files` verifier: Z-Image Turbo UNET + Qwen text encoder + AE VAE), so **Z-Image ImageGen
was preferred over an LTX/Wan video render**, exactly as the remediation plan specifies. LTX/Wan
weights are also present and `generation.video.queue` reports `locally_verified`; they were not
needed and were not exercised.

---

## 2. The real generation

Submitted through `POST /api/projects/{projectId}/imagegen` - the same endpoint
`studio-web`'s `api.imagegen()` calls (`studio-web/src/api.ts`), routed to
`enqueue_imagegen` in `studio-api/app/routers/extra.py`, then executed by `JobQueue._imagegen`
in `studio-api/app/queue_worker.py`.

| Field | Value |
|-------|-------|
| Project | `098744a3-9d6b-4c42-b873-bf817970b07c` - "M3.0 Local Artifact Proof" |
| Job id | `3edf2c90-3e77-4160-a083-841ce21265f9` (kind `imagegen`) |
| Comfy prompt id | `108843aa-ada6-4aa2-a78f-2830b89ee8e6` |
| Prompt | "cinematic wide shot of a lone lighthouse on a rocky coast at dusk, storm clouds, volumetric light, film grain, 35mm" |
| Negative | "blurry, low quality, watermark, text" (project default) |
| Model / checkpoint | Z-Image Turbo - `z_image_turbo_bf16.safetensors` |
| Text encoder / VAE | `qwen_3_4b.safetensors` (CLIPLoader type `lumina2`), `ae.safetensors` |
| Sampler | KSampler `euler` / `simple`, 8 steps, cfg 1.0, denoise 1.0, seed `30500` |
| Resolution | 1024 x 1024 |
| Submitted | `2026-07-27T06:39:04.460Z` |
| Completed | `2026-07-27T06:39:10.509Z` |
| Wall time | **6.08 s** (warm weights) |
| Comfy status | `success`, `completed: true` |

### Workflow graph actually executed

Built by `build_zimage_txt2img_workflow` (`studio-api/app/workflows/image_tools.py`) and
confirmed against ComfyUI's own `/history/{promptId}` record:

```
UNETLoader(z_image_turbo_bf16) -> ModelSamplingAuraFlow(shift 3.0) ---.
CLIPLoader(qwen_3_4b, lumina2) -> TextEncodeZImageOmni (positive) ----+-> KSampler -> VAEDecode -> SaveImage
                               -> CLIPTextEncode      (negative) ----'      ^            ^
EmptyLatentImage(1024x1024) ----------------------------------------------- '            |
VAELoader(ae.safetensors) --------------------------------------------------------------'
```

Node classes reported by Comfy history: `UNETLoader`, `CLIPLoader`, `VAELoader`,
`ModelSamplingAuraFlow`, `TextEncodeZImageOmni`, `CLIPTextEncode`, `EmptyLatentImage`,
`KSampler`, `VAEDecode`, `SaveImage`. This is the diffusion-only UNET path, never
`CheckpointLoaderSimple`.

---

## 3. Artifact verification

Comfy wrote `studio/098744a3_imagegen_00001_.png` into its shared output directory; the worker
copied those bytes into the project's own asset directory so the artifact does not depend on
Comfy's output cache.

| Field | Value |
|-------|-------|
| Artifact (repo-relative) | `data/projects/098744a3-9d6b-4c42-b873-bf817970b07c/assets/imagegen_generate_5ff52d2c.png` |
| Exists on disk | Yes |
| Size | **1,391,811 bytes** (1.33 MiB) |
| sha256 | `8e13b6e2eb0809b98ea55435a1a9bfcbaa613ff8fa71c8682f8caf5cbcb42439` |
| MIME | `image/png` (served as `image/png`; magic bytes `89504e470d0a1a0a`) |
| Dimensions | 1024 x 1024 |
| Content check | Opened and viewed: a lighthouse on rocky coast under storm clouds at dusk, matching the prompt. Not a blank or placeholder frame. |

`data/` is gitignored, so the artifact stays local by design; the checksum above is the portable
proof.

### Database rows (project association)

| Row | Value |
|-----|-------|
| `assets.id` | `1c6fd220-5668-4fc0-898a-3cddb0b81cc1` |
| `assets.project_id` | `098744a3-9d6b-4c42-b873-bf817970b07c` (matches the job's project) |
| `assets.tag` / `kind` / `scope` | `m30-local-proof` / `image` / `project` |
| `asset_versions` | version `1`, op `generate`, seed `30500`, model `z_image_turbo_bf16.safetensors` |
| `jobs.output_path` | points at the same file as `assets.path` |
| `jobs.params_json` | carries `output_asset_id` = the asset id above (no phantom id) |

The image is also served back through the API: `GET /api/assets/{assetId}/file` returns
HTTP 200, `content-type: image/png`, 1,391,811 bytes - byte-identical length to the file on disk.

---

## 4. Co-Director inspect path

Two distinct inspect surfaces exist, and only one covers this artifact. Recorded honestly:

| Path | Status for this artifact |
|------|--------------------------|
| `GET /api/codirector/jobs/{jobId}?projectId=...` (M2.7 Production Executive `inspect_job`) | **Exists and is enabled** (`productionExecutiveEnabled: true` in `/api/health`), but returns `404 {"detail":"Job not found."}` for this job. It reads the separate Production Executive `JobStore`, not the Studio job queue, so Studio-queue artifacts are not inspectable through it. Companion routes `/{jobId}/dependencies` and `/{jobId}/history` share that scope. |
| Studio queue inspect chain | **Works end to end** for this artifact. |

The working chain, all verified live against the real artifact:

| Call | Result |
|------|--------|
| `GET /api/jobs/{jobId}` | `status: done`, `stage: complete`, `comfy_prompt_id`, `output_path`, full `history_json` provenance |
| `GET /api/jobs/{jobId}/preview` | `stage: complete`, `status: done`, `progress: 1.0`, preview capabilities advertised |
| `GET /api/projects/{projectId}/library?scope=project` | 1 asset, the generated image |
| `GET /api/assets/{assetId}/graph` | asset + `related: []` + `versions: [{version 1, op generate, seed 30500, model z_image_turbo_bf16.safetensors}]` |
| `GET /api/assets/{assetId}/file` | the real PNG bytes |

**Gap to carry forward:** unifying Studio-queue jobs into the Co-Director executive inspect
endpoint is not done. Nothing in this phase papers over that.

---

## 5. Restart persistence approach

Persistence was confirmed by durability, not by restarting the operator's running API:

1. **Rows are committed to disk.** `data/studio.db` was read out-of-process, read-only, while
   the API held its own connection. The `projects`, `jobs`, `assets`, and `asset_versions` rows
   for this proof were all present with the same ids, paths, and provenance the API reports -
   so they are durable SQLite state, not in-memory session state.
2. **Bytes are owned by the project.** The worker copies Comfy's output into
   `data/projects/{projectId}/assets/`, so purging ComfyUI's output folder or history cannot
   orphan the asset.
3. **Startup reconciles anything left mid-flight.** `studio-api/app/main.py` awaits
   `job_queue.recover_interrupted()` in the lifespan hook *before* `job_queue.start()`
   (`studio-api/app/queue_worker.py`). Jobs still `queued` and newer than
   `STUDIO_JOB_RECOVERY_MAX_AGE_HOURS` (default 24 h) are re-enqueued; jobs left `running` are
   closed as `failed` / stage `interrupted` rather than silently resubmitted, since a re-submit
   could spend provider credits. Every transition appends an audit entry under
   `history_json.recovery`. Coverage lives in `studio-api/tests/test_job_queue_recovery.py`.
4. **Terminal rows are untouched.** This job is `done`, which is outside
   `NON_TERMINAL_STATES = ("queued", "running")`, so a restart leaves it and its asset exactly
   as recorded above.

**Honest scope:** no restart of the operator's API process was performed in this phase; the
claim rests on the committed on-disk rows plus the recovery code path and its tests.

---

## 6. Gated Playwright coverage

`tests/e2e/m30-completion/m30-completion-local-live.spec.ts` - opt-in via
`ADEPT_M30A_LOCAL_LIVE=1`, self-skipping otherwise.

| Run | Result |
|-----|--------|
| `ADEPT_M30A_LOCAL_LIVE=1` against the E2E stack (real ComfyUI, temp data dir) | **2 passed** in 12.5 s |
| Env unset | **2 skipped** (default suite stays green without a local Comfy) |
| `npx tsc -p tsconfig.e2e.json --noEmit` | Clean for this spec (only the pre-existing `production-bible-m23.spec.ts` `contentRevision` error remains) |

The live run created its own project, submitted a real ImageGen job, polled it to `done`,
asserted the Asset row, fetched the served PNG and checked its magic bytes and length, asserted
the `z_image_turbo` lineage row, then deleted its project. The E2E harness sets
`ADEPT_MOCK_IMAGEGEN` nowhere and the adapter refuses to fabricate completions, so this run was
genuinely local-Comfy backed.

---

## 7. Outputs

| Path | Purpose |
|------|---------|
| `docs/m3.0-completion/REAL_LOCAL_ARTIFACT_PROOF.md` | This proof |
| `artifacts/m30a-local/local_artifact_summary.json` | Machine-readable run record (gitignored under `artifacts/`) |
| `tests/e2e/m30-completion/m30-completion-local-live.spec.ts` | Gated local-live Playwright spec |

Blocker impact: **B5** ("no generative provider path proven end-to-end through API Asset/queue")
is now closed for the **local** provider. The fal side of B5 remains open and is Phase 6's job.
