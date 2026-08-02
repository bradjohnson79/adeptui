# IndexTTS2 Runtime

## Scope

M4.10 adds an isolated local runtime for `IndexTTS-2` under:

`<settings.data_dir>/runtimes/index-tts2/`

The runtime is pinned to:

- Official repo: `https://github.com/index-tts/index-tts`
- Locked revision: `13495845e3028f0bb6ca1462ad22aa0e76349e40`
- Model: `IndexTeam/IndexTTS-2`
- Provider id: `index-tts2-local`

## Layout

The runtime root is divided into fixed product-owned folders:

- `environment`
- `models`
- `manifests`
- `logs`
- `outputs`
- `repo`

The main manifest is stored at:

`runtimes/index-tts2/manifests/index-tts2-manifest.json`

## Runtime behavior

`studio-api/app/voice_performance/runtime/index_tts2.py` owns:

- install / verify / repair / remove
- repo clone at the locked SHA only
- dedicated virtual environment creation
- model presence inspection
- service adapter start / stop / restart
- job file creation for take and scene synthesis
- honest capability metadata

`studio-api/app/voice_performance/runtime/worker_infer.py` is the isolated worker entrypoint. It supports:

- `--job-json <path>` for inference
- `--health-json <path>` for runtime probing
- `--adapter-process` for a lightweight managed background process

## Honest readiness states

`inspect_installation()` reports one of:

- `not_installed`
- `checking`
- `compatible`
- `incompatible`
- `installing`
- `installed`
- `verifying`
- `ready`
- `repair_required`
- `failed`
- `update_available`

`compatible` means the pinned repo and isolated environment are present, but model assets are still incomplete.

`ready` means the worker probe succeeded and the required model files were found.

## CPU fallback policy

The runtime does not silently fall back to CPU.

If CUDA is unavailable, health and generation return a structured error unless `allow_cpu_fallback` / `allowCpuFallback` is explicitly set by the caller.
