# Standalone ComfyUI Clean Rebuild + MiniMax H3 Audio Reset

**Status:** COMPLETE  
**Date:** 2026-09-07 / 2026-09-08  
**Owner lock:** Route A `:8192` only. Comfy Desktop / `:8188` not touched.

**Verdict:** `GO — STANDALONE COMFYUI CLEAN REBUILD + FRESH MINIMAX H3 AUDIO STACK + 1F/T2V NATIVE AUDIO E2E CERTIFIED`

## Identity lock

| Role | Path / identity | Action |
|---|---|---|
| Comfy Desktop + `:8188` | `%LOCALAPPDATA%\Comfy-Desktop` Comfy **0.34.5**, argv Desktop Shared paths. Came back UP on its own after being down at rebuild start. | **NOT TOUCHED** (no stop, no `/free`, no file deletes) |
| Route A `:8192` (NEW) | `C:\AdeptFilmWorks\AIVideoStudio-h3\runtime\minimax-h3\comfyui` argv `--listen 127.0.0.1 --port 8192 --preview-method auto` `deploy=local-git` Comfy **0.34.0** HEAD `efa6c8f804bff78b46a0fd458ebd2e47bba07a30` | Rebuild target — LIVE |
| Route A Python (NEW) | `...\minimax-h3\.venv` Python 3.11.15 / Torch **2.11.0+cu128** / CUDA 12.8 / RTX 5090 | Fresh |
| Route A Python (OLD) | `.venv_OLD_QUARANTINE_2026-09-07`, `.venv-cuda_OLD_QUARANTINE_2026-09-07`, `.venv-broken_OLD_QUARANTINE_2026-09-07` | Quarantined — retained |
| Old Comfy tree | `...\comfyui_OLD_QUARANTINE_2026-09-07` | Quarantined — retained |
| Models | `D:\01_Models\Video\MiniMax-H3\ComfyUI` via new `extra_model_paths.yaml` `is_default: true` | UNET / CLIP / Video VAE kept |

## Protection report

| Item | Result |
|---|---|
| `COMFY BEFORE` Desktop `:8188` | Observed; later self-started as 0.34.5. Leave-alone. |
| `COMFY AFTER` Desktop `:8188` | Still UP 0.34.5. Same Desktop argv. |
| `COMFY RESTARTED?` Desktop | **NO** |
| Route A `:8192` | Intentional stop + fresh launch for this mission only |
| `taskkill /IM python.exe` | Not used |
| Full `run_runtime_supervisor.py restart` | Not used |
| SpeedCache / Sage / VDN | Not restored |
| New Adept project | Not created. Korri `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` reused |

## Audio VAE reset

