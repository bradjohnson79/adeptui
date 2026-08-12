# M42 W47 — Foundation Audit

| Field | Value |
| --- | --- |
| Milestone | M42 Phase 4.7 (W47) |
| Branch | `phase2/m42-docker-runtime-extensions` |
| Base | `phase2/m42-director-timeline-master` @ f758744 (working tree includes W46 dock/timeline) |
| Law | 27 — Isolated Extension Installation and Safe Removal |

## Discovered architecture

| Area | Finding |
| --- | --- |
| Docker Runtime Manager | **Absent** — deferred from W46 (`dockerDeferredToW47`) |
| Docker Desktop / compose | No Dockerfile/compose lifecycle APIs |
| NVIDIA Container Toolkit | Not wired; host `nvidia-smi` only |
| ComfyUI | External host service (`STUDIO_COMFY_URL`, optional `ADEPT_COMFY_LAUNCH`) |
| Production Dock | `local\|hosted` + `local\|api\|hybrid` — not Native/Docker/Hosted |
| Setup Wizard | Catalog + VideoModelLibrary; no Add Custom Capability |
| Uninstall | Voice-model uninstall only (Source Manager) |
| Job queue | `queue_worker.py` host workers |
| Secrets | Project security + env; must not inject into user containers |

## Beta

- UI: `http://127.0.0.1:8760/`
- API: `http://127.0.0.1:8758/`
- Start: `.\Start-AdeptUI-Beta.ps1` / `npm run beta:start`

## Out of scope absorbed

W46 explicitly deferred Docker install, custom runtime import, custom-node isolation, and safe uninstall to W47. This milestone implements them.
