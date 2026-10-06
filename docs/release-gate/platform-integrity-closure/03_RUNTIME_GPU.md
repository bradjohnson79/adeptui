# 03 — Gate C Runtime / GPU ownership

**Surface:** CURRENT DEVELOPMENT (supervisor) + BOTH (retired :8760 still live).  
**Date:** 2026-08-29

## Defect

Python Runtime Supervisor owned Studio API, Comfy `:8188`, tunnel, and Ollama. It did not own MiniMax Route A `:8192`. Retired `:8760` was still the default for `scripts/beta_runtime/supervisor.py` and `web_server.py`. Two Comfy stacks shared `cuda:0` with no admission.

## Repair

Same supervisor — not a second control plane:

- Route A is a tracked service (`minimax_h3_route_a`) with adopt / explicit start / owned stop.
- Normal `start_all` **adopts** a healthy `:8192` as reused/external. It does **not** spawn Route A (GPU admission).
- External Route A is never reported as Adept-owned Ready.
- GPU admission refuses to spawn a second heavyweight Comfy while the other holds or is busy on the GPU. Reuse of an already-healthy listener is allowed. No random process kills.
- Retired `:8760`: product supervisor still does not start it. Beta runtime default is Vite `:5173`. `start_web` and `web_server.py` refuse `:8760` unless `ADEPT_ALLOW_RETIRED_8760` is set for historical certs.

Creator Local Runtime now shows MiniMax Route A ownership and a dual-resident GPU warning.

## Tests

`cd studio-api; python -m pytest tests/test_runtime_supervisor_lifecycle.py -q`

New cases: GPU admission block when Comfy is busy; Route A reuse; adopt does not claim owned Ready; `start_all` still never starts `:8760`.

## Classification

| Finding | Surface | After repair |
|---|---|---|
| Route A hidden PS1 contract | CURRENT DEVELOPMENT | Same supervisor adopt/start |
| Dual Comfy no admission | BOTH | Admission + dualResident disclosure |
| `:8760` default start | BOTH | Refused; Vite `:5173` default |

## Peer close

- Kimi K3 (`21301c27`): **PASS WITH NON-BLOCKING** — same supervisor; `start_all` adopts `:8192` only; GPU admission blocks a second Comfy spawn; `:8760` refused unless `ADEPT_ALLOW_RETIRED_8760`. Non-blocking: Beta watchdog `ensure_comfy` can still spawn Comfy without `assess_gpu_admission` when `ADEPT_COMFY_LAUNCH` is set. **ACCEPTED NON-BLOCKING** (retired Beta watchdog is not the production start contract).
- GLM 5.2 (`8eb5c359`): **PASS WITH NON-BLOCKING** — production contract is `run_runtime_supervisor.py`. Non-blocking: live diagnostics still probe `:8760` as a proxy layer. **ACCEPTED NON-BLOCKING** (probe ≠ start).

**Gate C: CLOSED**