| Location | Bytes | SHA-256 | Action |
|---|---|---|---|
| Old D: official (moved) | 605,254,808 | `8E505D95DD1561D47ABD43D4238FD40D9BB1AE9E147ED0A4CBA778D76AE4DB48` | Quarantined under `C:\AdeptFilmWorks\_quarantine\2026-09-07_h3-audio-vae-old\` |
| Old Route A local shadow | **605,429,308** | `37DDDC2F…ADE5EA2` **DIFFERENT FILE** | Left inside old tree quarantine |
| Desktop Shared copy | 605,254,808 | `8E505D95…` | Inventory only — not deleted |
| Fresh `hf_hub_download` `Comfy-Org/MiniMax-H3` `vae/minimax_h3_audio_vae_fp32.safetensors` | 605,254,808 | **`8E505D95…AE4DB48` SAME as old official** | Now on D: |

**Integrity finding:** the D: official Audio VAE was **not** byte-corrupt. Fresh download matched. Blame for prior garbled audio is the old Route A env / `comfyui-speed-minimaxH3` (`minimax_patch.py` / Sage), not the official weight bytes.

UNET / CLIP / Video VAE sizes still match the lock table (20,970,379,616 / 15,687,142,551 / 5,207,808,496). `:8192` `/models/vae` lists only the two official names.

## Fresh Comfy

- Official clone into the **same** `...\comfyui` path so `_discover_route_a_launch` still finds `main.py`.
- New parent `.venv`. Official `requirements.txt`. GPU Torch 2.11.0+cu128. CUDA device `NVIDIA GeForce RTX 5090`.
- Custom nodes: `websocket_image_save.py` + example only. **Zero** `comfyui-speed-minimaxH3`.
- HTTP `object_info`: `MiniMaxH3ImageToVideo`, `VAEDecodeAudio`, `CreateVideo`, `SaveVideo` present. `MiniMaxH3SpeedCache` absent. `Wavespeed*` classes are official `comfy_api_nodes.nodes_wavespeed`, not the speed pack.
- Official UI templates are subgraphs (default **4 steps**). Golden gates used the **official expanded node graph** (same classes as `video_minimax_h3_i2v.json` / `video_minimax_h3_t2v.json`) with plan-mandated **20 steps**, `res_multistep` / `simple`, 22 frames (1F/T2V vanilla) or 5s Adept T2V.
- Comfy log warning: official 0.34.0 prefers PyTorch cu130 for optimized CUDA kernels. This rebuild kept the proven 5090 stack `2.11.0+cu128`. Audio gates still passed.

Manual launch (not MCP):

`...\minimax-h3\.venv\Scripts\python.exe -s ...\comfyui\main.py --listen 127.0.0.1 --port 8192 --preview-method auto`

Supervisor `POST /start-route-a` was **not** invoked after the fresh launch (would only adopt the already-healthy port). Adept jobs submitted to this same `:8192` and completed. Discovery paths unchanged.

## Evidence matrix

Corrupt signature (kept): peak ≈ 0.99, DC ≈ 0.017, floor ≈ −23 dB.  
Clean signature: peak ≪ 0.2, DC ≈ 0, no clip, floor ≲ −48 dB (speech clips may sit around −42 dB).

| Gate | prompt / job | Peak | RMS | DC | Floor dB | Preview | Library | Verdict |
|---|---|---|---|---|---|---|---|---|
| OLD 4-step raw FLAC | `h3_ab_steps4_raw` | 0.991 | 0.128 | 0.017 | −23.43 | n/a | n/a | CORRUPT (kept) |
| OLD Adept T2V 4-step | `Adept_H3_Private_af619931` | 0.994 | 0.119 | 0.018 | −31.00 | n/a | n/a | CORRUPT (kept) |
| OLD Adept 1F 4-step | `Adept_H3_Private_I2V_85d883e9` | 0.733 | 0.198 | 0.017 | −23.05 | n/a | n/a | CORRUPT (kept) |
| Golden 1F (prior) | `.runtime/golden_h3_1f_output.mp4` | 0.124 | 0.023 | ≈0 | −48.27 | n/a | n/a | CLEAN ref |
| **Vanilla 1F** | `28cef11b-…` MP4+FLAC | **0.027** | 0.007 | ≈0 | **−53.14** | n/a | n/a | **CLEAN** |
| **Vanilla T2V** | `0a41166f-…` MP4+FLAC | **0.009** | 0.002 | ≈0 | **−55.50** | n/a | n/a | **CLEAN** |
| **Adept 1F** | job `c09a6729-…` / Comfy `848f9845-…` | **0.187** | 0.019 | ≈0 | **−41.65** | **20 frames** | `3539784d-….mp4` | **CLEAN** |
| **Adept T2V** | job `8eb2810f-…` / Comfy `6aed792e-…` | **0.011** | 0.003 | ≈0 | **−56.33** | **20 frames** | `0d5d022a-….mp4` | **CLEAN** |

Vanilla 1F/T2V MP4 vs raw FLAC meters match (mux is not the first corruptor). Adept T2V on the new stack matches the clean vanilla T2V band, not last night’s 20-step Adept (peak 0.200 / floor −34.68).

Playback: each new MP4 was opened with the workstation default player (`Start-Process`). Spectrograms saved at `.runtime/h3_vanilla_1f_spectrogram.png` vs `.runtime/h3_old_4step_spectrogram.png`. Phone listen is owner-confirm on the same files (paths below).

## Adept reconnect

- Project: `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` (Korri Anadriya). No new project.
- `EXPERIMENTAL_STEPS = 20` already in `route_a_adapter.py`. Both Adept jobs sampled **20/20**.
- Adept 1F: Scene `1f46b621-…` temporarily set to legal 22 frames / 1280×704, then **restored** to 13.6667s / 1152×640 after the gate.
- Adept T2V: `POST /api/projects/{id}/txt2vid` engine `minimax-h3`, `duration_sec=5`, `fps:"24"`, local only.
- Live draft: `--preview-method auto` produced 20 preview JPEGs per Adept job under `data/preview_cache/{jobId}/`.
- Prewarm remains explicit 1-step (not used as a substitute for these gates).

## MCP / HTTP node proof

Comfy MCP still targets Desktop `:8188`. **No** MCP `launch` / `stop` / `restart`. Evidence is HTTP on `:8192`: `system_stats`, `object_info`, `/models/vae`, `/prompt` + `/history`. Official 1F/T2V node set present; SpeedCache absent; four H3 filenames resolve from D: only.

## Quarantine classification (do not delete yet)

| Item | Class |
|---|---|
| Native `comfy_extras/nodes_minimax_h3.py` (in new checkout) | **REQUIRED** |
| `extra_model_paths.yaml` → D: only | **REQUIRED** (rewritten) |
| `--preview-method auto` | **REQUIRED** |
| Parent `.venv` + official Comfy deps | **REQUIRED** |
| Adept `route_a_adapter.py` / supervisor discovery paths | **ADEPT REQUIRED** (already pointed at this tree) |
| Old `user/` / `input/` from quarantine | **ADEPT OPTIONAL** — copy only if a creator setting is missing |
| `custom_nodes/comfyui-speed-minimaxH3` / Sage / `minimax_patch.py` / VDN | **DO NOT RESTORE** |
| Old `.venv*` trees | **DO NOT RESTORE** |
| Local shadow Audio VAE `37DDDC2F…` | **DO NOT RESTORE** |
| Desktop Shared weights | **DO NOT TOUCH** |

Keep `comfyui_OLD_QUARANTINE_2026-09-07` and `_quarantine\2026-09-07_*` until the owner accepts this GO.

## Playback files (owner phone)

- `.runtime/h3_vanilla_1f_s20_l22.mp4`
- `.runtime/h3_vanilla_t2v_s20_l22.mp4`
- `.runtime/h3_adept_1f_rebuild.mp4`
- `.runtime/h3_adept_t2v_rebuild.mp4`

## Live URLs

- Local creator UI: `http://127.0.0.1:5173/` (HTTP 200)
- Studio API: `http://127.0.0.1:8758/api/healthz` (HTTP 200)
- Route A Comfy: `http://127.0.0.1:8192/` (0.34.0)
- Desktop Comfy: `http://127.0.0.1:8188/` observe-only

## Limitations

- Phone listen was not performed by the agent; workstation default-player playback was. Owner should play the four files above on a phone if they want that last subjective check.
- Official Comfy 0.34.0 warns that cu130 is preferred for optimized CUDA ops. This cert used cu128 (same family as the old Route A venv) and still produced clean audio.
- Supervisor did not take `owned:true` on the fresh `:8192` process (manual launch). Next intentional Route A stop should re-verify PID/cmd before supervisor-stop.
- Scene 1 duration/canvas were temporarily changed for the short 1F gate and restored afterward.

## Final language

`GO — STANDALONE COMFYUI CLEAN REBUILD + FRESH MINIMAX H3 AUDIO STACK + 1F/T2V NATIVE AUDIO E2E CERTIFIED`
