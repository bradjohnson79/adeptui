# SenseNova U1.5 — Uninstallation & System Removal

Governing document for this milestone (Build Law 30). Supersedes `SENSENOVA_U15_INTEGRATION.md` which is now historical.

**Date:** 2026-08-23
**Branch:** `feat/character-creator-final-closure`
**HEAD SHA:** `3b6fbd47a5ba7a9bfd6037bd314b88a0a823afd0` (short: `3b6fbd4`)
**Trigger:** User request — SenseNova U1.5 too large for current hardware (64 GB host / 32 GB RTX 5090). `from_pretrained` exhausted host RAM before tensors reached CUDA. Integration verdict was `E2E BLOCKED — NO-GO`.

## Verdict

```text
GO — SenseNova U1.5 runtime fully removed and verified
```

All runtime components (weights, custom node, Python package, config) have been uninstalled. Torch and all other runtimes are intact. Character Sheet generation defaults to Flux/Qwen.

## Scope

| Component | Action | Path | Size |
|---|---|---|---|
| Model weights | DELETED | `D:\01_Models\SenseNova\U1.5-8B-MoT` | 61.14 GB freed |
| ComfyUI custom node | DELETED | `…\ComfyUI-Installs\ComfyUI\ComfyUI\custom_nodes\ComfyUI-SenseNova-U1` | — |
| Python package | UNINSTALLED | `sensenova-u1 0.1.0` from ComfyUI `.venv` | — |
| Extra-paths config | REMOVED | `adept_sensenova` block in `…\Comfy Desktop\shared_model_paths.yaml` | — |

Full ComfyUI install path: `C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI`

## Left in place (by design)

The code-level integration remains in the repository. These modules are discovery-only and self-disable when the runtime components are absent:

| File | Role | Behavior without runtime |
|---|---|---|
| `studio-api/app/workflows/sensenova_u15.py` | Workflow builders + constants | Not invoked; `discover_sensenova_u15()` returns `runtimeReady: false` |
| `studio-api/app/image_studio/providers.py` | Provider registry entry | Shows "Not Ready" / hidden from dropdown |
| `studio-api/app/production_control/model_registry.py` | Model registry entry | Not listed as available |
| `studio-api/app/source_manager/install_jobs/comfy_extension_installer.py` | Installer guard (torch isolation) | Dormant; only activates if reinstalled |

Rationale: removing the code would be a large codebase change with regression risk for no runtime benefit. The discovery layer already handles the absent-runtime case gracefully. If a more capable machine is available in the future, reinstalling the weights + custom node + pip package re-enables SenseNova without code changes.

## Verification

### ComfyUI — SenseNova nodes gone

```
=== ComfyUI object_info check ===
OK: No SenseNova nodes found in ComfyUI object_info
```

### Filesystem — weights and custom node removed

```
=== Filesystem check ===
  weights (D:\01_Models\SenseNova): REMOVED
  custom_node (…\custom_nodes\ComfyUI-SenseNova-U1): REMOVED
```

### Python package — uninstalled

```
Found existing installation: sensenova-u1 0.1.0
Uninstalling sensenova-u1-0.1.0:
  Successfully uninstalled sensenova-u1-0.1.0
--- Checking for leftover sensenova packages ---
(none found)
```

### Torch — intact (not damaged by removal)

```
torch 2.10.0+cu130
cuda available True
cuda version 13.0
```

### Config — `adept_sensenova` entry removed

`shared_model_paths.yaml` now ends at `adept_qwen_edit_2509`. No `adept_sensenova` block remains.

### Adept API — no SenseNova in discovery or registry

```
SenseNova in discovered-models: False
No SenseNova entries found

SenseNova in registry: False
No SenseNova entries in registry

SenseNova API routes: none
```

## Runtime status after restart

```
ADEPT UI RUNTIME SUPERVISOR
  studio_api: OK (reused) already healthy PID 55104
  comfyui: OK (owned) healthy PID 11108
  cloudflared: OK (owned) process up PID 64848
  ollama: OK (external) already healthy
  retired_web_8760: not started (Law 15)
```

Health endpoints:
- Studio API: `http://127.0.0.1:8758/api/healthz` → `200 {"status":"ok"}`
- Local creator UI: `http://127.0.0.1:5173/`

## Downstream impact

| Surface | Before | After |
|---|---|---|
| Character Creator CRS | SenseNova selectable (Not Ready) | SenseNova not discoverable; Flux default |
| Spatial Map → ERS | SenseNova selectable (Not Ready) | SenseNova not discoverable; Qwen 2512 default |
| Scene Creator / Mini | Qwen + GPT Image 2 only (already restricted) | Unchanged |

No character projects, assets, or library entries were modified. Only the SenseNova runtime installation was removed.

## Limitations

- The code-level integration files remain in the repository (by design — see above).
- The governing integration report `SENSENOVA_U15_INTEGRATION.md` is now historical and superseded by this document.
- If SenseNova is reinstalled in the future, the installer guard in `comfy_extension_installer.py` will still protect torch from the `torch==2.8.0` pin conflict.

## Manual review

Runtime is running and ready:
- Local creator UI: `http://127.0.0.1:5173/`
- Studio API: `http://127.0.0.1:8758/`

To confirm SenseNova is gone: open Character Creator → generator dropdown should show Flux (default) and Qwen, with no SenseNova entry.

## Verdict

```text
GO — SenseNova U1.5 runtime fully removed and verified
```
