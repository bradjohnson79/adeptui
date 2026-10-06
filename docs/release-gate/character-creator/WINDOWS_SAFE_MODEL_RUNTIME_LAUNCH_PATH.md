# Windows-Safe Model / Runtime Launch Path

**Date:** 2026-08-24  
**Gate:** Windows Security / process-launch law  
**Wonder3D:** remains license-blocked. No Wonder3D download or install was performed.

## Verdict

`GO — WINDOWS-SAFE MODEL/RUNTIME LAUNCH PATH VERIFIED`

Security was not weakened. No Defender exclusions. No Hermes whitelist. The blocked `hf.exe` was not re-launched to “prove” a workaround.

## What Windows Security blocked

Smart App Control / Code Integrity (events 3033, 3077, 3118):

| Field | Observed |
| --- | --- |
| Process | `C:\Users\bradj\AppData\Local\hermes\hermes-agent\venv\Scripts\hf.exe` |
| Loaded image | `C:\Users\bradj\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe` |
| Policy | Enterprise signing level (Policy ID `{0283ac0f-fff1-49ae-ada1-8a933130cad6}`) |
| Status | `0xc0e90002` |
| Tonight’s cadence | ~every 5–6 minutes (triples = version + whoami + retry) |

`hf.exe` is a pip console-script launcher. It is not a signed Hugging Face product installer. It tries to load the sibling `python.exe` from the Hermes private venv. Smart App Control blocks that load. That is correct behavior.

## Process ancestry

User PATH (this session) resolves bare names to Hermes first:

1. `C:\Users\bradj\AppData\Local\hermes\hermes-agent\venv\Scripts`
2. `C:\Users\bradj\AppData\Local\hermes\bin`
3. other Hermes git/node dirs

Therefore:

| Bare command | Resolves to |
| --- | --- |
| `hf` | Hermes `hf.exe` |
| `huggingface-cli` | Hermes `huggingface-cli.exe` |
| `python` | Hermes `python.exe` |

### Adept product path (the defect)

Adept Setup / Source Manager called `detect_huggingface_cli()`.

That function used `shutil.which("hf")` **before** the Adept venv, then executed:

- `hf.exe version`
- `hf.exe auth whoami`

Studio API inherits the user PATH. Live API ancestry at investigation time:

```text
supervisor / studio-api\.venv\Scripts\python.exe
  → uv python -m uvicorn app.main:app --host 127.0.0.1 --port 8758
```

Call sites that executed detection:

- `GET /api/setup/download-sources`
- `POST /api/setup/download-sources/{provider}/detect`
- `GET /api/source-manager/providers` and `/overview` (`detect_all()`)

This is **not** Wonder3D. Wonder3D weights stay AGPL-blocked and were not downloaded.

This is **not** the isolated MV-Adapter download. That work already used:

```text
Cursor/Agent
  → data\venvs\mvadapter\Scripts\python.exe
  → huggingface_hub.snapshot_download / hf_hub_download
```

No Hermes `hf.exe` on that path.

### Other observed launch

`21:46:25` Code Integrity: `powershell.exe` attempted to load Hermes `python.exe`. That is a Cursor/agent shell inheriting user PATH (`python` = Hermes), not Studio API and not Wonder3D.

Hermes itself also keeps long-lived `hermes-agent\venv\Scripts\python.exe` UI servers on ports 7881+. Adept does not own those processes.

## Why `hf.exe` is not required

Hugging Face Hub access only needs the `huggingface_hub` Python library.

Intended Adept path:

```text
Cursor/Agent or Adept Setup
  → studio-api\.venv\Scripts\python.exe
  → import huggingface_hub / hf_hub_download / whoami
```

Intended isolated model runtime (MV-Adapter I2MV):

```text
Cursor/Agent
  → data\venvs\mvadapter\Scripts\python.exe
  → huggingface_hub API
  → data\models\MV-Adapter\
```

Forbidden:

```text
Cursor/Agent → Hermes private venv → hf.exe → blocked python.exe
```

Adept must not install or run Wonder3D through Hermes. Wonder3D remains `license_blocked`.

## Repair (no security weakening)

1. `detect_huggingface_cli()` uses Adept Python + `huggingface_hub` only.
2. PATH `hf` / `huggingface-cli` are ignored. Hermes overrides are rejected as `Misconfigured`.
3. Sign-in command is `python -m huggingface_hub.cli.hf auth login` on Adept Python.
4. Runtime Supervisor child PATH drops `hermes-agent` and `AppData\Local\hermes` entries so Studio API / Comfy children do not inherit that private venv.
5. Isolated MV-Adapter downloads stay on `data\venvs\mvadapter` + the Python API.

Files:

- `studio-api/app/setup/download_sources/cli_detect.py`
- `studio-api/app/setup/download_sources/service.py`
- `studio-api/runtime_supervisor/env.py`
- `studio-api/runtime_supervisor/services.py`
- `scripts/beta_runtime/supervisor.py` (legacy supervisor still on this machine)
- `studio-api/tests/test_download_sources.py`
- `studio-api/tests/test_runtime_supervisor_lifecycle.py`

## Honest remaining limitation

Hermes remains installed on this user account and can still launch its own `hf.exe`. Adept no longer does. A later Hermes-origin warning is a Hermes issue, not an Adept launch-path defect.

Do not “fix” that by excluding the Hermes directory or disabling Smart App Control.
