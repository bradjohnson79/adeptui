# Live Lifecycle Evidence

## Environment

- Branch: `feature/ai-guided-setup`
- Observed HEAD: `fa09c99d6395c29461cdec4555055faad116c435`
- Beta UI: `http://127.0.0.1:8760/`
- Beta API: `http://127.0.0.1:8758/api/health`
- Setup status sample: `33 ready`, `4 not_installed`, `0 needs_attention`

## Representative lifecycle outcomes

| Category | Component | Live result | Honest notes |
| --- | --- | --- | --- |
| Image | `qwen_image_2512_models` | `ready` | Observed via live `GET /api/setup/status`. Existing machine state was already linked and healthy; this pass did not re-download weights. |
| Image | `flux1_schnell_local` | `ready` | Observed via live `GET /api/setup/status`. Existing local path-link posture remains healthy. |
| Video | `hunyuan_video_15` | `ready` | Observed via live `GET /api/setup/status`. Existing install remains healthy with `huggingface_snapshot` installer metadata. |
| Voice | `index_tts2` | `ready` | Observed via live `GET /api/setup/status`. Existing local runtime remains healthy; this pass did not reinstall it. |
| API provider | `fal_key` | `ready` | Observed via live `GET /api/setup/status`. Credential-backed provider path is present and healthy; no secret values were logged. |
| ComfyUI extension | `comfyui_hunyuan_nodes` | `ready` | Trusted repair reached a fresh Ready job after dependency repair, a real Comfy Desktop restart, and a final node reverify. |

## ComfyUI extension repair evidence

### Original stuck snapshot

- Existing failed job: `ij_comfyui_hunyuan_nodes_f028a0b4b8`
- Historical failure: dependency repair snapshot remained on `No module named uv`
- Prior live POSTs returned `200 OK` but the persisted payload did not advance beyond the stale failure record

### Root causes

Two real issues were present:

1. the repair path handled PEP 668 by calling `python -m uv pip --system`, but the Comfy-side interpreter on this machine did not have the `uv` module importable, so the live Beta worker needed a fallback to a real `uv.exe` that targets the intended interpreter explicitly
2. the trusted extension probe was checking for stale `HunyuanVideo15*` / `HunyuanVideo13B*` node ids, while the catalog-registered default source (`ComfyUI-HunyuanVideoWrapper`) actually exports `HyVideo*` wrapper nodes and required a real Comfy Desktop restart before those nodes would appear in `/object_info`

### Live fix exercised

- Restarted Beta after code changes so the worker loaded the updated installer
- Trusted repair endpoint used:
  - `POST /api/setup/install-jobs/ij_comfyui_hunyuan_nodes_f028a0b4b8/repair`
  - `POST /api/setup/install-jobs/ij_comfyui_hunyuan_nodes_f6595bfd0e/repair`
- Fresh repair job under the corrected probe logic: `ij_comfyui_hunyuan_nodes_0074784d12`
- New dependency result captured in live payload:
  - `raw.deps.ok = true`
  - `raw.deps.method = uv_cli_python`
  - message: `Using Python 3.11.15 environment at: C:\Users\bradj\AppData\Local\hermes\hermes-agent\venv`
- Real Comfy Desktop restart performed after the extension was confirmed to be installed under:
  - `C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\custom_nodes\ComfyUI-HunyuanVideoWrapper`

### Post-repair verification results

- Follow-up trusted action used:
  - `POST /api/setup/install-jobs/ij_comfyui_hunyuan_nodes_f6595bfd0e/repair` with `action=restart_comfyui`
- Intermediate result before real Comfy restart:
  - ComfyUI reachable at `http://127.0.0.1:8188`
  - ComfyUI version: `0.28.2`
  - Node catalog available: yes
  - Probe result: `0 of 6 nodes detected`
  - Final live state: `repair_required`
  - Final message: `Extension installed, but 6 required nodes were not registered.`

- Live Comfy verification after real restart:
  - startup log now lists `C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\custom_nodes\ComfyUI-HunyuanVideoWrapper`
  - live `/object_info` detects all representative wrapper nodes:
    - `DownloadAndLoadHyVideoTextEncoder`
    - `HyVideoI2VEncode`
    - `HyVideoModelLoader`
    - `HyVideoSampler`
    - `HyVideoTextEncode`
    - `HyVideoVAELoader`
  - trusted reverify result on fresh job `ij_comfyui_hunyuan_nodes_0074784d12`:
    - `state = ready`
    - `message = 6 of 6 nodes detected. Capability ready.`

### Honest conclusion

The representative ComfyUI extension path is now honestly `ready`.

What was proven live:

- the `uv` dependency blocker is fixed via `uv_cli_python`
- the wrapper installs into the expected Comfy Desktop `custom_nodes` tree
- the original `restart_comfyui` repair action was not a real Comfy restart on this host because `ADEPT_COMFY_LAUNCH` is unset
- after a real Comfy Desktop restart, the wrapper loads and all 6 representative `HyVideo*` nodes are detected

What remains separate from this representative fix:

- Hunyuan workflow capability metadata elsewhere in the stack still references older `HunyuanVideo15*` / `HunyuanVideo13B*` node ids and was not recertified in this pass

## Performance samples captured during closure

- Earlier sampled first hit: `333.77 ms`
- Post-restart cold sample: `608.16 ms`
- Warm samples before final restart: `58.58 ms`, `14.31 ms`, `15.5 ms`, `16.71 ms`, `15.5 ms`
- Warm samples after final restart: `55.87 ms`, `14.22 ms`, `13.46 ms`, `13.96 ms`, `139.53 ms`

These samples satisfy the stated warm `<500ms` target and the post-restart cold `<3s` target for the current Beta build.
